/**
 * @file test_engine.c
 * @brief Complete Native C11 Test Suite for BMD Engine
 */

#include "bmd_engine.h"
#include "bmd_crypto.h"
#include "bmd_ledger.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#define ASSERT_TEST(cond, msg) \
    do { \
        if (!(cond)) { \
            fprintf(stderr, "[FAIL] %s:%d: %s\n", __FILE__, __LINE__, msg); \
            exit(1); \
        } \
    } while(0)

static void test_sha256(void) {
    printf("[*] Testing SHA-256...\n");
    const char* input = "Blockchain Markdown 2026";
    char hex[65];
    bmd_sha256_hex((const uint8_t*)input, strlen(input), hex);
    ASSERT_TEST(strlen(hex) == 64, "SHA-256 hex length must be 64");
    printf("    SHA-256('%s') = %s\n", input, hex);
}

static void test_ed25519(void) {
    printf("[*] Testing Ed25519 Key Generation, Signing & Verification...\n");
    uint8_t seed[32] = {0x42};
    uint8_t pk[32];
    uint8_t sk[64];
    bmd_ed25519_keypair(pk, sk, seed);

    const char* msg = "Transfer of IP Ownership Block 0x8F4C2A1";
    uint8_t sig[64];
    bmd_ed25519_sign(sig, (const uint8_t*)msg, strlen(msg), pk, sk);

    bool ok = bmd_ed25519_verify(sig, (const uint8_t*)msg, strlen(msg), pk);
    ASSERT_TEST(ok, "Ed25519 signature verification failed for authentic message");

    /* Tamper test */
    const char* tampered = "Transfer of IP Ownership Block 0x8F4C2A2";
    bool bad = bmd_ed25519_verify(sig, (const uint8_t*)tampered, strlen(tampered), pk);
    ASSERT_TEST(!bad, "Ed25519 signature verification MUST fail for tampered message");
    printf("    Ed25519 validation passed with tamper resistance!\n");
}

static void test_chacha20(void) {
    printf("[*] Testing ChaCha20 Stream Cipher...\n");
    uint8_t key[32] = {1, 2, 3, 4, 5};
    uint8_t nonce[12] = {9, 8, 7, 6};
    const char* plaintext = "Sensitive Corporate Financial Model Data 2026";
    size_t len = strlen(plaintext);

    uint8_t cipher[128];
    uint8_t decrypted[128];

    bmd_chacha20_xor(key, 1, nonce, (const uint8_t*)plaintext, cipher, len);
    ASSERT_TEST(memcmp(plaintext, cipher, len) != 0, "Ciphertext must not equal plaintext");

    bmd_chacha20_xor(key, 1, nonce, cipher, decrypted, len);
    decrypted[len] = '\0';
    ASSERT_TEST(strcmp(plaintext, (char*)decrypted) == 0, "Decrypted text must match plaintext exactly");
    printf("    ChaCha20 roundtrip encryption/decryption verified!\n");
}

static void test_bmd_document_lifecycle(void) {
    printf("[*] Testing BMD Document Parsing, Signing, Tamper-Detection...\n");

    const char* sample_bmd =
        "---\n"
        "block_id: \"0x0001_GENESIS\"\n"
        "previous_hash: \"0000000000000000000000000000000000000000000000000000000000000000\"\n"
        "current_hash: \"placeholder\"\n"
        "mode: \"draft\"\n"
        "signer_role: \"emisor\"\n"
        "timestamp: 1772210000\n"
        "public_key: \"\"\n"
        "signature_layer_2: \"\"\n"
        "payload_encrypted: false\n"
        "---\n\n"
        "# Genesis Contract\n"
        "Autonomous Agent Governance Framework Initialized.\n";

    bmd_document_t* doc = NULL;
    bmd_status_t st = bmd_parse_string(sample_bmd, strlen(sample_bmd), &doc);
    ASSERT_TEST(st == BMD_OK, "bmd_parse_string failed");
    ASSERT_TEST(strcmp(doc->header.block_id, "0x0001_GENESIS") == 0, "block_id mismatch");

    /* Sign document with seed */
    uint8_t seed[32] = {0xAA};
    st = bmd_sign_document(doc, seed, BMD_ROLE_EMISOR);
    ASSERT_TEST(st == BMD_OK, "bmd_sign_document failed");

    /* Verify authentic doc */
    st = bmd_verify_document(doc);
    ASSERT_TEST(st == BMD_OK, "bmd_verify_document should succeed on freshly signed doc");

    /* Tamper payload */
    char* old_payload = doc->payload;
    doc->payload = _strdup("# Tampered Contract!\nMalicious modification.\n");
    st = bmd_verify_document(doc);
    ASSERT_TEST(st == BMD_ERR_HASH_MISMATCH, "Tampered payload must cause BMD_ERR_HASH_MISMATCH");

    /* Restore and clean */
    free(doc->payload);
    doc->payload = old_payload;
    bmd_document_free(doc);
    printf("    BMD document lifecycle and tamper detection passed!\n");
}

static void test_sha512(void) {
    printf("[*] Testing SHA-512 (Ledger Cryptographic Standard)...\n");
    const char* input = "Blockchain Markdown 2026";
    char hex[129];
    bmd_sha512_hex((const uint8_t*)input, strlen(input), hex);
    ASSERT_TEST(strlen(hex) == 128, "SHA-512 hex length must be 128");
    printf("    SHA-512('%s') = %.32s...\n", input, hex);
}

int main(void) {
    printf("============================================================\n");
    printf("  RUNNING BMD ENGINE C11 UNIT TESTS (SHA-512 & ED25519)\n");
    printf("============================================================\n");
    test_sha256();
    test_sha512();
    test_ed25519();
    test_chacha20();
    test_bmd_document_lifecycle();
    printf("\n[SUCCESS] ALL NATIVE C11 TESTS PASSED WITH 100%% INTEGRITY!\n");
    return 0;
}
