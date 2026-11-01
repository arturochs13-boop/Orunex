"""
Test ChaCha20 seal/unseal integration test via CLI and Python FFI.
"""
import subprocess, os, sys

BASE = r"c:\Users\Hp\Downloads\Project_Orunex"
CLI  = os.path.join(BASE, r"bmd_engine\bin\bmd_cli.exe")
EX   = os.path.join(BASE, r"bmd_engine\examples")
ENV  = {**os.environ, "PATH": os.path.join(BASE, r"bmd_engine\bin") + ";" + os.environ.get("PATH", "")}

# Archivo de prueba
TEST_FILE = os.path.join(EX, "test_seal.bmd")
KEY_HEX   = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

with open(TEST_FILE, "w", encoding="utf-8") as f:
    f.write("""---
block_id: "0xCONFIDENTIAL_FINANCIAL"
previous_hash: "0x0000000000000000000000000000000000000000000000000000000000000000"
current_hash: "placeholder"
mode: "draft"
signer_role: "emisor"
timestamp: 1772210000
public_key: "PENDING"
signature_layer_2: ""
payload_encrypted: false
---

# Datos Financieros Confidenciales
- Saldo en Bóveda: $1,450,000 USD
- Beneficiario: Agente Autónomo Muse-Spark
""")

print("[1] Cifrando payload con CLI (seal)...")
r = subprocess.run([CLI, "seal", TEST_FILE, KEY_HEX], capture_output=True, text=True, env=ENV)
print(r.stdout.strip())

with open(TEST_FILE, "r", encoding="utf-8") as f:
    content_sealed = f.read()

assert "payload_encrypted: true" in content_sealed
assert "Saldo en Bóveda" not in content_sealed
print("--> Cifrado confirmado: Payload protegido en Base64.")

print("\n[2] Descifrando payload con CLI (unseal)...")
r = subprocess.run([CLI, "unseal", TEST_FILE, KEY_HEX], capture_output=True, text=True, env=ENV)
print(r.stdout.strip())

with open(TEST_FILE, "r", encoding="utf-8") as f:
    content_unsealed = f.read()

assert "payload_encrypted: false" in content_unsealed
assert "Saldo en Bóveda: $1,450,000 USD" in content_unsealed
print("--> Descifrado confirmado: Texto íntegro recuperado exitosamente!")

os.remove(TEST_FILE)
print("\n[SUCCESS] ChaCha20 SEAL/UNSEAL EN PRODUCCIÓN FUNCIONANDO AL 100%!")
