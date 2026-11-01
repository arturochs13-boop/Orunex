/**
 * @file bmd_ledger.h
 * @brief Distributed / Local Ledger & Inmutability Auditor for .bmd Blocks
 */

#ifndef BMD_LEDGER_H
#define BMD_LEDGER_H

#include "bmd_engine.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Validates if a hash string qualifies as a Genesis block ancestor
 */
BMD_API bool bmd_is_genesis_previous_hash(const char* prev_hash);

/**
 * @brief Validates link between parent block and child block in ledger
 */
BMD_API bmd_status_t bmd_ledger_validate_link(const bmd_document_t* parent, const bmd_document_t* child);

/**
 * @brief Computes a Merkle root over an array of block hashes
 */
BMD_API bmd_status_t bmd_ledger_compute_merkle_root(const char** hashes, size_t count, char out_root[BMD_HASH_HEX_LEN + 1]);

#ifdef __cplusplus
}
#endif

#endif /* BMD_LEDGER_H */
