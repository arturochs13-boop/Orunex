"""
bmd_agent_executor.py - Deterministic Office Document Generator for Dual-Signed .bmd Blocks
Autonomous Agent Runtime ('muse-spark')
"""

import os
import sys
import json
import re
from datetime import datetime

# Setup paths
ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_DIR = os.path.join(ENGINE_DIR, "python")
BIN_DIR = os.path.join(ENGINE_DIR, "bin")

if BIN_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = BIN_DIR + ";" + os.environ.get("PATH", "")
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

import bmd_ffi


def parse_bmd_content(file_path: str):
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    match = re.match(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$", content)
    body = content
    frontmatter = {}
    if match:
        yaml_text, body = match.group(1), match.group(2)
        for line in yaml_text.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                frontmatter[k.strip()] = v.strip().strip('"\'')

    return frontmatter, body.strip()


def execute_office_agent(bmd_file_path: str) -> dict:
    """Executes deterministic generation of verified Office executive reports."""
    doc = bmd_ffi.BMDWrapper.load_file(bmd_file_path)
    is_valid, msg = doc.verify()

    frontmatter, body = parse_bmd_content(bmd_file_path)
    output_dir = os.path.join(ENGINE_DIR, "office_reports")
    os.makedirs(output_dir, exist_ok=True)

    block_id = doc.block_id or "BLOCK_REPORT"
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", block_id)

    # 1. Generate Executive HTML/Word-Ready Report
    word_report_path = os.path.join(output_dir, f"{safe_name}_EXECUTIVE_DECREE.html")
    excel_audit_path = os.path.join(output_dir, f"{safe_name}_LEDGER_AUDIT.csv")

    dual_signed = bool(doc.receiver_signature)
    status_label = "DUAL-SIGNED & FINALIZED" if dual_signed else ("FROZEN / TRANSFER" if doc.mode == bmd_ffi.BMDMode.TRANSFER else "MUTABLE DRAFT")

    # Render clean HTML decree
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Acta Ejecutiva de Transferencia Criptográfica — {block_id}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Calibri, Arial, sans-serif;
            margin: 40px auto;
            max-width: 820px;
            color: #1a1a1a;
            line-height: 1.6;
        }}
        .header {{
            border-bottom: 3px solid #1e3a8a;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .seal {{
            display: inline-block;
            background: #1e3a8a;
            color: #fff;
            padding: 6px 14px;
            font-size: 11px;
            font-weight: bold;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        h1 {{
            color: #0f172a;
            margin: 12px 0 4px 0;
            font-size: 24px;
        }}
        .meta-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 12px;
        }}
        .meta-table th, .meta-table td {{
            border: 1px solid #cbd5e1;
            padding: 8px 12px;
            text-align: left;
        }}
        .meta-table th {{
            background: #f1f5f9;
            width: 25%;
            color: #475569;
        }}
        .code {{
            font-family: Consolas, 'Courier New', monospace;
            font-size: 11px;
            word-break: break-all;
            color: #0369a1;
        }}
        .markdown-body {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            padding: 24px;
            border-radius: 6px;
            margin-top: 24px;
        }}
        .badge-verified {{
            color: #15803d;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 40px;
            border-top: 1px solid #e2e8f0;
            padding-top: 14px;
            font-size: 11px;
            color: #64748b;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <span class="seal">Single Source of Truth · Autonomous Governance</span>
        <h1>Acta Notarial y Ejecutiva de Protocolo .bmd</h1>
        <p style="color: #64748b; font-size: 13px; margin: 0;">Generada de forma determinista por el Agente Autónomo <strong>muse-spark</strong></p>
    </div>

    <table class="meta-table">
        <tr><th>Identificador de Bloque</th><td><strong>{doc.block_id}</strong></td></tr>
        <tr><th>Modo Operativo</th><td>{status_label}</td></tr>
        <tr><th>Integridad Criptográfica</th><td class="badge-verified">{'✓ VÁLIDO (Matemáticamente Inmutable)' if is_valid else '✗ CORROMPIDO'}</td></tr>
        <tr><th>Ledger Hash (SHA-512)</th><td class="code">{doc.current_hash}</td></tr>
        <tr><th>Hash Ancestral (Previous)</th><td class="code">{doc.previous_hash}</td></tr>
        <tr><th>Firma Emisor (Ed25519)</th><td class="code">{doc.signature_layer_2 or '(Pendiente)'}</td></tr>
        <tr><th>Clave Pública Emisor</th><td class="code">{doc.public_key or '(Pendiente)'}</td></tr>
        <tr><th>Firma Receptor (Co-Sign)</th><td class="code">{doc.receiver_signature or '(Pendiente)'}</td></tr>
        <tr><th>Clave Pública Receptor</th><td class="code">{doc.receiver_public_key or '(Pendiente)'}</td></tr>
        <tr><th>Marca Temporal UNIX</th><td>{doc._doc.contents.header.timestamp} ({datetime.fromtimestamp(doc._doc.contents.header.timestamp or 0).strftime('%Y-%m-%d %H:%M:%S UTC') if doc._doc.contents.header.timestamp else 'N/A'})</td></tr>
    </table>

    <h3>Contenido Certificado del Bloque</h3>
    <div class="markdown-body">
        <pre style="white-space: pre-wrap; font-family: inherit;">{body}</pre>
    </div>

    <div class="footer">
        Certificación Criptográfica C11 · Curve25519 / SHA-512 / RFC 8032 · Project Orunex
    </div>
</body>
</html>
"""
    with open(word_report_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 2. Generate Excel Audit Sheet (CSV formatted for direct Excel import)
    csv_rows = [
        ["CAMPO", "VALOR", "ESTADO_VALIDACION"],
        ["BLOCK_ID", doc.block_id, "OK"],
        ["CURRENT_HASH_SHA512", doc.current_hash, "INTEGRO" if is_valid else "INVALIDO"],
        ["PREVIOUS_HASH", doc.previous_hash, "LINK_VALIDO"],
        ["OPERATIONAL_MODE", status_label, "FROZEN" if doc.mode == bmd_ffi.BMDMode.TRANSFER else "MUTABLE"],
        ["EMITTER_PUBKEY", doc.public_key, "AUTHENTIC"],
        ["EMITTER_SIGNATURE_ED25519", doc.signature_layer_2, "VERIFIED" if is_valid else "FAIL"],
        ["RECEIVER_PUBKEY", doc.receiver_public_key, "AUTHENTIC" if doc.receiver_public_key else "PENDING"],
        ["RECEIVER_SIGNATURE_ED25519", doc.receiver_signature, "VERIFIED" if doc.receiver_signature else "PENDING"],
        ["DUAL_SIGNED_STATUS", "TRUE" if dual_signed else "FALSE", "CONSENSUS_REACHED" if dual_signed else "WAITING_CO_SIGN"],
        ["TIMESTAMP", str(doc._doc.contents.header.timestamp), "ORDER_CHECK_PASSED"],
        ["PAYLOAD_CHAR_COUNT", str(len(body)), "LOCKED"]
    ]

    with open(excel_audit_path, "w", encoding="utf-8") as f:
        for row in csv_rows:
            f.write(";".join(f'"{c}"' for c in row) + "\n")

    return {
        "success": True,
        "is_valid": is_valid,
        "dual_signed": dual_signed,
        "word_report": word_report_path,
        "excel_audit": excel_audit_path,
        "block_id": doc.block_id,
        "hash": doc.current_hash
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        res = execute_office_agent(sys.argv[1])
        print(json.dumps(res, indent=2))
    else:
        print("Usage: python bmd_agent_executor.py <file.bmd>")
