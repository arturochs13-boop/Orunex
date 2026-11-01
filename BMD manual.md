# BMD Manual: Blockchain Markdown (.bmd) Specification & CLI Reference Guide
**Version:** 2.1.0 (Immutable Protocol • C11 Engine Runtime)  
**Standard:** Ed25519 (RFC 8032) • SHA-512 (NIST FIPS 180-4) • SHA-256 • ChaCha20 (RFC 8439)  
**Classification:** High-Assurance Cryptographic Document & Governance Architecture  

---

## Table of Contents
1. [Executive Summary & Strategic Vision](#1-executive-summary--strategic-vision)
2. [Core Principles of Blockchain Markdown](#2-core-principles-of-blockchain-markdown)
3. [The Cryptographic Stack & Security Model](#3-the-cryptographic-stack--security-model)
4. [File Format Specification (.bmd)](#4-file-format-specification-bmd)
   - [Frontmatter Metadata Schema](#41-frontmatter-metadata-schema)
   - [Document Body & Semantic Typography Tags](#42-document-body--semantic-typography-tags)
5. [Complete CLI Reference Manual (`bmd`)](#5-complete-cli-reference-manual-bmd)
   - [Summary of Commands](#51-summary-of-commands)
   - [Detailed Command Specifications](#52-detailed-command-specifications)
6. [BMD Redact Studio (In-Terminal Visual Editor)](#6-bmd-redact-studio-in-terminal-visual-editor)
   - [Overview & Architecture](#61-overview--architecture)
   - [Studio Action Buttons & Live Indicators](#62-studio-action-buttons--live-indicators)
   - [In-Studio Command Dictionary](#63-in-studio-command-dictionary)
7. [Operational Workflows & Real-World Scenarios](#7-operational-workflows--real-world-scenarios)
   - [Scenario A: Unilateral Declaration (Sole Author)](#scenario-a-unilateral-declaration-sole-author)
   - [Scenario B: Bilateral Commercial Agreement (Dual-Party Ratification)](#scenario-b-bilateral-commercial-agreement-dual-party-ratification)
   - [Scenario C: Intellectual Property Escrow & Registration](#scenario-c-intellectual-property-escrow--registration)
   - [Scenario D: Corporate Invoice & Ledger Record](#scenario-d-corporate-invoice--ledger-record)
8. [C11 Native Core Engine Architecture](#8-c11-native-core-engine-architecture)
   - [Library Components](#81-library-components)
   - [Compiling & Running Native Unit Tests](#82-compiling--running-native-unit-tests)
9. [Enterprise Best Practices & Security Advisory](#9-enterprise-best-practices--security-advisory)

---

## 1. Executive Summary & Strategic Vision

Modern software development, corporate operations, and contract execution suffer from deep systemic fragmentation. Organizations routinely exchange vulnerable text documents (PDFs, Word docs, standard Markdown) across untrusted communication channels. When combined with autonomous AI agents that generate or modify documents, the absence of cryptographic boundaries introduces existential risks: unnoticed data alteration, hallucinated terms, lack of non-repudiation, and impossible legal auditability.

**Blockchain Markdown (.bmd)** solves this by establishing a mathematically immutable **"Single Source of Truth"**. 

A `.bmd` file couples human-readable Markdown with a strictly validated cryptographic ledger header. Built upon a ultra-lightweight, zero-dependency C11 engine, Blockchain Markdown guarantees:
1. **Absolute Immutability:** Once sealed, altering even a single whitespace or punctuation mark invalidates the SHA-512 hash and Ed25519 digital signature.
2. **Cryptographic Ground Truth:** The `.bmd` file is the sole canonical reality. Any visual representation (HTML preview, terminal rendering, Word/Excel export) is strictly an ephemeral presentation layer.
3. **Autonomous Governance:** Enforces rigid state transitions (`draft` → `transfer`), non-bypassable signature limits (`max_signatures`), and bilateral consensus verification natively.

---

## 2. Core Principles of Blockchain Markdown

### 2.1 The Two Operational Modes
A `.bmd` document exists in one of two deterministic states:
- **`mode: draft` (Mutable Development State):**
  - Allows drafting, editing lines, modifying frontmatter, and testing layouts.
  - The hash and signatures are not locked; the file is open for iterative changes.
- **`mode: transfer` (Frozen / Immutable State):**
  - Sealed cryptographically with SHA-512 and signed with an Ed25519 private key.
  - The core engine permanently forbids modifying payload characters or frontmatter fields.
  - The file on disk is marked with the operating system read-only attribute (`bmd lock`).
  - No forking is permitted under the same `block_id`.

### 2.2 Signature Limits & Consensus Ratification (`max_signatures`)
To prevent unauthorized parties from tampering or appending signatures to a sealed document, the protocol enforces a strict signature cap:
- **`max_signatures: 1` (Unilateral):** Only the creator (Emitter) signs. Co-signing is permanently rejected by the engine.
- **`max_signatures: 2` (Bilateral):** Requires both Emitter and Receiver to sign. The document is officially classified as **CONSENSUS RATIFIED** only when both Ed25519 signatures are present and mathematically valid.
- **`max_signatures: N` (Multilateral):** Configurable multi-party consensus.

---

## 3. The Cryptographic Stack & Security Model

The BMD core runtime (`bmd_engine`) is written in pure C11 without external dependencies (no OpenSSL, no libsodium required), based on audited implementations:

| Primitive | Standard | Function in Protocol |
|:---|:---|:---|
| **SHA-512** | NIST FIPS 180-4 | 128-hex character payload integrity hash; deterministic tamper-evident lock |
| **Ed25519** | RFC 8032 | Asymmetric digital signature over twisted Edwards curve (Edwards25519) |
| **Key Derivation** | RFC 8032 / SHA-512 | Derivation of 32-byte public key and 64-byte secret key from a 32-byte seed |
| **SHA-256** | NIST FIPS 180-4 | Chained block ledger auditing (`previous_hash` → `current_hash`) and IP trees |
| **ChaCha20** | RFC 8439 | Stream cipher for optional authenticated payload confidentiality |

---

## 4. File Format Specification (.bmd)

A `.bmd` file is composed of two contiguous sections:
1. **YAML Frontmatter Header** (delimited by `---` lines at lines 1 and end of header).
2. **Document Payload Body** (semantic Markdown with BMD structural directives).

### 4.1 Frontmatter Metadata Schema

```yaml
---
bmd_version: 2.1
block_id: 0xBMD_PROOF_OF_CONCEPT_2026
document_type: declaration
mode: transfer
jurisdiction: International / Open Standard
max_signatures: 2
timestamp: 1772210000
public_key: 1ac464faf140f1f4361f3b355aab0124145f3a81ea287b559b6f2453d61657ca
signature_layer_2: 205f74f748bdd05beacb8d40f539d0b0f03b5924d34138d6976822f0fbd04c5a0eb1cd3b7379ff55ffe3566005acd9d51f2ff4c145db9d8beae036a5c2290002
receiver_public_key: acb5d74d835d17f5984fb4171c277d665466b812481914bc58569a1f5726df47
receiver_signature: d96a5bc888a2c14d7b03324ce3e58c90a47ef394573f23b8f912fc95ea77aabac2efa99aca865257ebdfcb9aa0326e824fa3a38ead118ac6a7239e2a3fbae206
current_hash: 60dd7104d681f22d70f02488129b692152e46a3120e6b004b3c6a775a2fac8f6e632c7612ed9dc75a9455ec61e80b37bda803bc9d927a99195b8dbf477a9c22b
previous_hash: 00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
---
```

#### Field Dictionary

| Field | Type | Description |
|:---|:---|:---|
| `bmd_version` | String | Protocol specification version (current: `2.1`). |
| `block_id` | String | Unique block identifier. Convention: prefixed with `0x`, uppercase alphanumeric. |
| `document_type` | String | Classification: `contract`, `declaration`, `license`, `invoice`, `certificate`, `addendum`. |
| `mode` | String | State of document: `draft` (mutable) or `transfer` (immutable sealed). |
| `jurisdiction` | String | Legal framework governing the agreement (e.g., `International`, `US - Delaware`). |
| `max_signatures` | Integer | Cap of valid signatures permitted (`1` = unilateral, `2` = bilateral, `N` = multilateral). |
| `timestamp` | Integer | Unix epoch timestamp of creation or signing. |
| `public_key` | Hex (64) | 32-byte Ed25519 public key of the primary signer (Emitter). |
| `signature_layer_2` | Hex (128) | 64-byte Ed25519 digital signature of Emitter over the SHA-512 payload hash. |
| `receiver_public_key` | Hex (64) | 32-byte Ed25519 public key of the co-signer (Receiver). |
| `receiver_signature` | Hex (128) | 64-byte Ed25519 digital signature of Receiver verifying bilateral consensus. |
| `current_hash` | Hex (128) | SHA-512 hash calculated strictly over the payload content. |
| `previous_hash` | Hex (128) | SHA-512 hash of previous block (all zeros for Genesis blocks). |
| `property_bundle_hash`| Hex (64) | Optional SHA-256 root hash of intellectual property assets sealed into the block. |

---

### 4.2 Document Body & Semantic Typography Tags

Content in a `.bmd` file is written using standard Markdown enhanced with semantic XML tags. These tags ensure that terminal letter-sheet rendering and HTML viewers render text with consistent, professional legal typography without depending on dynamic CSS:

| Tag | Purpose & Rendering Behavior |
|:---|:---|
| `<title>Text</title>` | Document primary title. Rendered large, centered, with border accents. |
| `<subtitle>Text</subtitle>` | Secondary subtitle or party designation line. |
| `<heading>Text</heading>` | Major section heading (rendered with `===` section separators). |
| `<body>Text</body>` | Standard paragraph text. Automatically word-wrapped to 72–76 columns. |
| `<bmd:rule>` | Double horizontal rule separator (`====================`) across the sheet. |
| `<bmd:rule single>` | Single horizontal rule separator (`--------------------`) across the sheet. |
| `<bmd:parties>` | Automatically rendered two-column table displaying Emitter & Receiver public keys. |
| `<bmd:signatures>` | Verification panel showing Ed25519 signature statuses (`DIGITALLY SEALED` / `RATIFIED`). |
| `<bmd:seal>` | Cryptographic custody seal banner with verified SHA-512 integrity status. |

---

## 5. Complete CLI Reference Manual (`bmd`)

The `bmd` command-line utility provides a direct interface to the C11 engine. All commands feature auto-path resolution, UTF-8 console support, and strict exit codes suitable for automated scripting.

### 5.1 Summary of Commands

```text
================================================================================
  BLOCKCHAIN MARKDOWN (.bmd) COMMAND REFERENCE MANUAL
================================================================================

DOCUMENT VIEWING & VERIFICATION:
  bmd read <file.bmd>                   Render document natively (letter-sheet view)
  bmd <file.bmd>                        Short form: immediately view document
  bmd verify <file.bmd>                 Verify SHA-512 hash & Ed25519 signatures
  bmd verify --json <file.bmd>          Same verification with JSON output
  bmd inspect <file.bmd>                Full block metadata, hashes & signature cap

DRAFTING & REDACT STUDIO:
  bmd redact [file.bmd]                 Open terminal editor (create or edit draft)

SIGNING & IMMUTABILITY:
  bmd sign <file.bmd> <seed_hex>        Compile: auto SHA-512 hash + Ed25519 sign + freeze
  bmd cosign <file.bmd> <seed_hex>      Receiver co-signs (only if max_signatures >= 2)
  bmd genkey                            Generate new Ed25519 keypair (seed + pubkey)
  bmd lock <file.bmd>                   Apply OS read-only attribute to file

LEDGER AUDIT:
  bmd audit <b1.bmd> [b2.bmd ...]       Audit cryptographic chain of custody

EXPORTS & INTELLECTUAL PROPERTY:
  bmd render <file.bmd> [out.html]      Export standalone zero-dependency HTML viewer
  bmd --inject-property <dir> <bmd>     Inject IP asset bundle with SHA-256 tree
  bmd --extract-property <bmd> [--out]  Extract IP assets and verify file hashes
  bmd --export-office <file.bmd>        Export structured JSON metadata for integrations

SHELL & UTILITY:
  bmd                                   Launch interactive BMD shell
  /help, help, -h, --help               Display this command manual
  exit, quit, q                         Exit the interactive shell
================================================================================
```

---

### 5.2 Detailed Command Specifications

#### `bmd read <file.bmd>`
Renders the `.bmd` file as a framed **Executive Letter-Sheet** directly in the terminal using ASCII-safe borders (`+`, `-`, `|`, `=`). 
- Resolves paths automatically across working directories.
- Verifies SHA-512 hash and Ed25519 signatures on load.
- Automatically word-wraps body text and hides raw metadata tags for clean reading.
```bash
bmd read contracts/service_agreement.bmd
# Or simply:
bmd contracts/service_agreement.bmd
```

#### `bmd verify <file.bmd>`
Performs a cryptographic verification of the file:
1. Re-computes the SHA-512 hash of the payload text.
2. Compares against the frontmatter `current_hash`.
3. Validates the Emitter's Ed25519 signature against `public_key`.
4. If co-signed, validates the Receiver's signature against `receiver_public_key`.
- **Exit Code 0:** Authentic, verified, unmodified.
- **Exit Code 2:** Tamper detected or signature mismatch.

#### `bmd verify --json <file.bmd>`
Executes the same mathematical verification as `verify`, but formats the output as a structured JSON string. Designed for CI/CD pipelines, web servers, and automated agent loops:
```bash
bmd verify --json contracts/service_agreement.bmd
```
```json
{
  "status": "ok",
  "error": "none",
  "hash_valid": true,
  "current_state": "dual_signed",
  "block_id": "0xCONTRACT_2026",
  "document_type": "contract",
  "current_hash": "60dd7104...",
  "computed_hash": "60dd7104...",
  "signer_role": "emisor",
  "emitter_pubkey": "1ac464fa...",
  "emitter_signature": "205f74f7...",
  "receiver_pubkey": "acb5d74d...",
  "receiver_signature": "d96a5bc8...",
  "has_property_bundle": false
}
```

#### `bmd inspect <file.bmd>`
Prints a complete forensic audit of the block's frontmatter, including timestamps, role definitions, signature capacity slots remaining, and an excerpt of the raw payload.

#### `bmd redact [file.bmd]`
Launches the **BMD Redact Studio**, an in-terminal visual drafting application. Allows composing documents, setting metadata, previewing clean outputs, and executing automated compile-and-sign workflows without leaving the terminal.

#### `bmd sign <file.bmd> <seed_hex>`
The single primary command to seal a draft into an immutable document:
1. Takes a 64-character hexadecimal private seed (32 bytes).
2. Derives the Ed25519 keypair deterministically.
3. Automatically computes the exact SHA-512 hash of the document body.
4. Cryptographically signs the hash.
5. Transitions frontmatter `mode` from `draft` to `transfer`.
6. Embeds public key, signature, and timestamp.
7. Locks the file on disk as read-only.
```bash
bmd sign draft_notice.bmd 4242424242424242424242424242424242424242424242424242424242424242
```

#### `bmd cosign <file.bmd> <seed_hex>`
Executes the second party (Receiver) co-signature on a sealed document:
- Checks that the document is already signed by the Emitter.
- Verifies that `max_signatures >= 2`. If `max_signatures == 1`, the engine strictly refuses the signature.
- Signs the immutable SHA-512 hash and embeds `receiver_public_key` and `receiver_signature`.
- Transitions the document status to **CONSENSUS RATIFIED**.

#### `bmd genkey`
Generates a cryptographically strong 32-byte private seed and derives its matching Ed25519 public key.
```bash
bmd genkey
```
```text
[+] NEW ED25519 CRYPTOGRAPHIC KEYPAIR GENERATED:
    PRIVATE SEED (32 bytes): e8a3d4f19b2c7e6a5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e
    PUBLIC KEY   (32 bytes): 7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a
```

#### `bmd lock <file.bmd>`
Sets the OS-level read-only attribute on the file, preventing accidental deletion or modification by external text editors.

#### `bmd audit <b1.bmd> [b2.bmd ...]`
Evaluates a chain of `.bmd` blocks in sequence, verifying that block $N$'s `previous_hash` mathematically equals block $N-1$'s `current_hash`. Produces an executive consensus audit report.

#### `bmd render <file.bmd> [out.html]`
Compiles the `.bmd` file into a self-contained, zero-dependency standalone HTML5 document with embedded WebCrypto verification logic. The generated HTML file can be opened in any web browser completely offline.

#### `bmd --inject-property <dir> <file.bmd>` & `bmd --extract-property`
Embeds a complete directory of source code, intellectual property, or binary files into the `.bmd` container with a SHA-256 Merkle tree verification record.

---

## 6. BMD Redact Studio (In-Terminal Visual Editor)

The Redact Studio provides an authoring environment directly inside standard Windows Command Prompt and PowerShell windows without external dependencies.

```text
  ================================================================================
   BMD REDACT STUDIO  |  contracts/nda.bmd  |  mode: DRAFT (MUTABLE)
  ================================================================================

  Frontmatter:
    block_id        : 0xNDA_PARTNERSHIP_2026
    type            : contract
    jurisdiction    : International / Open Standard
    max_signatures  : 2  (bilateral - requires Emitter + Receiver)
    emitter_sig     : [UNSIGNED]
    SHA-512 hash    : (computed automatically on :compile or :sign)

  Document  (5 lines):
  +--------+--------------------------------------------------------------------+
  |  Line  |  Content                                                           |
  +--------+--------------------------------------------------------------------+
  |      1 | <title>Mutual Non-Disclosure Agreement</title>                      |
  |      2 | <bmd:rule>                                                         |
  |      3 | <body>The parties agree to hold proprietary data confidential.</body>|
  |      4 | <bmd:signatures>                                                   |
  |      5 | <bmd:seal>                                                         |
  +--------+--------------------------------------------------------------------+

  ================================================================================
  ACTIONS:
  +-----------------------------+  +-----------------------------+
  |  :compile                   |  |  :sign <seed_hex>           |
  |  Compute SHA-512 hash &     |  |  Hash + Ed25519 sign +      |
  |  seal document to TRANSFER  |  |  freeze to IMMUTABLE mode   |
  |  (prompts for seed)         |  |  (provide 64-hex seed)      |
  +-----------------------------+  +-----------------------------+

  CONTENT:  :add <tag> text   :insert N <tag> text   :delete N   :set <field> <val>
  UTILITY:  :save [file]  :preview  :list  :genkey  :verify  :render  :help  :quit
  ================================================================================

  redact> 
```

### 6.1 Action Buttons & Live Indicators
- **`[ :compile ]`**: Automatic wizard. Checks required metadata, computes the SHA-512 payload hash, prompts to generate or provide a private seed, signs with Ed25519, and freezes the document to `transfer` mode.
- **`[ :sign <seed_hex> ]`**: One-step execution. Automatically computes the SHA-512 hash and signs immediately.
- **Live Signature Status**: Dynamically tracks `[UNSIGNED]`, `[SIGNED]`, `[AWAITING CO-SIGNATURE]`, and `[CO-SIGNED & RATIFIED]`.

### 6.2 In-Studio Command Dictionary

| Studio Command | Action |
|:---|:---|
| `:help` | Opens the full comprehensive reference manual and syntax examples. |
| `:add <tag> text` | Appends a new tagged line to the bottom of the document. |
| `:insert <N> <tag> text` | Inserts a line before line number $N$ (1-based index). |
| `:delete <N>` | Deletes line number $N$. |
| `:set <field> <value>` | Updates frontmatter field (`block_id`, `type`, `jurisdiction`, `max_signatures`). |
| `:preview` | Toggles clean reading mode (all `<>` tags are hidden, rendering pure typography). |
| `:list` | Displays the complete document with continuous line numbering. |
| `:compile [seed]` | Triggers automated SHA-512 calculation, key derivation, and sealing wizard. |
| `:sign [seed]` | Hashes and signs as Emitter. Prompts interactively if seed is omitted. |
| `:cosign <seed>` | Receiver co-signs (enabled only if `max_signatures >= 2`). |
| `:save [filename]` | Writes current buffer and metadata to disk. |
| `:genkey` | Generates a fresh Ed25519 seed and displays it on screen for easy copying. |
| `:verify` | Performs an immediate cryptographic audit of the saved file. |
| `:render [out.html]` | Exports the document to a zero-dependency standalone HTML viewer. |
| `:up` / `:down` | Scrolls the document view window up or down. |
| `:quit` / `:quit!` | Exits the studio (`:quit!` forces exit without saving). |

---

## 7. Operational Workflows & Real-World Scenarios

### Scenario A: Unilateral Declaration (Sole Author)
*Use case: Proof of authorship, copyright registration, public declaration.*

1. Open the studio:
   ```bash
   bmd redact my_declaration.bmd
   ```
2. Set metadata:
   ```text
   :set block_id 0xDECL_AUTHORSHIP_2026
   :set type declaration
   :set jurisdiction International
   :set max_signatures 1
   ```
3. Add content:
   ```text
   :add <title>Declaration of Software Authorship</title>
   :add <bmd:rule>
   :add <body>I hereby declare sole authorship of the enclosed cryptographic codebase.</body>
   :add <bmd:parties>
   :add <bmd:seal>
   ```
4. Generate key and sign:
   ```text
   :save
   :genkey
   :sign <your_generated_seed>
   ```
   *Result:* Document is permanently sealed. Any subsequent `:cosign` is rejected because `max_signatures = 1`.

---

### Scenario B: Bilateral Commercial Agreement (Dual-Party Ratification)
*Use case: Service contracts, NDAs, partnership agreements.*

1. **Party A (Emitter) drafts and signs:**
   ```text
   :set block_id 0xSERVICE_AGREEMENT_2026
   :set type contract
   :set max_signatures 2
   :add <title>Master Service Agreement</title>
   :add <subtitle>Between Alpha Corp and Beta LLC</subtitle>
   :add <bmd:rule>
   :add <heading>Scope of Work</heading>
   :add <body>Alpha Corp agrees to provide high-performance systems engineering.</body>
   :add <bmd:signatures>
   :add <bmd:seal>
   :save service_agreement.bmd
   :compile
   ```
   *Alpha Corp signs with their seed. Document mode transitions to `transfer`.*

2. **Transmission:**
   Alpha Corp sends `service_agreement.bmd` to Beta LLC (via email, git, or messaging).

3. **Party B (Receiver) validates and co-signs:**
   ```bash
   # Beta LLC verifies Alpha's signature first:
   bmd verify service_agreement.bmd
   
   # Beta LLC opens in studio or signs directly from CLI:
   bmd cosign service_agreement.bmd <beta_seed_hex>
   ```
   *Result:* Document is now **CONSENSUS RATIFIED** with both signatures mathematically embedded.

---

### Scenario C: Intellectual Property Escrow & Registration
*Use case: Sealing proprietary algorithms or models.*

```bash
# 1. Package source folder into a BMD container with Merkle tree
bmd --inject-property ./src/ai_model ./contracts/ai_model_ip.bmd

# 2. Sign and lock the asset
bmd sign ./contracts/ai_model_ip.bmd <owner_seed_hex>

# 3. Third parties verify the integrity of the assets
bmd verify ./contracts/ai_model_ip.bmd
```

---

## 8. C11 Native Core Engine Architecture

### 8.1 Library Components
- **`bmd_crypto.c`**: Pure C implementation of Ed25519 (curve25519 operations, scalar multiplication, SHA-512 digests).
- **`bmd_parser.c`**: Streaming tokenizer and parser for YAML frontmatter and payload lines.
- **`bmd_engine.c`**: Lifecycle governance (`bmd_parse_file`, `bmd_transition_to_transfer`, `bmd_sign_document`, `bmd_cosign_receiver`).
- **`bmd_ledger.c`**: Multi-block chain verification and Merkle tree generation.
- **`bmd_main.c`**: High-performance CLI interface, ANSI color banner, and in-terminal Redact Studio.

### 8.2 Compiling & Running Native Unit Tests
To build the engine DLL and CLI binary on Windows using Microsoft Visual C++:

```cmd
cd bmd_engine
build_full.bat
```

The build script automatically:
1. Compiles `bmd_engine.dll` (shared library).
2. Compiles and executes `test_engine.exe` running 5 comprehensive C11 unit tests:
   - SHA-256 test vectors
   - SHA-512 ledger cryptographic standards
   - Ed25519 keypair generation, signature verification, and tamper resistance
   - ChaCha20 stream cipher roundtrip
   - Document lifecycle state transitions
3. Compiles `bmd.exe` and installs it to `%LOCALAPPDATA%\Microsoft\WindowsApps\` for global system access.

---

## 9. Enterprise Best Practices & Security Advisory

1. **Seed Management:** Never share or commit private seeds (64-character hex strings) to public repositories. Seeds grant signing authority. Public keys are safe to share.
2. **Canonical Authority:** Always treat the `.bmd` file as the primary source of truth. If a dispute arises, verify the `.bmd` file with `bmd verify <file.bmd>`. HTML representations are strictly for human reading convenience.
3. **Backup Before Signing:** Once `:sign`, `:compile`, or `bmd sign` is executed, the file becomes strictly read-only and immutable. Ensure your draft content is thoroughly reviewed via `:preview` before applying signatures.
4. **Offline Independence:** The `bmd` runtime requires zero internet connection, cloud APIs, or external servers. All cryptographic calculations take place locally on the host machine.
