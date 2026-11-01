/**
 * @file bmd_engine.h
 * @brief Blockchain Markdown (.bmd) Core C11 Engine - Public API & Structs
 * 
 * Enterprise-grade cryptographic engine, parser, ledger system, and FFI layer
 * for the Blockchain Markdown (.bmd) Language.
 * Designed for High-Assurance Autonomous Agent Governance ('muse-spark').
 */

#ifndef BMD_ENGINE_H
#define BMD_ENGINE_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32) || defined(__CYGWIN__)
  #ifdef BMD_BUILD_DLL
    #define BMD_API __declspec(dllexport)
  #elif defined(BMD_USE_DLL)
    #define BMD_API __declspec(dllimport)
  #else
    #define BMD_API
  #endif
#else
  #define BMD_API __attribute__((visibility("default")))
#endif

#define BMD_VERSION_MAJOR 2
#define BMD_VERSION_MINOR 1
#define BMD_VERSION_PATCH 0

/* Maximum field lengths for strict buffer-overflow prevention */
#define BMD_MAX_BLOCK_ID_LEN     128
#define BMD_HASH_HEX_LEN         128  /* 64 bytes SHA-512 in hex */
#define BMD_PUBKEY_HEX_LEN       128  /* 32 bytes Ed25519 in hex/base64 */
#define BMD_SIG_HEX_LEN          256  /* 64 bytes Ed25519 signature in hex/base64 */
#define BMD_MAX_ROLE_LEN         32
#define BMD_MAX_MODE_LEN         32

/**
 * @brief Status and Error Codes for BMD Operations
 */
typedef enum {
    BMD_OK                       = 0,
    BMD_ERR_NULL_PARAM          = -1,
    BMD_ERR_FILE_NOT_FOUND      = -2,
    BMD_ERR_OUT_OF_MEMORY       = -3,
    BMD_ERR_SYNTAX_FRONTMATTER  = -4,
    BMD_ERR_MISSING_REQUIRED_KEY= -5,
    BMD_ERR_INVALID_MODE        = -6,
    BMD_ERR_INVALID_ROLE        = -7,
    BMD_ERR_HASH_MISMATCH       = -8,
    BMD_ERR_SIG_INVALID         = -9,
    BMD_ERR_CHAIN_BROKEN        = -10,
    BMD_ERR_ENCRYPTION_FAILED   = -11,
    BMD_ERR_DECRYPTION_FAILED   = -12,
    BMD_ERR_TRANSFER_VIOLATION  = -13,
    BMD_ERR_BUFFER_TOO_SMALL    = -14,

    /* v2.0 IP Property Bundle errors */
    BMD_ERR_PROPERTY_PATH_NOT_FOUND    = 20,
    BMD_ERR_PROPERTY_INJECTION_FAILED  = 21,
    BMD_ERR_PROPERTY_DECOMPILE_BLOCKED = 22,

    /* v2.1 Signature governance errors */
    BMD_ERR_SIGNATURE_LIMIT_EXCEEDED   = 30   /**< max_signatures cap reached */
} bmd_status_t;

/**
 * @brief Operational Modes
 */
typedef enum {
    BMD_MODE_UNKNOWN = 0,
    BMD_MODE_DRAFT,     /**< Editable, exploratory, drafting */
    BMD_MODE_TRANSFER   /**< Immutable, frozen legal/asset transfer */
} bmd_mode_t;

/**
 * @brief Signer Roles
 */
typedef enum {
    BMD_ROLE_UNKNOWN = 0,
    BMD_ROLE_EMISOR,    /**< Source entity, transfers/signs asset */
    BMD_ROLE_RECEPTOR   /**< Destination entity, verifies & accepts */
} bmd_role_t;

/**
 * @brief Typed Frontmatter Header of a .bmd block
 */
typedef struct {
    char block_id[BMD_MAX_BLOCK_ID_LEN];
    char previous_hash[BMD_HASH_HEX_LEN + 1];
    char current_hash[BMD_HASH_HEX_LEN + 1];
    bmd_mode_t mode;
    bmd_role_t signer_role;
    int64_t timestamp;
    char public_key[BMD_PUBKEY_HEX_LEN + 1];
    char signature_layer_2[BMD_SIG_HEX_LEN + 1];
    char receiver_public_key[BMD_PUBKEY_HEX_LEN + 1];
    char receiver_signature[BMD_SIG_HEX_LEN + 1];
    bool payload_encrypted;

    /* v2.0 Extended Directives */
    char document_type[64];           /**< testament|contract|ip_transfer|declaration|decree */
    char jurisdiction[128];           /**< optional: "México, CDMX" etc. */
    int64_t expiry_timestamp;         /**< 0 = never */
    int  witnesses_required;          /**< 0 = none needed */
    bool require_cosigner;            /**< true = co-sign button shown in UI */
    char co_sign_label[128];          /**< custom co-sign button label */
    int  max_signatures;              /**< 0 = unlimited; 1 = emitter-only unilateral; 2 = bilateral; N = multi-party */

    /* IP Property Bundle (inject_property) */
    char inject_property_path[512];   /**< source path (cleared after injection) */
    /* NOTE: property_bundle blob is NOT stored here — use bmd_document_t.property_bundle_data */
    char property_bundle_hash[BMD_HASH_HEX_LEN + 1]; /**< SHA-512 of the encrypted bundle */
    uint64_t property_bundle_size;    /**< bytes of the encrypted+base64 bundle */
    bool property_bundle_destroyed;   /**< true = source files were deleted */
} bmd_header_t;

/**
 * @brief Complete in-memory BMD Document representation
 */
typedef struct {
    bmd_header_t header;
    char* payload;              /**< Null-terminated markdown or encrypted text */
    size_t payload_len;         /**< Length of payload in bytes */
    char* raw_frontmatter;      /**< Preserved raw YAML frontmatter */
    bool is_verified;           /**< True if hash and signature were verified */
    char computed_hash[BMD_HASH_HEX_LEN + 1]; /**< Hash computed on last check */

    /* v2.0 IP Property Bundle — heap-allocated (can be MB-sized) */
    char* property_bundle_data;     /**< heap-allocated base64 bundle */
    size_t property_bundle_data_len;
} bmd_document_t;

/**
 * @brief Audit and Chain Verification Report
 */
typedef struct {
    size_t total_blocks;
    size_t valid_blocks;
    size_t corrupted_blocks;
    char last_valid_hash[BMD_HASH_HEX_LEN + 1];
    char failing_block_id[BMD_MAX_BLOCK_ID_LEN];
    bmd_status_t failure_reason;
    char audit_summary[512];
} bmd_chain_report_t;

/* --- Lifecycle Management --- */
BMD_API bmd_document_t* bmd_document_create(void);
BMD_API void bmd_document_free(bmd_document_t* doc);

/* --- Parsing & Serialization --- */
BMD_API bmd_status_t bmd_parse_string(const char* content, size_t length, bmd_document_t** out_doc);
BMD_API bmd_status_t bmd_parse_file(const char* filepath, bmd_document_t** out_doc);
BMD_API bmd_status_t bmd_serialize(const bmd_document_t* doc, char** out_string, size_t* out_length);
BMD_API bmd_status_t bmd_save_file(const bmd_document_t* doc, const char* filepath);

/* --- Cryptographic Verification & Calculation --- */
BMD_API bmd_status_t bmd_compute_hash(const bmd_document_t* doc, char out_hash[BMD_HASH_HEX_LEN + 1]);
BMD_API bmd_status_t bmd_verify_document(bmd_document_t* doc);
BMD_API bmd_status_t bmd_sign_document(bmd_document_t* doc, const uint8_t private_key[32], bmd_role_t role);

/* --- Cryptographic Payload Sealing (ChaCha20) --- */
BMD_API bmd_status_t bmd_encrypt_payload(bmd_document_t* doc, const uint8_t key[32], const uint8_t nonce[12]);
BMD_API bmd_status_t bmd_decrypt_payload(bmd_document_t* doc, const uint8_t key[32], const uint8_t nonce[12]);

/* --- State Machine Transitions --- */
BMD_API bmd_status_t bmd_transition_to_transfer(bmd_document_t* doc, const uint8_t private_key[32]);
BMD_API bmd_status_t bmd_accept_transfer(bmd_document_t* doc, const uint8_t receptor_privkey[32], const char* receptor_pubkey);
BMD_API bmd_status_t bmd_cosign_receiver(bmd_document_t* doc, const uint8_t receiver_privkey[32]);

/* --- Multi-Block Ledger & Audit Chain --- */
BMD_API bmd_status_t bmd_verify_chain(const char* const* filepaths, size_t file_count, bmd_chain_report_t* out_report);

/* --- Utility & Diagnostics --- */
BMD_API const char* bmd_status_string(bmd_status_t status);
BMD_API const char* bmd_mode_string(bmd_mode_t mode);
BMD_API const char* bmd_role_string(bmd_role_t role);
BMD_API bmd_mode_t  bmd_mode_from_string(const char* str);
BMD_API bmd_role_t  bmd_role_from_string(const char* str);

#ifdef __cplusplus
}
#endif

#endif /* BMD_ENGINE_H */
