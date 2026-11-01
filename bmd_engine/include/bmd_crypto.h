/**
 * @file bmd_crypto.h
 * @brief Enterprise Cryptographic Primitives for BMD Engine (C11)
 * 
 * Provides self-contained, high-performance implementations of:
 * - SHA-256 (FIPS 180-4 compliant)
 * - Ed25519 Digital Signatures (RFC 8032)
 * - ChaCha20 Stream Cipher (RFC 8439)
 * - Hex / Base64 Canonical Encoders and Constant-Time Comparators
 */

#ifndef BMD_CRYPTO_H
#define BMD_CRYPTO_H

#include "bmd_engine.h"
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* SHA-256 Definitions */
typedef struct {
    uint32_t state[8];
    uint64_t count;
    uint8_t  buffer[64];
} bmd_sha256_ctx_t;

BMD_API void bmd_sha256_init(bmd_sha256_ctx_t* ctx);
BMD_API void bmd_sha256_update(bmd_sha256_ctx_t* ctx, const uint8_t* data, size_t len);
BMD_API void bmd_sha256_final(bmd_sha256_ctx_t* ctx, uint8_t hash[32]);
BMD_API void bmd_sha256_hex(const uint8_t* data, size_t len, char out_hex[65]);
BMD_API void bmd_sha512(const uint8_t* in, size_t in_len, uint8_t out[64]);
BMD_API void bmd_sha512_hex(const uint8_t* data, size_t len, char out_hex[129]);

/* Constant-Time Memory Comparison */
BMD_API int bmd_constant_time_memcmp(const void* a, const void* b, size_t size);
BMD_API void bmd_secure_memzero(void* ptr, size_t size);

/* Hex / Base64 Helpers */
BMD_API void bmd_bin_to_hex(const uint8_t* bin, size_t bin_len, char* out_hex);
BMD_API bool bmd_hex_to_bin(const char* hex, uint8_t* out_bin, size_t bin_len);

BMD_API size_t bmd_base64_encode(const uint8_t* in, size_t in_len, char* out, size_t out_max);
BMD_API bool bmd_base64_decode(const char* in, uint8_t* out, size_t* out_len);

/* Ed25519 (RFC 8032) */
BMD_API void bmd_ed25519_keypair(uint8_t public_key[32], uint8_t secret_key[64], const uint8_t seed[32]);
BMD_API void bmd_ed25519_sign(uint8_t signature[64], const uint8_t* message, size_t message_len,
                              const uint8_t public_key[32], const uint8_t secret_key[64]);
BMD_API bool bmd_ed25519_verify(const uint8_t signature[64], const uint8_t* message, size_t message_len,
                                const uint8_t public_key[32]);

/* ChaCha20 (RFC 8439) */
BMD_API void bmd_chacha20_xor(const uint8_t key[32], uint32_t counter, const uint8_t nonce[12],
                              const uint8_t* in, uint8_t* out, size_t len);

#ifdef __cplusplus
}
#endif

#endif /* BMD_CRYPTO_H */
