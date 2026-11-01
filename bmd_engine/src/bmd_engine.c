/**
 * @file bmd_engine.c
 * @brief Core Execution Engine & Lifecycle for Blockchain Markdown (.bmd)
 */

#include "bmd_engine.h"
#include "bmd_crypto.h"
#include "bmd_parser.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

#ifndef BMD_BUILD_DLL
#define BMD_BUILD_DLL
#endif

/* --- Lifecycle Management --- */

bmd_document_t* bmd_document_create(void) {
    bmd_document_t* doc = (bmd_document_t*)calloc(1, sizeof(bmd_document_t));
    if (!doc) return NULL;
    doc->header.mode = BMD_MODE_DRAFT;
    doc->header.signer_role = BMD_ROLE_UNKNOWN;
    doc->header.payload_encrypted = false;
    doc->payload = _strdup("");
    doc->payload_len = 0;
    return doc;
}

void bmd_document_free(bmd_document_t* doc) {
    if (!doc) return;
    if (doc->payload) {
        bmd_secure_memzero(doc->payload, doc->payload_len);
        free(doc->payload);
        doc->payload = NULL;
    }
    if (doc->raw_frontmatter) {
        free(doc->raw_frontmatter);
        doc->raw_frontmatter = NULL;
    }
    /* v2.0: securely erase and free the heap-allocated property bundle */
    if (doc->property_bundle_data) {
        bmd_secure_memzero(doc->property_bundle_data, doc->property_bundle_data_len);
        free(doc->property_bundle_data);
        doc->property_bundle_data = NULL;
    }
    bmd_secure_memzero(doc, sizeof(bmd_document_t));
    free(doc);
}

/* --- Canonical Hash Calculation (SHA-512) --- */

bmd_status_t bmd_compute_hash(const bmd_document_t* doc, char out_hash[BMD_HASH_HEX_LEN + 1]) {
    if (!doc || !out_hash) return BMD_ERR_NULL_PARAM;

    /* Canonical payload digest — strip leading/trailing whitespace for platform independence */
    const char* payload_start = doc->payload ? doc->payload : "";
    /* Skip leading newlines/spaces */
    while (*payload_start == '\n' || *payload_start == '\r' || *payload_start == ' ') {
        payload_start++;
    }
    size_t plen = strlen(payload_start);
    /* Strip trailing newlines/spaces */
    while (plen > 0 && (payload_start[plen-1] == '\n' || payload_start[plen-1] == '\r' ||
                         payload_start[plen-1] == ' ')) {
        plen--;
    }
    char payload_hex[129];
    bmd_sha512_hex((const uint8_t*)payload_start, plen, payload_hex);

    /* Construct Canonical Header String:
     * canonical_str = block_id | prev_hash | mode | role | timestamp | pubkey | encrypted | payload_hex
     * v2.0 extension: append new fields if non-zero/non-empty
     */
    char canonical_buf[8192];
    int clen = snprintf(canonical_buf, sizeof(canonical_buf),
             "%s|%s|%s|%s|%" PRId64 "|%s|%d|%s",
             doc->header.block_id,
             doc->header.previous_hash,
             bmd_mode_string(doc->header.mode),
             bmd_role_string(doc->header.signer_role),
             doc->header.timestamp,
             doc->header.public_key,
             doc->header.payload_encrypted ? 1 : 0,
             payload_hex);

    /* v2.0: append extended fields when present */
    if (doc->header.document_type[0] != '\0' ||
        doc->header.jurisdiction[0] != '\0'  ||
        doc->header.expiry_timestamp != 0    ||
        doc->header.witnesses_required != 0  ||
        doc->header.require_cosigner         ||
        doc->header.max_signatures != 0      ||
        doc->header.property_bundle_hash[0] != '\0') {

        snprintf(canonical_buf + clen, sizeof(canonical_buf) - (size_t)clen,
                 "|%s|%s|%" PRId64 "|%d|%d|%s|%d",
                 doc->header.document_type,
                 doc->header.jurisdiction,
                 doc->header.expiry_timestamp,
                 doc->header.witnesses_required,
                 doc->header.require_cosigner ? 1 : 0,
                 doc->header.property_bundle_hash,
                 doc->header.max_signatures);
    }

    bmd_sha512_hex((const uint8_t*)canonical_buf, strlen(canonical_buf), out_hash);
    return BMD_OK;
}

/* --- Parsing & Loading --- */

bmd_status_t bmd_parse_string(const char* content, size_t length, bmd_document_t** out_doc) {
    if (!content || !out_doc) return BMD_ERR_NULL_PARAM;
    *out_doc = NULL;

    bmd_document_t* doc = bmd_document_create();
    if (!doc) return BMD_ERR_OUT_OF_MEMORY;

    char* fm_text = NULL;
    size_t fm_len = 0;
    char* payload_text = NULL;
    size_t payload_len = 0;

    bmd_status_t status = bmd_parser_extract_frontmatter(content, length,
                                                         &fm_text, &fm_len,
                                                         &payload_text, &payload_len);
    if (status != BMD_OK) {
        bmd_document_free(doc);
        return status;
    }

    doc->raw_frontmatter = fm_text;
    if (doc->payload) free(doc->payload);
    doc->payload = payload_text;
    doc->payload_len = payload_len;

    status = bmd_parser_parse_yaml_header(doc->raw_frontmatter, &doc->header);
    if (status != BMD_OK) {
        bmd_document_free(doc);
        return status;
    }

    /* v2.0: extract property_bundle block scalar from frontmatter */
    {
        char* pb_data = NULL;
        size_t pb_len = 0;
        bmd_status_t pb_st = bmd_parser_extract_property_bundle(doc->raw_frontmatter, &pb_data, &pb_len);
        if (pb_st != BMD_OK) {
            bmd_document_free(doc);
            return pb_st;
        }
        if (pb_data) {
            doc->property_bundle_data     = pb_data;
            doc->property_bundle_data_len = pb_len;
        }
    }

    *out_doc = doc;
    return BMD_OK;
}

bmd_status_t bmd_parse_file(const char* filepath, bmd_document_t** out_doc) {
    if (!filepath || !out_doc) return BMD_ERR_NULL_PARAM;
    *out_doc = NULL;

    FILE* f = fopen(filepath, "rb");
    if (!f) return BMD_ERR_FILE_NOT_FOUND;

    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (size < 0) {
        fclose(f);
        return BMD_ERR_FILE_NOT_FOUND;
    }

    char* buffer = (char*)malloc((size_t)size + 1);
    if (!buffer) {
        fclose(f);
        return BMD_ERR_OUT_OF_MEMORY;
    }

    size_t read_bytes = fread(buffer, 1, (size_t)size, f);
    buffer[read_bytes] = '\0';
    fclose(f);

    bmd_status_t st = bmd_parse_string(buffer, read_bytes, out_doc);
    free(buffer);
    return st;
}

/* --- Cryptographic Verification --- */

bmd_status_t bmd_verify_document(bmd_document_t* doc) {
    if (!doc) return BMD_ERR_NULL_PARAM;
    doc->is_verified = false;

    char expected_hash[BMD_HASH_HEX_LEN + 1];
    bmd_status_t st = bmd_compute_hash(doc, expected_hash);
    if (st != BMD_OK) return st;

    strncpy(doc->computed_hash, expected_hash, BMD_HASH_HEX_LEN);
    doc->computed_hash[BMD_HASH_HEX_LEN] = '\0';

    /* Verify Hash Integrity */
    if (_stricmp(doc->header.current_hash, expected_hash) != 0) {
        return BMD_ERR_HASH_MISMATCH;
    }

    /* Verification rules per mode */
    if (doc->header.mode == BMD_MODE_TRANSFER) {
        /* Transfer mode requires an Ed25519 signature */
        if (doc->header.public_key[0] == '\0' || doc->header.signature_layer_2[0] == '\0') {
            return BMD_ERR_TRANSFER_VIOLATION;
        }

        uint8_t pk_bin[32];
        if (!bmd_hex_to_bin(doc->header.public_key, pk_bin, 32)) {
            /* Try base64 */
            size_t out_len = 0;
            if (!bmd_base64_decode(doc->header.public_key, pk_bin, &out_len) || out_len != 32) {
                return BMD_ERR_SIG_INVALID;
            }
        }

        uint8_t sig_bin[64];
        if (!bmd_hex_to_bin(doc->header.signature_layer_2, sig_bin, 64)) {
            size_t out_len = 0;
            if (!bmd_base64_decode(doc->header.signature_layer_2, sig_bin, &out_len) || out_len != 64) {
                return BMD_ERR_SIG_INVALID;
            }
        }

        bool valid = bmd_ed25519_verify(sig_bin, (const uint8_t*)doc->header.current_hash,
                                        strlen(doc->header.current_hash), pk_bin);
        if (!valid) {
            return BMD_ERR_SIG_INVALID;
        }

        /* If receiver has co-signed, verify receiver signature too */
        if (doc->header.receiver_public_key[0] != '\0' && doc->header.receiver_signature[0] != '\0') {
            uint8_t rec_pk_bin[32];
            uint8_t rec_sig_bin[64];
            if (!bmd_hex_to_bin(doc->header.receiver_public_key, rec_pk_bin, 32)) {
                size_t out_len = 0;
                bmd_base64_decode(doc->header.receiver_public_key, rec_pk_bin, &out_len);
            }
            if (!bmd_hex_to_bin(doc->header.receiver_signature, rec_sig_bin, 64)) {
                size_t out_len = 0;
                bmd_base64_decode(doc->header.receiver_signature, rec_sig_bin, &out_len);
            }
            bool rec_valid = bmd_ed25519_verify(rec_sig_bin, (const uint8_t*)doc->header.current_hash,
                                                strlen(doc->header.current_hash), rec_pk_bin);
            if (!rec_valid) {
                return BMD_ERR_SIG_INVALID;
            }
        }
    } else {
        /* Draft mode: if signature exists, verify it */
        if (doc->header.signature_layer_2[0] != '\0' && doc->header.public_key[0] != '\0') {
            uint8_t pk_bin[32];
            uint8_t sig_bin[64];
            if (bmd_hex_to_bin(doc->header.public_key, pk_bin, 32) &&
                bmd_hex_to_bin(doc->header.signature_layer_2, sig_bin, 64)) {
                if (!bmd_ed25519_verify(sig_bin, (const uint8_t*)doc->header.current_hash,
                                        strlen(doc->header.current_hash), pk_bin)) {
                    return BMD_ERR_SIG_INVALID;
                }
            }
        }
    }

    doc->is_verified = true;
    return BMD_OK;
}

/* --- Document Signing --- */

bmd_status_t bmd_sign_document(bmd_document_t* doc, const uint8_t private_key_seed[32], bmd_role_t role) {
    if (!doc || !private_key_seed) return BMD_ERR_NULL_PARAM;

    uint8_t pk[32];
    uint8_t sk[64];
    bmd_ed25519_keypair(pk, sk, private_key_seed);

    doc->header.signer_role = role;
    bmd_bin_to_hex(pk, 32, doc->header.public_key);

    /* Compute fresh current_hash */
    char new_hash[BMD_HASH_HEX_LEN + 1];
    bmd_status_t st = bmd_compute_hash(doc, new_hash);
    if (st != BMD_OK) return st;

    strncpy(doc->header.current_hash, new_hash, BMD_HASH_HEX_LEN);
    doc->header.current_hash[BMD_HASH_HEX_LEN] = '\0';

    /* Sign current_hash with Ed25519 */
    uint8_t sig[64];
    bmd_ed25519_sign(sig, (const uint8_t*)doc->header.current_hash, strlen(doc->header.current_hash), pk, sk);

    bmd_bin_to_hex(sig, 64, doc->header.signature_layer_2);
    doc->is_verified = true;
    strncpy(doc->computed_hash, new_hash, BMD_HASH_HEX_LEN);

    bmd_secure_memzero(sk, sizeof(sk));
    return BMD_OK;
}

/* --- State Machine Transitions --- */

bmd_status_t bmd_transition_to_transfer(bmd_document_t* doc, const uint8_t private_key[32]) {
    if (!doc || !private_key) return BMD_ERR_NULL_PARAM;
    doc->header.mode = BMD_MODE_TRANSFER;
    return bmd_sign_document(doc, private_key, BMD_ROLE_EMISOR);
}

bmd_status_t bmd_accept_transfer(bmd_document_t* doc, const uint8_t receptor_privkey[32], const char* receptor_pubkey) {
    if (!doc || !receptor_privkey) return BMD_ERR_NULL_PARAM;
    (void)receptor_pubkey;
    return bmd_cosign_receiver(doc, receptor_privkey);
}

bmd_status_t bmd_cosign_receiver(bmd_document_t* doc, const uint8_t receiver_privkey[32]) {
    if (!doc || !receiver_privkey) return BMD_ERR_NULL_PARAM;

    /* Document must be in TRANSFER mode and already verified */
    if (doc->header.mode != BMD_MODE_TRANSFER) {
        return BMD_ERR_TRANSFER_VIOLATION;
    }

    /* Count current signatures: emitter=1 baseline, receiver co-sign=+1 */
    int current_sig_count = (doc->header.signature_layer_2[0] != '\0') ? 1 : 0;
    if (doc->header.receiver_signature[0] != '\0') current_sig_count++;

    /* Enforce max_signatures cap (0 = unlimited) */
    if (doc->header.max_signatures > 0 && current_sig_count >= doc->header.max_signatures) {
        return BMD_ERR_SIGNATURE_LIMIT_EXCEEDED;
    }

    bmd_status_t st = bmd_verify_document(doc);
    if (st != BMD_OK) return st;

    uint8_t pk[32];
    uint8_t sk[64];
    bmd_ed25519_keypair(pk, sk, receiver_privkey);

    bmd_bin_to_hex(pk, 32, doc->header.receiver_public_key);

    /* Sign the existing immutable current_hash without changing it */
    uint8_t sig[64];
    bmd_ed25519_sign(sig, (const uint8_t*)doc->header.current_hash, strlen(doc->header.current_hash), pk, sk);
    bmd_bin_to_hex(sig, 64, doc->header.receiver_signature);

    bmd_secure_memzero(sk, sizeof(sk));
    return BMD_OK;
}

/* --- Payload Encryption / Decryption --- */

bmd_status_t bmd_encrypt_payload(bmd_document_t* doc, const uint8_t key[32], const uint8_t nonce[12]) {
    if (!doc || !key || !nonce) return BMD_ERR_NULL_PARAM;
    if (doc->header.payload_encrypted) return BMD_OK; /* Already encrypted */

    size_t plen = doc->payload ? strlen(doc->payload) : 0;
    if (plen == 0) return BMD_OK;

    uint8_t* ciphertext = (uint8_t*)malloc(plen);
    if (!ciphertext) return BMD_ERR_OUT_OF_MEMORY;

    bmd_chacha20_xor(key, 1, nonce, (const uint8_t*)doc->payload, ciphertext, plen);

    /* Allocate Base64 buffer */
    size_t b64_max = plen * 2 + 64;
    char* b64_buf = (char*)malloc(b64_max);
    if (!b64_buf) {
        free(ciphertext);
        return BMD_ERR_OUT_OF_MEMORY;
    }

    size_t b64_len = bmd_base64_encode(ciphertext, plen, b64_buf, b64_max);
    free(ciphertext);

    free(doc->payload);
    doc->payload = b64_buf;
    doc->payload_len = b64_len;
    doc->header.payload_encrypted = true;

    /* Recalculate hash */
    char new_hash[BMD_HASH_HEX_LEN + 1];
    bmd_compute_hash(doc, new_hash);
    strncpy(doc->header.current_hash, new_hash, BMD_HASH_HEX_LEN);

    return BMD_OK;
}

bmd_status_t bmd_decrypt_payload(bmd_document_t* doc, const uint8_t key[32], const uint8_t nonce[12]) {
    if (!doc || !key || !nonce) return BMD_ERR_NULL_PARAM;
    if (!doc->header.payload_encrypted) return BMD_OK; /* Not encrypted */

    size_t plen = doc->payload ? strlen(doc->payload) : 0;
    if (plen == 0) return BMD_OK;

    uint8_t* cipher_bin = (uint8_t*)malloc(plen);
    if (!cipher_bin) return BMD_ERR_OUT_OF_MEMORY;

    size_t raw_len = 0;
    if (!bmd_base64_decode(doc->payload, cipher_bin, &raw_len)) {
        free(cipher_bin);
        return BMD_ERR_DECRYPTION_FAILED;
    }

    char* plaintext = (char*)malloc(raw_len + 1);
    if (!plaintext) {
        free(cipher_bin);
        return BMD_ERR_OUT_OF_MEMORY;
    }

    bmd_chacha20_xor(key, 1, nonce, cipher_bin, (uint8_t*)plaintext, raw_len);
    plaintext[raw_len] = '\0';
    free(cipher_bin);

    free(doc->payload);
    doc->payload = plaintext;
    doc->payload_len = raw_len;
    doc->header.payload_encrypted = false;

    /* Recalculate hash */
    char new_hash[BMD_HASH_HEX_LEN + 1];
    bmd_compute_hash(doc, new_hash);
    strncpy(doc->header.current_hash, new_hash, BMD_HASH_HEX_LEN);

    return BMD_OK;
}

/* --- Serialization --- */

bmd_status_t bmd_serialize(const bmd_document_t* doc, char** out_string, size_t* out_length) {
    if (!doc || !out_string) return BMD_ERR_NULL_PARAM;
    *out_string = NULL;

    size_t payload_len    = doc->payload ? strlen(doc->payload) : 0;
    size_t bundle_b64_len = doc->property_bundle_data ? doc->property_bundle_data_len : 0;
    /* Estimate: base YAML + payload + property bundle (base64 with line-wraps) */
    size_t est_size = 8192 + payload_len + bundle_b64_len + 256;

    char* buf = (char*)malloc(est_size);
    if (!buf) return BMD_ERR_OUT_OF_MEMORY;

    size_t pos = 0;

#define APPEND(...) \
    do { \
        int _n = snprintf(buf + pos, est_size - pos, __VA_ARGS__); \
        if (_n > 0) pos += (size_t)_n; \
    } while (0)

    APPEND("---\n");
    APPEND("block_id: \"%s\"\n",         doc->header.block_id);
    APPEND("previous_hash: \"%s\"\n",    doc->header.previous_hash);
    APPEND("current_hash: \"%s\"\n",     doc->header.current_hash);
    APPEND("mode: \"%s\"\n",             bmd_mode_string(doc->header.mode));
    APPEND("signer_role: \"%s\"\n",      bmd_role_string(doc->header.signer_role));
    APPEND("timestamp: %" PRId64 "\n",   doc->header.timestamp);
    APPEND("public_key: \"%s\"\n",       doc->header.public_key);
    APPEND("signature_layer_2: \"%s\"\n", doc->header.signature_layer_2);

    if (doc->header.receiver_public_key[0] != '\0' || doc->header.receiver_signature[0] != '\0') {
        APPEND("receiver_public_key: \"%s\"\n", doc->header.receiver_public_key);
        APPEND("receiver_signature: \"%s\"\n",  doc->header.receiver_signature);
    }

    APPEND("payload_encrypted: %s\n", doc->header.payload_encrypted ? "true" : "false");

    /* v2.0 Extended Directives — emit only when non-zero/non-empty */
    if (doc->header.document_type[0] != '\0') {
        APPEND("document_type: \"%s\"\n", doc->header.document_type);
    }
    if (doc->header.jurisdiction[0] != '\0') {
        APPEND("jurisdiction: \"%s\"\n", doc->header.jurisdiction);
    }
    if (doc->header.expiry_timestamp != 0) {
        APPEND("expiry_timestamp: %" PRId64 "\n", doc->header.expiry_timestamp);
    }
    if (doc->header.witnesses_required != 0) {
        APPEND("witnesses_required: %d\n", doc->header.witnesses_required);
    }
    if (doc->header.require_cosigner) {
        APPEND("require_cosigner: true\n");
    }
    if (doc->header.co_sign_label[0] != '\0') {
        APPEND("co_sign_label: \"%s\"\n", doc->header.co_sign_label);
    }
    if (doc->header.max_signatures > 0) {
        APPEND("max_signatures: \"%d\"\n", doc->header.max_signatures);
    }

    /* IP Property Bundle metadata */
    if (doc->header.inject_property_path[0] != '\0') {
        APPEND("inject_property_path: \"%s\"\n", doc->header.inject_property_path);
    }
    if (doc->header.property_bundle_hash[0] != '\0') {
        APPEND("property_bundle_hash: \"%s\"\n", doc->header.property_bundle_hash);
    }
    if (doc->header.property_bundle_size != 0) {
        APPEND("property_bundle_size: %" PRIu64 "\n", doc->header.property_bundle_size);
    }
    if (doc->header.property_bundle_destroyed) {
        APPEND("property_bundle_destroyed: true\n");
    }

    /* IP Property Bundle data — YAML literal block scalar, lines wrapped at 76 chars */
    if (doc->property_bundle_data && doc->property_bundle_data_len > 0) {
        APPEND("property_bundle: |\n");
        const char* bd = doc->property_bundle_data;
        size_t remaining = doc->property_bundle_data_len;
        while (remaining > 0) {
            size_t chunk = remaining < 76 ? remaining : 76;
            /* Ensure we have space */
            if (pos + 2 + chunk + 1 >= est_size) break; /* safety */
            buf[pos++] = ' ';
            buf[pos++] = ' ';
            memcpy(buf + pos, bd, chunk);
            pos += chunk;
            buf[pos++] = '\n';
            bd        += chunk;
            remaining -= chunk;
        }
    }

    APPEND("---\n\n");
    APPEND("%s", doc->payload ? doc->payload : "");

#undef APPEND

    if (pos >= est_size) {
        free(buf);
        return BMD_ERR_OUT_OF_MEMORY;
    }

    buf[pos] = '\0';
    *out_string = buf;
    if (out_length) *out_length = pos;
    return BMD_OK;
}

bmd_status_t bmd_save_file(const bmd_document_t* doc, const char* filepath) {
    if (!doc || !filepath) return BMD_ERR_NULL_PARAM;

    char* serialized = NULL;
    size_t len = 0;
    bmd_status_t st = bmd_serialize(doc, &serialized, &len);
    if (st != BMD_OK) return st;

    FILE* f = fopen(filepath, "wb");
    if (!f) {
        free(serialized);
        return BMD_ERR_FILE_NOT_FOUND;
    }

    fwrite(serialized, 1, len, f);
    fclose(f);
    free(serialized);
    return BMD_OK;
}

/* --- Helpers & String Conversions --- */

const char* bmd_status_string(bmd_status_t status) {
    switch (status) {
        case BMD_OK: return "OK / Cryptographic Integrity Verified";
        case BMD_ERR_NULL_PARAM: return "Error: Null parameter";
        case BMD_ERR_FILE_NOT_FOUND: return "Error: .bmd file not found";
        case BMD_ERR_OUT_OF_MEMORY: return "Error: Out of memory";
        case BMD_ERR_SYNTAX_FRONTMATTER: return "Syntax Error: Invalid YAML frontmatter";
        case BMD_ERR_MISSING_REQUIRED_KEY: return "Error: Missing required keys in frontmatter";
        case BMD_ERR_INVALID_MODE: return "Error: Invalid block mode";
        case BMD_ERR_INVALID_ROLE: return "Error: Invalid signer role";
        case BMD_ERR_HASH_MISMATCH: return "INTEGRITY BREACH: Block hash mismatch (Document tampered)";
        case BMD_ERR_SIG_INVALID: return "SECURITY ERROR L2: Invalid Ed25519 digital signature";
        case BMD_ERR_CHAIN_BROKEN: return "CHAIN BREAK: Broken cryptographic link to previous block";
        case BMD_ERR_ENCRYPTION_FAILED: return "Error during ChaCha20 encryption";
        case BMD_ERR_DECRYPTION_FAILED: return "Error during ChaCha20 decryption";
        case BMD_ERR_TRANSFER_VIOLATION: return "Governance Violation: Transfer mode requires valid ownership signature";
        case BMD_ERR_BUFFER_TOO_SMALL: return "Error: Output buffer too small";
        case BMD_ERR_PROPERTY_PATH_NOT_FOUND:    return "Error: IP property path not found";
        case BMD_ERR_PROPERTY_INJECTION_FAILED:  return "Error: Property bundle injection failed";
        case BMD_ERR_PROPERTY_DECOMPILE_BLOCKED: return "Error: Property decompilation blocked (source destroyed)";
        case BMD_ERR_SIGNATURE_LIMIT_EXCEEDED:   return "Governance Error: max_signatures cap reached — co-signature rejected";
        default: return "Unknown Error";
    }
}

const char* bmd_mode_string(bmd_mode_t mode) {
    switch (mode) {
        case BMD_MODE_DRAFT: return "draft";
        case BMD_MODE_TRANSFER: return "transfer";
        default: return "unknown";
    }
}

const char* bmd_role_string(bmd_role_t role) {
    switch (role) {
        case BMD_ROLE_EMISOR: return "emisor";
        case BMD_ROLE_RECEPTOR: return "receptor";
        default: return "unknown";
    }
}

bmd_mode_t bmd_mode_from_string(const char* str) {
    if (!str) return BMD_MODE_UNKNOWN;
    if (_stricmp(str, "draft") == 0) return BMD_MODE_DRAFT;
    if (_stricmp(str, "transfer") == 0) return BMD_MODE_TRANSFER;
    return BMD_MODE_UNKNOWN;
}

bmd_role_t bmd_role_from_string(const char* str) {
    if (!str) return BMD_ROLE_UNKNOWN;
    if (_stricmp(str, "emisor") == 0 || _stricmp(str, "emitter") == 0) return BMD_ROLE_EMISOR;
    if (_stricmp(str, "receptor") == 0 || _stricmp(str, "receiver") == 0) return BMD_ROLE_RECEPTOR;
    return BMD_ROLE_UNKNOWN;
}
