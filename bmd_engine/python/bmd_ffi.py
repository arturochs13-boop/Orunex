"""
bmd_ffi.py - High-Level Python FFI Binding for Blockchain Markdown (.bmd) Engine
Autonomous Agent Governance Runtime ('muse-spark')
"""

import ctypes
import os
import sys
from enum import IntEnum
from typing import Optional, List, Tuple

# Locate bmd_engine.dll
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_DLL_PATH = os.path.join(_CURRENT_DIR, "..", "bin", "bmd_engine.dll")

if not os.path.exists(_DLL_PATH):
    raise FileNotFoundError(f"Could not locate bmd_engine.dll at {_DLL_PATH}. Run build.bat first.")

# Load DLL
_LIB = ctypes.CDLL(_DLL_PATH)

# Constants
BMD_MAX_BLOCK_ID_LEN = 128
BMD_HASH_HEX_LEN = 128  # SHA-512 standard hex length
BMD_PUBKEY_HEX_LEN = 128
BMD_SIG_HEX_LEN = 256

class BMDStatus(IntEnum):
    OK = 0
    ERR_NULL_PARAM = -1
    ERR_FILE_NOT_FOUND = -2
    ERR_OUT_OF_MEMORY = -3
    ERR_SYNTAX_FRONTMATTER = -4
    ERR_MISSING_REQUIRED_KEY = -5
    ERR_INVALID_MODE = -6
    ERR_INVALID_ROLE = -7
    ERR_HASH_MISMATCH = -8
    ERR_SIG_INVALID = -9
    ERR_CHAIN_BROKEN = -10
    ERR_ENCRYPTION_FAILED = -11
    ERR_DECRYPTION_FAILED = -12
    ERR_TRANSFER_VIOLATION = -13
    ERR_BUFFER_TOO_SMALL = -14

class BMDMode(IntEnum):
    UNKNOWN = 0
    DRAFT = 1
    TRANSFER = 2

class BMDRole(IntEnum):
    UNKNOWN = 0
    EMISOR = 1
    RECEPTOR = 2

# C Structs
class BMDHeader(ctypes.Structure):
    _fields_ = [
        ("block_id", ctypes.c_char * BMD_MAX_BLOCK_ID_LEN),
        ("previous_hash", ctypes.c_char * (BMD_HASH_HEX_LEN + 1)),
        ("current_hash", ctypes.c_char * (BMD_HASH_HEX_LEN + 1)),
        ("mode", ctypes.c_int),
        ("signer_role", ctypes.c_int),
        ("timestamp", ctypes.c_int64),
        ("public_key", ctypes.c_char * (BMD_PUBKEY_HEX_LEN + 1)),
        ("signature_layer_2", ctypes.c_char * (BMD_SIG_HEX_LEN + 1)),
        ("receiver_public_key", ctypes.c_char * (BMD_PUBKEY_HEX_LEN + 1)),
        ("receiver_signature", ctypes.c_char * (BMD_SIG_HEX_LEN + 1)),
        ("payload_encrypted", ctypes.c_bool),

        # v2.0 Extended Directives
        ("document_type", ctypes.c_char * 64),
        ("jurisdiction", ctypes.c_char * 128),
        ("expiry_timestamp", ctypes.c_int64),
        ("witnesses_required", ctypes.c_int),
        ("require_cosigner", ctypes.c_bool),
        ("co_sign_label", ctypes.c_char * 128),

        # v2.1 Signature governance
        ("max_signatures", ctypes.c_int),

        # IP Property Bundle
        ("inject_property_path", ctypes.c_char * 512),
        ("property_bundle_hash", ctypes.c_char * (BMD_HASH_HEX_LEN + 1)),
        ("property_bundle_size", ctypes.c_uint64),
        ("property_bundle_destroyed", ctypes.c_bool),
    ]

class BMDDocument(ctypes.Structure):
    _fields_ = [
        ("header", BMDHeader),
        ("payload", ctypes.c_char_p),
        ("payload_len", ctypes.c_size_t),
        ("raw_frontmatter", ctypes.c_char_p),
        ("is_verified", ctypes.c_bool),
        ("computed_hash", ctypes.c_char * (BMD_HASH_HEX_LEN + 1)),
        ("property_bundle_data", ctypes.c_char_p),
        ("property_bundle_data_len", ctypes.c_size_t),
    ]

class BMDChainReport(ctypes.Structure):
    _fields_ = [
        ("total_blocks", ctypes.c_size_t),
        ("valid_blocks", ctypes.c_size_t),
        ("corrupted_blocks", ctypes.c_size_t),
        ("last_valid_hash", ctypes.c_char * (BMD_HASH_HEX_LEN + 1)),
        ("failing_block_id", ctypes.c_char * BMD_MAX_BLOCK_ID_LEN),
        ("failure_reason", ctypes.c_int),
        ("audit_summary", ctypes.c_char * 512),
    ]

# Function signatures
_LIB.bmd_document_create.restype = ctypes.POINTER(BMDDocument)
_LIB.bmd_document_create.argtypes = []

_LIB.bmd_document_free.restype = None
_LIB.bmd_document_free.argtypes = [ctypes.POINTER(BMDDocument)]

_LIB.bmd_parse_file.restype = ctypes.c_int
_LIB.bmd_parse_file.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.POINTER(BMDDocument))]

_LIB.bmd_parse_string.restype = ctypes.c_int
_LIB.bmd_parse_string.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(ctypes.POINTER(BMDDocument))]

_LIB.bmd_save_file.restype = ctypes.c_int
_LIB.bmd_save_file.argtypes = [ctypes.POINTER(BMDDocument), ctypes.c_char_p]

_LIB.bmd_verify_document.restype = ctypes.c_int
_LIB.bmd_verify_document.argtypes = [ctypes.POINTER(BMDDocument)]

_LIB.bmd_sign_document.restype = ctypes.c_int
_LIB.bmd_sign_document.argtypes = [ctypes.POINTER(BMDDocument), ctypes.POINTER(ctypes.c_uint8), ctypes.c_int]

_LIB.bmd_transition_to_transfer.restype = ctypes.c_int
_LIB.bmd_transition_to_transfer.argtypes = [ctypes.POINTER(BMDDocument), ctypes.POINTER(ctypes.c_uint8)]

_LIB.bmd_accept_transfer.restype = ctypes.c_int
_LIB.bmd_accept_transfer.argtypes = [ctypes.POINTER(BMDDocument), ctypes.POINTER(ctypes.c_uint8), ctypes.c_char_p]

_LIB.bmd_cosign_receiver.restype = ctypes.c_int
_LIB.bmd_cosign_receiver.argtypes = [ctypes.POINTER(BMDDocument), ctypes.POINTER(ctypes.c_uint8)]

_LIB.bmd_verify_chain.restype = ctypes.c_int
_LIB.bmd_verify_chain.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.c_size_t, ctypes.POINTER(BMDChainReport)]

_LIB.bmd_status_string.restype = ctypes.c_char_p
_LIB.bmd_status_string.argtypes = [ctypes.c_int]

_LIB.bmd_encrypt_payload.restype = ctypes.c_int
_LIB.bmd_encrypt_payload.argtypes = [ctypes.POINTER(BMDDocument), ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint8)]

_LIB.bmd_decrypt_payload.restype = ctypes.c_int
_LIB.bmd_decrypt_payload.argtypes = [ctypes.POINTER(BMDDocument), ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint8)]

_LIB.bmd_ed25519_keypair.restype = None
_LIB.bmd_ed25519_keypair.argtypes = [
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.POINTER(ctypes.c_uint8)
]


class BMDWrapper:
    """High-Level Object-Oriented wrapper for a .bmd document."""

    def __init__(self, doc_ptr):
        self._doc = doc_ptr

    def __del__(self):
        if self._doc:
            _LIB.bmd_document_free(self._doc)
            self._doc = None

    @classmethod
    def load_file(cls, filepath: str) -> "BMDWrapper":
        doc_ptr = ctypes.POINTER(BMDDocument)()
        ret = _LIB.bmd_parse_file(filepath.encode("utf-8"), ctypes.byref(doc_ptr))
        if ret != 0:
            err_msg = _LIB.bmd_status_string(ret).decode("utf-8")
            raise RuntimeError(f"Failed to load BMD file: {err_msg} (code: {ret})")
        return cls(doc_ptr)

    @classmethod
    def from_string(cls, content: str) -> "BMDWrapper":
        doc_ptr = ctypes.POINTER(BMDDocument)()
        data = content.encode("utf-8")
        ret = _LIB.bmd_parse_string(data, len(data), ctypes.byref(doc_ptr))
        if ret != 0:
            err_msg = _LIB.bmd_status_string(ret).decode("utf-8")
            raise RuntimeError(f"Failed to parse BMD string: {err_msg} (code: {ret})")
        return cls(doc_ptr)

    def save(self, filepath: str):
        ret = _LIB.bmd_save_file(self._doc, filepath.encode("utf-8"))
        if ret != 0:
            err_msg = _LIB.bmd_status_string(ret).decode("utf-8")
            raise RuntimeError(f"Failed to save BMD file: {err_msg} (code: {ret})")

    def verify(self) -> Tuple[bool, str]:
        ret = _LIB.bmd_verify_document(self._doc)
        msg = _LIB.bmd_status_string(ret).decode("utf-8")
        return (ret == 0, msg)

    def sign(self, seed_bytes: bytes, role: BMDRole = BMDRole.EMISOR):
        if len(seed_bytes) != 32:
            raise ValueError("Seed must be exactly 32 bytes")
        c_seed = (ctypes.c_uint8 * 32).from_buffer_copy(seed_bytes)
        ret = _LIB.bmd_sign_document(self._doc, c_seed, int(role))
        if ret != 0:
            err_msg = _LIB.bmd_status_string(ret).decode("utf-8")
            raise RuntimeError(f"Failed to sign document: {err_msg} (code: {ret})")

    def transition_to_transfer(self, seed_bytes: bytes):
        if len(seed_bytes) != 32:
            raise ValueError("Seed must be exactly 32 bytes")
        c_seed = (ctypes.c_uint8 * 32).from_buffer_copy(seed_bytes)
        ret = _LIB.bmd_transition_to_transfer(self._doc, c_seed)
        if ret != 0:
            err_msg = _LIB.bmd_status_string(ret).decode("utf-8")
            raise RuntimeError(f"Failed to transition to transfer: {err_msg} (code: {ret})")

    def seal(self, key_bytes: bytes, nonce_bytes: Optional[bytes] = None):
        """Cifra el cuerpo usando ChaCha20."""
        if len(key_bytes) != 32:
            raise ValueError("Key must be 32 bytes")
        if nonce_bytes is None:
            # Deterministic/secure 12-byte nonce
            ts = self._doc.contents.header.timestamp
            nonce_bytes = bytes([(ts ^ (i * 0x5a)) & 0xff for i in range(12)])
        elif len(nonce_bytes) != 12:
            raise ValueError("Nonce must be 12 bytes")

        c_key = (ctypes.c_uint8 * 32).from_buffer_copy(key_bytes)
        c_nonce = (ctypes.c_uint8 * 12).from_buffer_copy(nonce_bytes)
        ret = _LIB.bmd_encrypt_payload(self._doc, c_key, c_nonce)
        if ret != 0:
            err_msg = _LIB.bmd_status_string(ret).decode("utf-8")
            raise RuntimeError(f"Failed to seal/encrypt payload: {err_msg} (code: {ret})")

    def unseal(self, key_bytes: bytes, nonce_bytes: Optional[bytes] = None):
        """Descifra el cuerpo usando ChaCha20."""
        if len(key_bytes) != 32:
            raise ValueError("Key must be 32 bytes")
        if nonce_bytes is None:
            ts = self._doc.contents.header.timestamp
            nonce_bytes = bytes([(ts ^ (i * 0x5a)) & 0xff for i in range(12)])
        elif len(nonce_bytes) != 12:
            raise ValueError("Nonce must be 12 bytes")

        c_key = (ctypes.c_uint8 * 32).from_buffer_copy(key_bytes)
        c_nonce = (ctypes.c_uint8 * 12).from_buffer_copy(nonce_bytes)
        ret = _LIB.bmd_decrypt_payload(self._doc, c_key, c_nonce)
        if ret != 0:
            err_msg = _LIB.bmd_status_string(ret).decode("utf-8")
            raise RuntimeError(f"Failed to unseal/decrypt payload: {err_msg} (code: {ret})")

    def cosign_receiver(self, seed_bytes: bytes):
        """Receiver co-signs the already compiled and immutable current_hash."""
        if len(seed_bytes) != 32:
            raise ValueError("Seed must be exactly 32 bytes")
        c_seed = (ctypes.c_uint8 * 32).from_buffer_copy(seed_bytes)
        ret = _LIB.bmd_cosign_receiver(self._doc, c_seed)
        if ret != 0:
            err_msg = _LIB.bmd_status_string(ret).decode("utf-8")
            raise RuntimeError(f"Failed to co-sign as receiver: {err_msg} (code: {ret})")

    @property
    def block_id(self) -> str:
        return self._doc.contents.header.block_id.decode("utf-8")

    @property
    def previous_hash(self) -> str:
        return self._doc.contents.header.previous_hash.decode("utf-8")

    @property
    def current_hash(self) -> str:
        return self._doc.contents.header.current_hash.decode("utf-8")

    @property
    def mode(self) -> BMDMode:
        return BMDMode(self._doc.contents.header.mode)

    @property
    def signer_role(self) -> BMDRole:
        return BMDRole(self._doc.contents.header.signer_role)

    @property
    def public_key(self) -> str:
        return self._doc.contents.header.public_key.decode("utf-8")

    @property
    def signature_layer_2(self) -> str:
        return self._doc.contents.header.signature_layer_2.decode("utf-8")

    @property
    def receiver_public_key(self) -> str:
        return self._doc.contents.header.receiver_public_key.decode("utf-8")

    @property
    def receiver_signature(self) -> str:
        return self._doc.contents.header.receiver_signature.decode("utf-8")

    @property
    def payload(self) -> str:
        return self._doc.contents.payload.decode("utf-8") if self._doc.contents.payload else ""

    @property
    def document_type(self) -> str:
        return self._doc.contents.header.document_type.decode("utf-8")

    @property
    def jurisdiction(self) -> str:
        return self._doc.contents.header.jurisdiction.decode("utf-8")

    @property
    def require_cosigner(self) -> bool:
        return bool(self._doc.contents.header.require_cosigner)

    @property
    def co_sign_label(self) -> str:
        return self._doc.contents.header.co_sign_label.decode("utf-8")

    @property
    def max_signatures(self) -> int:
        """Maximum signatures allowed by the v2.1 governance cap (0 = unlimited)."""
        return int(self._doc.contents.header.max_signatures)

    @property
    def property_bundle_hash(self) -> str:
        return self._doc.contents.header.property_bundle_hash.decode("utf-8")

    @property
    def property_bundle_size(self) -> int:
        return int(self._doc.contents.header.property_bundle_size)

    @property
    def property_bundle_destroyed(self) -> bool:
        return bool(self._doc.contents.header.property_bundle_destroyed)

    @property
    def property_bundle_data(self) -> str:
        return self._doc.contents.property_bundle_data.decode("utf-8") if self._doc.contents.property_bundle_data else ""


def generate_keypair(seed_bytes: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """Generates an Ed25519 (public_key_32B, secret_key_64B) pair."""
    if seed_bytes is None:
        seed_bytes = os.urandom(32)
    elif len(seed_bytes) != 32:
        raise ValueError("Seed must be 32 bytes")

    c_seed = (ctypes.c_uint8 * 32).from_buffer_copy(seed_bytes)
    c_pk = (ctypes.c_uint8 * 32)()
    c_sk = (ctypes.c_uint8 * 64)()

    _LIB.bmd_ed25519_keypair(c_pk, c_sk, c_seed)
    return bytes(c_pk), bytes(c_sk)


def audit_chain(filepaths: List[str]) -> Tuple[bool, dict]:
    """Audits an array of .bmd files establishing cryptographic ledger consensus."""
    count = len(filepaths)
    arr_type = ctypes.c_char_p * count
    c_files = arr_type(*(f.encode("utf-8") for f in filepaths))

    report = BMDChainReport()
    ret = _LIB.bmd_verify_chain(c_files, count, ctypes.byref(report))

    summary = {
        "status": ret == 0,
        "total_blocks": report.total_blocks,
        "valid_blocks": report.valid_blocks,
        "corrupted_blocks": report.corrupted_blocks,
        "last_valid_hash": report.last_valid_hash.decode("utf-8"),
        "failing_block_id": report.failing_block_id.decode("utf-8"),
        "summary": report.audit_summary.decode("utf-8"),
    }
    return ret == 0, summary
