# BMD Engine — Motor Criptográfico para Blockchain Markdown

> **Lenguaje:** Blockchain Markdown (`.bmd`) · **Versión:** 2.1.0  
> **Estándar:** Ed25519 (RFC 8032) · SHA-512 (NIST FIPS 180-4) · ChaCha20 (RFC 8439)  
> **Compatible 100%** con TweetNaCl / libsodium — verificable externamente

---

## 🎯 Objetivo Estratégico

El motor BMD resuelve la **fragmentación operativa entre desarrollo de software y ejecución empresarial/financiera**, eliminando emuladores pesados y procesos manuales lentos.

El lenguaje `.bmd` actúa como **"Fuente Única de Verdad" (Single Source of Truth)** para que el Agente Autónomo `muse-spark` procese, audite, transfiera propiedad de código y genere documentos legales o financieros con **inmutabilidad matemática y trazabilidad absoluta**.

---

## 🏗️ Arquitectura

```
bmd_engine/
├── include/
│   ├── bmd_engine.h       # API principal del motor
│   ├── bmd_crypto.h       # Primitivas criptográficas (Ed25519, SHA, ChaCha20)
│   ├── bmd_parser.h       # Parser YAML+Markdown
│   └── bmd_ledger.h       # Ledger local de bloques
├── src/
│   ├── bmd_crypto.c       # Implementación criptográfica pura C11
│   ├── bmd_parser.c       # Parser del formato .bmd
│   ├── bmd_engine.c       # Motor central (sign, verify, transition)
│   ├── bmd_ledger.c       # Cadena de bloques local
│   └── bmd_main.c         # CLI (bmd_cli.exe)
├── compat/                # Stubs de headers para MSVC sin SDK completo
├── tests/
│   ├── test_engine.c      # Tests nativos C11
│   ├── test_ffi.py        # Tests Python FFI (ctypes)
│   └── test_crossvalidate.py  # Cross-validación con PyNaCl
├── python/
│   └── bmd_ffi.py         # Puente Python ↔ DLL (ctypes)
├── examples/
│   └── genesis_block.bmd  # Bloque génesis de ejemplo
├── specs/
│   └── BMD_LANGUAGE_SPEC_V1.md
├── bin/                   # Artefactos compilados (DLL, EXE, LIB)
└── build_full.bat         # Script de compilación completo
```

---

## 🔐 Stack Criptográfico

| Primitiva     | Estándar       | Uso                                           |
|---------------|----------------|-----------------------------------------------|
| **Ed25519**   | RFC 8032       | Firma digital de documentos `.bmd`            |
| **SHA-512**   | NIST FIPS 180-4| Hash canónico del payload y del bloque (128 hex) |
| **SHA-256**   | NIST FIPS 180-4| Primitiva auxiliar y vector de prueba; no es el hash del bloque |
| **ChaCha20**  | RFC 8439       | Cifrado simétrico del payload (`payload_encrypted: true`) |

> **Sin dependencias externas.** Todo implementado en C11 puro, port exacto de TweetNaCl.

---

## 📄 Formato del Archivo `.bmd`

```yaml
---
block_id: "0x8F4C2A1_BLOCK_CORP"
previous_hash: "0000...0000"             # 128 hex; 128 ceros = génesis
current_hash: "4A8B...9C2D"              # SHA-512 del bloque (128 hex)
mode: "transfer"                         # "draft" | "transfer"
signer_role: "emisor"                    # "emisor" | "receptor"
timestamp: 1772210000
public_key: "ED25519_PUB_KEY..."
signature_layer_2: "SIG_ED25519..."
payload_encrypted: false
document_type: "contract"                # contrato, licencia, NDA, servicios...
jurisdiction: "Colombia"
require_cosigner: true
max_signatures: "2"                      # 0 ilimitado, 1 unilateral, 2 bilateral, N multipartita
---

# Contenido Markdown del Documento
...
```

### Modos de Operación

| Modo       | Descripción                                                    |
|------------|----------------------------------------------------------------|
| `draft`    | Edición libre — hash mutable, sin congelamiento               |
| `transfer` | **Inmutable** — firmado, congelado, listo para traspaso legal |

La gobernanza de firmas de v2.1 se declara con `max_signatures`:
`0` = sin límite, `1` = unilateral (solo emisor), `2` = bilateral
(emisor + receptor), `N` = multipartita. El motor rechaza una co-firma cuando
la cuota ya se alcanzó con `BMD_ERR_SIGNATURE_LIMIT_EXCEEDED (30)`.

---

## 🔨 Compilación

### Requisitos
- MSVC 2022 (`vcvars64.bat` disponible)
- Windows x64
- Python 3.x (opcional, para FFI y cross-validación)

### Build completo (DLL + CLI + Tests)

```cmd
cd bmd_engine
build_full.bat
```

**Salida esperada:**
```
[1/4] Compilando DLL bmd_engine...   [OK]
[2/4] Compilando test_engine.exe...  [OK]
[3/4] Compilando bmd_cli.exe...      [OK]
[4/4] Ejecutando tests nativos C11...
[SUCCESS] ALL NATIVE C11 TESTS PASSED WITH 100% INTEGRITY!
```

---

## ✅ Tests

### Tests nativos C11

```cmd
bmd_engine\bin\test_engine.exe
```

Cubre:
- SHA-256 y SHA-512 con vectores NIST (el hash del bloque es SHA-512 de 128 hex)
- Ed25519: generación de clave, firma, verificación, detección de tampering
- ChaCha20: cifrado/descifrado roundtrip
- Ciclo de vida completo de documento BMD: parse → sign → verify → tamper → detect

### Tests Python FFI

```cmd
set PATH=bmd_engine\bin;%PATH%
python bmd_engine\tests\test_ffi.py
```

Cubre:
- Generación de keypair vía DLL
- Parse de documento `.bmd`
- Firma y verificación en modo DRAFT
- Transición DRAFT → TRANSFER y re-verificación

### Cross-validación con PyNaCl

```cmd
python bmd_engine\tests\test_crossvalidate.py
```

**Resultado verificado:**
```
Public Key match     : OK IDENTICAL
R point (bytes 0-31) : OK IDENTICAL
S scalar (bytes 32-63): OK IDENTICAL
Full Signature match : OK IDENTICAL
PyNaCl verifies BMD-C sig: VALID
[SUCCESS] BMD ENGINE 100% COMPATIBLE CON TWEETNACL/LIBSODIUM
```

---

## 🖥️ CLI — `bmd_cli.exe`

```cmd
# Generar par de claves Ed25519
bmd_cli.exe genkey

# Leer el documento en el visor nativo
bmd_cli.exe read examples\genesis_block.bmd

# Inspeccionar metadatos, modo, firmas y max_signatures
bmd_cli.exe inspect examples\genesis_block.bmd

# Firmar y congelar (DRAFT → TRANSFER) como emisor
bmd_cli.exe sign examples\genesis_block.bmd <SEED_EMISOR>

# Co-firmar como receptor (solo si max_signatures >= 2)
bmd_cli.exe cosign examples\genesis_block.bmd <SEED_RECEPTOR>

# Verificar integridad criptográfica
bmd_cli.exe verify examples\genesis_block.bmd
bmd_cli.exe verify --json examples\genesis_block.bmd

# Aplicar solo lectura y auditar una cadena
bmd_cli.exe lock examples\genesis_block.bmd
bmd_cli.exe audit bloque1.bmd bloque2.bmd

# Render HTML y exportación Office
bmd_cli.exe render examples\genesis_block.bmd salida.html
bmd_cli.exe --export-office examples\genesis_block.bmd
```

> Los comandos de v2.0 `--compile-sign`, `--co-sign`, `freeze`, `accept`,
> `seal` y `unseal` ya no existen en el dispatch del CLI. El cifrado
> ChaCha20 sigue disponible a través de la FFI (`doc.seal`/`doc.unseal`).

---

## 🐍 Python FFI Bridge

```python
import sys

sys.path.insert(0, "bmd_engine/python")
from bmd_ffi import BMDWrapper, generate_keypair

seed = b"\x42" * 32
pub_key, sec_key = generate_keypair(seed)

# Cargar el bloque y verificar su integridad
doc = BMDWrapper.load_file("examples/genesis_block.bmd")
valid, message = doc.verify()
print(valid, message)

# Firmar y congelar como emisor (DRAFT -> TRANSFER)
doc.transition_to_transfer(seed)
doc.save("examples/genesis_block.bmd")

# La cuota v2.1 se lee desde la DLL
print("max_signatures:", doc.max_signatures)
```

---

## 🤖 Gobernanza del Agente Autónomo `muse-spark`

El agente opera sobre documentos `.bmd` con las siguientes capacidades:

1. **LEER** — Procesar bloques DRAFT sin restricción
2. **FIRMAR** — Emitir firma Ed25519 sobre el `current_hash` (`sign`)
3. **CO-FIRMAR** — Añadir la aceptación del receptor (`cosign`) si `max_signatures` lo permite
4. **VERIFICAR** — Validar la cadena de integridad completa (`verify`, `verify --json`)
5. **CONGELAR** — Transicionar DRAFT → TRANSFER (irreversible)
6. **BLOQUEAR** — Aplicar solo lectura al archivo (`lock`)
7. **AUDITAR** — Inspeccionar el ledger local y detectar adulteraciones (`audit`)

### Garantías Matemáticas

- **Inmutabilidad**: La firma Ed25519 sobre el `current_hash` hace imposible modificar el contenido sin invalidar la firma
- **Trazabilidad**: El `previous_hash` vincula cada bloque al anterior formando una cadena verificable
- **No-repudio**: La clave pública identifica de forma única al firmante (emisor/receptor)
- **Confidencialidad**: ChaCha20 cifra el payload para documentos sensibles

---

## 📊 Rendimiento

| Operación          | Tiempo aproximado (x86-64) |
|--------------------|---------------------------|
| SHA-256 (1 KB)     | < 1 µs                    |
| SHA-512 (1 KB)     | < 2 µs                    |
| Ed25519 keypair    | ~50 µs                    |
| Ed25519 sign       | ~80 µs                    |
| Ed25519 verify     | ~150 µs                   |
| ChaCha20 (1 KB)    | < 1 µs                    |

---

*BMD Engine v2.1.0 — Implementación de grado empresarial, 100% C11, compatible con TweetNaCl/libsodium*
