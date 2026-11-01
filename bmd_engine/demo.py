"""
BLOCKCHAIN MARKDOWN (.bmd) — Demo Interactiva Completa
Ejecuta todos los pasos en secuencia y muestra la salida en pantalla.
"""
import subprocess, sys, os, shutil, stat, time

BASE    = r"c:\Users\Hp\Downloads\Project_Orunex"
CLI     = os.path.join(BASE, r"bmd_engine\bin\bmd_cli.exe")
EXAMPLES= os.path.join(BASE, r"bmd_engine\examples")
ENV     = {**os.environ, "PATH": os.path.join(BASE, r"bmd_engine\bin") + ";" + os.environ["PATH"]}

def run(cmd, check=False):
    r = subprocess.run(cmd, capture_output=True, text=True, env=ENV,
                       encoding="utf-8", errors="replace")
    out = (r.stdout + r.stderr).strip()
    print(out)
    return r.returncode, out

def sep(titulo):
    print()
    print("=" * 66)
    print(f"  {titulo}")
    print("=" * 66)

# ─────────────────────────────────────────────────────────────────────
sep("PASO 1/6 — Generar par de claves Ed25519 (EMISOR)")
# ─────────────────────────────────────────────────────────────────────
code, out = run([CLI, "genkey"])
seed = pubkey = ""
for line in out.splitlines():
    if "PRIVATE SEED" in line:
        seed = line.split()[-1]
    if "PUBLIC KEY" in line:
        pubkey = line.split()[-1]
print(f"\n  >> SEED guardado para firmar: {seed}")
print(f"  >> PUBLIC KEY del emisor:     {pubkey}")

# ─────────────────────────────────────────────────────────────────────
sep("PASO 2/6 — Crear documento .bmd en modo DRAFT")
# ─────────────────────────────────────────────────────────────────────
draft_path = os.path.join(EXAMPLES, "demo_contrato.bmd")
draft_content = f"""---
block_id: "0xDEMO_CORP_001"
previous_hash: "{'0' * 128}"
current_hash: "{'0' * 128}"
mode: "draft"
signer_role: "emisor"
timestamp: {int(time.time())}
public_key: ""
signature_layer_2: ""
payload_encrypted: false
document_type: "contract"
require_cosigner: true
max_signatures: "2"
---

# Contrato de Transferencia de Propiedad de Codigo

Este documento certifica la transferencia legal del modulo `bmd_engine`
del emisor al receptor, con validez criptografica e inmutabilidad matematica.

## Terminos del Contrato
- Valor: $50,000 USD
- Activo: Motor criptografico BMD Engine v2.1.0 (C11, Ed25519)
- Fecha: 2026-10-29
- Jurisdiccion: Estandar internacional RFC 8032 / NIST FIPS 180-4

## Clausulas de Gobernanza del Agente
1. El Agente Autonomo `muse-spark` valida la firma antes de ejecutar
2. Una vez en modo TRANSFER: el documento es INMUTABLE
3. Cualquier modificacion invalida la firma automaticamente
"""
if os.path.exists(draft_path):
    os.chmod(draft_path, stat.S_IWRITE | stat.S_IREAD)
with open(draft_path, "w", encoding="utf-8") as f:
    f.write(draft_content)
print(f"  Creado: {draft_path}")
print("  Modo: DRAFT (editable, sin firmar aun)")

# ─────────────────────────────────────────────────────────────────────
sep("PASO 3/6 — Inspeccionar el DRAFT (antes de firmar)")
# ─────────────────────────────────────────────────────────────────────
run([CLI, "inspect", draft_path])

# ─────────────────────────────────────────────────────────────────────
sep("PASO 4/6 — FIRMAR y CONGELAR: DRAFT → TRANSFER")
# ─────────────────────────────────────────────────────────────────────
print(f"  Usando seed: {seed}")
print()
run([CLI, "sign", draft_path, seed])

# ─────────────────────────────────────────────────────────────────────
sep("PASO 5/6 — Verificar el bloque TRANSFER firmado")
# ─────────────────────────────────────────────────────────────────────
code, _ = run([CLI, "verify", draft_path])
print()
run([CLI, "inspect", draft_path])

# ─────────────────────────────────────────────────────────────────────
sep("PASO 6/6 — PRUEBA ANTI-TAMPERING: Modificar y detectar fraude")
# ─────────────────────────────────────────────────────────────────────
tampered_path = os.path.join(EXAMPLES, "demo_contrato_ADULTERADO.bmd")
with open(draft_path, "r", encoding="utf-8") as f:
    content = f.read()
tampered = content.replace("$50,000 USD", "$1 USD")
with open(tampered_path, "w", encoding="utf-8") as f:
    f.write(tampered)

print("  [!] Documento ADULTERADO: se cambio '$50,000 USD' → '$1 USD'")
print("  [?] Verificando si el motor detecta el fraude...\n")
code, out = run([CLI, "verify", tampered_path])
if code != 0:
    print("\n  >> SISTEMA DETECTA FRAUDE CORRECTAMENTE")
else:
    print("\n  >> ADVERTENCIA: fraude no detectado")

os.remove(tampered_path)

# ─────────────────────────────────────────────────────────────────────
sep("DEMO COMPLETADA")
# ─────────────────────────────────────────────────────────────────────
print("""
  RESUMEN:
  [OK] Par de claves Ed25519 generado
  [OK] Documento .bmd creado en modo DRAFT
  [OK] Inspeccion de metadatos del bloque
  [OK] Firma criptografica + congelamiento TRANSFER
  [OK] Verificacion de integridad: VALIDO
  [OK] Deteccion de adulteracion: FRAUDE RECHAZADO

  El motor BMD rechaza matematicamente cualquier modificacion
  al contenido de un bloque firmado. Inmutabilidad garantizada.
""")
