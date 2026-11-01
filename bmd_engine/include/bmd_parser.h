/**
 * @file bmd_parser.h
 * @brief High-Assurance Lexer and Parser for Blockchain Markdown (.bmd)
 */

#ifndef BMD_PARSER_H
#define BMD_PARSER_H

#include "bmd_engine.h"
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Token types for BMD frontmatter scanner
 */
typedef enum {
    BMD_TOK_EOF,
    BMD_TOK_FENCE,       /* '---' */
    BMD_TOK_KEY,
    BMD_TOK_COLON,
    BMD_TOK_STRING_LITERAL,
    BMD_TOK_INT_LITERAL,
    BMD_TOK_BOOL_LITERAL,
    BMD_TOK_COMMENT,
    BMD_TOK_NEWLINE,
    BMD_TOK_ERROR
} bmd_token_type_t;

/**
 * @brief Internal frontmatter key-value pair extracted by parser
 */
typedef struct {
    char key[64];
    char value[512];
} bmd_kv_pair_t;

/**
 * @brief Low-level parser functions
 */
bmd_status_t bmd_parser_extract_frontmatter(const char* content, size_t length,
                                            char** out_frontmatter, size_t* out_fm_len,
                                            char** out_payload, size_t* out_payload_len);

bmd_status_t bmd_parser_parse_yaml_header(const char* fm_text, bmd_header_t* out_header);

/**
 * @brief Extract `property_bundle: |` YAML block scalar from frontmatter text.
 * Allocates and returns the concatenated base64 lines in *out_data (caller frees).
 * Returns BMD_OK with *out_data = NULL when the key is absent.
 */
bmd_status_t bmd_parser_extract_property_bundle(const char* fm_text,
                                                 char** out_data,
                                                 size_t* out_len);

void bmd_trim_whitespace(char* str);

#ifdef __cplusplus
}
#endif

#endif /* BMD_PARSER_H */
