#ifndef ASBX_H
#define ASBX_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    ASBX_OK = 0,
    ASBX_ERR_INVALID_ARGUMENT = 1,
    ASBX_ERR_OUT_OF_MEMORY = 2,
    ASBX_ERR_MALFORMED = 3,
    ASBX_ERR_UNSUPPORTED = 4
} asbx_status;

typedef enum {
    ASBX_SELECTOR_DETERMINISTIC = 0,
    ASBX_SELECTOR_ORACLE = 1
} asbx_selector;

typedef enum {
    ASBX_CONTAINER_RAW = 0,
    ASBX_CONTAINER_BLOCKS = 1
} asbx_container_kind;

typedef struct {
    uint8_t *data;
    size_t size;
} asbx_buffer;

typedef struct {
    size_t block_size;
    asbx_selector selector;
} asbx_config;

typedef struct {
    size_t input_size;
    size_t output_size;
    size_t block_size;
    size_t block_count;
    asbx_container_kind container_kind;
} asbx_stats;

uint32_t asbx_format_version(void);

const char *asbx_status_message(asbx_status status);

void asbx_buffer_free(asbx_buffer *buffer);

asbx_config asbx_default_config(void);

asbx_status asbx_encode_with_config(
    const uint8_t *input,
    size_t input_size,
    const asbx_config *config,
    asbx_buffer *output,
    asbx_stats *stats
);

asbx_status asbx_encode(
    const uint8_t *input,
    size_t input_size,
    size_t block_size,
    asbx_selector selector,
    asbx_buffer *output
);

asbx_status asbx_validate(const uint8_t *container, size_t container_size, asbx_stats *stats);

asbx_status asbx_decode(
    const uint8_t *container,
    size_t container_size,
    asbx_buffer *output
);

#ifdef __cplusplus
}
#endif

#endif
