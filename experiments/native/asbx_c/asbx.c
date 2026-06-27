#include "asbx.h"

#include <limits.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#define ASBX_MAGIC0 'A'
#define ASBX_MAGIC1 'S'
#define ASBX_MAGIC2 'B'
#define ASBX_MAGIC3 'X'
#define ASBX_VERSION 0

#define ASBX_STREAM_RAW 0
#define ASBX_STREAM_BLOCKS 1

typedef enum {
    MODE_RAW = 0,
    MODE_ZERO = 1,
    MODE_ZERO_TRIM = 2,
    MODE_ONE_GAPS = 3,
    MODE_ZERO_GAPS = 4,
    MODE_ONE_RUNS = 5,
    MODE_NONZERO_BYTES = 6
} mode_t;

typedef struct {
    uint8_t *data;
    size_t size;
    size_t capacity;
} builder;

typedef struct {
    mode_t mode;
    asbx_buffer payload;
    asbx_buffer record;
    bool valid;
} candidate;

typedef struct {
    size_t length;
    size_t leading_zero_bytes;
    size_t trailing_zero_bytes;
    size_t nonzero_bytes;
    uint64_t one_bits;
    uint64_t one_runs;
} block_features;

static void candidate_free(candidate *item);

uint32_t asbx_format_version(void) {
    return ASBX_VERSION;
}

const char *asbx_status_message(asbx_status status) {
    switch (status) {
    case ASBX_OK:
        return "ok";
    case ASBX_ERR_INVALID_ARGUMENT:
        return "invalid argument";
    case ASBX_ERR_OUT_OF_MEMORY:
        return "out of memory";
    case ASBX_ERR_MALFORMED:
        return "malformed ASBX stream";
    case ASBX_ERR_UNSUPPORTED:
        return "unsupported ASBX feature";
    default:
        return "unknown ASBX status";
    }
}

void asbx_buffer_free(asbx_buffer *buffer) {
    if (buffer == NULL) {
        return;
    }
    free(buffer->data);
    buffer->data = NULL;
    buffer->size = 0;
}

asbx_config asbx_default_config(void) {
    asbx_config config;
    config.block_size = 256;
    config.selector = ASBX_SELECTOR_DETERMINISTIC;
    return config;
}

static asbx_status builder_reserve(builder *b, size_t extra) {
    if (extra > SIZE_MAX - b->size) {
        return ASBX_ERR_OUT_OF_MEMORY;
    }
    size_t needed = b->size + extra;
    if (needed <= b->capacity) {
        return ASBX_OK;
    }
    size_t next = b->capacity ? b->capacity : 64;
    while (next < needed) {
        if (next > SIZE_MAX / 2) {
            next = needed;
            break;
        }
        next *= 2;
    }
    uint8_t *data = (uint8_t *)realloc(b->data, next);
    if (data == NULL) {
        return ASBX_ERR_OUT_OF_MEMORY;
    }
    b->data = data;
    b->capacity = next;
    return ASBX_OK;
}

static asbx_status builder_append_byte(builder *b, uint8_t value) {
    asbx_status status = builder_reserve(b, 1);
    if (status != ASBX_OK) {
        return status;
    }
    b->data[b->size++] = value;
    return ASBX_OK;
}

static asbx_status builder_append(builder *b, const uint8_t *data, size_t size) {
    if (size == 0) {
        return ASBX_OK;
    }
    asbx_status status = builder_reserve(b, size);
    if (status != ASBX_OK) {
        return status;
    }
    memcpy(b->data + b->size, data, size);
    b->size += size;
    return ASBX_OK;
}

static asbx_buffer builder_finish(builder *b) {
    asbx_buffer out;
    out.data = b->data;
    out.size = b->size;
    b->data = NULL;
    b->size = 0;
    b->capacity = 0;
    return out;
}

static void builder_discard(builder *b) {
    free(b->data);
    b->data = NULL;
    b->size = 0;
    b->capacity = 0;
}

static size_t uvarint_size(uint64_t value) {
    size_t size = 1;
    while (value >= 0x80) {
        value >>= 7;
        size++;
    }
    return size;
}

static asbx_status append_uvarint(builder *b, uint64_t value) {
    while (true) {
        uint8_t byte = (uint8_t)(value & 0x7F);
        value >>= 7;
        if (value != 0) {
            byte |= 0x80;
        }
        asbx_status status = builder_append_byte(b, byte);
        if (status != ASBX_OK) {
            return status;
        }
        if (value == 0) {
            return ASBX_OK;
        }
    }
}

static asbx_status read_uvarint(
    const uint8_t *data,
    size_t size,
    size_t *offset,
    uint64_t *value
) {
    size_t start = *offset;
    uint64_t result = 0;
    unsigned shift = 0;
    while (*offset < size) {
        uint8_t byte = data[(*offset)++];
        if (shift >= 64 && (byte & 0x7F) != 0) {
            return ASBX_ERR_MALFORMED;
        }
        result |= ((uint64_t)(byte & 0x7F)) << shift;
        if ((byte & 0x80) == 0) {
            if (*offset - start != uvarint_size(result)) {
                return ASBX_ERR_MALFORMED;
            }
            *value = result;
            return ASBX_OK;
        }
        shift += 7;
        if (shift > 63) {
            return ASBX_ERR_MALFORMED;
        }
    }
    return ASBX_ERR_MALFORMED;
}

static unsigned byte_popcount(uint8_t value) {
    unsigned count = 0;
    while (value) {
        count += (unsigned)(value & 1U);
        value >>= 1;
    }
    return count;
}

static block_features compute_features(const uint8_t *block, size_t length) {
    block_features f;
    memset(&f, 0, sizeof(f));
    f.length = length;
    while (f.leading_zero_bytes < length && block[f.leading_zero_bytes] == 0) {
        f.leading_zero_bytes++;
    }
    size_t right = length;
    while (right > f.leading_zero_bytes && block[right - 1] == 0) {
        right--;
    }
    f.trailing_zero_bytes = length - right;
    int previous = 0;
    for (size_t i = 0; i < length; i++) {
        uint8_t value = block[i];
        if (value != 0) {
            f.nonzero_bytes++;
        }
        f.one_bits += byte_popcount(value);
        for (int shift = 7; shift >= 0; shift--) {
            int current = (value >> shift) & 1;
            if (current && !previous) {
                f.one_runs++;
            }
            previous = current;
        }
    }
    return f;
}

static size_t average_gap_varint_size(uint64_t span, uint64_t count) {
    if (count == 0) {
        return 0;
    }
    uint64_t average = span / count;
    if (average == 0) {
        average = 1;
    }
    return uvarint_size(average);
}

static uint64_t estimated_payload_cost(block_features f, mode_t mode) {
    uint64_t bit_length = (uint64_t)f.length * 8U;
    uint64_t zero_bits = bit_length - f.one_bits;
    size_t middle = f.length - f.leading_zero_bytes - f.trailing_zero_bytes;
    switch (mode) {
    case MODE_RAW:
        return f.length;
    case MODE_ZERO:
        return 0;
    case MODE_ZERO_TRIM:
        return uvarint_size(f.leading_zero_bytes)
            + uvarint_size(f.trailing_zero_bytes)
            + middle;
    case MODE_ONE_GAPS:
        return uvarint_size(f.one_bits)
            + f.one_bits * average_gap_varint_size(bit_length, f.one_bits);
    case MODE_ZERO_GAPS:
        return uvarint_size(zero_bits)
            + zero_bits * average_gap_varint_size(bit_length, zero_bits);
    case MODE_ONE_RUNS:
        return uvarint_size(f.one_runs)
            + f.one_runs
            * (
                average_gap_varint_size(bit_length, f.one_runs)
                + average_gap_varint_size(f.one_bits ? f.one_bits : 1, f.one_runs)
            );
    case MODE_NONZERO_BYTES:
        return uvarint_size(f.nonzero_bytes)
            + f.nonzero_bytes
            * (average_gap_varint_size(f.length, f.nonzero_bytes) + 1);
    default:
        return UINT64_MAX;
    }
}

static uint64_t estimated_record_cost(block_features f, mode_t mode) {
    uint64_t payload = estimated_payload_cost(f, mode);
    if (payload == UINT64_MAX) {
        return UINT64_MAX;
    }
    return 1 + uvarint_size(f.length) + uvarint_size(payload) + payload;
}

static bool mode_applicable(const uint8_t *block, size_t length, mode_t mode) {
    if (mode == MODE_ZERO) {
        for (size_t i = 0; i < length; i++) {
            if (block[i] != 0) {
                return false;
            }
        }
    }
    return mode >= MODE_RAW && mode <= MODE_NONZERO_BYTES;
}

static mode_t deterministic_mode(const uint8_t *block, size_t length) {
    block_features f = compute_features(block, length);
    mode_t best = MODE_RAW;
    uint64_t best_cost = UINT64_MAX;
    for (int m = MODE_RAW; m <= MODE_NONZERO_BYTES; m++) {
        mode_t mode = (mode_t)m;
        if (!mode_applicable(block, length, mode)) {
            continue;
        }
        uint64_t cost = estimated_record_cost(f, mode);
        if (cost < best_cost || (cost == best_cost && mode < best)) {
            best = mode;
            best_cost = cost;
        }
    }
    return best;
}

static asbx_status encode_positions(
    const uint8_t *block,
    size_t length,
    int target,
    asbx_buffer *payload
) {
    builder b = {0};
    uint64_t count = 0;
    for (size_t i = 0; i < length; i++) {
        for (int bit = 0; bit < 8; bit++) {
            int value = (block[i] >> (7 - bit)) & 1;
            if (value == target) {
                count++;
            }
        }
    }
    asbx_status status = append_uvarint(&b, count);
    if (status != ASBX_OK) {
        builder_discard(&b);
        return status;
    }
    uint64_t previous_plus_one = 0;
    for (size_t i = 0; i < length; i++) {
        for (int bit = 0; bit < 8; bit++) {
            int value = (block[i] >> (7 - bit)) & 1;
            if (value == target) {
                uint64_t position = (uint64_t)i * 8U + (uint64_t)bit;
                uint64_t gap = position + 1 - previous_plus_one;
                status = append_uvarint(&b, gap);
                if (status != ASBX_OK) {
                    builder_discard(&b);
                    return status;
                }
                previous_plus_one = position + 1;
            }
        }
    }
    *payload = builder_finish(&b);
    return ASBX_OK;
}

static asbx_status encode_one_runs(const uint8_t *block, size_t length, asbx_buffer *payload) {
    builder b = {0};
    uint64_t bit_length = (uint64_t)length * 8U;
    uint64_t count = 0;
    bool active = false;
    for (uint64_t pos = 0; pos < bit_length; pos++) {
        size_t byte_index = (size_t)(pos / 8U);
        int bit_index = (int)(pos % 8U);
        bool bit = (block[byte_index] & (uint8_t)(1U << (7 - bit_index))) != 0;
        if (bit && !active) {
            count++;
            active = true;
        } else if (!bit && active) {
            active = false;
        }
    }
    asbx_status status = append_uvarint(&b, count);
    if (status != ASBX_OK) {
        builder_discard(&b);
        return status;
    }
    uint64_t previous_end = 0;
    uint64_t run_start = 0;
    active = false;
    for (uint64_t pos = 0; pos <= bit_length; pos++) {
        bool bit = false;
        if (pos < bit_length) {
            size_t byte_index = (size_t)(pos / 8U);
            int bit_index = (int)(pos % 8U);
            bit = (block[byte_index] & (uint8_t)(1U << (7 - bit_index))) != 0;
        }
        if (bit && !active) {
            run_start = pos;
            active = true;
        } else if ((!bit || pos == bit_length) && active) {
            status = append_uvarint(&b, run_start - previous_end);
            if (status == ASBX_OK) {
                status = append_uvarint(&b, pos - run_start);
            }
            if (status != ASBX_OK) {
                builder_discard(&b);
                return status;
            }
            previous_end = pos;
            active = false;
        }
    }
    *payload = builder_finish(&b);
    return ASBX_OK;
}

static asbx_status encode_nonzero_bytes(const uint8_t *block, size_t length, asbx_buffer *payload) {
    builder b = {0};
    uint64_t count = 0;
    for (size_t i = 0; i < length; i++) {
        if (block[i] != 0) {
            count++;
        }
    }
    asbx_status status = append_uvarint(&b, count);
    if (status != ASBX_OK) {
        builder_discard(&b);
        return status;
    }
    size_t previous_plus_one = 0;
    for (size_t i = 0; i < length; i++) {
        if (block[i] == 0) {
            continue;
        }
        status = append_uvarint(&b, (uint64_t)(i + 1 - previous_plus_one));
        if (status == ASBX_OK) {
            status = builder_append_byte(&b, block[i]);
        }
        if (status != ASBX_OK) {
            builder_discard(&b);
            return status;
        }
        previous_plus_one = i + 1;
    }
    *payload = builder_finish(&b);
    return ASBX_OK;
}

static asbx_status encode_payload(
    mode_t mode,
    const uint8_t *block,
    size_t length,
    asbx_buffer *payload
) {
    payload->data = NULL;
    payload->size = 0;
    builder b = {0};
    asbx_status status = ASBX_OK;
    switch (mode) {
    case MODE_RAW:
        status = builder_append(&b, block, length);
        break;
    case MODE_ZERO:
        if (!mode_applicable(block, length, mode)) {
            status = ASBX_ERR_INVALID_ARGUMENT;
        }
        break;
    case MODE_ZERO_TRIM: {
        size_t left = 0;
        while (left < length && block[left] == 0) {
            left++;
        }
        size_t right = length;
        while (right > left && block[right - 1] == 0) {
            right--;
        }
        status = append_uvarint(&b, left);
        if (status == ASBX_OK) {
            status = append_uvarint(&b, length - right);
        }
        if (status == ASBX_OK) {
            status = builder_append(&b, block + left, right - left);
        }
        break;
    }
    case MODE_ONE_GAPS:
        return encode_positions(block, length, 1, payload);
    case MODE_ZERO_GAPS:
        return encode_positions(block, length, 0, payload);
    case MODE_ONE_RUNS:
        return encode_one_runs(block, length, payload);
    case MODE_NONZERO_BYTES:
        return encode_nonzero_bytes(block, length, payload);
    default:
        status = ASBX_ERR_UNSUPPORTED;
    }
    if (status != ASBX_OK) {
        builder_discard(&b);
        return status;
    }
    *payload = builder_finish(&b);
    return ASBX_OK;
}

static asbx_status make_candidate(
    const uint8_t *block,
    size_t length,
    mode_t mode,
    candidate *out
) {
    memset(out, 0, sizeof(*out));
    if (!mode_applicable(block, length, mode)) {
        out->valid = false;
        return ASBX_OK;
    }
    asbx_status status = encode_payload(mode, block, length, &out->payload);
    if (status != ASBX_OK) {
        return status;
    }
    builder r = {0};
    status = builder_append_byte(&r, (uint8_t)mode);
    if (status == ASBX_OK) {
        status = append_uvarint(&r, length);
    }
    if (status == ASBX_OK) {
        status = append_uvarint(&r, out->payload.size);
    }
    if (status == ASBX_OK) {
        status = builder_append(&r, out->payload.data, out->payload.size);
    }
    if (status != ASBX_OK) {
        builder_discard(&r);
        candidate_free(out);
        return status;
    }
    out->mode = mode;
    out->record = builder_finish(&r);
    out->valid = true;
    return ASBX_OK;
}

static void candidate_free(candidate *item) {
    asbx_buffer_free(&item->payload);
    asbx_buffer_free(&item->record);
    item->valid = false;
}

static asbx_status select_candidate(
    const uint8_t *block,
    size_t length,
    asbx_selector selector,
    candidate *selected
) {
    memset(selected, 0, sizeof(*selected));
    if (selector == ASBX_SELECTOR_DETERMINISTIC) {
        return make_candidate(block, length, deterministic_mode(block, length), selected);
    }
    if (selector != ASBX_SELECTOR_ORACLE) {
        return ASBX_ERR_INVALID_ARGUMENT;
    }
    candidate best;
    memset(&best, 0, sizeof(best));
    for (int m = MODE_RAW; m <= MODE_NONZERO_BYTES; m++) {
        candidate current;
        asbx_status status = make_candidate(block, length, (mode_t)m, &current);
        if (status != ASBX_OK) {
            candidate_free(&best);
            return status;
        }
        if (!current.valid) {
            continue;
        }
        if (
            !best.valid
            || current.record.size < best.record.size
            || (current.record.size == best.record.size && current.mode < best.mode)
        ) {
            candidate_free(&best);
            best = current;
        } else {
            candidate_free(&current);
        }
    }
    *selected = best;
    return best.valid ? ASBX_OK : ASBX_ERR_MALFORMED;
}

asbx_status asbx_encode_with_config(
    const uint8_t *input,
    size_t input_size,
    const asbx_config *config,
    asbx_buffer *output,
    asbx_stats *stats
) {
    asbx_config local_config = config != NULL ? *config : asbx_default_config();
    if (
        output == NULL
        || (input == NULL && input_size != 0)
        || local_config.block_size == 0
        || (
            local_config.selector != ASBX_SELECTOR_DETERMINISTIC
            && local_config.selector != ASBX_SELECTOR_ORACLE
        )
    ) {
        return ASBX_ERR_INVALID_ARGUMENT;
    }
    output->data = NULL;
    output->size = 0;
    if (stats != NULL) {
        memset(stats, 0, sizeof(*stats));
        stats->input_size = input_size;
        stats->block_size = local_config.block_size;
    }

    builder raw = {0};
    asbx_status status = builder_append(&raw, (const uint8_t *)"ASBX", 4);
    if (status == ASBX_OK) {
        status = builder_append_byte(&raw, ASBX_VERSION);
    }
    if (status == ASBX_OK) {
        status = builder_append_byte(&raw, ASBX_STREAM_RAW);
    }
    if (status == ASBX_OK) {
        status = append_uvarint(&raw, input_size);
    }
    if (status == ASBX_OK) {
        status = builder_append(&raw, input, input_size);
    }
    if (status != ASBX_OK) {
        builder_discard(&raw);
        return status;
    }

    builder blocks = {0};
    status = builder_append(&blocks, (const uint8_t *)"ASBX", 4);
    if (status == ASBX_OK) {
        status = builder_append_byte(&blocks, ASBX_VERSION);
    }
    if (status == ASBX_OK) {
        status = builder_append_byte(&blocks, ASBX_STREAM_BLOCKS);
    }
    size_t block_size = local_config.block_size;
    size_t block_count = (input_size + block_size - 1) / block_size;
    if (status == ASBX_OK) {
        status = append_uvarint(&blocks, input_size);
    }
    if (status == ASBX_OK) {
        status = append_uvarint(&blocks, block_size);
    }
    if (status == ASBX_OK) {
        status = append_uvarint(&blocks, block_count);
    }
    for (size_t i = 0; status == ASBX_OK && i < block_count; i++) {
        size_t start = i * block_size;
        size_t n = block_size;
        if (n > input_size - start) {
            n = input_size - start;
        }
        candidate selected;
        status = select_candidate(input + start, n, local_config.selector, &selected);
        if (status != ASBX_OK) {
            break;
        }
        status = builder_append(&blocks, selected.record.data, selected.record.size);
        candidate_free(&selected);
    }
    if (status != ASBX_OK) {
        builder_discard(&raw);
        builder_discard(&blocks);
        return status;
    }

    if (blocks.size < raw.size) {
        builder_discard(&raw);
        *output = builder_finish(&blocks);
        if (stats != NULL) {
            stats->output_size = output->size;
            stats->block_count = block_count;
            stats->container_kind = ASBX_CONTAINER_BLOCKS;
        }
    } else {
        builder_discard(&blocks);
        *output = builder_finish(&raw);
        if (stats != NULL) {
            stats->output_size = output->size;
            stats->block_count = 0;
            stats->container_kind = ASBX_CONTAINER_RAW;
        }
    }
    return ASBX_OK;
}

asbx_status asbx_encode(
    const uint8_t *input,
    size_t input_size,
    size_t block_size,
    asbx_selector selector,
    asbx_buffer *output
) {
    asbx_config config;
    config.block_size = block_size;
    config.selector = selector;
    return asbx_encode_with_config(input, input_size, &config, output, NULL);
}

static asbx_status decode_mode_payload(
    mode_t mode,
    const uint8_t *payload,
    size_t payload_size,
    size_t block_length,
    builder *out
) {
    switch (mode) {
    case MODE_RAW:
        if (payload_size != block_length) {
            return ASBX_ERR_MALFORMED;
        }
        return builder_append(out, payload, payload_size);
    case MODE_ZERO:
        if (payload_size != 0) {
            return ASBX_ERR_MALFORMED;
        }
        return builder_reserve(out, block_length) == ASBX_OK
            ? (memset(out->data + out->size, 0, block_length), out->size += block_length, ASBX_OK)
            : ASBX_ERR_OUT_OF_MEMORY;
    case MODE_ZERO_TRIM: {
        size_t offset = 0;
        uint64_t left = 0;
        uint64_t right = 0;
        asbx_status status = read_uvarint(payload, payload_size, &offset, &left);
        if (status == ASBX_OK) {
            status = read_uvarint(payload, payload_size, &offset, &right);
        }
        if (status != ASBX_OK || left > SIZE_MAX || right > SIZE_MAX) {
            return ASBX_ERR_MALFORMED;
        }
        size_t middle = payload_size - offset;
        if ((size_t)left + middle + (size_t)right != block_length) {
            return ASBX_ERR_MALFORMED;
        }
        if (middle > 0 && (payload[offset] == 0 || payload[payload_size - 1] == 0)) {
            return ASBX_ERR_MALFORMED;
        }
        status = builder_reserve(out, block_length);
        if (status != ASBX_OK) {
            return status;
        }
        memset(out->data + out->size, 0, (size_t)left);
        out->size += (size_t)left;
        memcpy(out->data + out->size, payload + offset, middle);
        out->size += middle;
        memset(out->data + out->size, 0, (size_t)right);
        out->size += (size_t)right;
        return ASBX_OK;
    }
    case MODE_ONE_GAPS:
    case MODE_ZERO_GAPS: {
        uint8_t fill = mode == MODE_ZERO_GAPS ? 0xFF : 0x00;
        asbx_status status = builder_reserve(out, block_length);
        if (status != ASBX_OK) {
            return status;
        }
        uint8_t *dest = out->data + out->size;
        memset(dest, fill, block_length);
        out->size += block_length;
        size_t offset = 0;
        uint64_t count = 0;
        status = read_uvarint(payload, payload_size, &offset, &count);
        uint64_t bit_length = (uint64_t)block_length * 8U;
        if (status != ASBX_OK || count > bit_length) {
            return ASBX_ERR_MALFORMED;
        }
        uint64_t previous_plus_one = 0;
        for (uint64_t i = 0; i < count; i++) {
            uint64_t gap = 0;
            status = read_uvarint(payload, payload_size, &offset, &gap);
            if (status != ASBX_OK || gap == 0) {
                return ASBX_ERR_MALFORMED;
            }
            uint64_t position = previous_plus_one + gap - 1;
            if (position >= bit_length) {
                return ASBX_ERR_MALFORMED;
            }
            size_t byte_index = (size_t)(position / 8U);
            int bit_index = (int)(position % 8U);
            uint8_t mask = (uint8_t)(1U << (7 - bit_index));
            if (mode == MODE_ONE_GAPS) {
                dest[byte_index] |= mask;
            } else {
                dest[byte_index] &= (uint8_t)~mask;
            }
            previous_plus_one = position + 1;
        }
        return offset == payload_size ? ASBX_OK : ASBX_ERR_MALFORMED;
    }
    case MODE_ONE_RUNS: {
        asbx_status status = builder_reserve(out, block_length);
        if (status != ASBX_OK) {
            return status;
        }
        uint8_t *dest = out->data + out->size;
        memset(dest, 0, block_length);
        out->size += block_length;
        size_t offset = 0;
        uint64_t count = 0;
        status = read_uvarint(payload, payload_size, &offset, &count);
        if (status != ASBX_OK) {
            return ASBX_ERR_MALFORMED;
        }
        uint64_t previous_end = 0;
        uint64_t bit_length = (uint64_t)block_length * 8U;
        for (uint64_t i = 0; i < count; i++) {
            uint64_t zero_gap = 0;
            uint64_t run_length = 0;
            status = read_uvarint(payload, payload_size, &offset, &zero_gap);
            if (status == ASBX_OK) {
                status = read_uvarint(payload, payload_size, &offset, &run_length);
            }
            if (status != ASBX_OK || run_length == 0) {
                return ASBX_ERR_MALFORMED;
            }
            uint64_t start = previous_end + zero_gap;
            uint64_t end = start + run_length;
            if (start < previous_end || end > bit_length) {
                return ASBX_ERR_MALFORMED;
            }
            for (uint64_t pos = start; pos < end; pos++) {
                size_t byte_index = (size_t)(pos / 8U);
                int bit_index = (int)(pos % 8U);
                dest[byte_index] |= (uint8_t)(1U << (7 - bit_index));
            }
            previous_end = end;
        }
        return offset == payload_size ? ASBX_OK : ASBX_ERR_MALFORMED;
    }
    case MODE_NONZERO_BYTES: {
        asbx_status status = builder_reserve(out, block_length);
        if (status != ASBX_OK) {
            return status;
        }
        uint8_t *dest = out->data + out->size;
        memset(dest, 0, block_length);
        out->size += block_length;
        size_t offset = 0;
        uint64_t count = 0;
        status = read_uvarint(payload, payload_size, &offset, &count);
        if (status != ASBX_OK || count > block_length) {
            return ASBX_ERR_MALFORMED;
        }
        size_t previous_plus_one = 0;
        for (uint64_t i = 0; i < count; i++) {
            uint64_t gap = 0;
            status = read_uvarint(payload, payload_size, &offset, &gap);
            if (status != ASBX_OK || gap == 0 || gap > SIZE_MAX) {
                return ASBX_ERR_MALFORMED;
            }
            size_t position = previous_plus_one + (size_t)gap - 1;
            if (position >= block_length || offset >= payload_size || payload[offset] == 0) {
                return ASBX_ERR_MALFORMED;
            }
            dest[position] = payload[offset++];
            previous_plus_one = position + 1;
        }
        return offset == payload_size ? ASBX_OK : ASBX_ERR_MALFORMED;
    }
    default:
        return ASBX_ERR_UNSUPPORTED;
    }
}

asbx_status asbx_decode(
    const uint8_t *container,
    size_t container_size,
    asbx_buffer *output
) {
    if (output == NULL || (container == NULL && container_size != 0)) {
        return ASBX_ERR_INVALID_ARGUMENT;
    }
    output->data = NULL;
    output->size = 0;
    if (
        container_size < 6
        || container[0] != ASBX_MAGIC0
        || container[1] != ASBX_MAGIC1
        || container[2] != ASBX_MAGIC2
        || container[3] != ASBX_MAGIC3
        || container[4] != ASBX_VERSION
    ) {
        return ASBX_ERR_MALFORMED;
    }
    size_t offset = 5;
    uint8_t stream_mode = container[offset++];
    uint64_t original_length = 0;
    asbx_status status = read_uvarint(container, container_size, &offset, &original_length);
    if (status != ASBX_OK || original_length > SIZE_MAX) {
        return ASBX_ERR_MALFORMED;
    }
    if (stream_mode == ASBX_STREAM_RAW) {
        if (container_size - offset != (size_t)original_length) {
            return ASBX_ERR_MALFORMED;
        }
        builder out = {0};
        status = builder_append(&out, container + offset, (size_t)original_length);
        if (status != ASBX_OK) {
            builder_discard(&out);
            return status;
        }
        *output = builder_finish(&out);
        return ASBX_OK;
    }
    if (stream_mode != ASBX_STREAM_BLOCKS) {
        return ASBX_ERR_MALFORMED;
    }
    uint64_t block_size = 0;
    uint64_t block_count = 0;
    status = read_uvarint(container, container_size, &offset, &block_size);
    if (status == ASBX_OK) {
        status = read_uvarint(container, container_size, &offset, &block_count);
    }
    if (status != ASBX_OK || block_size == 0 || block_size > SIZE_MAX || block_count > SIZE_MAX) {
        return ASBX_ERR_MALFORMED;
    }
    uint64_t expected_count = original_length == 0
        ? 0
        : (original_length + block_size - 1) / block_size;
    if (block_count != expected_count) {
        return ASBX_ERR_MALFORMED;
    }
    builder out = {0};
    status = builder_reserve(&out, (size_t)original_length);
    if (status != ASBX_OK) {
        return status;
    }
    for (uint64_t i = 0; i < block_count; i++) {
        if (offset >= container_size) {
            builder_discard(&out);
            return ASBX_ERR_MALFORMED;
        }
        uint8_t mode_byte = container[offset++];
        if (mode_byte > MODE_NONZERO_BYTES) {
            builder_discard(&out);
            return ASBX_ERR_MALFORMED;
        }
        uint64_t block_length = 0;
        uint64_t payload_length = 0;
        status = read_uvarint(container, container_size, &offset, &block_length);
        if (status == ASBX_OK) {
            status = read_uvarint(container, container_size, &offset, &payload_length);
        }
        if (
            status != ASBX_OK
            || block_length > SIZE_MAX
            || payload_length > SIZE_MAX
            || payload_length > container_size - offset
        ) {
            builder_discard(&out);
            return ASBX_ERR_MALFORMED;
        }
        size_t expected_block = (size_t)block_size;
        if (i + 1 == block_count) {
            uint64_t consumed_before_last = i * block_size;
            expected_block = (size_t)(original_length - consumed_before_last);
        }
        if ((size_t)block_length != expected_block) {
            builder_discard(&out);
            return ASBX_ERR_MALFORMED;
        }
        status = decode_mode_payload(
            (mode_t)mode_byte,
            container + offset,
            (size_t)payload_length,
            (size_t)block_length,
            &out
        );
        if (status != ASBX_OK) {
            builder_discard(&out);
            return status;
        }
        offset += (size_t)payload_length;
    }
    if (offset != container_size || out.size != (size_t)original_length) {
        builder_discard(&out);
        return ASBX_ERR_MALFORMED;
    }
    *output = builder_finish(&out);
    return ASBX_OK;
}

asbx_status asbx_decode_with_limit(
    const uint8_t *container,
    size_t container_size,
    size_t max_output_size,
    asbx_buffer *output
) {
    if (output == NULL || (container == NULL && container_size != 0)) {
        return ASBX_ERR_INVALID_ARGUMENT;
    }
    output->data = NULL;
    output->size = 0;
    if (
        container_size < 6
        || container[0] != ASBX_MAGIC0
        || container[1] != ASBX_MAGIC1
        || container[2] != ASBX_MAGIC2
        || container[3] != ASBX_MAGIC3
        || container[4] != ASBX_VERSION
    ) {
        return ASBX_ERR_MALFORMED;
    }
    size_t offset = 6;
    uint64_t original_length = 0;
    asbx_status status = read_uvarint(container, container_size, &offset, &original_length);
    if (status != ASBX_OK || original_length > SIZE_MAX) {
        return ASBX_ERR_MALFORMED;
    }
    if ((size_t)original_length > max_output_size) {
        return ASBX_ERR_UNSUPPORTED;
    }
    return asbx_decode(container, container_size, output);
}

asbx_status asbx_validate(const uint8_t *container, size_t container_size, asbx_stats *stats) {
    asbx_buffer decoded = {0};
    asbx_status status = asbx_decode(container, container_size, &decoded);
    if (status != ASBX_OK) {
        return status;
    }
    asbx_buffer_free(&decoded);

    if (stats == NULL) {
        return ASBX_OK;
    }

    memset(stats, 0, sizeof(*stats));
    stats->output_size = container_size;

    size_t offset = 5;
    uint8_t stream_mode = container[offset++];
    uint64_t original_length = 0;
    status = read_uvarint(container, container_size, &offset, &original_length);
    if (status != ASBX_OK || original_length > SIZE_MAX) {
        return ASBX_ERR_MALFORMED;
    }
    stats->input_size = (size_t)original_length;

    if (stream_mode == ASBX_STREAM_RAW) {
        stats->container_kind = ASBX_CONTAINER_RAW;
        return ASBX_OK;
    }

    uint64_t block_size = 0;
    uint64_t block_count = 0;
    status = read_uvarint(container, container_size, &offset, &block_size);
    if (status == ASBX_OK) {
        status = read_uvarint(container, container_size, &offset, &block_count);
    }
    if (status != ASBX_OK || block_size > SIZE_MAX || block_count > SIZE_MAX) {
        return ASBX_ERR_MALFORMED;
    }
    stats->container_kind = ASBX_CONTAINER_BLOCKS;
    stats->block_size = (size_t)block_size;
    stats->block_count = (size_t)block_count;
    return ASBX_OK;
}
