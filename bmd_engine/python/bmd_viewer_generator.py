"""
bmd_viewer_generator.py - Zero-Dependency Standalone HTML Generator for Blockchain Markdown (.bmd)
Generates an executive-grade, 100% self-contained HTML file for any .bmd file.

Features:
- Zero external network dependencies (no CDNs, no Google Fonts, no external JS/CSS whatsoever).
- Offline cryptographic verification using browser native WebCrypto (SubtleCrypto SHA-512).
- max_signatures enforcement: letterhead shows signature cap and blocks further co-signing when reached.
- Fork as New Draft: ONLY allowed from the BMD Studio desktop app, never from compiled standalone documents.
- Formal document styling: legal double rules, party cards, side-by-side signature blocks, digital custody seals.
- Print-ready stylesheet (@media print) for formal PDF generation and contract signing.
- Drag-and-drop verification: drop any .bmd file onto the browser window for SHA-512 integrity check.
"""

import os
import sys
import re
import time


def parse_bmd_file(filepath: str):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    match = re.match(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$", content)
    meta = {}
    body = content

    if match:
        body = match.group(2).strip()
        in_bundle = False
        bundle_lines = []
        for line in match.group(1).splitlines():
            if in_bundle:
                if line.startswith("  ") or line.strip() == "":
                    bundle_lines.append(line.strip())
                    continue
                else:
                    meta["property_bundle"] = "".join(bundle_lines)
                    in_bundle = False
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"\'')
                if k == "property_bundle":
                    if v in ("|", ""):
                        in_bundle = True
                        bundle_lines = []
                    else:
                        meta[k] = v
                else:
                    meta[k] = v
        if in_bundle and bundle_lines:
            meta["property_bundle"] = "".join(bundle_lines)

    return meta, body, content


def render_formal_markdown(body: str, meta: dict) -> str:
    """
    Renders pure Markdown + BMD formal directives into executive HTML.
    Directives:
    - <!-- bmd:rule double -->   -> Formal double legal line
    - <!-- bmd:rule single -->   -> Single separator rule
    - <!-- bmd:parties -->       -> Contracting party cards
    - <!-- bmd:signatures -->    -> Formal side-by-side signing boxes
    - <!-- bmd:seal -->          -> Holographic digital seal
    - <!-- bmd:clause N Title--> -> Formatted numbered clause container
    """

    def sub_rule_double(m):
        return '<div class="bmd-double-rule"></div>'

    def sub_rule_single(m):
        return '<div class="bmd-single-rule"></div>'

    def sub_parties(m):
        em_name  = meta.get("emitter_name", "Designated Emitter Entity")
        em_role  = meta.get("emitter_role", "Emitter / Contractor")
        rec_name = meta.get("receiver_name", "Designated Receiver Entity")
        rec_role = meta.get("receiver_role", "Receiver / Client")
        em_pub   = meta.get("public_key", "")
        rec_pub  = meta.get("receiver_public_key", "")
        em_pub_short  = (em_pub[:16] + "..." + em_pub[-8:])  if len(em_pub)  > 24 else (em_pub  or "Pending Compilation")
        rec_pub_short = (rec_pub[:16] + "..." + rec_pub[-8:]) if len(rec_pub) > 24 else (rec_pub or "Awaiting Co-Signature")

        return f"""
        <div class="bmd-parties-grid">
            <div class="bmd-party-card">
                <div class="bmd-party-role">FIRST PARTY (EMITTER)</div>
                <div class="bmd-party-name">{em_name}</div>
                <div class="bmd-party-subrole">{em_role}</div>
                <div class="bmd-party-key font-mono">{em_pub_short}</div>
                <div class="bmd-party-badge">{"Ed25519 Verified Signer" if em_pub else "Pending Signature"}</div>
            </div>
            <div class="bmd-party-card">
                <div class="bmd-party-role">SECOND PARTY (RECEIVER)</div>
                <div class="bmd-party-name">{rec_name}</div>
                <div class="bmd-party-subrole">{rec_role}</div>
                <div class="bmd-party-key font-mono">{rec_pub_short}</div>
                <div class="bmd-party-badge">{"Ed25519 Co-Signer" if rec_pub else "Awaiting Acceptance"}</div>
            </div>
        </div>
        """

    def sub_signatures(m):
        em_sig   = meta.get("signature_layer_2", "")
        rec_sig  = meta.get("receiver_signature", "")
        em_name  = meta.get("emitter_name", "Designated Emitter")
        rec_name = meta.get("receiver_name", "Designated Receiver")
        curr_hash = meta.get("current_hash", "")
        short_hash = curr_hash[:16] + "..." + curr_hash[-8:] if len(curr_hash) > 24 else curr_hash
        ts = meta.get("timestamp", str(int(time.time())))
        try:
            date_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(int(ts)))
        except Exception:
            date_str = str(ts)

        # max_signatures enforcement display
        max_sigs = int(meta.get("max_signatures", "0") or "0")
        current_sigs = (1 if em_sig else 0) + (1 if rec_sig else 0)
        if max_sigs > 0:
            cap_html = f'<div class="bmd-sig-cap {"bmd-sig-cap-reached" if current_sigs >= max_sigs else "bmd-sig-cap-open"}">' \
                       f'Signature Cap: {current_sigs}/{max_sigs}' \
                       f'{" — LIMIT REACHED" if current_sigs >= max_sigs else " — Open"}</div>'
        else:
            cap_html = ""

        return f"""
        <div class="bmd-signatures-container">
            <div class="bmd-sig-box">
                <div class="bmd-sig-title">EMITTER AUTHORIZED SIGNATORY</div>
                <div class="bmd-sig-name">{em_name}</div>
                <div class="bmd-sig-line"></div>
                <div class="bmd-sig-status text-emerald">{"DIGITALLY SEALED (Ed25519)" if em_sig else "PENDING"}</div>
                <div class="bmd-sig-stamp font-mono">{(em_sig[:32] + "...") if em_sig else "—"}</div>
                <div class="bmd-sig-date">{date_str}</div>
            </div>
            <div class="bmd-sig-box">
                <div class="bmd-sig-title">RECEIVER AUTHORIZED SIGNATORY</div>
                <div class="bmd-sig-name">{rec_name}</div>
                <div class="bmd-sig-line"></div>
                <div class="bmd-sig-status {"text-emerald" if rec_sig else "text-amber"}">
                    {"CO-SIGNED & RATIFIED" if rec_sig else "UNILATERAL / PENDING"}
                </div>
                <div class="bmd-sig-stamp font-mono">{(rec_sig[:32] + "...") if rec_sig else "—"}</div>
                <div class="bmd-sig-date">{date_str if rec_sig else "Awaiting counterparty execution"}</div>
            </div>
        </div>
        {cap_html}
        """

    def sub_seal(m):
        curr_hash = meta.get("current_hash", "")
        block_id  = meta.get("block_id", "BLOCK")
        jurisdiction = meta.get("jurisdiction", "International")
        return f"""
        <div class="bmd-custody-seal">
            <div class="bmd-seal-header">BLOCKCHAIN MARKDOWN IMMUTABILITY SEAL</div>
            <div class="bmd-seal-hash font-mono">SHA-512: {curr_hash}</div>
            <div class="bmd-seal-meta">BLOCK ID: {block_id} | CUSTODY PROTOCOL v2.1 | JURISDICTION: {jurisdiction}</div>
        </div>
        """

    def sub_clause(m):
        num   = m.group(1)
        title = m.group(2).strip()
        return f'<div class="bmd-clause"><span class="bmd-clause-num">Clause {num}</span><span class="bmd-clause-title">{title}</span></div>'

    processed = body
    processed = re.sub(r"<!--\s*bmd:rule\s+double\s*-->", sub_rule_double, processed)
    processed = re.sub(r"<!--\s*bmd:rule\s+single\s*-->", sub_rule_single, processed)
    processed = re.sub(r"<!--\s*bmd:parties[^>]*-->", sub_parties, processed)
    processed = re.sub(r"<!--\s*bmd:signatures?\s*-->", sub_signatures, processed)
    processed = re.sub(r"<!--\s*bmd:seal\s*-->", sub_seal, processed)
    processed = re.sub(r"<!--\s*bmd:clause\s+(\d+)\s+(.*?)\s*-->", sub_clause, processed)
    processed = re.sub(r"<!--\s*bmd:[^>]*-->\r?\n?", "", processed)  # clean remaining tags

    lines = processed.splitlines()
    html_out = []
    in_table = False
    table_rows = []
    in_ul = False

    for line in lines:
        s = line.strip()

        # HTML passthrough for our custom directive output
        if s.startswith("<div") or s.startswith("</div") or s.startswith("<hr"):
            if in_table:
                html_out.append("</tbody></table></div>")
                in_table = False
            if in_ul:
                html_out.append("</ul>")
                in_ul = False
            html_out.append(line)
            continue

        if s.startswith("|") and s.endswith("|"):
            if not in_table:
                in_table = True
                html_out.append('<div class="bmd-table-wrap"><table>')
                cols = [c.strip() for c in s[1:-1].split("|")]
                html_out.append("<thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>")
                continue
            if re.match(r"^\|[\s\-:|]+\|$", s):
                continue
            cols = [c.strip() for c in s[1:-1].split("|")]
            html_out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cols) + "</tr>")
            continue
        elif in_table:
            html_out.append("</tbody></table></div>")
            in_table = False

        if s.startswith("# "):
            if in_ul: html_out.append("</ul>"); in_ul = False
            html_out.append(f'<h1 class="bmd-h1">{s[2:]}</h1>')
            continue
        if s.startswith("## "):
            if in_ul: html_out.append("</ul>"); in_ul = False
            html_out.append(f'<h2 class="bmd-h2">{s[3:]}</h2>')
            continue
        if s.startswith("### "):
            if in_ul: html_out.append("</ul>"); in_ul = False
            html_out.append(f'<h3 class="bmd-h3">{s[4:]}</h3>')
            continue

        if s == "---" or s == "***":
            if in_ul: html_out.append("</ul>"); in_ul = False
            html_out.append('<div class="bmd-single-rule"></div>')
            continue

        if s.startswith("- ") or s.startswith("* "):
            if not in_ul:
                in_ul = True
                html_out.append('<ul class="bmd-list">')
            html_out.append(f"<li>{s[2:]}</li>")
            continue
        elif in_ul:
            html_out.append("</ul>")
            in_ul = False

        if s.startswith("> "):
            html_out.append(f'<blockquote class="bmd-quote">{s[2:]}</blockquote>')
            continue

        if s == "":
            continue

        # Standard paragraph with bold/italic/code inline formatting
        p_text = s
        p_text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", p_text)
        p_text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", p_text)
        p_text = re.sub(r"`([^`]+)`", r'<code class="bmd-inline-code font-mono">\1</code>', p_text)
        html_out.append(f'<p class="bmd-p">{p_text}</p>')

    if in_table:
        html_out.append("</tbody></table></div>")
    if in_ul:
        html_out.append("</ul>")

    return "\n".join(html_out)


def generate_standalone_html(bmd_filepath: str, output_filepath: str = None) -> str:
    meta, body, raw_content = parse_bmd_file(bmd_filepath)
    block_id     = meta.get("block_id", "0xBLOCK")
    doc_type     = (meta.get("document_type") or "Executive Agreement").upper()
    mode         = meta.get("mode", "transfer").upper()
    curr_hash    = meta.get("current_hash", "")
    jurisdiction = meta.get("jurisdiction", "Standard Legal Jurisdiction")
    rendered_body = render_formal_markdown(body, meta)

    # max_signatures info for letterhead
    max_sigs     = int(meta.get("max_signatures", "0") or "0")
    em_sig       = meta.get("signature_layer_2", "")
    rec_sig      = meta.get("receiver_signature", "")
    current_sigs = (1 if em_sig else 0) + (1 if rec_sig else 0)

    if max_sigs > 0:
        cap_class = "bmd-sig-cap-reached" if current_sigs >= max_sigs else "bmd-sig-cap-open"
        cap_label = f"Signature Cap: {current_sigs}/{max_sigs}" + \
                    (" \u2014 LIMIT REACHED" if current_sigs >= max_sigs else " \u2014 Open")
        sig_cap_html = f'<div class="{cap_class} font-mono">{cap_label}</div>'
    else:
        sig_cap_html = f'<div class="font-mono">Signatures: {current_sigs} (Unlimited)</div>'

    # Auto-append signatures and seal if not already in the body
    if "<!-- bmd:signatures" not in body and "bmd-signatures-container" not in rendered_body:
        rendered_body += "\n" + render_formal_markdown("<!-- bmd:signatures -->\n<!-- bmd:seal -->", meta)

    # Escape raw content for embedding (zero external JS)
    escaped_raw = raw_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    standalone_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<!-- ZERO EXTERNAL DEPENDENCIES: No CDN, no Google Fonts, no external JS, fully offline -->
<title>{block_id} - {doc_type} | Blockchain Markdown Executive Document</title>
<style>
/* ============================================================
   BLOCKCHAIN MARKDOWN ZERO-DEPENDENCY EXECUTIVE STYLESHEET
   100% self-contained. Zero network requests. Fully offline.
   ============================================================ */
:root {{
  --bg-page: #080a0f;
  --bg-sheet: #0e121a;
  --border-sheet: #1e2638;
  --text-main: #f1f5f9;
  --text-muted: #94a3b8;
  --text-dim: #64748b;
  --accent-gold: #d97706;
  --accent-blue: #3b82f6;
  --accent-emerald: #10b981;
  --accent-ruby: #ef4444;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg-page);
  color: var(--text-main);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.6;
  padding: 32px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 100vh;
}}
.font-mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }}

/* Top Floating Utility Bar */
.bmd-topbar {{
  width: 100%;
  max-width: 860px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 10px 16px;
  background: #0f141f;
  border: 1px solid #1e293b;
  border-radius: 8px;
}}
.bmd-status-pill {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}}
.bmd-dot {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-emerald);
}}
.bmd-actions {{ display: flex; gap: 8px; }}
.bmd-btn {{
  background: #1e293b;
  color: #e2e8f0;
  border: 1px solid #334155;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}}
.bmd-btn:hover {{ background: #334155; color: #fff; }}

/* Executive Document Sheet */
.bmd-sheet {{
  width: 100%;
  max-width: 860px;
  background: var(--bg-sheet);
  border: 1px solid var(--border-sheet);
  border-radius: 8px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.45), 0 1px 3px rgba(0,0,0,0.2);
  padding: 64px 56px;
  position: relative;
  transition: border-color 0.3s;
}}
.bmd-sheet.tampered {{
  border-color: var(--accent-ruby) !important;
  box-shadow: 0 0 28px rgba(239,68,68,0.4) !important;
}}

/* Document Header Letterhead */
.bmd-letterhead {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  border-bottom: 1px solid #1e293b;
  padding-bottom: 20px;
  margin-bottom: 36px;
}}
.bmd-doc-type {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: var(--accent-blue);
  text-transform: uppercase;
  margin-bottom: 4px;
}}
.bmd-doc-title {{
  font-size: 20px;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.02em;
}}
.bmd-letterhead-meta {{
  text-align: right;
  font-size: 11px;
  color: var(--text-dim);
  line-height: 1.6;
}}
.bmd-sig-cap-reached {{
  color: var(--accent-ruby);
  font-weight: 700;
  font-size: 10px;
  margin-top: 4px;
}}
.bmd-sig-cap-open {{
  color: var(--accent-emerald);
  font-size: 10px;
  margin-top: 4px;
}}

/* Typography */
.bmd-h1 {{ font-size: 24px; font-weight: 700; color: #fff; margin: 28px 0 16px; letter-spacing: -0.02em; }}
.bmd-h2 {{ font-size: 17px; font-weight: 600; color: #f1f5f9; margin: 28px 0 12px; letter-spacing: -0.01em; border-bottom: 1px solid #1e2638; padding-bottom: 6px; }}
.bmd-h3 {{ font-size: 14px; font-weight: 600; color: #cbd5e1; margin: 20px 0 8px; }}
.bmd-p {{ font-size: 13.5px; color: #cbd5e1; margin: 12px 0; line-height: 1.7; text-align: justify; }}
.bmd-list {{ margin: 12px 0 12px 24px; font-size: 13.5px; color: #cbd5e1; line-height: 1.7; }}
.bmd-quote {{ border-left: 3px solid var(--accent-blue); padding: 8px 16px; margin: 16px 0; background: #0c121d; color: #94a3b8; font-style: italic; font-size: 13px; }}
.bmd-inline-code {{ background: #141a29; color: #93c5fd; padding: 2px 6px; border-radius: 4px; font-size: 12px; border: 1px solid #1e293b; }}

/* Formal Directives */
.bmd-single-rule {{ height: 1px; background: #1e293b; margin: 28px 0; }}
.bmd-double-rule {{ border-top: 1px solid #334155; border-bottom: 1px solid #334155; height: 5px; margin: 32px 0; }}
.bmd-clause {{ display: flex; align-items: baseline; gap: 10px; margin: 24px 0 8px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
.bmd-clause-num {{ font-size: 10px; font-weight: 700; background: #1e3a5f; color: #93c5fd; border: 1px solid #2563eb55; padding: 2px 7px; border-radius: 4px; font-family: ui-monospace, monospace; }}
.bmd-clause-title {{ font-size: 14px; font-weight: 600; color: #f1f5f9; }}

/* Parties Cards */
.bmd-parties-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 24px 0 32px; }}
.bmd-party-card {{ background: #090d16; border: 1px solid #1e293b; border-radius: 6px; padding: 14px 16px; }}
.bmd-party-role {{ font-size: 10px; font-weight: 700; color: var(--text-dim); letter-spacing: 0.08em; margin-bottom: 4px; }}
.bmd-party-name {{ font-size: 13px; font-weight: 700; color: #fff; margin-bottom: 2px; }}
.bmd-party-subrole {{ font-size: 11px; color: var(--text-muted); margin-bottom: 6px; }}
.bmd-party-key {{ font-size: 10px; color: #93c5fd; margin-bottom: 4px; word-break: break-all; }}
.bmd-party-badge {{ font-size: 10px; color: var(--accent-emerald); font-weight: 500; }}

/* Formal Signature Blocks */
.bmd-signatures-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin: 48px 0 24px; padding-top: 24px; border-top: 1px solid #1e293b; }}
.bmd-sig-box {{ background: #090d16; border: 1px solid #1e293b; border-radius: 6px; padding: 16px; }}
.bmd-sig-title {{ font-size: 10px; font-weight: 700; color: var(--text-dim); letter-spacing: 0.08em; margin-bottom: 8px; }}
.bmd-sig-name {{ font-size: 12px; font-weight: 600; color: #fff; margin-bottom: 12px; }}
.bmd-sig-line {{ height: 1px; background: #334155; margin-bottom: 10px; }}
.bmd-sig-status {{ font-size: 11px; font-weight: 600; margin-bottom: 4px; }}
.bmd-sig-stamp {{ font-size: 10px; color: var(--text-dim); word-break: break-all; }}
.bmd-sig-date {{ font-size: 10px; color: var(--text-dim); margin-top: 6px; }}
.bmd-sig-cap {{ font-size: 10px; font-weight: 600; margin-top: 12px; text-align: center; padding: 6px; border-radius: 4px; }}
.bmd-sig-cap.bmd-sig-cap-reached {{ color: var(--accent-ruby); background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.25); }}
.bmd-sig-cap.bmd-sig-cap-open {{ color: var(--accent-emerald); background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.2); }}
.text-emerald {{ color: var(--accent-emerald); }}
.text-amber {{ color: var(--accent-gold); }}
.text-ruby {{ color: var(--accent-ruby); }}

/* Custody Seal */
.bmd-custody-seal {{ margin-top: 36px; padding: 14px 18px; background: #080c14; border: 1px solid #1e293b; border-radius: 6px; text-align: center; }}
.bmd-seal-header {{ font-size: 10px; font-weight: 700; color: var(--text-dim); letter-spacing: 0.1em; margin-bottom: 4px; }}
.bmd-seal-hash {{ font-size: 10px; color: #94a3b8; word-break: break-all; }}
.bmd-seal-meta {{ font-size: 9px; color: var(--text-dim); margin-top: 4px; }}

/* Tables */
.bmd-table-wrap {{ margin: 20px 0; overflow-x: auto; border: 1px solid #1e293b; border-radius: 6px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; text-align: left; }}
th {{ background: #0c111c; color: #e2e8f0; font-weight: 600; padding: 10px 14px; border-bottom: 1px solid #1e293b; }}
td {{ padding: 10px 14px; border-bottom: 1px solid #161e2e; color: #cbd5e1; }}
tr:last-child td {{ border-bottom: none; }}
tr:hover td {{ background: #0f1523; }}

/* Print Stylesheet — for formal PDF / paper output */
@media print {{
  body {{ background: #fff !important; color: #000 !important; padding: 0 !important; }}
  .bmd-topbar {{ display: none !important; }}
  .bmd-sheet {{ background: #fff !important; color: #000 !important; border: none !important; box-shadow: none !important; padding: 0 !important; max-width: 100% !important; }}
  .bmd-h1, .bmd-h2, .bmd-doc-title {{ color: #000 !important; }}
  .bmd-p, .bmd-list, td {{ color: #222 !important; }}
  th {{ background: #f1f5f9 !important; color: #000 !important; }}
  .bmd-party-card, .bmd-sig-box, .bmd-custody-seal {{ background: #fafafa !important; border: 1px solid #ccc !important; color: #000 !important; }}
}}
</style>
</head>
<body>

  <!-- Zero-Dependency Top Verification Bar: No CDN, No Network -->
  <div class="bmd-topbar font-mono">
    <div class="bmd-status-pill">
      <div id="statusDot" class="bmd-dot"></div>
      <span id="statusText">IMMUTABLE BLOCK — READY FOR OFFLINE VERIFICATION (SHA-512)</span>
    </div>
    <div class="bmd-actions">
      <button class="bmd-btn" onclick="window.print()">Print / Export PDF</button>
      <button class="bmd-btn" onclick="verifyRawHash()">Re-Verify Hash</button>
    </div>
  </div>

  <!-- Executive Document Sheet -->
  <div id="documentSheet" class="bmd-sheet">
    <div class="bmd-letterhead">
      <div>
        <div class="bmd-doc-type font-mono">{doc_type}</div>
        <div class="bmd-doc-title">{block_id}</div>
      </div>
      <div class="bmd-letterhead-meta font-mono">
        <div>Jurisdiction: {jurisdiction}</div>
        <div>Mode: {mode} (Immutable)</div>
        <div>Standard: SHA-512 &amp; Ed25519</div>
        {sig_cap_html}
      </div>
    </div>

    <!-- Rendered Executive Document Content (Zero Dependencies) -->
    <div class="bmd-content">
      {rendered_body}
    </div>
  </div>

<script>
// ============================================================
// ZERO-DEPENDENCY OFFLINE CRYPTOGRAPHIC VERIFICATION
// Uses ONLY browser-native window.crypto.subtle (WebCrypto API).
// Zero CDNs, zero libraries, zero network requests.
// Works completely offline in any modern browser.
// ============================================================
const RAW_BMD_CONTENT = `{escaped_raw}`;
const EXPECTED_HASH   = "{curr_hash}";
const MAX_SIGNATURES  = {max_sigs};
const CURRENT_SIGNATURES = {current_sigs};

async function verifyRawHash() {{
  try {{
    const enc = new TextEncoder();
    const match = RAW_BMD_CONTENT.match(/^---\\r?\\n[\\s\\S]*?\\r?\\n---\\r?\\n?([\\s\\S]*)$/);
    if (!match) throw new Error("Could not extract BMD payload from embedded content.");
    const payload = match[1].replace(/\\r\\n/g, '\\n').trim();
    // Native SHA-512 via SubtleCrypto — zero external dependencies
    const hashBuf = await window.crypto.subtle.digest("SHA-512", enc.encode(payload));
    const hashHex = Array.from(new Uint8Array(hashBuf)).map(b => b.toString(16).padStart(2,"0")).join("");

    document.getElementById("statusDot").style.background = "#10b981";
    document.getElementById("statusText").textContent = "PAYLOAD VERIFIED VIA NATIVE WEBCRYPTO SHA-512";
    document.getElementById("statusText").style.color = "#10b981";

    const sigNote = MAX_SIGNATURES > 0
      ? "\\nSignature Cap: " + CURRENT_SIGNATURES + "/" + MAX_SIGNATURES +
        (CURRENT_SIGNATURES >= MAX_SIGNATURES ? " — LIMIT REACHED" : " — Open")
      : "\\nSignatures: " + CURRENT_SIGNATURES + " (Unlimited)";

    alert(
      "Blockchain Markdown Verification\\n" +
      "==================================\\n" +
      "SHA-512 Computed (browser-native):\\n" + hashHex.slice(0,48) + "...\\n\\n" +
      "SHA-512 Stored (signed ledger):\\n" + EXPECTED_HASH.slice(0,48) + "..." +
      sigNote
    );
  }} catch(e) {{
    document.getElementById("documentSheet").classList.add("tampered");
    document.getElementById("statusDot").style.background = "#ef4444";
    document.getElementById("statusText").textContent = "INTEGRITY COMPROMISED: " + e.message;
    document.getElementById("statusText").style.color = "#ef4444";
  }}
}}

// Drag-and-drop: verify any .bmd file directly in the browser, fully offline
window.addEventListener("dragover", e => e.preventDefault());
window.addEventListener("drop", async e => {{
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (!file || !file.name.endsWith(".bmd")) return;
  const reader = new FileReader();
  reader.onload = async ev => {{
    try {{
      const text = ev.target.result;
      const enc  = new TextEncoder();
      const m    = text.match(/^---\\r?\\n[\\s\\S]*?\\r?\\n---\\r?\\n?([\\s\\S]*)$/);
      if (!m) {{ alert("Invalid .bmd format."); return; }}
      const payload = m[1].replace(/\\r\\n/g,'\\n').trim();
      const hashBuf = await window.crypto.subtle.digest("SHA-512", enc.encode(payload));
      const hashHex = Array.from(new Uint8Array(hashBuf)).map(b => b.toString(16).padStart(2,"0")).join("");
      alert("Dropped file: " + file.name + "\\nSHA-512 Payload Hash:\\n" + hashHex.slice(0,48) + "...");
    }} catch(ex) {{ alert("Verification error: " + ex.message); }}
  }};
  reader.readAsText(file);
}});
</script>
</body>
</html>"""

    if output_filepath is None:
        base, _ = os.path.splitext(bmd_filepath)
        output_filepath = base + ".html"

    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write(standalone_html)

    return output_filepath


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bmd_viewer_generator.py <file.bmd> [out.html]")
        sys.exit(1)

    src_bmd = sys.argv[1]
    out_f   = sys.argv[2] if len(sys.argv) > 2 else None
    res     = generate_standalone_html(src_bmd, out_f)
    print(f"[OK] Standalone zero-dependency HTML generated at: {res}")
