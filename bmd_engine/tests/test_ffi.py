import sys
import os
sys.path.insert(0, os.path.abspath("."))

from bmd_engine.python.bmd_ffi import BMDWrapper, generate_keypair, BMDRole, BMDMode

# Test keygen
pk, sk = generate_keypair()
print("[+] Python FFI Keypair generated! PK:", pk.hex())

sample = (
    "---\n"
    "block_id: \"0x001_CORP\"\n"
    "previous_hash: \"0000000000000000000000000000000000000000000000000000000000000000\"\n"
    "current_hash: \"placeholder\"\n"
    "mode: \"draft\"\n"
    "signer_role: \"emisor\"\n"
    "timestamp: 1772210000\n"
    "public_key: \"\"\n"
    "signature_layer_2: \"\"\n"
    "payload_encrypted: false\n"
    "---\n\n"
    "# Strategic IP Transfer\n"
    "Autonomous Agent governance execution confirmed.\n"
)

doc = BMDWrapper.from_string(sample)
print("[+] Parsed block:", doc.block_id, "mode:", doc.mode.name)

# Sign
seed = b"\x55" * 32
doc.sign(seed, BMDRole.EMISOR)
print("[+] Signed! Hash:", doc.current_hash)
print("[+] Signature:", doc.signature_layer_2[:32], "...")

# Verify
valid, msg = doc.verify()
print("[+] Verification result:", valid, msg)
assert valid, "Verification failed in Python!"

# Transition to transfer
doc.transition_to_transfer(seed)
print("[+] Transitioned to transfer mode! Mode:", doc.mode.name)
valid, msg = doc.verify()
print("[+] Verification in transfer mode:", valid, msg)
assert valid, "Transfer verification failed in Python!"

print("[SUCCESS] PYTHON FFI BRIDGE 100% OPERATIONAL!")
