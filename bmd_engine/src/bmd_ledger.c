/**
 * @file bmd_ledger.c
 * @brief Multi-Block Ledger Validation, Merkle Tree & Audit Engine
 */

#include "bmd_ledger.h"
#include "bmd_crypto.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

bool bmd_is_genesis_previous_hash(const char* prev_hash) {
    if (!prev_hash) return false;
    const char* p = prev_hash;
    if (p[0] == '0' && (p[1] == 'x' || p[1] == 'X')) p += 2;

    while (*p != '\0') {
        if (*p != '0') return false;
        p++;
    }
    return true;
}

bmd_status_t bmd_ledger_validate_link(const bmd_document_t* parent, const bmd_document_t* child) {
    if (!parent || !child) return BMD_ERR_NULL_PARAM;

    /* Verify parent document integrity */
    bmd_status_t st = bmd_verify_document((bmd_document_t*)parent);
    if (st != BMD_OK) return st;

    /* Verify child document integrity */
    st = bmd_verify_document((bmd_document_t*)child);
    if (st != BMD_OK) return st;

    /* Child previous_hash must match parent current_hash */
    const char* child_prev = child->header.previous_hash;
    if (child_prev[0] == '0' && (child_prev[1] == 'x' || child_prev[1] == 'X')) child_prev += 2;

    const char* parent_curr = parent->header.current_hash;
    if (parent_curr[0] == '0' && (parent_curr[1] == 'x' || parent_curr[1] == 'X')) parent_curr += 2;

    if (_stricmp(child_prev, parent_curr) != 0) {
        return BMD_ERR_CHAIN_BROKEN;
    }

    /* Timestamp order check */
    if (child->header.timestamp < parent->header.timestamp) {
        return BMD_ERR_CHAIN_BROKEN;
    }

    return BMD_OK;
}

bmd_status_t bmd_ledger_compute_merkle_root(const char** hashes, size_t count, char out_root[BMD_HASH_HEX_LEN + 1]) {
    if (!hashes || count == 0 || !out_root) return BMD_ERR_NULL_PARAM;

    if (count == 1) {
        strncpy(out_root, hashes[0], BMD_HASH_HEX_LEN);
        out_root[BMD_HASH_HEX_LEN] = '\0';
        return BMD_OK;
    }

    /* Allocate working buffer of 64-byte binary SHA-512 hashes */
    uint8_t (*layer)[64] = (uint8_t(*)[64])malloc(count * 64);
    if (!layer) return BMD_ERR_OUT_OF_MEMORY;

    for (size_t i = 0; i < count; ++i) {
        if (!bmd_hex_to_bin(hashes[i], layer[i], 64)) {
            free(layer);
            return BMD_ERR_HASH_MISMATCH;
        }
    }

    size_t current_count = count;
    while (current_count > 1) {
        size_t next_count = (current_count + 1) / 2;
        for (size_t i = 0; i < current_count; i += 2) {
            size_t left = i;
            size_t right = (i + 1 < current_count) ? i + 1 : i;

            uint8_t combined[128];
            memcpy(combined, layer[left], 64);
            memcpy(combined + 64, layer[right], 64);

            bmd_sha512(combined, 128, layer[i / 2]);
        }
        current_count = next_count;
    }

    bmd_bin_to_hex(layer[0], 64, out_root);
    free(layer);
    return BMD_OK;
}

bmd_status_t bmd_verify_chain(const char* const* filepaths, size_t file_count, bmd_chain_report_t* out_report) {
    if (!filepaths || file_count == 0 || !out_report) return BMD_ERR_NULL_PARAM;
    memset(out_report, 0, sizeof(bmd_chain_report_t));
    out_report->total_blocks = file_count;

    bmd_document_t* prev_doc = NULL;

    for (size_t i = 0; i < file_count; ++i) {
        bmd_document_t* curr_doc = NULL;
        bmd_status_t st = bmd_parse_file(filepaths[i], &curr_doc);
        if (st != BMD_OK) {
            out_report->failure_reason = st;
            out_report->corrupted_blocks = file_count - i;
            snprintf(out_report->failing_block_id, BMD_MAX_BLOCK_ID_LEN, "File: %s", filepaths[i]);
            snprintf(out_report->audit_summary, sizeof(out_report->audit_summary),
                     "Fallo al parsear archivo '%s': %s", filepaths[i], bmd_status_string(st));
            if (prev_doc) bmd_document_free(prev_doc);
            return st;
        }

        /* Verify individual document cryptographic integrity */
        st = bmd_verify_document(curr_doc);
        if (st != BMD_OK) {
            out_report->failure_reason = st;
            out_report->corrupted_blocks = file_count - i;
            strncpy(out_report->failing_block_id, curr_doc->header.block_id, BMD_MAX_BLOCK_ID_LEN);
            snprintf(out_report->audit_summary, sizeof(out_report->audit_summary),
                     "Bloque '%s' corrompido o manipulado: %s",
                     curr_doc->header.block_id, bmd_status_string(st));
            bmd_document_free(curr_doc);
            if (prev_doc) bmd_document_free(prev_doc);
            return st;
        }

        /* Link check */
        if (i == 0) {
            /* Genesis block check */
            if (!bmd_is_genesis_previous_hash(curr_doc->header.previous_hash)) {
                out_report->failure_reason = BMD_ERR_CHAIN_BROKEN;
                out_report->corrupted_blocks = file_count;
                strncpy(out_report->failing_block_id, curr_doc->header.block_id, BMD_MAX_BLOCK_ID_LEN);
                snprintf(out_report->audit_summary, sizeof(out_report->audit_summary),
                         "El bloque inicial '%s' no tiene un previous_hash de Génesis válido.",
                         curr_doc->header.block_id);
                bmd_document_free(curr_doc);
                return BMD_ERR_CHAIN_BROKEN;
            }
        } else {
            st = bmd_ledger_validate_link(prev_doc, curr_doc);
            if (st != BMD_OK) {
                out_report->failure_reason = st;
                out_report->corrupted_blocks = file_count - i;
                strncpy(out_report->failing_block_id, curr_doc->header.block_id, BMD_MAX_BLOCK_ID_LEN);
                snprintf(out_report->audit_summary, sizeof(out_report->audit_summary),
                         "Ruptura de cadena entre '%s' y '%s': %s",
                         prev_doc->header.block_id, curr_doc->header.block_id, bmd_status_string(st));
                bmd_document_free(curr_doc);
                bmd_document_free(prev_doc);
                return st;
            }
        }

        out_report->valid_blocks++;
        strncpy(out_report->last_valid_hash, curr_doc->header.current_hash, BMD_HASH_HEX_LEN);

        if (prev_doc) bmd_document_free(prev_doc);
        prev_doc = curr_doc;
    }

    if (prev_doc) bmd_document_free(prev_doc);

    snprintf(out_report->audit_summary, sizeof(out_report->audit_summary),
             "AUDITORÍA EXITOSA: %zu bloques verificados con inmutabilidad matemática total.",
             out_report->valid_blocks);
    return BMD_OK;
}
