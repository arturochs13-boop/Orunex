/**
 * @file bmd_parser.c
 * @brief High-Assurance Lexer and Parser for Blockchain Markdown (.bmd)
 */

#include "bmd_parser.h"
#include "bmd_crypto.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

void bmd_trim_whitespace(char* str) {
    if (!str) return;
    char* start = str;
    while (*start && isspace((unsigned char)*start)) {
        start++;
    }
    if (start != str) {
        memmove(str, start, strlen(start) + 1);
    }
    size_t len = strlen(str);
    while (len > 0 && isspace((unsigned char)str[len - 1])) {
        str[--len] = '\0';
    }
}

static void strip_quotes(char* str) {
    if (!str) return;
    bmd_trim_whitespace(str);
    size_t len = strlen(str);
    if (len >= 2) {
        if ((str[0] == '"' && str[len - 1] == '"') ||
            (str[0] == '\'' && str[len - 1] == '\'')) {
            memmove(str, str + 1, len - 2);
            str[len - 2] = '\0';
        }
    }
    bmd_trim_whitespace(str);
}

static void strip_inline_comment(char* str) {
    if (!str) return;
    bool in_quote = false;
    char quote_char = '\0';
    for (size_t i = 0; str[i] != '\0'; ++i) {
        if (!in_quote && (str[i] == '"' || str[i] == '\'')) {
            in_quote = true;
            quote_char = str[i];
        } else if (in_quote && str[i] == quote_char) {
            in_quote = false;
        } else if (!in_quote && str[i] == '#') {
            str[i] = '\0';
            break;
        }
    }
    bmd_trim_whitespace(str);
}

bmd_status_t bmd_parser_extract_frontmatter(const char* content, size_t length,
                                            char** out_frontmatter, size_t* out_fm_len,
                                            char** out_payload, size_t* out_payload_len) {
    if (!content || !out_frontmatter || !out_payload) {
        return BMD_ERR_NULL_PARAM;
    }

    *out_frontmatter = NULL;
    *out_payload = NULL;
    if (out_fm_len) *out_fm_len = 0;
    if (out_payload_len) *out_payload_len = 0;

    /* Skip leading whitespace / BOM */
    const char* ptr = content;
    if (length >= 3 && (uint8_t)ptr[0] == 0xEF && (uint8_t)ptr[1] == 0xBB && (uint8_t)ptr[2] == 0xBF) {
        ptr += 3;
    }
    while (*ptr && isspace((unsigned char)*ptr)) {
        ptr++;
    }

    /* Verify opening fence '---' */
    if (strncmp(ptr, "---", 3) != 0) {
        return BMD_ERR_SYNTAX_FRONTMATTER;
    }
    ptr += 3;
    /* Expect newline */
    while (*ptr == ' ' || *ptr == '\t' || *ptr == '\r') ptr++;
    if (*ptr != '\n') return BMD_ERR_SYNTAX_FRONTMATTER;
    ptr++;

    const char* fm_start = ptr;
    const char* fm_end = NULL;

    /* Look for closing fence '---' */
    while (*ptr != '\0') {
        if ((ptr == content || *(ptr - 1) == '\n') && strncmp(ptr, "---", 3) == 0) {
            const char* after_fence = ptr + 3;
            while (*after_fence == ' ' || *after_fence == '\t' || *after_fence == '\r') after_fence++;
            if (*after_fence == '\n' || *after_fence == '\0') {
                fm_end = ptr;
                ptr = after_fence + (*after_fence == '\n' ? 1 : 0);
                break;
            }
        }
        ptr++;
    }

    if (!fm_end) {
        return BMD_ERR_SYNTAX_FRONTMATTER;
    }

    size_t fm_len = fm_end - fm_start;
    char* fm_buf = (char*)malloc(fm_len + 1);
    if (!fm_buf) return BMD_ERR_OUT_OF_MEMORY;
    memcpy(fm_buf, fm_start, fm_len);
    fm_buf[fm_len] = '\0';

    /* Remaining content is payload — normalize \r\n → \n for canonical hash */
    size_t payload_raw_len = strlen(ptr);
    char* payload_buf = (char*)malloc(payload_raw_len + 1);
    if (!payload_buf) {
        free(fm_buf);
        return BMD_ERR_OUT_OF_MEMORY;
    }
    /* Strip \r from \r\n sequences so hash is platform-independent */
    size_t payload_len = 0;
    for (size_t i = 0; i < payload_raw_len; ++i) {
        if (ptr[i] == '\r' && (i + 1 < payload_raw_len) && ptr[i + 1] == '\n') {
            continue; /* skip \r before \n */
        }
        payload_buf[payload_len++] = ptr[i];
    }
    payload_buf[payload_len] = '\0';

    *out_frontmatter = fm_buf;
    if (out_fm_len) *out_fm_len = fm_len;
    *out_payload = payload_buf;
    if (out_payload_len) *out_payload_len = payload_len;

    return BMD_OK;
}

bmd_status_t bmd_parser_parse_yaml_header(const char* fm_text, bmd_header_t* out_header) {
    if (!fm_text || !out_header) return BMD_ERR_NULL_PARAM;
    memset(out_header, 0, sizeof(bmd_header_t));

    /* Set default values */
    out_header->mode = BMD_MODE_DRAFT;
    out_header->signer_role = BMD_ROLE_UNKNOWN;
    out_header->payload_encrypted = false;

    char line_buf[1024];
    const char* p = fm_text;

    while (*p != '\0') {
        size_t line_len = 0;
        while (p[line_len] != '\0' && p[line_len] != '\n' && line_len < sizeof(line_buf) - 1) {
            line_len++;
        }
        memcpy(line_buf, p, line_len);
        line_buf[line_len] = '\0';

        p += line_len;
        if (*p == '\n') p++;

        /* Strip inline comments and whitespace */
        strip_inline_comment(line_buf);
        bmd_trim_whitespace(line_buf);
        if (line_buf[0] == '\0') continue;

        char* colon = strchr(line_buf, ':');
        if (!colon) continue;

        *colon = '\0';
        char* key = line_buf;
        char* val = colon + 1;

        bmd_trim_whitespace(key);
        strip_quotes(val);

        if (strcmp(key, "block_id") == 0) {
            strncpy(out_header->block_id, val, BMD_MAX_BLOCK_ID_LEN - 1);
        } else if (strcmp(key, "previous_hash") == 0) {
            strncpy(out_header->previous_hash, val, BMD_HASH_HEX_LEN);
        } else if (strcmp(key, "current_hash") == 0) {
            strncpy(out_header->current_hash, val, BMD_HASH_HEX_LEN);
        } else if (strcmp(key, "mode") == 0) {
            out_header->mode = bmd_mode_from_string(val);
        } else if (strcmp(key, "signer_role") == 0) {
            out_header->signer_role = bmd_role_from_string(val);
        } else if (strcmp(key, "timestamp") == 0) {
            out_header->timestamp = (int64_t)_atoi64(val);
        } else if (strcmp(key, "public_key") == 0) {
            strncpy(out_header->public_key, val, BMD_PUBKEY_HEX_LEN);
        } else if (strcmp(key, "signature_layer_2") == 0) {
            strncpy(out_header->signature_layer_2, val, BMD_SIG_HEX_LEN);
        } else if (strcmp(key, "receiver_public_key") == 0) {
            strncpy(out_header->receiver_public_key, val, BMD_PUBKEY_HEX_LEN);
        } else if (strcmp(key, "receiver_signature") == 0) {
            strncpy(out_header->receiver_signature, val, BMD_SIG_HEX_LEN);
        } else if (strcmp(key, "payload_encrypted") == 0) {
            if (_stricmp(val, "true") == 0 || strcmp(val, "1") == 0) {
                out_header->payload_encrypted = true;
            } else {
                out_header->payload_encrypted = false;
            }

        /* v2.0 Extended Directives */
        } else if (strcmp(key, "document_type") == 0) {
            strncpy(out_header->document_type, val, sizeof(out_header->document_type) - 1);
        } else if (strcmp(key, "jurisdiction") == 0) {
            strncpy(out_header->jurisdiction, val, sizeof(out_header->jurisdiction) - 1);
        } else if (strcmp(key, "expiry_timestamp") == 0) {
            out_header->expiry_timestamp = (int64_t)_atoi64(val);
        } else if (strcmp(key, "witnesses_required") == 0) {
            out_header->witnesses_required = atoi(val);
        } else if (strcmp(key, "require_cosigner") == 0) {
            if (_stricmp(val, "true") == 0 || strcmp(val, "1") == 0) {
                out_header->require_cosigner = true;
            } else {
                out_header->require_cosigner = false;
            }
        } else if (strcmp(key, "co_sign_label") == 0) {
            strncpy(out_header->co_sign_label, val, sizeof(out_header->co_sign_label) - 1);
        } else if (strcmp(key, "max_signatures") == 0) {
            out_header->max_signatures = atoi(val);

        /* IP Property Bundle metadata keys */
        } else if (strcmp(key, "property_bundle_hash") == 0) {
            strncpy(out_header->property_bundle_hash, val, BMD_HASH_HEX_LEN);
        } else if (strcmp(key, "property_bundle_size") == 0) {
            out_header->property_bundle_size = (uint64_t)strtoull(val, NULL, 10);
        } else if (strcmp(key, "property_bundle_destroyed") == 0) {
            if (_stricmp(val, "true") == 0 || strcmp(val, "1") == 0) {
                out_header->property_bundle_destroyed = true;
            } else {
                out_header->property_bundle_destroyed = false;
            }
        } else if (strcmp(key, "inject_property_path") == 0) {
            strncpy(out_header->inject_property_path, val, sizeof(out_header->inject_property_path) - 1);
        }
        /* NOTE: property_bundle: block scalar is handled separately by
         * bmd_parser_extract_property_bundle() called from bmd_parse_string() */
    }

    /* Strict verification of mandatory schema keys */
    if (out_header->block_id[0] == '\0') return BMD_ERR_MISSING_REQUIRED_KEY;
    if (out_header->previous_hash[0] == '\0') return BMD_ERR_MISSING_REQUIRED_KEY;
    if (out_header->current_hash[0] == '\0') return BMD_ERR_MISSING_REQUIRED_KEY;

    return BMD_OK;
}

/**
 * @brief Extract `property_bundle:` YAML block scalar from frontmatter text.
 *
 * Searches for a line matching "property_bundle: |" (literal block scalar) and
 * collects all subsequent indented lines (until the next YAML key at column 0
 * or end of string).  The collected base64 lines are concatenated (whitespace
 * stripped per line) and returned as a heap-allocated string in *out_data.
 * The caller is responsible for freeing *out_data.
 *
 * Returns BMD_OK even when no property_bundle key is present (*out_data = NULL).
 */
bmd_status_t bmd_parser_extract_property_bundle(const char* fm_text,
                                                 char** out_data,
                                                 size_t* out_len) {
    if (!out_data || !out_len) return BMD_ERR_NULL_PARAM;
    *out_data = NULL;
    *out_len  = 0;

    if (!fm_text) return BMD_OK;

    /* Locate the "property_bundle: |" line */
    const char* p = fm_text;
    while (*p != '\0') {
        /* Find start of this line */
        const char* line_start = p;
        /* Advance to end of line */
        while (*p != '\0' && *p != '\n') p++;
        size_t line_len = (size_t)(p - line_start);
        if (*p == '\n') p++;

        /* Copy line for inspection */
        char lbuf[1024];
        if (line_len >= sizeof(lbuf)) line_len = sizeof(lbuf) - 1;
        memcpy(lbuf, line_start, line_len);
        lbuf[line_len] = '\0';
        bmd_trim_whitespace(lbuf);

        /* Check for "property_bundle: |" */
        if (strncmp(lbuf, "property_bundle:", 16) == 0) {
            char* after_key = lbuf + 16;
            while (*after_key == ' ' || *after_key == '\t') after_key++;
            if (*after_key == '|') {
                /* Found the block scalar marker — now collect subsequent lines */
                /* First pass: calculate total length */
                size_t total = 0;
                const char* scan = p;
                while (*scan != '\0') {
                    const char* ls = scan;
                    while (*scan != '\0' && *scan != '\n') scan++;
                    size_t ll = (size_t)(scan - ls);
                    if (*scan == '\n') scan++;

                    /* A line that starts at column 0 and isn't blank ends the block */
                    if (ll > 0 && ls[0] != ' ' && ls[0] != '\t') break;

                    /* Trim and accumulate length (+1 for possible newline) */
                    char tmp[1024];
                    if (ll >= sizeof(tmp)) ll = sizeof(tmp) - 1;
                    memcpy(tmp, ls, ll);
                    tmp[ll] = '\0';
                    bmd_trim_whitespace(tmp);
                    total += strlen(tmp);
                }

                if (total == 0) return BMD_OK; /* Empty block */

                char* buf = (char*)malloc(total + 1);
                if (!buf) return BMD_ERR_OUT_OF_MEMORY;
                buf[0] = '\0';

                /* Second pass: fill the buffer */
                size_t pos = 0;
                scan = p;
                while (*scan != '\0') {
                    const char* ls = scan;
                    while (*scan != '\0' && *scan != '\n') scan++;
                    size_t ll = (size_t)(scan - ls);
                    if (*scan == '\n') scan++;

                    if (ll > 0 && ls[0] != ' ' && ls[0] != '\t') break;

                    char tmp[1024];
                    if (ll >= sizeof(tmp)) ll = sizeof(tmp) - 1;
                    memcpy(tmp, ls, ll);
                    tmp[ll] = '\0';
                    bmd_trim_whitespace(tmp);
                    size_t tlen = strlen(tmp);
                    if (tlen > 0 && pos + tlen <= total) {
                        memcpy(buf + pos, tmp, tlen);
                        pos += tlen;
                    }
                }
                buf[pos] = '\0';
                *out_data = buf;
                *out_len  = pos;
                return BMD_OK;
            }
        }
    }

    return BMD_OK; /* key not present — not an error */
}
