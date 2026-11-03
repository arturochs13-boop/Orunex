# BMD Manual: Blockchain Markdown (.bmd) Specification & CLI Reference Guide
**Version:** 2.1.0 (Immutable Protocol • C11 Engine Runtime)  
**Standard:** Ed25519 (RFC 8032) • SHA-512 (NIST FIPS 180-4) • SHA-256 • ChaCha20 (RFC 8439)  
**Classification:** High-Assurance Cryptographic Document & Governance Architecture  

---

## Table of Contents
1. [Executive Summary & Strategic Vision](#1-executive-summary--strategic-vision)
2. [Core Principles of Blockchain Markdown](#2-core-principles-of-blockchain-markdown)
   - [Zero-Dependency Ledger Identity (No Arbitrary Block IDs)](#21-zero-dependency-ledger-identity-no-arbitrary-block-ids)
   - [The Two Operational Modes (`draft` vs `transfer`)](#22-the-two-operational-modes-draft-vs-transfer)
   - [Automatic Device Identity Signatures](#23-automatic-device-identity-signatures)
   - [Signature Limits & Consensus Ratification (`max_signatures`)](#24-signature-limits--consensus-ratification-max_signatures)
3. [The Cryptographic Stack & Security Model](#3-the-cryptographic-stack--security-model)
   - [Cryptographic Primitives](#31-cryptographic-primitives)
   - [Anti-Decompilation & Tamper-Proofing Guarantees](#32-anti-decompilation--tamper-proofing-guarantees)
4. [File Format Specification (.bmd)](#4-file-format-specification-bmd)
   - [Frontmatter Metadata Schema](#41-frontmatter-metadata-schema)
   - [Document Body & Button Directives](#42-document-body--button-directives)
5. [Complete CLI Reference Manual (`bmd`)](#5-complete-cli-reference-manual-bmd)
   - [Summary of Commands](#51-summary-of-commands)
   - [Detailed Command Specifications](#52-detailed-command-specifications)
6. [BMD Redact Studio (In-Terminal Visual Editor)](#6-bmd-redact-studio-in-terminal-visual-editor)
   - [Studio Architecture & Interface](#61-studio-architecture--interface)
   - [Interactive Button Directives & Action Bar](#62-interactive-button-directives--action-bar)
   - [In-Studio Command Dictionary](#63-in-studio-command-dictionary)
7. [Operational Workflows & Real-World Scenarios](#7-operational-workflows--real-world-scenarios)
   - [Scenario A: Unilateral Declaration (Sole Author)](#scenario-a-unilateral-declaration-sole-author)
   - [Scenario B: Bilateral Commercial Agreement (Dual-Party Ratification)](#scenario-b-bilateral-commercial-agreement-dual-party-ratification)
   - [Scenario C: Intelligent Property (IP) Escrow & Registration](#scenario-c-intelligent-property-ip-escrow--registration)
   - [Scenario D: Corporate Invoice & Ledger Record](#scenario-d-corporate-invoice--ledger-record)
8. [C11 Native Core Engine Architecture](#8-c11-native-core-engine-architecture)
   - [Library Components](#81-library-components)
   - [Compiling & Running Native Unit Tests](#82-compiling--running-native-unit-tests)
9. [Enterprise Best Practices & Security Advisory](#9-enterprise-best-practices--security-advisory)

---

## 1. Executive Summary & Strategic Vision

Modern software development, corporate operations, and contract execution suffer from deep systemic fragmentation. Organizations routinely exchange vulnerable text documents (PDFs, Word docs, standard Markdown) across untrusted communication channels. When combined with autonomous AI agents that generate or modify documents, the absence of cryptographic boundaries introduces existential risks: unnoticed data alteration, hallucinated terms, lack of non-repudiation, and impossible legal auditability.

**Blockchain Markdown (.bmd)** solves this by establishing a mathematically immutable **"Single Source of Truth"**.

A `.bmd` file couples human-readable Markdown with a strictly validated cryptographic ledger header. Built upon an ultra-lightweight, zero-dependency C11 engine, Blockchain Markdown guarantees:
1. **Absolute Immutability:** Once compiled, altering even a single whitespace or punctuation mark invalidates the SHA-512 ledger hash and Ed25519 digital signature.
2. **Cryptographic Ground Truth:** The `.bmd` file is the sole canonical reality. Any visual representation (HTML preview, terminal rendering, Word/Excel export) is strictly an ephemeral presentation layer.
3. **Hardware-Anchored Device Identity:** Both Emitter and Receiver signatures are calculated automatically from authenticated device identity keys. Users can never insert arbitrary or forged signatures — the engine computes them from the hardware identity of the signing device.
4. **Autonomous Governance:** Enforces rigid state transitions (`draft` → `transfer`), non-bypassable signature limits (`max_signatures`), and bilateral consensus verification natively.

> [!IMPORTANT]
> **Definición de "IP" (Intelligent Property / Intellectual Property):**
> A lo largo de esta especificación, manual y utilidades del sistema, el término y acrónimo **IP** se refiere estrictamente a **Intelligent Property / Intellectual Property (Propiedad Intelectual)** — activos digitales como código fuente, algoritmos propietarios, modelos de IA y documentación confidencial. **No tiene relación alguna con una "dirección IP" de red (Internet Protocol)**.

---

## 2. Core Principles of Blockchain Markdown

### 2.1 Zero-Dependency Ledger Identity (No Arbitrary Block IDs)
Earlier versions of immutable document schemes relied on arbitrary string identifiers (`block_id`). In high-assurance environments, arbitrary block IDs can be easily forged, spoofed, or set to duplicate values.

In **BMD Protocol v2.1**, `block_id` is completely **optional and non-essential**. Document authenticity, identity, and global uniqueness are anchored strictly in mathematical truth:
- The **SHA-512 Ledger Hash** (128 hexadecimal characters) computed over the exact document payload.
- The **Ed25519 Elliptic Curve Signatures** validating author non-repudiation.
- The **Previous Hash linkage** in chained ledger records.

### 2.2 The Two Operational Modes (`draft` vs `transfer`)
A `.bmd` document exists in one of two deterministic states:
- **`mode: draft` (Mutable Development State):**
  - Allows drafting, editing lines, modifying frontmatter, and testing layouts.
  - Signing in draft mode (`bmd sign` or `:sign`) attaches the Emitter's authenticated Ed25519 signature and computes the SHA-512 hash, but leaves the document **open and mutable** so additional sections, clauses, or signature buttons can be added.
- **`mode: transfer` (Frozen / Immutable State):**
  - Triggered exclusively by `bmd compile` (or `:compile` in Redact Studio).
  - Displays a retro purple pixel gradient loading bar animation during final compilation.
  - The core engine permanently freezes the payload and frontmatter.
  - Modifying any byte on disk is physically blocked by the filesystem read-only lock attribute (`attrib +R`).
  - No transition from `transfer` back to `draft` is permitted by the engine.
  - Upon completion, the engine prints the **full absolute path** of the sealed file.

### 2.3 Automatic Device Identity Signatures

> [!IMPORTANT]
> Signatures in BMD are **always computed automatically** from the device's hardware identity key. Users cannot and must not enter signatures manually — doing so would allow forged or arbitrary values that undermine the entire security model.

The BMD engine derives a deterministic 32-byte Ed25519 seed from the authenticated device identity, persisted securely in:
- `%USERPROFILE%\.bmd\emitter_device.key` — Emitter (author) key
- `%USERPROFILE%\.bmd\receiver_device.key` — Receiver (counterparty) key

When signing:
- `bmd sign` automatically computes the SHA-512 hash and signs as Emitter with the host's authentic device key.
- `bmd compile` re-computes the final hash, freezes the document, and seals it with the Emitter device key.
- `bmd cosign` automatically signs as Receiver with the counterparty's authentic device key.

No manual seed, no custom hexadecimal entry, no possibility of forging a signature.

### 2.4 Signature Limits & Consensus Ratification (`max_signatures`)
To prevent unauthorized parties from appending signatures to a sealed document, the protocol enforces a strict signature cap:
- **`max_signatures: 1` (Unilateral):** Only the creator (Emitter) signs. Co-signing is permanently rejected by the engine.
- **`max_signatures: 2` (Bilateral):** Requires both Emitter and Receiver to sign. The document is officially classified as **CONSENSUS RATIFIED** only when both Ed25519 signatures are present and mathematically valid.
- **`max_signatures: N` (Multilateral):** Configurable multi-party consensus.

---

## 3. The Cryptographic Stack & Security Model

### 3.1 Cryptographic Primitives

The BMD core runtime (`bmd_engine`) is written in pure C11 without external dependencies (no OpenSSL, no libsodium required), based on audited implementations:

| Primitive | Standard | Function in Protocol |
|:---|:---|:---|
| **SHA-512** | NIST FIPS 180-4 | 128-hex character payload integrity hash; deterministic tamper-evident lock |
| **Ed25519** | RFC 8032 | Asymmetric digital signature over twisted Edwards curve (Edwards25519) |
| **Key Derivation** | RFC 8032 / SHA-512 | Derivation of 32-byte public key and 64-byte secret key from authenticated seed |
| **SHA-256** | NIST FIPS 180-4 | Chained block ledger auditing (`previous_hash` → `current_hash`) and IP trees |
| **ChaCha20** | RFC 8439 | Stream cipher for optional authenticated payload confidentiality |

### 3.2 Anti-Decompilation & Tamper-Proofing Guarantees
A recurring question in secure document protocols is whether a compiled document can be "decompiled" or modified back into a draft state.

1. **State Machine Lock:** The C11 engine strictly prevents reverse transitions. Once a document has reached `mode: transfer`, the engine forbids changing `mode` back to `draft`.
2. **Payload Hash Interlock:** The SHA-512 ledger hash is calculated over every byte of the payload. Changing even a single character, space, or newline produces an immediate hash breach detected by `bmd verify`.
3. **Signature Invalidation:** The Ed25519 signature signs the SHA-512 digest. Tampering with the payload breaks the signature verification instantly.
4. **OS Attribute Enforcement:** When compiled, the file is automatically protected on the filesystem with the read-only attribute (`attrib +R`), preventing external editors from silently modifying the file.
5. **No Manual Signature Entry:** The engine never accepts externally crafted or user-typed signatures — all signing material is derived from hardware device identity, making forgery structurally impossible.

---

## 4. File Format Specification (.bmd)

A `.bmd` file is composed of two contiguous sections:
1. **YAML Frontmatter Header** (delimited by `---` lines at lines 1 and end of header).
2. **Document Payload Body** (semantic Markdown with BMD structural directives).

### 4.1 Frontmatter Metadata Schema

```yaml
---
bmd_version: 2.1
document_type: agreement
mode: transfer
jurisdiction: International / Open Standard
max_signatures: 2
timestamp: 1772580000
public_key: 3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29
signature_layer_2: 2109a7b92715aa2f34175add60997db597db644cd841bb95c3a7005f61dc76f9...
receiver_public_key: 8c4d29fe3412ab7891230cdba456ef1234567890abcdef1234567890abcdef12
receiver_signature: 4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b...
current_hash: 09711beb10fee338fced10ec5fac2c8da1820e91fa15e1ac2be40d401a92dda9174c026ec53427ceded9369c791b3be4af74b03cbd1f8e5229368f91f0f75da3
---
```

#### Field Dictionary

| Field | Type | Required | Description |
|:---|:---|:---|:---|
| `bmd_version` | String | Yes | Protocol specification version (current: `2.1`). |
| `document_type` | String | Yes | Classification: `contract`, `declaration`, `license`, `invoice`, `agreement`. |
| `mode` | String | Yes | State of document: `draft` (mutable) or `transfer` (immutable sealed). |
| `jurisdiction` | String | Yes | Legal framework governing the agreement (e.g., `International`, `US - Delaware`). |
| `max_signatures` | Integer | Yes | Cap of valid signatures (`1` = unilateral, `2` = bilateral, `N` = multilateral). |
| `timestamp` | Integer | Yes | Unix epoch timestamp of creation or signing. |
| `public_key` | Hex (64) | On sign | 32-byte Ed25519 public key of primary signer (Emitter). Auto-computed on `:sign`. |
| `signature_layer_2` | Hex (128) | On sign | 64-byte Ed25519 digital signature of Emitter over the SHA-512 payload hash. Auto-computed. |
| `receiver_public_key` | Hex (64) | On cosign | 32-byte Ed25519 public key of co-signer (Receiver). Auto-computed on `:cosign`. |
| `receiver_signature` | Hex (128) | On cosign | 64-byte Ed25519 digital signature of Receiver. Auto-computed. |
| `current_hash` | Hex (128) | On sign | SHA-512 hash calculated strictly over the payload content. Auto-computed. |
| `previous_hash` | Hex (128) | Optional | SHA-512 hash of previous block (defaults to 64 zeros if omitted). |
| `block_id` | String | Optional | Optional legacy label; not required for integrity or identification. |

> [!NOTE]
> All cryptographic fields (`public_key`, `signature_layer_2`, `receiver_public_key`, `receiver_signature`, `current_hash`) are **computed automatically** by the engine. You never write these values manually.

---

### 4.2 Document Body & Button Directives

Content in a `.bmd` file is written using standard Markdown enhanced with semantic directives. These directives ensure consistent professional legal typography in both terminal letter-sheet rendering and HTML viewers:

#### Typography Tags (Legal Hierarchy)

| Tag | Terminal Rendering | HTML Rendering |
|:---|:---|:---|
| `<title>Text</title>` | Bold white, centered, UPPERCASE, `*** TITLE ***` | 28px / 800-weight, centered, uppercase |
| `<subtitle>Text</subtitle>` | Dimmed, centered, `-- Subtitle --` | 15px / 500-weight, muted |
| `<heading>Text</heading>` | Bold, centered, UPPERCASE, `=== HEADING ===` | 18px / 700-weight, uppercase |
| `<body>Text</body>` | Left-aligned, word-wrapped at 72 cols | 14px / 400-weight, justified |

Standard Markdown headings (`#`, `##`, `###`) also map to the same hierarchy automatically.

#### Structural Directives

| Directive | Purpose |
|:---|:---|
| `<bmd:sign_button>` | Emitter signature button. In preview: shows ASCII button frame (display only). In `bmd read` after compile: shows verified pubkey & status. Shortcut: `:add sign_button`. |
| `<bmd:cosign_button>` | Receiver co-signature button. Sets `max_signatures = 2` automatically. Shortcut: `:add cosign_button`. |
| `<bmd:rule>` | Double horizontal rule separator (`====================`) across the sheet. |
| `<bmd:rule single>` | Single horizontal rule separator (`--------------------`) across the sheet. |
| `<bmd:parties>` | Two-column table displaying Emitter & Receiver public keys side-by-side. |
| `<bmd:signatures>` | Verification panel showing Ed25519 signature statuses (`DIGITALLY SEALED` / `RATIFIED`). |
| `<bmd:seal>` | Cryptographic custody seal banner with verified SHA-512 integrity status. |

> [!IMPORTANT]
> **Signature buttons in `:preview` are display-only.** They render as ASCII framed boxes but do not execute any action. Only after `bmd compile` are buttons interactive when viewed with `bmd read`.

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
  bmd sign <file.bmd>                   Sign as Emitter (auto device key & SHA-512)
  bmd compile <file.bmd>                Compile, freeze to TRANSFER mode & seal disk
  bmd cosign <file.bmd>                 Receiver co-signs (auto device key)
  bmd lock <file.bmd>                   Apply OS read-only attribute to file

LEDGER AUDIT:
  bmd audit <b1.bmd> [b2.bmd ...]       Audit cryptographic chain of custody

EXPORTS & INTELLIGENT / INTELLECTUAL PROPERTY (IP):
  bmd render <file.bmd> [out.html]      Export standalone zero-dependency HTML viewer
  bmd --inject-property <dir> <bmd>     Inject IP (Intelligent Property) code bundle
  bmd --extract-property <bmd> [--out]  Extract & decrypt IP assets from block
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
- Renders `<bmd:sign_button>` and `<bmd:cosign_button>` as framed ASCII visual buttons showing real signature status.
- Renders `<title>` with ANSI bold-white centering, `<subtitle>` dimmed and centered, `<heading>` bold uppercase, `<body>` left-aligned word-wrapped.
```bash
bmd read contracts/service_agreement.bmd
# Or simply:
bmd contracts/service_agreement.bmd
```

#### `bmd verify <file.bmd>`
Performs an instant mathematical verification of the file:
1. Re-computes the SHA-512 hash of the payload text.
2. Compares against the frontmatter `current_hash`.
3. Validates the Emitter's Ed25519 signature against `public_key`.
4. If co-signed, validates the Receiver's signature against `receiver_public_key`.
- **Exit Code 0:** Authentic, verified, unmodified.
- **Exit Code 2:** Tamper detected or signature mismatch.

#### `bmd verify --json <file.bmd>`
Executes verification with structured JSON output for automated integrations and agent loops:
```bash
bmd verify --json contracts/service_agreement.bmd
```

#### `bmd inspect <file.bmd>`
Prints a complete forensic audit of the block's frontmatter, including timestamps, role definitions, signature capacity slots remaining, and an excerpt of the raw payload.

#### `bmd redact [file.bmd]`
Launches **BMD Redact Studio**, an in-terminal visual drafting application. Composes documents, inserts signature button directives, previews clean letter-sheets, and executes automated compile-and-sign workflows without leaving the terminal.

If no filename is provided, opens a blank document. If a `.bmd` filename is provided, loads it for editing (only if in `mode: draft`).

#### `bmd sign <file.bmd>`
Signs the document as Emitter in **`mode: draft`**:
- Automatically derives your authentic device identity key from `%USERPROFILE%\.bmd\emitter_device.key`.
- Computes the SHA-512 payload hash automatically.
- Attaches the Ed25519 public key and signature to the frontmatter.
- **Leaves the document in `mode: draft`** so additional clauses or buttons can still be added before sealing.

> [!NOTE]
> No manual seed or key input is required or accepted. The SHA-512 hash and Ed25519 signature are always computed from your device's authentic identity.

#### `bmd compile <file.bmd>`
The definitive sealing step:
- Plays the retro TrueColor purple pixel gradient loading bar animation across the terminal.
- Re-calculates the final SHA-512 ledger hash over the complete payload.
- Permanently sets `mode: transfer`.
- Applies the OS read-only filesystem lock attribute (`attrib +R`).
- **Prints the full absolute path of the compiled file** upon completion:
  ```
  File         : C:\Users\You\Documents\contracts\service_agreement.bmd
  SHA-512 Hash : 0d904b4870ec3b5d...
  Pubkey       : 3b6a27bcceb6a42d...
  Mode         : TRANSFER (IMMUTABLE SEALED)
  Disk Status  : Read-only locked (tamper-proof)
  ```

#### `bmd cosign <file.bmd>`
Executes counterparty co-signature on a compiled document:
- Checks that the document is already signed by the Emitter.
- Verifies that `max_signatures >= 2`.
- Automatically uses the counterparty device identity key from `%USERPROFILE%\.bmd\receiver_device.key`.
- Transitions the document status to **CONSENSUS RATIFIED**.

#### `bmd lock <file.bmd>`
Sets the OS-level read-only attribute on the file, preventing accidental modification by external editors. (`bmd compile` does this automatically; use `bmd lock` for manual control.)

#### `bmd audit <b1.bmd> [b2.bmd ...]`
Evaluates a chain of `.bmd` blocks in sequence, verifying that block $N$'s `previous_hash` equals block $N-1$'s `current_hash`.

#### `bmd render <file.bmd> [out.html]`
Compiles the `.bmd` file into a self-contained, zero-dependency standalone HTML5 viewer with embedded WebCrypto verification logic, proper legal typography (28px title vs 14px body), and print-ready stylesheet.

---

## 6. BMD Redact Studio (In-Terminal Visual Editor)

### 6.1 Studio Architecture & Interface

The Redact Studio provides an authoring environment directly inside standard Windows Command Prompt and PowerShell windows:

```text
  ================================================================================
   BMD REDACT STUDIO  |  contracts/nda.bmd  |  mode: DRAFT (MUTABLE)
  ================================================================================

  Frontmatter:
    type            : contract
    jurisdiction    : International / Open Standard
    max_signatures  : 2  (bilateral - requires Emitter + Receiver)
    emitter_sig     : [SIGNED]  pubkey: 3b6a27bcceb6a42d62a3a8d02a6f0d73653215771...
    receiver_sig    : [AWAITING CO-SIGNATURE]
    SHA-512 hash    : f0510a5105482fd03ceee936f0232031d0139149c44e797fb802891ee0e9e37c
                      8c9f80897931d957110850e647a9c0d7b520c9aba8821eb5391e1185091d7fb7

  Document  (6 lines):
  +--------+--------------------------------------------------------------------+
  |  Line  |  Content                                                           |
  +--------+--------------------------------------------------------------------+
  |      1 | <title>Mutual Non-Disclosure Agreement</title>                     |
  |      2 | <bmd:rule>                                                         |
  |      3 | <body>The parties agree to hold proprietary data confidential.</body>|
  |      4 | <bmd:sign_button>                                                  |
  |      5 | <bmd:cosign_button>                                                |
  |      6 | <bmd:seal>                                                         |
  +--------+--------------------------------------------------------------------+

  ================================================================================
  ACTIONS:
  +-----------------------------+  +-----------------------------+
  |  :sign                      |  |  :compile                   |
  |  Sign with auto device key  |  |  Retro purple loading bar   |
  |  (remains in DRAFT mode)    |  |  Freeze to IMMUTABLE mode   |
  +-----------------------------+  +-----------------------------+

  BUTTONS:  :add sign_button   :add cosign_button
  IP ASSET: :inject <path>     (encrypts folder & embeds into block)
  CONTENT:  :add <tag> text   :insert N <tag> text   :delete N   :set <field> <val>
  UTILITY:  :save [file]  :preview  :list  :verify  :render  :help  :quit
  ================================================================================

  redact> 
```

### 6.2 Interactive Button Directives & Action Bar

#### Signature Buttons in Preview vs. After Compile

Buttons render differently depending on the document state:

**In `:preview` (draft — display only, not functional):**
```
  |  +------------------------------------------------------------------+  |
  |  |  [ SIGN AS EMITTER ]   SHA-512 auto-computed  (run :sign)        |  |
  |  +------------------------------------------------------------------+  |
```
```
  |  +------------------------------------------------------------------+  |
  |  |  [ CO-SIGN AS RECEIVER ]  SHA-512 auto-computed  (run :cosign)   |  |
  |  +------------------------------------------------------------------+  |
```

**In `bmd read` after compile (functionally verified):**
```
  |  +-- [ BUTTON: SIGN AS EMITTER ] ----------------------------------------+ |
  |  | Status: DIGITALLY SEALED (Ed25519 Verified)                            | |
  |  | Pubkey: 3b6a27bcceb6a42d62a3a8d...                                     | |
  |  +------------------------------------------------------------------------+ |
```

#### Key Studio Actions
- **`:add sign_button`**: Appends `<bmd:sign_button>` to the document body.
- **`:add cosign_button`**: Appends `<bmd:cosign_button>` and automatically sets `max_signatures = 2`.
- **`:inject <path>`**: Injects and encrypts an IP codebase or directory directly into the current document without exiting the editor. The source folder is securely moved/destroyed (True Ownership Transfer), and the encrypted ChaCha20 bundle is embedded into the block.
- **`:extract [dir]`**: Decrypts and restores the IP bundle from the current document into the specified directory (defaults to `./extracted_ip`).
- **`:sign`**: Signs the draft as Emitter using your automatic device key. Remains in DRAFT mode.
- **`:compile`**: Plays the retro purple pixel loading bar, transitions to TRANSFER (IMMUTABLE), locks the file read-only on disk, and prints the full absolute path of the sealed file.
- **`:cosign`**: Signs as Receiver using the counterparty device key (only available if `max_signatures >= 2`).

> [!NOTE]
> If the document has no filename set when you run `:sign` or `:compile`, the studio will ask you for a filename interactively before proceeding. You do not need to run `:save` manually first.

### 6.3 In-Studio Command Dictionary

| Studio Command | Action |
|:---|:---|
| `:help` | Opens the full comprehensive reference manual and syntax examples. |
| `:add <tag> text` | Appends a new tagged line to the bottom of the document. |
| `:add sign_button` | Inserts the Emitter interactive signature button (`<bmd:sign_button>`). |
| `:add cosign_button` | Inserts the Receiver co-signature button (`<bmd:cosign_button>`) and sets `max_signatures = 2`. |
| `:insert <N> <tag> text` | Inserts a line before line number N (1-based index). |
| `:delete <N>` | Deletes line number N. |
| `:set <field> <value>` | Updates frontmatter field (`type`, `jurisdiction`, `max_signatures`). |
| `:preview` | Displays clean reading preview with rendered signature buttons and formatted text. |
| `:list` | Displays the complete document with continuous line numbering. |
| `:inject [path]` | Injects and encrypts IP codebase/folder directly into the document (no need to exit editor). |
| `:extract [dir]` | Extracts and decrypts IP codebase bundle from the document into target folder. |
| `:sign` | Computes SHA-512 hash automatically and signs as Emitter using auto device key (remains in DRAFT). |
| `:compile` | Plays retro purple animation, freezes to TRANSFER mode, locks file read-only, prints full file path. |
| `:cosign` | Receiver co-signs using auto device key (only available if `max_signatures >= 2`). |
| `:save [filename.bmd]` | Writes current buffer and metadata to disk. Optional before `:sign` or `:compile` — the studio auto-prompts if needed. |
| `:verify` | Performs an immediate cryptographic audit of the saved file. |
| `:render [out.html]` | Exports the document to a zero-dependency standalone HTML viewer. |
| `:read <file.bmd>` | Opens another `.bmd` file in the studio. |
| `:up` / `:down` / `:top` / `:bottom` | Scrolls the document view window. |
| `:quit` / `:q` | Exits the studio (warns if unsaved changes exist). |
| `:quit!` / `:q!` | Forces exit without saving. |

---

## 7. Operational Workflows & Real-World Scenarios

### Scenario A: Unilateral Declaration (Sole Author)
*Use case: Proof of authorship, copyright registration, public declaration.*

1. Open the studio:
   ```bash
   bmd redact my_declaration.bmd
   ```
2. Set metadata and content:
   ```text
   :set type declaration
   :set jurisdiction International
   :set max_signatures 1
   :add <title>Declaration of Software Authorship</title>
   :add <bmd:rule>
   :add <body>I hereby declare sole authorship of the enclosed codebase.</body>
   :add sign_button
   :add <bmd:seal>
   ```
3. Sign and compile (no manual `:save` needed first):
   ```text
   :sign
   :compile
   ```
   *Result:* The document is cryptographically sealed with the author's device key and permanently locked in TRANSFER mode. The full file path is displayed on screen.

---

### Scenario B: Bilateral Commercial Agreement (Dual-Party Ratification)
*Use case: Service contracts, NDAs, partnership agreements.*

1. **Party A (Emitter) drafts, signs, and compiles:**
   ```text
   bmd redact service_agreement.bmd
   :set type contract
   :set max_signatures 2
   :add <title>Master Engineering Agreement</title>
   :add <subtitle>Between Protocol Core and Client LLC</subtitle>
   :add <bmd:rule>
   :add <heading>1. Terms</heading>
   :add <body>Provider agrees to maintain cryptographic core infrastructure.</body>
   :add sign_button
   :add cosign_button
   :add <bmd:signatures>
   :add <bmd:seal>
   :sign
   :compile
   ```
   *Result:* Document is compiled into TRANSFER mode. Party A sees the absolute path of the sealed file.

2. **Transmission:**
   Party A sends `service_agreement.bmd` to Party B.

3. **Party B (Receiver) validates and co-signs:**
   ```bash
   # Party B verifies Party A's signature:
   bmd verify service_agreement.bmd

   # Party B co-signs with their device key:
   bmd cosign service_agreement.bmd
   ```
   *Result:* Document is now **CONSENSUS RATIFIED** with both signatures mathematically embedded.

---

### Scenario C: Intelligent Property (IP) Escrow & Registration
*(Nota: En este contexto, **IP** se refiere exclusivamente a **Intelligent / Intellectual Property (Propiedad Intelectual)** y nunca a una dirección IP de red).*
*Use case: Sealing proprietary algorithms, models, or confidential codebases.*

#### Method 1: 100% In-Studio Workflow (Recommended — Zero Context Switching)
You can draft the contract, inject the codebase, sign, compile, and extract all from within Redact Studio without ever exiting or typing the filename repeatedly:

```text
# 1. Open the studio with your target document:
bmd redact ai_model_escrow.bmd

# 2. Add metadata and legal clauses:
:set type ip_assignment
:add <title>PROPRIETARY AI MODEL ESCROW & ASSIGNMENT</title>
:add <body>The source code bundle encrypted in this block is assigned to the recipient.</body>
:add sign_button
:add <bmd:seal>

# 3. Inject the IP codebase directly (moves source folder into block & encrypts with ChaCha20):
:inject ./src/ai_model

# 4. Sign as Emitter (auto device key & SHA-512 over payload + bundle):
:sign

# 5. Compile to TRANSFER mode (retro purple animation, locks disk read-only):
:compile

# 6. (Optional) Test-extract and verify the code directly inside the studio:
:extract ./extracted_model

# 7. Exit editor when finished:
:quit
```

#### Method 2: Command Line Batch Workflow
For CI/CD pipelines, automated agents, or terminal scripting:

```bash
# 1. Package and encrypt source folder into a BMD container (destroys source on disk):
bmd --inject-property ./src/ai_model ./contracts/ai_model_ip.bmd

# 2. Sign and lock the asset (auto device key, no manual seed):
bmd sign ./contracts/ai_model_ip.bmd
bmd compile ./contracts/ai_model_ip.bmd

# 3. Third parties verify the integrity of the asset:
bmd verify ./contracts/ai_model_ip.bmd

# 4. Decrypt and restore the source code to a destination folder:
bmd --extract-property ./contracts/ai_model_ip.bmd --out ./restored_code
```

---

### Scenario D: Corporate Invoice & Ledger Record
*Use case: Immutable financial records, invoice chains.*

```bash
# 1. Create the invoice document
bmd redact invoice_001.bmd
# (set type invoice, add content, add sign_button)
:sign
:compile

# 2. Create a chained follow-up record linking to the previous hash
bmd redact invoice_002.bmd
# (use bmd inspect invoice_001.bmd to get its current_hash, then link via previous_hash)
:sign
:compile

# 3. Audit the chain integrity
bmd audit invoice_001.bmd invoice_002.bmd
```

---

## 8. C11 Native Core Engine Architecture

### 8.1 Library Components
- **`bmd_crypto.c`**: Pure C implementation of Ed25519 (curve25519 operations, scalar multiplication, SHA-512 digests) and ChaCha20 stream cipher.
- **`bmd_parser.c`**: Streaming tokenizer and parser for YAML frontmatter and payload lines. Handles UTF-8 BOM, CRLF, and all frontmatter fields.
- **`bmd_engine.c`**: Lifecycle governance (`bmd_parse_file`, `bmd_transition_to_transfer`, `bmd_sign_document`, `bmd_cosign_receiver`, `bmd_verify_document`, `bmd_save_file`).
- **`bmd_ledger.c`**: Multi-block chain verification and Merkle tree generation for IP asset bundles.
- **`bmd_main.c`**: High-performance CLI interface, ANSI color banner, retro purple loading bar, in-terminal Redact Studio, typography helpers, and device identity key management.
- **`bmd_viewer_generator.py`**: Zero-dependency standalone HTML generator. Produces a fully self-contained `.html` viewer with embedded WebCrypto, legal CSS typography hierarchy, and print stylesheet.

### 8.2 Compiling & Running Native Unit Tests
To build the engine DLL and CLI binary on Windows using Microsoft Visual C++:

```cmd
cd bmd_engine
build_full.bat
```

The build script automatically:
1. Compiles `bmd_engine.dll` (shared library).
2. Compiles and executes `test_engine.exe` running 5 comprehensive C11 unit tests (SHA-256, SHA-512, Ed25519, ChaCha20, BMD document lifecycle + tamper detection).
3. Compiles `bmd.exe` and installs it to `%LOCALAPPDATA%\Microsoft\WindowsApps\` for global system access.

Expected output on success:
```
[SUCCESS] ALL NATIVE C11 TESTS PASSED WITH 100% INTEGRITY!
```

---

## 9. Enterprise Best Practices & Security Advisory

1. **Deterministic Device Keys:** Ensure `%USERPROFILE%\.bmd\` is backed up if persistent device identity across OS reinstalls is required. Losing this directory means future signing will generate a new identity key.

2. **Canonical Authority:** Always treat the `.bmd` file as the primary source of truth. If a dispute arises, verify the `.bmd` file with `bmd verify <file.bmd>`. HTML representations and terminal renders are strictly for human reading convenience.

3. **Draft Before Sealing:** Use `bmd sign` (or `:sign`) while drafting to authenticate without freezing. Execute `bmd compile` (or `:compile`) only when all terms and button directives are finalized. Once compiled, no modification is possible.

4. **Verify Before Co-Signing:** Party B should always run `bmd verify <file.bmd>` before executing `bmd cosign`, confirming that Party A's signature is authentic and the content is unaltered.

5. **Offline Independence:** The `bmd` runtime requires zero internet connection, cloud APIs, or external servers. All cryptographic calculations take place locally on the host machine.

6. **File Path Tracking:** After each `bmd compile`, the engine prints the full absolute path of the sealed file. Keep this path as the canonical record locator for the document.

7. **Bilateral `max_signatures`:** For any contract between two parties, always set `max_signatures: 2` and include both `:add sign_button` and `:add cosign_button` in the document body so both signatures are visually represented and cryptographically enforced.
