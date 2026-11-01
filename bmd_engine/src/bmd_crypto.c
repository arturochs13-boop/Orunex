/**
 * @file bmd_crypto.c
 * @brief High-Assurance Cryptographic Implementations for BMD Engine
 * 
 * Includes:
 * - SHA-256 (FIPS 180-4)
 * - ChaCha20 (RFC 8439)
 * - Ed25519 (RFC 8032 / TweetNaCl constant-time core)
 * - Base64 and Hex Canonical Codecs
 */

#include "bmd_crypto.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <ctype.h>

/* ========================================================================= */
/* 1. CONSTANT TIME UTILITIES & SECURE ZERO                                 */
/* ========================================================================= */

int bmd_constant_time_memcmp(const void* a, const void* b, size_t size) {
    const uint8_t* pa = (const uint8_t*)a;
    const uint8_t* pb = (const uint8_t*)b;
    uint8_t diff = 0;
    for (size_t i = 0; i < size; ++i) {
        diff |= (pa[i] ^ pb[i]);
    }
    return (int)diff;
}

void bmd_secure_memzero(void* ptr, size_t size) {
    if (!ptr || size == 0) return;
    volatile uint8_t* p = (volatile uint8_t*)ptr;
    while (size--) {
        *p++ = 0;
    }
}

/* ========================================================================= */
/* 2. HEX CODEC                                                              */
/* ========================================================================= */

static const char HEX_CHARS[] = "0123456789abcdef";

void bmd_bin_to_hex(const uint8_t* bin, size_t bin_len, char* out_hex) {
    if (!bin || !out_hex) return;
    for (size_t i = 0; i < bin_len; ++i) {
        out_hex[i * 2]     = HEX_CHARS[(bin[i] >> 4) & 0x0F];
        out_hex[i * 2 + 1] = HEX_CHARS[bin[i] & 0x0F];
    }
    out_hex[bin_len * 2] = '\0';
}

static int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

bool bmd_hex_to_bin(const char* hex, uint8_t* out_bin, size_t bin_len) {
    if (!hex || !out_bin) return false;
    if (hex[0] == '0' && (hex[1] == 'x' || hex[1] == 'X')) {
        hex += 2;
    }
    size_t hex_len = strlen(hex);
    if (hex_len != bin_len * 2) return false;

    for (size_t i = 0; i < bin_len; ++i) {
        int hi = hex_nibble(hex[i * 2]);
        int lo = hex_nibble(hex[i * 2 + 1]);
        if (hi < 0 || lo < 0) return false;
        out_bin[i] = (uint8_t)((hi << 4) | lo);
    }
    return true;
}

/* ========================================================================= */
/* 3. BASE64 CODEC                                                           */
/* ========================================================================= */

static const char B64_CHARS[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

size_t bmd_base64_encode(const uint8_t* in, size_t in_len, char* out, size_t out_max) {
    size_t out_len = 4 * ((in_len + 2) / 3);
    if (out_max <= out_len) return 0;

    size_t i = 0, j = 0;
    while (i < in_len) {
        size_t rem = in_len - i;
        uint32_t octet_a = in[i++];
        uint32_t octet_b = (rem > 1) ? in[i++] : 0;
        uint32_t octet_c = (rem > 2) ? in[i++] : 0;
        uint32_t triple = (octet_a << 16) | (octet_b << 8) | octet_c;

        out[j++] = B64_CHARS[(triple >> 18) & 0x3F];
        out[j++] = B64_CHARS[(triple >> 12) & 0x3F];
        out[j++] = (rem > 1) ? B64_CHARS[(triple >> 6) & 0x3F] : '=';
        out[j++] = (rem > 2) ? B64_CHARS[triple & 0x3F] : '=';
    }
    out[j] = '\0';
    return j;
}

static int b64_val(char c) {
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    if (c == '+') return 62;
    if (c == '/') return 63;
    if (c == '=') return 0;
    return -1;
}

bool bmd_base64_decode(const char* in, uint8_t* out, size_t* out_len) {
    if (!in || !out || !out_len) return false;
    
    /* Filtrar espacios y saltos de línea para decodificación limpia */
    size_t in_len = 0;
    while (in[in_len]) in_len++;

    char* clean = (char*)malloc(in_len + 1);
    if (!clean) return false;

    size_t c_len = 0;
    for (size_t k = 0; k < in_len; ++k) {
        if (!isspace((unsigned char)in[k])) {
            clean[c_len++] = in[k];
        }
    }
    clean[c_len] = '\0';

    if (c_len % 4 != 0) {
        free(clean);
        return false;
    }

    size_t j = 0;
    for (size_t i = 0; i < c_len; i += 4) {
        int b0 = b64_val(clean[i]);
        int b1 = b64_val(clean[i + 1]);
        int b2 = b64_val(clean[i + 2]);
        int b3 = b64_val(clean[i + 3]);
        if (b0 < 0 || b1 < 0 || b2 < 0 || b3 < 0) {
            free(clean);
            return false;
        }

        uint32_t triple = ((uint32_t)b0 << 18) | ((uint32_t)b1 << 12) |
                          ((uint32_t)b2 << 6)  | (uint32_t)b3;

        out[j++] = (triple >> 16) & 0xFF;
        if (clean[i + 2] != '=') out[j++] = (triple >> 8) & 0xFF;
        if (clean[i + 3] != '=') out[j++] = triple & 0xFF;
    }
    free(clean);
    *out_len = j;
    return true;
}

/* ========================================================================= */
/* 4. SHA-256 IMPLEMENTATION (FIPS 180-4)                                    */
/* ========================================================================= */

#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define CH(x, y, z)  (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define SIGMA0(x) (ROTR(x, 2) ^ ROTR(x, 13) ^ ROTR(x, 22))
#define SIGMA1(x) (ROTR(x, 6) ^ ROTR(x, 11) ^ ROTR(x, 25))
#define SIGMA_S0(x) (ROTR(x, 7) ^ ROTR(x, 18) ^ ((x) >> 3))
#define SIGMA_S1(x) (ROTR(x, 17) ^ ROTR(x, 19) ^ ((x) >> 10))

static const uint32_t K256[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

static void sha256_transform(uint32_t state[8], const uint8_t data[64]) {
    uint32_t a, b, c, d, e, f, g, h, t1, t2, m[64];

    for (int i = 0, j = 0; i < 16; ++i, j += 4) {
        m[i] = ((uint32_t)data[j] << 24) | ((uint32_t)data[j + 1] << 16) |
               ((uint32_t)data[j + 2] << 8) | ((uint32_t)data[j + 3]);
    }
    for (int i = 16; i < 64; ++i) {
        m[i] = SIGMA_S1(m[i - 2]) + m[i - 7] + SIGMA_S0(m[i - 15]) + m[i - 16];
    }

    a = state[0]; b = state[1]; c = state[2]; d = state[3];
    e = state[4]; f = state[5]; g = state[6]; h = state[7];

    for (int i = 0; i < 64; ++i) {
        t1 = h + SIGMA1(e) + CH(e, f, g) + K256[i] + m[i];
        t2 = SIGMA0(a) + MAJ(a, b, c);
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }

    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}

void bmd_sha256_init(bmd_sha256_ctx_t* ctx) {
    if (!ctx) return;
    ctx->count = 0;
    ctx->state[0] = 0x6a09e667;
    ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372;
    ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f;
    ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab;
    ctx->state[7] = 0x5be0cd19;
}

void bmd_sha256_update(bmd_sha256_ctx_t* ctx, const uint8_t* data, size_t len) {
    if (!ctx || !data || len == 0) return;
    size_t buffer_idx = (size_t)(ctx->count & 0x3F);
    ctx->count += len;

    while (len > 0) {
        size_t copy_len = 64 - buffer_idx;
        if (copy_len > len) copy_len = len;

        memcpy(&ctx->buffer[buffer_idx], data, copy_len);
        data += copy_len;
        len -= copy_len;
        buffer_idx += copy_len;

        if (buffer_idx == 64) {
            sha256_transform(ctx->state, ctx->buffer);
            buffer_idx = 0;
        }
    }
}

void bmd_sha256_final(bmd_sha256_ctx_t* ctx, uint8_t hash[32]) {
    if (!ctx || !hash) return;
    size_t buffer_idx = (size_t)(ctx->count & 0x3F);
    ctx->buffer[buffer_idx++] = 0x80;

    if (buffer_idx > 56) {
        memset(&ctx->buffer[buffer_idx], 0, 64 - buffer_idx);
        sha256_transform(ctx->state, ctx->buffer);
        buffer_idx = 0;
    }
    memset(&ctx->buffer[buffer_idx], 0, 56 - buffer_idx);

    uint64_t total_bits = ctx->count * 8;
    for (int i = 7; i >= 0; --i) {
        ctx->buffer[56 + (7 - i)] = (uint8_t)((total_bits >> (i * 8)) & 0xFF);
    }
    sha256_transform(ctx->state, ctx->buffer);

    for (int i = 0; i < 8; ++i) {
        hash[i * 4]     = (uint8_t)((ctx->state[i] >> 24) & 0xFF);
        hash[i * 4 + 1] = (uint8_t)((ctx->state[i] >> 16) & 0xFF);
        hash[i * 4 + 2] = (uint8_t)((ctx->state[i] >> 8) & 0xFF);
        hash[i * 4 + 3] = (uint8_t)(ctx->state[i] & 0xFF);
    }
    bmd_secure_memzero(ctx, sizeof(bmd_sha256_ctx_t));
}

void bmd_sha256_hex(const uint8_t* data, size_t len, char out_hex[65]) {
    uint8_t hash[32];
    bmd_sha256_ctx_t ctx;
    bmd_sha256_init(&ctx);
    bmd_sha256_update(&ctx, data, len);
    bmd_sha256_final(&ctx, hash);
    bmd_bin_to_hex(hash, 32, out_hex);
}

/* ========================================================================= */
/* 5. CHACHA20 STREAM CIPHER (RFC 8439)                                      */
/* ========================================================================= */

#define CHACHA_ROTL(x, n) (((x) << (n)) | ((x) >> (32 - (n))))
#define CHACHA_QR(a, b, c, d) \
    a += b; d ^= a; d = CHACHA_ROTL(d, 16); \
    c += d; b ^= c; b = CHACHA_ROTL(b, 12); \
    a += b; d ^= a; d = CHACHA_ROTL(d, 8);  \
    c += d; b ^= c; b = CHACHA_ROTL(b, 7);

static void chacha20_block(uint32_t out[16], const uint32_t in[16]) {
    for (int i = 0; i < 16; ++i) out[i] = in[i];
    for (int i = 0; i < 10; ++i) {
        /* Column round */
        CHACHA_QR(out[0], out[4], out[8],  out[12]);
        CHACHA_QR(out[1], out[5], out[9],  out[13]);
        CHACHA_QR(out[2], out[6], out[10], out[14]);
        CHACHA_QR(out[3], out[7], out[11], out[15]);
        /* Diagonal round */
        CHACHA_QR(out[0], out[5], out[10], out[15]);
        CHACHA_QR(out[1], out[6], out[11], out[12]);
        CHACHA_QR(out[2], out[7], out[8],  out[13]);
        CHACHA_QR(out[3], out[4], out[9],  out[14]);
    }
    for (int i = 0; i < 16; ++i) out[i] += in[i];
}

void bmd_chacha20_xor(const uint8_t key[32], uint32_t counter, const uint8_t nonce[12],
                      const uint8_t* in, uint8_t* out, size_t len) {
    if (!key || !nonce || !in || !out) return;

    uint32_t state[16];
    /* "expand 32-byte k" */
    state[0] = 0x61707865;
    state[1] = 0x3320646e;
    state[2] = 0x79622d32;
    state[3] = 0x6b206574;

    for (int i = 0; i < 8; ++i) {
        state[4 + i] = ((uint32_t)key[i * 4]) |
                       ((uint32_t)key[i * 4 + 1] << 8) |
                       ((uint32_t)key[i * 4 + 2] << 16) |
                       ((uint32_t)key[i * 4 + 3] << 24);
    }

    state[12] = counter;
    for (int i = 0; i < 3; ++i) {
        state[13 + i] = ((uint32_t)nonce[i * 4]) |
                        ((uint32_t)nonce[i * 4 + 1] << 8) |
                        ((uint32_t)nonce[i * 4 + 2] << 16) |
                        ((uint32_t)nonce[i * 4 + 3] << 24);
    }

    uint32_t keystream_words[16];
    uint8_t keystream_bytes[64];

    while (len > 0) {
        chacha20_block(keystream_words, state);
        state[12]++; /* Increment block counter */

        for (int i = 0; i < 16; ++i) {
            keystream_bytes[i * 4]     = (uint8_t)(keystream_words[i] & 0xFF);
            keystream_bytes[i * 4 + 1] = (uint8_t)((keystream_words[i] >> 8) & 0xFF);
            keystream_bytes[i * 4 + 2] = (uint8_t)((keystream_words[i] >> 16) & 0xFF);
            keystream_bytes[i * 4 + 3] = (uint8_t)((keystream_words[i] >> 24) & 0xFF);
        }

        size_t chunk = len > 64 ? 64 : len;
        for (size_t i = 0; i < chunk; ++i) {
            *out++ = *in++ ^ keystream_bytes[i];
        }
        len -= chunk;
    }
}

/* ========================================================================= */
/* 6. ED25519 DIGITAL SIGNATURE ENGINE (RFC 8032 / TweetNaCl Compact Core)    */
/* ========================================================================= */

/*
 * Implementation of Ed25519 based on standard TweetNaCl constant-time arithmetic
 * with SHA-512 foundation.
 */

typedef int64_t gf[16];

static const gf _0 = { 0 };
static const gf _1 = { 1 };

static const gf _D = {
    0x78a3, 0x1359, 0x4dca, 0x75eb, 0xd8ab, 0x4141, 0x0a4d, 0x0070,
    0xe898, 0x7779, 0x4079, 0x8cc7, 0xfe73, 0x2b6f, 0x6cee, 0x5203
};

static const gf _D2 = {
    0xf159, 0x26b2, 0x9b94, 0xebd6, 0xb156, 0x8283, 0x149a, 0x00e0,
    0xd130, 0xeef3, 0x80f2, 0x198e, 0xfce7, 0x56df, 0xd9dc, 0x2406
};

static const gf _X = {
    0xd51a, 0x8f25, 0x2d60, 0xc956, 0xa7b2, 0x9525, 0xc760, 0x692c,
    0xdc5c, 0xfdd6, 0xe231, 0xc0a4, 0x53fe, 0xcd6e, 0x36d3, 0x2169
};

static const gf _Y = {
    0x6658, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666,
    0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666
};

static const gf _I = {
    0xa0b0, 0x4a0e, 0x1b27, 0xc4ee, 0xe478, 0xad2f, 0x1806, 0x2f43,
    0xd7a7, 0x3dfb, 0x0099, 0x2b4d, 0xdf0b, 0x4fc1, 0x2480, 0x2b83
};

/* SHA-512 — pure stateless implementation via hashblocks, port of TweetNaCl */

/* SHA-512 initial hash values (FIPS 180-4) */
static const uint64_t sha512_iv[8] = {
    0x6a09e667f3bcc908ULL, 0xbb67ae8584caa73bULL,
    0x3c6ef372fe94f82bULL, 0xa54ff53a5f1d36f1ULL,
    0x510e527fade682d1ULL, 0x9b05688c2b3e6c1fULL,
    0x1f83d9abfb41bd6bULL, 0x5be0cd19137e2179ULL
};

/* SHA-512 round constants */
static const uint64_t K512[80] = {
    0x428a2f98d728ae22ULL, 0x7137449123ef65cdULL, 0xb5c0fbcfec4d3b2fULL, 0xe9b5dba58189dbbcULL,
    0x3956c25bf348b538ULL, 0x59f111f1b605d019ULL, 0x923f82a4af194f9bULL, 0xab1c5ed5da6d8118ULL,
    0xd807aa98a3030242ULL, 0x12835b0145706fbeULL, 0x243185be4ee4b28cULL, 0x550c7dc3d5ffb4e2ULL,
    0x72be5d74f27b896fULL, 0x80deb1fe3b1696b1ULL, 0x9bdc06a725c71235ULL, 0xc19bf174cf692694ULL,
    0xe49b69c19ef14ad2ULL, 0xefbe4786384f25e3ULL, 0x0fc19dc68b8cd5b5ULL, 0x240ca1cc77ac9c65ULL,
    0x2de92c6f592b0275ULL, 0x4a7484aa6ea6e483ULL, 0x5cb0a9dcbd41fbd4ULL, 0x76f988da831153b5ULL,
    0x983e5152ee66dfabULL, 0xa831c66d2db43210ULL, 0xb00327c898fb213fULL, 0xbf597fc7beef0ee4ULL,
    0xc6e00bf33da88fc2ULL, 0xd5a79147930aa725ULL, 0x06ca6351e003826fULL, 0x142929670a0e6e70ULL,
    0x27b70a8546d22ffcULL, 0x2e1b21385c26c926ULL, 0x4d2c6dfc5ac42aedULL, 0x53380d139d95b3dfULL,
    0x650a73548baf63deULL, 0x766a0abb3c77b2a8ULL, 0x81c2c92e47edaee6ULL, 0x92722c851482353bULL,
    0xa2bfe8a14cf10364ULL, 0xa81a664bbc423001ULL, 0xc24b8b70d0f89791ULL, 0xc76c51a30654be30ULL,
    0xd192e819d6ef5218ULL, 0xd69906245565a910ULL, 0xf40e35855771202aULL, 0x106aa07032bbd1b8ULL,
    0x19a4c116b8d2d0c8ULL, 0x1e376c085141ab53ULL, 0x2748774cdf8eeb99ULL, 0x34b0bcb5e19b48a8ULL,
    0x391c0cb3c5c95a63ULL, 0x4ed8aa4ae3418acbULL, 0x5b9cca4f7763e373ULL, 0x682e6ff3d6b2b8a3ULL,
    0x748f82ee5defb2fcULL, 0x78a5636f43172f60ULL, 0x84c87814a1f0ab72ULL, 0x8cc702081a6439ecULL,
    0x90befffa23631e28ULL, 0xa4506cebde82bde9ULL, 0xbef9a3f7b2c67915ULL, 0xc67178f2e372532bULL,
    0xca273eceea26619cULL, 0xd186b8c721c0c207ULL, 0xeada7dd6cde0eb1eULL, 0xf57d4f7fee6ed178ULL,
    0x06f067aa72176fbaULL, 0x0a637dc5a2c898a6ULL, 0x113f9804bef90daeULL, 0x1b710b35131c471bULL,
    0x28db77f523047d84ULL, 0x32caab7b40c72493ULL, 0x3c9ebe0a15c9bebcULL, 0x431d67c49c100d4cULL,
    0x4cc5d4becb3e42b6ULL, 0x597f299cfc657e2aULL, 0x5fcb6fab3ad6faecULL, 0x6c44198c4a475817ULL
};

#define ROTR64(x, n) (((x) >> (n)) | ((x) << (64 - (n))))

/* Load big-endian u64 */
static uint64_t load64be(const uint8_t* p) {
    return ((uint64_t)p[0] << 56) | ((uint64_t)p[1] << 48) |
           ((uint64_t)p[2] << 40) | ((uint64_t)p[3] << 32) |
           ((uint64_t)p[4] << 24) | ((uint64_t)p[5] << 16) |
           ((uint64_t)p[6] <<  8) |  (uint64_t)p[7];
}

/* Store big-endian u64 */
static void store64be(uint8_t* p, uint64_t v) {
    p[0] = (uint8_t)(v >> 56); p[1] = (uint8_t)(v >> 48);
    p[2] = (uint8_t)(v >> 40); p[3] = (uint8_t)(v >> 32);
    p[4] = (uint8_t)(v >> 24); p[5] = (uint8_t)(v >> 16);
    p[6] = (uint8_t)(v >>  8); p[7] = (uint8_t)(v      );
}

/*
 * sha512_blocks: compress one or more 128-byte blocks.
 * state[0..7] = running hash; data points to n bytes (multiple of 128).
 * Returns number of bytes consumed (always n, rounded down to 128 multiple).
 * This is the TweetNaCl-style rolling-window approach translated to C.
 */
static void sha512_blocks(uint64_t state[8], const uint8_t* data, size_t n) {
    uint64_t a, b, c, d, e, f, g, h, T1, T2;
    uint64_t w[16];  /* rolling 16-word window */

    while (n >= 128) {
        /* Load message block into w[0..15] (big-endian) */
        for (int i = 0; i < 16; i++) {
            w[i] = load64be(data + 8 * i);
        }

        a = state[0]; b = state[1]; c = state[2]; d = state[3];
        e = state[4]; f = state[5]; g = state[6]; h = state[7];

        for (int i = 0; i < 80; i++) {
            /* Message schedule expansion (rolling window) */
            if (i >= 16) {
                int j = i & 15;
                uint64_t s0 = ROTR64(w[(j + 1) & 15], 1)  ^ ROTR64(w[(j + 1) & 15], 8)  ^ (w[(j + 1) & 15] >> 7);
                uint64_t s1 = ROTR64(w[(j + 14) & 15], 19) ^ ROTR64(w[(j + 14) & 15], 61) ^ (w[(j + 14) & 15] >> 6);
                w[j] += w[(j + 9) & 15] + s0 + s1;
            }
            T1 = h
               + (ROTR64(e, 14) ^ ROTR64(e, 18) ^ ROTR64(e, 41))   /* Sigma1(e) */
               + ((e & f) ^ (~e & g))                                 /* Ch(e,f,g) */
               + K512[i]
               + w[i & 15];
            T2 = (ROTR64(a, 28) ^ ROTR64(a, 34) ^ ROTR64(a, 39))   /* Sigma0(a) */
               + ((a & b) ^ (a & c) ^ (b & c));                      /* Maj(a,b,c) */
            h = g; g = f; f = e; e = d + T1;
            d = c; c = b; b = a; a = T1 + T2;
        }

        state[0] += a; state[1] += b; state[2] += c; state[3] += d;
        state[4] += e; state[5] += f; state[6] += g; state[7] += h;

        data += 128;
        n    -= 128;
    }
}

/*
 * bmd_sha512: one-shot SHA-512.  Handles all padding internally.
 */
void bmd_sha512(const uint8_t* in, size_t in_len, uint8_t out[64]) {
    uint64_t state[8];
    uint8_t  pad[256];    /* at most two padding blocks */
    size_t   remainder = in_len & 127; /* bytes in last incomplete block */
    uint64_t bit_len   = (uint64_t)in_len << 3;

    /* Initialise state */
    for (int i = 0; i < 8; i++) state[i] = sha512_iv[i];

    /* Process all complete 128-byte blocks */
    if (in_len >= 128) {
        sha512_blocks(state, in, in_len - remainder);
    }

    /* Build the padding block(s) */
    memcpy(pad, in + (in_len - remainder), remainder);
    pad[remainder] = 0x80;

    /* Choose 1 or 2 padding blocks:
       We need at least 17 bytes (1 for 0x80 + 16 for 128-bit length).
       If remainder > 111, we need a second block. */
    size_t pad_len;
    if (remainder < 112) {
        /* Fits in one block */
        memset(pad + remainder + 1, 0, 111 - remainder);
        /* 128-bit big-endian bit length: high 64 bits = 0, low 64 = bit_len */
        memset(pad + 112, 0, 8);
        store64be(pad + 120, bit_len);
        pad_len = 128;
    } else {
        /* Need two blocks */
        memset(pad + remainder + 1, 0, 127 - remainder);
        /* Second block: 112 zeros then 16-byte length */
        memset(pad + 128, 0, 112);
        memset(pad + 240, 0, 8);
        store64be(pad + 248, bit_len);
        pad_len = 256;
    }
    sha512_blocks(state, pad, pad_len);

    /* Serialise state big-endian */
    for (int i = 0; i < 8; i++) store64be(out + 8 * i, state[i]);
}

void bmd_sha512_hex(const uint8_t* data, size_t len, char out_hex[129]) {
    uint8_t hash[64];
    bmd_sha512(data, len, hash);
    bmd_bin_to_hex(hash, 64, out_hex);
    bmd_secure_memzero(hash, sizeof(hash));
}

/* Streaming SHA-512 context for Ed25519 signing (which needs two passes) */
typedef struct {
    uint64_t state[8];
    uint64_t count;         /* total bytes fed so far */
    uint8_t  buf[128];
    size_t   buf_len;
} sha512_ctx_t;

static void sha512_init(sha512_ctx_t* ctx) {
    for (int i = 0; i < 8; i++) ctx->state[i] = sha512_iv[i];
    ctx->count   = 0;
    ctx->buf_len = 0;
}

static void sha512_update(sha512_ctx_t* ctx, const uint8_t* data, size_t len) {
    ctx->count += len;

    if (ctx->buf_len > 0) {
        size_t fill = 128 - ctx->buf_len;
        if (fill > len) fill = len;
        memcpy(ctx->buf + ctx->buf_len, data, fill);
        ctx->buf_len += fill;
        data         += fill;
        len          -= fill;
        if (ctx->buf_len == 128) {
            sha512_blocks(ctx->state, ctx->buf, 128);
            ctx->buf_len = 0;
        }
    }

    if (len >= 128) {
        size_t full = len & ~(size_t)127;
        sha512_blocks(ctx->state, data, full);
        data += full;
        len  -= full;
    }

    if (len > 0) {
        memcpy(ctx->buf, data, len);
        ctx->buf_len = len;
    }
}

static void sha512_final(sha512_ctx_t* ctx, uint8_t hash[64]) {
    uint8_t pad[256];
    size_t  remainder = ctx->buf_len;
    uint64_t bit_len  = ctx->count << 3;

    memcpy(pad, ctx->buf, remainder);
    pad[remainder] = 0x80;

    size_t pad_len;
    if (remainder < 112) {
        memset(pad + remainder + 1, 0, 111 - remainder);
        memset(pad + 112, 0, 8);
        store64be(pad + 120, bit_len);
        pad_len = 128;
    } else {
        memset(pad + remainder + 1, 0, 127 - remainder);
        memset(pad + 128, 0, 112);
        memset(pad + 240, 0, 8);
        store64be(pad + 248, bit_len);
        pad_len = 256;
    }
    sha512_blocks(ctx->state, pad, pad_len);

    for (int i = 0; i < 8; i++) store64be(hash + 8 * i, ctx->state[i]);
    bmd_secure_memzero(ctx, sizeof(sha512_ctx_t));
}

/* --- TweetNaCl curve25519 field arithmetic for Ed25519 --- */

static void set25519(gf r, const gf a) {
    for (int i = 0; i < 16; ++i) r[i] = a[i];
}

static void car25519(gf o) {
    for (int i = 0; i < 16; ++i) {
        o[i] += (1LL << 16);
        int64_t c = o[i] >> 16;
        o[(i + 1) * (i < 15)] += c - 1 + 37 * (c - 1) * (i == 15);
        o[i] -= c << 16;
    }
}

static void sel25519(gf p, gf q, int b) {
    int64_t c = ~(b - 1);
    for (int i = 0; i < 16; ++i) {
        int64_t t = c & (p[i] ^ q[i]);
        p[i] ^= t;
        q[i] ^= t;
    }
}

static void pack25519(uint8_t* o, const gf n) {
    gf m, t;
    set25519(t, n);
    car25519(t); car25519(t); car25519(t);
    for (int j = 0; j < 2; ++j) {
        m[0] = t[0] - 0xffed;
        for (int i = 1; i < 15; ++i) {
            m[i] = t[i] - 0xffff - ((m[i - 1] >> 16) & 1);
            m[i - 1] &= 0xffff;
        }
        m[15] = t[15] - 0x7fff - ((m[14] >> 16) & 1);
        m[14] &= 0xffff;
        int b = (int)((m[15] >> 16) & 1);
        m[15] &= 0xffff;
        sel25519(t, m, 1 - b);
    }
    for (int i = 0; i < 16; ++i) {
        o[2 * i] = (uint8_t)(t[i] & 0xFF);
        o[2 * i + 1] = (uint8_t)(t[i] >> 8);
    }
}

static int par25519(const gf a) {
    uint8_t d[32];
    pack25519(d, a);
    return d[0] & 1;
}

static void unpack25519(gf o, const uint8_t* n) {
    for (int i = 0; i < 16; ++i) {
        o[i] = (int64_t)n[2 * i] + ((int64_t)n[2 * i + 1] << 8);
    }
    o[15] &= 0x7fff;
}

static void A(gf o, const gf a, const gf b) {
    for (int i = 0; i < 16; ++i) o[i] = a[i] + b[i];
}

static void Z(gf o, const gf a, const gf b) {
    for (int i = 0; i < 16; ++i) o[i] = a[i] - b[i];
}

static void M(gf o, const gf a, const gf b) {
    int64_t t[31] = {0};
    for (int i = 0; i < 16; ++i) {
        for (int j = 0; j < 16; ++j) {
            t[i + j] += a[i] * b[j];
        }
    }
    for (int i = 0; i < 15; ++i) t[i] += 38 * t[i + 16];
    for (int i = 0; i < 16; ++i) o[i] = t[i];
    car25519(o);
    car25519(o);
}

static void S(gf o, const gf a) {
    M(o, a, a);
}

static void inv25519(gf o, const gf i) {
    gf c;
    set25519(c, i);
    for (int a = 253; a >= 0; --a) {
        S(c, c);
        if (a != 2 && a != 4) M(c, c, i);
    }
    set25519(o, c);
}

static void pow2523(gf o, const gf i) {
    gf c;
    set25519(c, i);
    for (int a = 250; a >= 0; --a) {
        S(c, c);
        if (a != 1) M(c, c, i);
    }
    set25519(o, c);
}

static int vn(const uint8_t* x, const uint8_t* y, int n) {
    uint32_t d = 0;
    for (int i = 0; i < n; ++i) d |= (x[i] ^ y[i]);
    return (int)((1 & ((d - 1) >> 8)) - 1);
}

/* Group arithmetic on Ed25519 */
static void add(gf p[4], gf q[4]) {
    gf a, b, c, d, t, e, f, g, h;
    Z(a, p[1], p[0]);
    Z(t, q[1], q[0]);
    M(a, a, t);
    A(b, p[1], p[0]);
    A(t, q[1], q[0]);
    M(b, b, t);
    M(c, p[3], q[3]);
    M(c, c, _D2);
    M(d, p[2], q[2]);
    A(d, d, d);
    Z(e, b, a);
    Z(f, d, c);
    A(g, d, c);
    A(h, b, a);
    M(p[0], e, f);
    M(p[1], h, g);
    M(p[2], g, f);
    M(p[3], e, h);
}

static void cswap(gf p[4], gf q[4], int b) {
    for (int i = 0; i < 4; ++i) sel25519(p[i], q[i], b);
}

static void pack(uint8_t* r, gf p[4]) {
    gf tx, ty, zi;
    inv25519(zi, p[2]);
    M(tx, p[0], zi);
    M(ty, p[1], zi);
    pack25519(r, ty);
    r[31] ^= (uint8_t)(par25519(tx) << 7);
}

static void scalarmult(gf p[4], gf q[4], const uint8_t* s) {
    set25519(p[0], _0);
    set25519(p[1], _1);
    set25519(p[2], _1);
    set25519(p[3], _0);
    for (int i = 255; i >= 0; --i) {
        int b = (s[i / 8] >> (i & 7)) & 1;
        cswap(p, q, b);
        add(q, p);
        add(p, p);
        cswap(p, q, b);
    }
}

static void scalarbase(gf p[4], const uint8_t* s) {
    gf q[4];
    set25519(q[0], _X);
    set25519(q[1], _Y);
    set25519(q[2], _1);
    M(q[3], _X, _Y);
    scalarmult(p, q, s);
}

static const int64_t L[32] = {
    0xed, 0xd3, 0xf5, 0x5c, 0x1a, 0x63, 0x12, 0x58,
    0xd6, 0x9c, 0xf7, 0xa2, 0xde, 0xf9, 0xde, 0x14,
    0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0x10
};

static void modL(uint8_t* r, int64_t x[64]) {
    int64_t carry, i, j;
    for (i = 63; i >= 32; --i) {
        carry = 0;
        for (j = i - 32; j < i - 12; ++j) {
            x[j] += carry - 16 * x[i] * L[j - (i - 32)];
            carry = (x[j] + 128) >> 8;
            x[j] -= carry << 8;
        }
        x[j] += carry;
        x[i] = 0;
    }
    carry = 0;
    for (j = 0; j < 32; ++j) {
        x[j] += carry - (x[31] >> 4) * L[j];
        carry = x[j] >> 8;
        x[j] &= 255;
    }
    for (j = 0; j < 32; ++j) {
        x[j] -= carry * L[j];
    }
    /* Critical carry propagation before packing — matches TweetNaCl exactly */
    for (i = 0; i < 32; ++i) {
        x[i + 1] += x[i] >> 8;
        r[i] = (uint8_t)(x[i] & 255);
    }
}

static void reduce(uint8_t* r) {
    int64_t x[64];
    for (int i = 0; i < 64; ++i) x[i] = (uint64_t)r[i];
    for (int i = 0; i < 64; ++i) r[i] = 0;
    modL(r, x);
}

/* Ed25519 Public API */

void bmd_ed25519_keypair(uint8_t public_key[32], uint8_t secret_key[64], const uint8_t seed[32]) {
    uint8_t d[64];
    gf p[4];

    bmd_sha512(seed, 32, d);
    d[0] &= 248;
    d[31] &= 127;
    d[31] |= 64;

    scalarbase(p, d);
    pack(public_key, p);

    memcpy(secret_key, seed, 32);
    memcpy(secret_key + 32, public_key, 32);

    bmd_secure_memzero(d, sizeof(d));
}

void bmd_ed25519_sign(uint8_t signature[64], const uint8_t* message, size_t message_len,
                      const uint8_t public_key[32], const uint8_t secret_key[64]) {
    uint8_t d[64], r[64], h[64];
    gf p[4];
    sha512_ctx_t ctx;

    bmd_sha512(secret_key, 32, d);
    d[0] &= 248;
    d[31] &= 127;
    d[31] |= 64;

    sha512_init(&ctx);
    sha512_update(&ctx, d + 32, 32);
    sha512_update(&ctx, message, message_len);
    sha512_final(&ctx, r);

    reduce(r);
    scalarbase(p, r);
    pack(signature, p);

    sha512_init(&ctx);
    sha512_update(&ctx, signature, 32);
    sha512_update(&ctx, public_key, 32);
    sha512_update(&ctx, message, message_len);
    sha512_final(&ctx, h);

    reduce(h);

    int64_t x[64] = {0};
    for (int i = 0; i < 32; ++i) x[i] = r[i];
    for (int i = 0; i < 32; ++i) {
        for (int j = 0; j < 32; ++j) {
            x[i + j] += (int64_t)h[i] * (int64_t)d[j];
        }
    }
    modL(signature + 32, x);

    bmd_secure_memzero(d, sizeof(d));
    bmd_secure_memzero(r, sizeof(r));
    bmd_secure_memzero(h, sizeof(h));
}

static int neq25519(const gf a, const gf b) {
    uint8_t c[32], d[32];
    pack25519(c, a);
    pack25519(d, b);
    /* Returns 0 if equal, non-zero if different (like TweetNaCl) */
    return bmd_constant_time_memcmp(c, d, 32);
}

/*
 * unpackneg: TweetNaCl exact port.
 * Recovers r[0] (x-coordinate) from r[1] (y-coordinate, from p[]).
 * Returns 0 on success, -1 if p is not a valid Ed25519 point.
 *
 * Key difference from previous version: uses sel25519() on the first check,
 * NOT an early return. Only the final check triggers the early return.
 */
static int unpackneg(gf r[4], const uint8_t p[32]) {
    gf t, chk, num, den, den2, den4, den6;

    set25519(r[2], _1);
    unpack25519(r[1], p);

    S(num, r[1]);
    M(den, num, _D);
    Z(num, num, r[2]);
    A(den, r[2], den);

    S(den2, den);
    S(den4, den2);
    M(den6, den4, den2);
    M(t, den6, num);
    M(t, t, den);

    pow2523(t, t);
    M(t, t, num);
    M(t, t, den);
    M(t, t, den);
    M(r[0], t, den);

    S(chk, r[0]);
    M(chk, chk, den);
    if (neq25519(chk, num) != 0) {
        M(r[0], r[0], _I);
    }
    S(chk, r[0]);
    M(chk, chk, den);
    if (neq25519(chk, num) != 0) return -1;

    if (par25519(r[0]) == (p[31] >> 7)) {
        Z(r[0], _0, r[0]);
    }
    M(r[3], r[0], r[1]);
    return 0;
}

bool bmd_ed25519_verify(const uint8_t signature[64], const uint8_t* message, size_t message_len,
                        const uint8_t public_key[32]) {
    uint8_t h[64], check[32];
    gf p[4], q[4];
    sha512_ctx_t ctx;

    if (unpackneg(q, public_key) != 0) return false;

    sha512_init(&ctx);
    sha512_update(&ctx, signature, 32);
    sha512_update(&ctx, public_key, 32);
    sha512_update(&ctx, message, message_len);
    sha512_final(&ctx, h);

    reduce(h);
    scalarmult(p, q, h);
    scalarbase(q, signature + 32);
    add(p, q);
    pack(check, p);

    return (bmd_constant_time_memcmp(check, signature, 32) == 0);
}
