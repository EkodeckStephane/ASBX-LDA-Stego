#include "asbx.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int read_file(const char *path, asbx_buffer *buffer) {
    buffer->data = NULL;
    buffer->size = 0;
    FILE *fh = fopen(path, "rb");
    if (fh == NULL) {
        fprintf(stderr, "cannot open input: %s\n", path);
        return 1;
    }
    if (fseek(fh, 0, SEEK_END) != 0) {
        fclose(fh);
        return 1;
    }
    long size = ftell(fh);
    if (size < 0) {
        fclose(fh);
        return 1;
    }
    if (fseek(fh, 0, SEEK_SET) != 0) {
        fclose(fh);
        return 1;
    }
    buffer->data = (uint8_t *)malloc((size_t)size ? (size_t)size : 1);
    if (buffer->data == NULL) {
        fclose(fh);
        return 1;
    }
    buffer->size = (size_t)size;
    if (buffer->size && fread(buffer->data, 1, buffer->size, fh) != buffer->size) {
        fclose(fh);
        asbx_buffer_free(buffer);
        return 1;
    }
    fclose(fh);
    return 0;
}

static int write_file(const char *path, const asbx_buffer *buffer) {
    FILE *fh = fopen(path, "wb");
    if (fh == NULL) {
        fprintf(stderr, "cannot open output: %s\n", path);
        return 1;
    }
    if (buffer->size && fwrite(buffer->data, 1, buffer->size, fh) != buffer->size) {
        fclose(fh);
        return 1;
    }
    fclose(fh);
    return 0;
}

static void usage(FILE *stream) {
    fprintf(stream, "Usage:\n");
    fprintf(stream, "  asbxc encode [--block-size N] <input> <output>\n");
    fprintf(stream, "  asbxc encode-oracle [--block-size N] <input> <output>\n");
    fprintf(stream, "  asbxc decode <input.asbx> <output>\n");
    fprintf(stream, "  asbxc validate <input.asbx>\n");
    fprintf(stream, "  asbxc bench [--block-size N] <repeats> <input>\n");
}

int main(int argc, char **argv) {
    if (argc < 3) {
        usage(stderr);
        return 2;
    }

    const char *command = argv[1];
    size_t block_size = 256;
    int arg = 2;
    if ((strcmp(command, "encode") == 0 || strcmp(command, "encode-oracle") == 0 || strcmp(command, "bench") == 0)
        && arg + 2 < argc
        && strcmp(argv[arg], "--block-size") == 0) {
        char *end = NULL;
        unsigned long parsed = strtoul(argv[arg + 1], &end, 10);
        if (end == argv[arg + 1] || *end != '\0' || parsed == 0) {
            fprintf(stderr, "invalid block size\n");
            return 2;
        }
        block_size = (size_t)parsed;
        arg += 2;
    }

    if (strcmp(command, "encode") == 0 || strcmp(command, "encode-oracle") == 0) {
        if (argc - arg != 2) {
            usage(stderr);
            return 2;
        }
        asbx_buffer input = {0};
        asbx_buffer output = {0};
        if (read_file(argv[arg], &input) != 0) {
            return 1;
        }
        asbx_config config = asbx_default_config();
        config.block_size = block_size;
        config.selector = strcmp(command, "encode-oracle") == 0
            ? ASBX_SELECTOR_ORACLE
            : ASBX_SELECTOR_DETERMINISTIC;
        asbx_stats stats = {0};
        asbx_status status = asbx_encode_with_config(input.data, input.size, &config, &output, &stats);
        asbx_buffer_free(&input);
        if (status != ASBX_OK) {
            fprintf(stderr, "encode failed: %s\n", asbx_status_message(status));
            return 1;
        }
        int rc = write_file(argv[arg + 1], &output);
        asbx_buffer_free(&output);
        return rc;
    }

    if (strcmp(command, "bench") == 0) {
        if (argc - arg != 2) {
            usage(stderr);
            return 2;
        }
        char *end = NULL;
        unsigned long repeats = strtoul(argv[arg], &end, 10);
        if (end == argv[arg] || *end != '\0' || repeats == 0) {
            fprintf(stderr, "invalid repeat count\n");
            return 2;
        }
        asbx_buffer input = {0};
        if (read_file(argv[arg + 1], &input) != 0) {
            return 1;
        }

        asbx_buffer encoded = {0};
        clock_t start = clock();
        for (unsigned long i = 0; i < repeats; i++) {
            asbx_buffer_free(&encoded);
            asbx_config config = asbx_default_config();
            config.block_size = block_size;
            asbx_status status = asbx_encode_with_config(input.data, input.size, &config, &encoded, NULL);
            if (status != ASBX_OK) {
                fprintf(stderr, "encode failed: %s\n", asbx_status_message(status));
                asbx_buffer_free(&input);
                return 1;
            }
        }
        clock_t mid = clock();

        asbx_buffer decoded = {0};
        for (unsigned long i = 0; i < repeats; i++) {
            asbx_buffer_free(&decoded);
            asbx_status status = asbx_decode(encoded.data, encoded.size, &decoded);
            if (status != ASBX_OK) {
                fprintf(stderr, "decode failed: %s\n", asbx_status_message(status));
                asbx_buffer_free(&input);
                asbx_buffer_free(&encoded);
                return 1;
            }
            if (decoded.size != input.size || memcmp(decoded.data, input.data, input.size) != 0) {
                fprintf(stderr, "round-trip mismatch\n");
                asbx_buffer_free(&input);
                asbx_buffer_free(&encoded);
                asbx_buffer_free(&decoded);
                return 1;
            }
        }
        clock_t end_clock = clock();
        double encode_ms = 1000.0 * (double)(mid - start) / (double)CLOCKS_PER_SEC;
        double decode_ms = 1000.0 * (double)(end_clock - mid) / (double)CLOCKS_PER_SEC;
        printf(
            "input_bytes=%zu,encoded_bytes=%zu,repeats=%lu,encode_ms=%.6f,decode_ms=%.6f\n",
            input.size,
            encoded.size,
            repeats,
            encode_ms,
            decode_ms
        );
        asbx_buffer_free(&input);
        asbx_buffer_free(&encoded);
        asbx_buffer_free(&decoded);
        return 0;
    }

    if (strcmp(command, "validate") == 0) {
        if (argc - arg != 1) {
            usage(stderr);
            return 2;
        }
        asbx_buffer input = {0};
        if (read_file(argv[arg], &input) != 0) {
            return 1;
        }
        asbx_stats stats = {0};
        asbx_status status = asbx_validate(input.data, input.size, &stats);
        asbx_buffer_free(&input);
        if (status != ASBX_OK) {
            fprintf(stderr, "validate failed: %s\n", asbx_status_message(status));
            return 1;
        }
        printf(
            "format_version=%u,input_bytes=%zu,encoded_bytes=%zu,container=%s,block_size=%zu,block_count=%zu\n",
            asbx_format_version(),
            stats.input_size,
            stats.output_size,
            stats.container_kind == ASBX_CONTAINER_BLOCKS ? "blocks" : "raw",
            stats.block_size,
            stats.block_count
        );
        return 0;
    }

    if (strcmp(command, "decode") == 0) {
        if (argc - arg != 2) {
            usage(stderr);
            return 2;
        }
        asbx_buffer input = {0};
        asbx_buffer output = {0};
        if (read_file(argv[arg], &input) != 0) {
            return 1;
        }
        asbx_status status = asbx_decode(input.data, input.size, &output);
        asbx_buffer_free(&input);
        if (status != ASBX_OK) {
            fprintf(stderr, "decode failed: %s\n", asbx_status_message(status));
            return 1;
        }
        int rc = write_file(argv[arg + 1], &output);
        asbx_buffer_free(&output);
        return rc;
    }

    usage(stderr);
    return 2;
}
