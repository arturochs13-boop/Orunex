"""
Cross-validation: firma generada por nuestro motor C vs PyNaCl.
"""
import sys, os, ctypes

# ---- cargar DLL ----
dll_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'bin', 'bmd_engine.dll'))
lib = ctypes.CDLL(dll_path)

Buf32 = ctypes.c_uint8 * 32
Buf64 = ctypes.c_uint8 * 64
P8    = ctypes.POINTER(ctypes.c_uint8)

lib.bmd_ed25519_keypair.restype  = None
lib.bmd_ed25519_keypair.argtypes = [P8, P8, P8]

# signature[64], message, message_len, public_key[32], secret_key[64]
lib.bmd_ed25519_sign.restype  = None
lib.bmd_ed25519_sign.argtypes = [P8, ctypes.c_char_p, ctypes.c_size_t, P8, P8]

SEED = bytes([0x42] * 32)
MSG  = b"Blockchain Markdown 2026 - BMD Engine v1"

seed_buf = Buf32(*SEED)
pub_buf  = Buf32()
sec_buf  = Buf64()
lib.bmd_ed25519_keypair(pub_buf, sec_buf, seed_buf)

sig_buf  = Buf64()
# Correct call: pass pub_buf and sec_buf
lib.bmd_ed25519_sign(sig_buf, MSG, len(MSG), pub_buf, sec_buf)

our_pub = bytes(pub_buf)
our_sig = bytes(sig_buf)

print("[BMD-C] Public Key : " + our_pub.hex())
print("[BMD-C] Signature  : " + our_sig.hex())
print("[BMD-C] Sig R(0-31): " + our_sig[:32].hex())
print("[BMD-C] Sig S(32-63): " + our_sig[32:].hex())

try:
    import nacl.signing
    sk     = nacl.signing.SigningKey(SEED)
    vk     = sk.verify_key
    signed = sk.sign(MSG)
    nacl_pub = bytes(vk)
    nacl_sig = signed.signature

    print("\n[PyNaCl] Public Key: " + nacl_pub.hex())
    print("[PyNaCl] Signature : " + nacl_sig.hex())
    print("[PyNaCl] Sig R(0-31): " + nacl_sig[:32].hex())
    print("[PyNaCl] Sig S(32-63): " + nacl_sig[32:].hex())

    pk_match  = (our_pub == nacl_pub)
    sig_match = (our_sig == nacl_sig)
    r_match   = (our_sig[:32] == nacl_sig[:32])
    s_match   = (our_sig[32:] == nacl_sig[32:])

    print("\nPublic Key match     : " + ("OK IDENTICAL" if pk_match  else "MISMATCH"))
    print("R point (bytes 0-31) : " + ("OK IDENTICAL" if r_match   else "MISMATCH"))
    print("S scalar (bytes 32-63): " + ("OK IDENTICAL" if s_match  else "MISMATCH"))
    print("Full Signature match : " + ("OK IDENTICAL" if sig_match else "MISMATCH"))

    if not sig_match:
        diff = [(i, our_sig[i], nacl_sig[i]) for i in range(64) if our_sig[i] != nacl_sig[i]]
        print(f"\n{len(diff)} byte differences:")
        for i, a, b in diff[:16]:
            print(f"  [{i:2d}] ours=0x{a:02x}  nacl=0x{b:02x}")
        if len(diff) > 16:
            print(f"  ... and {len(diff)-16} more")

    # cross-verify
    try:
        vk.verify(MSG, our_sig)
        print("\nPyNaCl verifies BMD-C sig: VALID")
    except Exception as e:
        print(f"\nPyNaCl verifies BMD-C sig: INVALID -- {e}")

    if pk_match and sig_match:
        print("\n[SUCCESS] BMD ENGINE 100% COMPATIBLE CON TWEETNACL/LIBSODIUM")
    elif pk_match and r_match:
        print("\n[PARTIAL] R coincide, S falla -- modL bug en sign()")
    elif pk_match:
        print("\n[PARTIAL] PK correcta, firma entera falla -- problema en sha512 de nonce o sign flow")
    else:
        print("\n[FAIL] PK incorrecta -- bug en keypair")

except ImportError:
    print("[INFO] PyNaCl no disponible")
