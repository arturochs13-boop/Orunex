"""
bmd_studio_app.py - Executive Mini-IDE for Blockchain Markdown (.bmd) v2.3
Autonomous Agent Governance Runtime & Cryptographic Ledger Workspace

Key Architectural Invariants:
1. Strict Lifecycle Bifurcation:
   - Draft Mode: Split-view with Source Code Editor on left + Live Preview on right.
   - Compiled Mode (transfer): Source code editor panel COMPLETELY DISAPPEARS.
     The workspace transitions into a 100% read-only, centered Executive Document Sheet.
2. Formal Design Directives:
   - <!-- bmd:rule double --> -> Formal legal double rule.
   - <!-- bmd:parties --> -> Contracting parties grid.
   - <!-- bmd:signatures --> -> Side-by-side formal signature blocks.
   - <!-- bmd:seal --> -> Digital custody stamp with SHA-512 ledger proof.
3. Universal Zero-Dependency Distribution:
   - Direct one-click export to standalone offline HTML viewer (no Python/Node/pip needed).
4. Real-time Contingency & Border Glow:
   - 100% English, zero emojis, dynamic red alert on hash mismatch.
"""

import os
import sys
import re
import json
import time
import flet as ft

# Setup environment & load FFI
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(BASE_DIR, "bin")
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")
PYTHON_DIR = os.path.join(BASE_DIR, "python")

if BIN_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = BIN_DIR + ";" + os.environ.get("PATH", "")
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

import bmd_ffi
import bmd_agent_executor
import bmd_property
import bmd_viewer_generator


def parse_bmd_metadata(raw_content: str):
    """
    Parses frontmatter and detects inline directives.
    Returns (meta_dict, body_clean, raw_body, require_cosigner, has_property)
    """
    match = re.match(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$", raw_content)
    meta = {}
    body = raw_content

    if match:
        yaml_text = match.group(1)
        body = match.group(2).strip()
        in_bundle = False
        bundle_lines = []
        for line in yaml_text.splitlines():
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

    cosign_in_meta = meta.get("require_cosigner", "").lower() in ("true", "1")
    cosign_marker = bool(re.search(r"<!--\s*bmd:insert_co_sign_button", body, re.IGNORECASE)) or \
                    bool(re.search(r"insert_co[-_]sign_button", body, re.IGNORECASE))
    require_cosigner = cosign_in_meta or cosign_marker
    has_property = bool(meta.get("property_bundle") or meta.get("property_bundle_hash"))

    return meta, body, require_cosigner, has_property


def render_formal_executive_markdown(body: str, meta: dict, is_compiled: bool) -> str:
    """
    Transforms body and BMD formal directives into an executive sheet format.
    Renders double rules, parties cards, signature boxes, and custody seals.
    """
    em_pub = meta.get("public_key", "Pending")
    em_pub_short = (em_pub[:16] + "..." + em_pub[-8:]) if len(em_pub) > 24 else em_pub
    rec_pub = meta.get("receiver_public_key", "")
    rec_pub_short = (rec_pub[:16] + "..." + rec_pub[-8:]) if rec_pub else "Pending Co-Signature"
    
    em_sig = meta.get("signature_layer_2", "")
    rec_sig = meta.get("receiver_signature", "")
    curr_hash = meta.get("current_hash", "")
    short_hash = (curr_hash[:16] + "..." + curr_hash[-8:]) if len(curr_hash) > 24 else curr_hash
    block_id = meta.get("block_id", "BLOCK")

    # Double rule replacement
    processed = re.sub(
        r"<!--\s*bmd:rule(?:\s+double)?\s*-->",
        "\n\n════════════════════════════════════════════════════════════════════════════════\n\n",
        body
    )

    # Parties replacement
    parties_md = f"""
| FIRST PARTY (EMITTER) | SECOND PARTY (RECEIVER) |
| :--- | :--- |
| **Role:** Primary Originator / Emitter | **Role:** Counterparty / Receiver |
| **Public Key:** `{em_pub_short}` | **Public Key:** `{rec_pub_short}` |
| **Status:** {'Ed25519 Verified Signer' if em_pub != 'Pending' else 'Drafting'} | **Status:** {'Co-Signer Ratified' if rec_sig else 'Awaiting Acceptance'} |
"""
    processed = re.sub(r"<!--\s*bmd:parties[^>]*-->", parties_md, processed)

    # Signatures replacement
    signatures_md = f"""
---

### Formal Cryptographic Signatures

| EMITTER DIGITAL SEAL | RECEIVER RATIFICATION |
| :--- | :--- |
| **Signature State:** {'DIGITALLY SEALED (Ed25519)' if em_sig else 'PENDING'} | **Signature State:** {'CO-SIGNED & RATIFIED' if rec_sig else 'UNILATERAL / PENDING'} |
| **Signature Stamp:** `{em_sig[:24]}...` | **Signature Stamp:** `{(rec_sig[:24] + '...') if rec_sig else '—'}` |
| **Algorithm:** Curve25519 / RFC 8032 | **Algorithm:** Curve25519 / RFC 8032 |
"""
    processed = re.sub(r"<!--\s*bmd:signatures?\s*-->", signatures_md, processed)

    # Seal replacement
    seal_md = f"""
> **BLOCKCHAIN MARKDOWN IMMUTABILITY SEAL**  
> `SHA-512 Digest:` {curr_hash}  
> `Block Custody:` {block_id} | FIPS 180-4 / RFC 8032 LEDGER STANDARD
"""
    processed = re.sub(r"<!--\s*bmd:seal\s*-->", seal_md, processed)

    # Clean any remaining technical comments
    clean_text = re.sub(r"<!--\s*bmd:[^>]*-->\r?\n?", "", processed)

    # If compiled and no signatures tag was explicit, append formal signature and seal block
    if is_compiled:
        if "### Formal Cryptographic Signatures" not in clean_text:
            clean_text += "\n\n" + signatures_md
        if "BLOCKCHAIN MARKDOWN IMMUTABILITY SEAL" not in clean_text and curr_hash:
            clean_text += "\n\n" + seal_md

    return clean_text


def main(page: ft.Page):
    page.title = "BMD Studio — Executive Workspace v2.3"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1320
    page.window.height = 860
    page.window.min_width = 1040
    page.window.min_height = 680
    page.padding = 0
    page.spacing = 0

    # Modern Dark Palette
    BG_BASE = "#07090e"
    BG_PANEL = "#0d1117"
    BG_SURFACE = "#111622"
    BORDER_SUBTLE = "#1e293b"
    BORDER_EMERALD = "#059669"
    BORDER_ALERT = "#ef4444"
    ACCENT_BLUE = "#3b82f6"

    # Default file
    default_draft = os.path.join(EXAMPLES_DIR, "draft_contract_example.bmd")
    if os.path.exists(default_draft):
        current_file_path = default_draft
    else:
        current_file_path = os.path.join(EXAMPLES_DIR, "demo_contrato.bmd")

    # Document Selector Options
    def get_file_options():
        opts = []
        if os.path.exists(EXAMPLES_DIR):
            for f in sorted(os.listdir(EXAMPLES_DIR)):
                if f.endswith(".bmd"):
                    opts.append(ft.dropdown.Option(f))
        return opts

    file_dropdown = ft.Dropdown(
        width=260,
        height=36,
        options=get_file_options(),
        value=os.path.basename(current_file_path),
        text_style=ft.TextStyle(font_family="Consolas", size=12),
        border_color="#334155",
        bgcolor=BG_PANEL,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
    )

    # 1. STREAMLINED TOP STATUS BAR
    status_indicator_dot = ft.Container(
        width=8,
        height=8,
        border_radius=4,
        bgcolor=ft.Colors.AMBER_400,
    )
    status_title_text = ft.Text(
        "MUTABLE DRAFT - EDITING ENABLED",
        size=12,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.AMBER_400,
        font_family="Consolas",
    )
    status_meta_text = ft.Text(
        "Mode: draft | SHA-512 / Ed25519",
        size=11,
        color=ft.Colors.GREY_400,
        font_family="Consolas",
    )

    # Inspector Dialog
    inspector_dialog = ft.AlertDialog(
        modal=False,
        title=ft.Text("Cryptographic Ledger Inspector", size=14, weight=ft.FontWeight.BOLD),
        content=ft.Container(width=520, height=270),
    )

    def show_inspector(e):
        meta, _, _, has_prop = parse_bmd_metadata(source_editor.value)
        block_id = meta.get("block_id", "N/A")
        mode = meta.get("mode", "draft")
        curr_hash = meta.get("current_hash", "N/A")
        pubkey = meta.get("public_key", "Pending")
        rec_pub = meta.get("receiver_public_key", "None")
        pb_hash = meta.get("property_bundle_hash", "None")

        inspector_dialog.content = ft.Column(
            controls=[
                ft.Text(f"Block Identifier: {block_id}", size=12, font_family="Consolas"),
                ft.Text(f"Operational Mode: {mode.upper()}", size=12, font_family="Consolas"),
                ft.Text(f"Emitter Ed25519: {pubkey}", size=11, font_family="Consolas", color=ft.Colors.BLUE_300),
                ft.Text(f"Receiver Ed25519: {rec_pub}", size=11, font_family="Consolas", color=ft.Colors.GREEN_300),
                ft.Divider(color=BORDER_SUBTLE),
                ft.Text(f"SHA-512 Ledger Hash:\n{curr_hash}", size=10, font_family="Consolas", color=ft.Colors.GREY_300),
                ft.Text(f"SHA-512 IP Bundle Hash:\n{pb_hash}", size=10, font_family="Consolas", color=ft.Colors.ORANGE_300) if has_prop else ft.Container(),
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        )
        page.dialog = inspector_dialog
        inspector_dialog.open = True
        page.update()

    sleek_top_bar = ft.Container(
        content=ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.DATA_OBJECT, color=ACCENT_BLUE, size=18),
                        ft.Text("BMD Studio", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        status_indicator_dot,
                        status_title_text,
                        ft.Container(width=1, height=14, bgcolor="#334155"),
                        status_meta_text,
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        file_dropdown,
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            icon_size=16,
                            icon_color=ft.Colors.BLUE_300,
                            tooltip="Reload file from disk",
                            on_click=lambda _: sync_views(),
                        ),
                        ft.FilledButton(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.WHITE70),
                                    ft.Text("Inspector", size=11, weight=ft.FontWeight.W_500),
                                ],
                                spacing=4,
                            ),
                            style=ft.ButtonStyle(
                                bgcolor="#1e293b",
                                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                shape=ft.RoundedRectangleBorder(radius=4),
                            ),
                            on_click=show_inspector,
                            tooltip="View cryptographic metadata and signatures",
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=BG_PANEL,
        padding=ft.Padding.symmetric(horizontal=16, vertical=8),
        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER_SUBTLE)),
    )

    # 2. SOURCE EDITOR & EXECUTIVE SHEET
    source_editor = ft.TextField(
        multiline=True,
        min_lines=32,
        max_lines=42,
        expand=True,
        border=ft.NoInputBorder(),
        text_style=ft.TextStyle(font_family="Consolas", size=13, color="#e2e8f0"),
        bgcolor=BG_BASE,
        content_padding=16,
    )

    preview_markdown = ft.Markdown(
        value="",
        expand=True,
        selectable=True,
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
    )

    preview_scroll_col = ft.Column(
        controls=[preview_markdown],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    editor_caption = ft.Container(
        content=ft.Row(
            controls=[
                ft.Text("Drafting Studio — Source Code (.bmd)", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_400),
                ft.Text("Editable YAML Frontmatter + Markdown", size=10, color=ft.Colors.GREY_600),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bgcolor=BG_SURFACE,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER_SUBTLE)),
    )

    preview_caption_text = ft.Text("Executive Sheet", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_400)
    preview_caption_sub = ft.Text("Clean Document View", size=10, color=ACCENT_BLUE)

    preview_caption = ft.Container(
        content=ft.Row(
            controls=[
                preview_caption_text,
                preview_caption_sub,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bgcolor=BG_SURFACE,
        padding=ft.Padding.symmetric(horizontal=16, vertical=6),
        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER_SUBTLE)),
    )

    # Left Container (Editor): Visible ONLY in draft mode
    left_container = ft.Container(
        content=ft.Column(
            controls=[editor_caption, source_editor],
            expand=True,
            spacing=0,
        ),
        expand=5,
        bgcolor=BG_BASE,
        border=ft.Border.all(1, BORDER_SUBTLE),
        border_radius=8,
        margin=ft.Padding.only(left=12, top=10, bottom=10, right=6),
    )

    # Right Container (Executive Sheet): Expands to full screen in compiled mode!
    right_container = ft.Container(
        content=ft.Column(
            controls=[
                preview_caption,
                ft.Container(
                    content=preview_scroll_col,
                    padding=ft.Padding.symmetric(horizontal=36, vertical=24),
                    expand=True,
                ),
            ],
            expand=True,
            spacing=0,
        ),
        expand=5,
        bgcolor="#090d15",
        border=ft.Border.all(1, BORDER_SUBTLE),
        border_radius=8,
        margin=ft.Padding.only(left=6, top=10, bottom=10, right=12),
    )

    workspace_split = ft.Row(
        controls=[left_container, right_container],
        expand=True,
        spacing=0,
    )

    # Toast Bar
    toast_text = ft.Text("Ready", size=11, color=ft.Colors.GREY_400, font_family="Consolas")

    # 3. ACTION TOOLBAR
    toolbar_row = ft.Row(controls=[], spacing=10, alignment=ft.MainAxisAlignment.START)
    action_toolbar = ft.Container(
        content=ft.Row(
            controls=[
                toolbar_row,
                ft.Row(
                    controls=[
                        toast_text,
                        ft.Container(width=1, height=12, bgcolor="#334155"),
                        ft.Text("FIPS 180-4 · RFC 8032 · C11 Engine", size=10, color=ft.Colors.GREY_600, font_family="Consolas"),
                    ],
                    spacing=10,
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=BG_PANEL,
        padding=ft.Padding.symmetric(horizontal=16, vertical=8),
        border=ft.Border.only(top=ft.BorderSide(1, BORDER_SUBTLE)),
    )

    # --- REAL-TIME CONTINGENCY & BORDER LOGIC ---

    def apply_contingency_borders(has_tamper: bool, is_dual_signed: bool):
        if has_tamper:
            left_container.border = ft.Border.all(2, BORDER_ALERT)
            right_container.border = ft.Border.all(2, BORDER_ALERT)
        elif is_dual_signed:
            left_container.border = ft.Border.all(1, BORDER_EMERALD)
            right_container.border = ft.Border.all(1, BORDER_EMERALD)
        else:
            left_container.border = ft.Border.all(1, BORDER_SUBTLE)
            right_container.border = ft.Border.all(1, BORDER_SUBTLE)

        left_container.update()
        right_container.update()

    def update_status_bar(meta: dict, is_valid: bool, has_tamper: bool, receiver_signed: bool):
        mode = (meta.get("mode") or "draft").lower()
        block_id = meta.get("block_id") or "BLOCK"
        curr_hash = meta.get("current_hash") or "N/A"
        short_h = (curr_hash[:12] + "..." + curr_hash[-8:]) if len(curr_hash) > 24 else curr_hash

        if has_tamper:
            status_indicator_dot.bgcolor = ft.Colors.RED_500
            status_title_text.value = "[ CONTINGENCY MODE: HASH MISMATCH / UNAUTHORIZED EDIT DETECTED ]"
            status_title_text.color = ft.Colors.RED_400
            status_meta_text.value = f"Integrity Failure in {block_id} | C11 Verification Failed"
            status_meta_text.color = ft.Colors.RED_300
            sleek_top_bar.bgcolor = "#220808"
        elif mode == "transfer" and receiver_signed:
            status_indicator_dot.bgcolor = ft.Colors.GREEN_400
            status_title_text.value = "CRYPTOGRAPHICALLY FINALIZED & DUAL-SIGNED"
            status_title_text.color = ft.Colors.GREEN_400
            status_meta_text.value = f"Block {block_id} dual-signed | SHA-512: {short_h}"
            status_meta_text.color = ft.Colors.GREY_400
            sleek_top_bar.bgcolor = BG_PANEL
        elif mode == "transfer":
            status_indicator_dot.bgcolor = ft.Colors.BLUE_400
            status_title_text.value = "IMMUTABLE EXECUTIVE DOCUMENT - SEALED"
            status_title_text.color = ft.Colors.BLUE_400
            status_meta_text.value = f"Block {block_id} frozen (Emitter) | SHA-512: {short_h}"
            status_meta_text.color = ft.Colors.GREY_400
            sleek_top_bar.bgcolor = BG_PANEL
        else:
            status_indicator_dot.bgcolor = ft.Colors.AMBER_400
            status_title_text.value = "MUTABLE DRAFT - EDITING ENABLED"
            status_title_text.color = ft.Colors.AMBER_400
            status_meta_text.value = f"Draft in progress ({block_id}) | Edits permitted"
            status_meta_text.color = ft.Colors.GREY_400
            sleek_top_bar.bgcolor = BG_PANEL

        sleek_top_bar.update()

    # --- ACTIONS ---

    def handle_revert_changes(e):
        sync_views()

    def handle_save_draft(e):
        try:
            with open(current_file_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(source_editor.value)
            toast_text.value = f"Saved draft: {os.path.basename(current_file_path)}"
            sync_views()
        except Exception as ex:
            toast_text.value = f"Error saving: {ex}"
            page.update()

    def handle_compile_and_sign_emitter(e):
        """Compiles, freezes, locks editing, and transitions to compiled executive sheet!"""
        try:
            raw_text = source_editor.value
            meta, body_text, _, _ = parse_bmd_metadata(raw_text)

            block_id = meta.get("block_id") or "0xBLOCK_001"
            timestamp = int(meta.get("timestamp") or time.time())
            emitter_seed = bytes([0x42] * 32)

            prop_path = meta.get("inject_property") or meta.get("inject_property_path")
            bundle_b64 = None
            bundle_size = 0
            bundle_hash = ""

            if prop_path and os.path.exists(prop_path):
                toast_text.value = f"Injecting and destroying source: {prop_path}..."
                page.update()
                bundle_b64, bundle_size, bundle_hash = bmd_property.inject_property(
                    prop_path, block_id, timestamp, emitter_seed, destroy_source=True
                )
                meta["property_bundle_hash"] = bundle_hash
                meta["property_bundle_size"] = str(bundle_size)
                meta["property_bundle_destroyed"] = "true"
                meta.pop("inject_property", None)
                meta.pop("inject_property_path", None)

            lines = ["---"]
            for k, v in meta.items():
                if k == "property_bundle":
                    continue
                if isinstance(v, bool):
                    lines.append(f"{k}: {'true' if v else 'false'}")
                else:
                    lines.append(f"{k}: \"{v}\"")

            if bundle_b64:
                lines.append("property_bundle: |")
                lines.append(bmd_property.format_bundle_for_yaml(bundle_b64))

            lines.append("---")
            lines.append("")
            lines.append(body_text)
            new_raw_content = "\n".join(lines)

            with open(current_file_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_raw_content)

            doc = bmd_ffi.BMDWrapper.load_file(current_file_path)
            doc.transition_to_transfer(emitter_seed)
            doc.save(current_file_path)

            toast_text.value = "Document compiled and sealed. Editor closed."
            sync_views()
        except Exception as ex:
            toast_text.value = f"Compile & Sign error: {ex}"
            page.update()

    def handle_cosign_receiver(e):
        try:
            doc = bmd_ffi.BMDWrapper.load_file(current_file_path)
            receiver_seed = bytes([0x99] * 32)
            doc.cosign_receiver(receiver_seed)
            doc.save(current_file_path)

            toast_text.value = "Receiver validated and co-signed the immutable block."
            sync_views()
        except Exception as ex:
            toast_text.value = f"Co-Sign error: {ex}"
            page.update()

    def handle_export_standalone(e):
        """Generates zero-dependency standalone HTML and opens in browser."""
        try:
            out_html = bmd_viewer_generator.generate_standalone_html(current_file_path)
            toast_text.value = f"Standalone HTML exported: {os.path.basename(out_html)}"
            try:
                os.startfile(out_html)
            except Exception:
                pass
            page.update()
        except Exception as ex:
            toast_text.value = f"Export error: {ex}"
            page.update()

    def handle_fork_as_draft(e):
        """Forks the current document into a new editable draft without altering original block."""
        try:
            nonlocal current_file_path
            meta, body_text, _, _ = parse_bmd_metadata(source_editor.value)
            new_id = f"0xDRAFT_{int(time.time())}"
            forked_file = os.path.join(EXAMPLES_DIR, f"{new_id}.bmd")
            
            meta["block_id"] = new_id
            meta["mode"] = "draft"
            meta["previous_hash"] = meta.get("current_hash", "0" * 128)
            meta["current_hash"] = "0" * 128
            meta["public_key"] = ""
            meta["signature_layer_2"] = ""
            meta["receiver_public_key"] = ""
            meta["receiver_signature"] = ""

            lines = ["---"]
            for k, v in meta.items():
                if k == "property_bundle":
                    continue
                lines.append(f"{k}: \"{v}\"")
            lines.append("---")
            lines.append("")
            lines.append(body_text)

            with open(forked_file, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines))

            current_file_path = forked_file
            file_dropdown.options = get_file_options()
            file_dropdown.value = os.path.basename(current_file_path)
            file_dropdown.update()

            toast_text.value = f"Forked new draft: {new_id}.bmd"
            sync_views()
        except Exception as ex:
            toast_text.value = f"Fork error: {ex}"
            page.update()

    def handle_extract_property(e):
        try:
            with open(current_file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()

            meta, _, _, has_property = parse_bmd_metadata(raw_text)
            bundle_b64 = meta.get("property_bundle")
            if not bundle_b64:
                toast_text.value = "No property bundle found in block."
                page.update()
                return

            block_id = meta.get("block_id") or "0xBLOCK"
            timestamp = int(meta.get("timestamp") or time.time())
            emitter_seed = bytes([0x42] * 32)

            out_dir = os.path.join(BASE_DIR, "extracted_property", block_id)
            res = bmd_property.extract_property(bundle_b64, block_id, timestamp, emitter_seed, out_dir)
            toast_text.value = f"{res['files_extracted']} files extracted to: {out_dir}"
            page.update()
        except Exception as ex:
            toast_text.value = f"Extraction error: {ex}"
            page.update()

    def handle_verify_doc(e):
        try:
            doc = bmd_ffi.BMDWrapper.load_file(current_file_path)
            is_valid, msg = doc.verify()
            if is_valid:
                toast_text.value = "Consensus Verified: Cryptographic integrity intact."
            else:
                toast_text.value = f"Alert: {msg}"
            page.update()
        except Exception as ex:
            toast_text.value = f"Verification error: {ex}"
            page.update()

    def handle_run_office_agent(e):
        try:
            result = bmd_agent_executor.execute_office_agent(current_file_path)
            if result.get("success"):
                word_f = os.path.basename(result["word_report"])
                excel_f = os.path.basename(result["excel_audit"])
                toast_text.value = f"Office reports generated: {word_f} and {excel_f}"
                try:
                    os.startfile(result["word_report"])
                except Exception:
                    pass
            else:
                toast_text.value = "Office agent rejected block: integrity failure."
            page.update()
        except Exception as ex:
            toast_text.value = f"Office agent error: {ex}"
            page.update()

    # --- DYNAMIC ACTION BUTTONS ---

    def update_toolbar_buttons(mode: str, require_cosigner: bool, is_dual_signed: bool, has_property: bool, has_tamper: bool):
        controls = []
        is_transfer = (mode == "transfer")

        if has_tamper:
            controls.append(
                ft.FilledButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.UNDO, color=ft.Colors.WHITE, size=14),
                            ft.Text("Revert Unauthorized Changes", size=12, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=6,
                    ),
                    style=ft.ButtonStyle(
                        bgcolor="#b91c1c",
                        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                        shape=ft.RoundedRectangleBorder(radius=4),
                    ),
                    on_click=handle_revert_changes,
                )
            )
        elif not is_transfer and not is_dual_signed:
            # DRAFT MODE BUTTONS
            controls.append(
                ft.FilledButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.BOLT, color=ft.Colors.WHITE, size=15),
                            ft.Text("Compile, Lock & Sign as Emitter", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ],
                        spacing=6,
                    ),
                    style=ft.ButtonStyle(
                        bgcolor="#2563eb",
                        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                        shape=ft.RoundedRectangleBorder(radius=4),
                    ),
                    tooltip="Freezes document, closes editor and seals in immutable mode",
                    on_click=handle_compile_and_sign_emitter,
                )
            )
            controls.append(
                ft.IconButton(
                    icon=ft.Icons.SAVE,
                    icon_color=ft.Colors.GREY_400,
                    icon_size=18,
                    tooltip="Save draft changes",
                    on_click=handle_save_draft,
                )
            )
        elif is_transfer and not is_dual_signed:
            # COMPILED MODE BUTTONS
            if require_cosigner:
                controls.append(
                    ft.FilledButton(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.VERIFIED_USER, color=ft.Colors.WHITE, size=15),
                                ft.Text("Accept & Co-Sign as Receiver", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ],
                            spacing=6,
                        ),
                        style=ft.ButtonStyle(
                            bgcolor="#059669",
                            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                            shape=ft.RoundedRectangleBorder(radius=4),
                        ),
                        tooltip="Validates SHA-512 and co-signs immutable block",
                        on_click=handle_cosign_receiver,
                    )
                )

            controls.append(
                ft.OutlinedButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.OPEN_IN_BROWSER, color=ft.Colors.BLUE_300, size=15),
                            ft.Text("Export Standalone HTML (Zero Dependencies)", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.BLUE_300),
                        ],
                        spacing=6,
                    ),
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, "#3b82f6"),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        shape=ft.RoundedRectangleBorder(radius=4),
                    ),
                    tooltip="Generates a self-contained HTML document viewable offline without any dependencies",
                    on_click=handle_export_standalone,
                )
            )

            controls.append(
                ft.OutlinedButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SHIELD_OUTLINED, color=ft.Colors.GREY_400, size=15),
                            ft.Text("Verify Consensus", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_300),
                        ],
                        spacing=6,
                    ),
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, "#334155"),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        shape=ft.RoundedRectangleBorder(radius=4),
                    ),
                    on_click=handle_verify_doc,
                )
            )

            if has_property:
                controls.append(
                    ft.FilledButton(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_ZIP, color=ft.Colors.WHITE, size=15),
                                ft.Text("Extract Property Bundle", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ],
                            spacing=6,
                        ),
                        style=ft.ButtonStyle(
                            bgcolor="#c2410c",
                            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                            shape=ft.RoundedRectangleBorder(radius=4),
                        ),
                        on_click=handle_extract_property,
                    )
                )

            controls.append(
                ft.TextButton(
                    content=ft.Text("Fork as New Draft", size=11, color=ft.Colors.BLUE_400),
                    on_click=handle_fork_as_draft,
                    tooltip="Start a new editable draft without modifying this immutable block",
                )
            )
        elif is_dual_signed:
            # DUAL-SIGNED FINALIZED BUTTONS
            controls.append(
                ft.FilledButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SMART_TOY, color=ft.Colors.WHITE, size=15),
                            ft.Text("Run Office Autonomous Agent", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ],
                        spacing=6,
                    ),
                    style=ft.ButtonStyle(
                        bgcolor="#7c3aed",
                        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                        shape=ft.RoundedRectangleBorder(radius=4),
                    ),
                    on_click=handle_run_office_agent,
                )
            )
            controls.append(
                ft.OutlinedButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.OPEN_IN_BROWSER, color=ft.Colors.GREEN_300, size=15),
                            ft.Text("Export Standalone HTML", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.GREEN_300),
                        ],
                        spacing=6,
                    ),
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, "#10b981"),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        shape=ft.RoundedRectangleBorder(radius=4),
                    ),
                    on_click=handle_export_standalone,
                )
            )
            if has_property:
                controls.append(
                    ft.FilledButton(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_ZIP, color=ft.Colors.WHITE, size=15),
                                ft.Text("Extract Property Bundle", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ],
                            spacing=6,
                        ),
                        style=ft.ButtonStyle(
                            bgcolor="#c2410c",
                            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                            shape=ft.RoundedRectangleBorder(radius=4),
                        ),
                        on_click=handle_extract_property,
                    )
                )

            controls.append(
                ft.TextButton(
                    content=ft.Text("Fork as New Draft", size=11, color=ft.Colors.BLUE_400),
                    on_click=handle_fork_as_draft,
                )
            )

        toolbar_row.controls = controls
        toolbar_row.update()

    def sync_views(file_path: str = None):
        target_path = file_path or current_file_path
        if not os.path.exists(target_path):
            return

        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            raw_text = f.read()

        source_editor.value = raw_text
        meta, body_text, require_cosigner, has_property = parse_bmd_metadata(raw_text)
        mode = (meta.get("mode") or "draft").lower()
        is_compiled = (mode == "transfer")

        # RENDER FORMAL DOCUMENT
        clean_formatted_text = render_formal_executive_markdown(body_text, meta, is_compiled)
        preview_markdown.value = clean_formatted_text

        try:
            doc = bmd_ffi.BMDWrapper.load_file(target_path)
            is_valid, _ = doc.verify()
            has_tamper = (not is_valid and is_compiled)
            rec_signed = bool(doc.receiver_signature)
        except Exception:
            is_valid = False
            has_tamper = is_compiled
            rec_signed = False

        # STRICT LIFECYCLE BIFURCATION:
        # If compiled, the source code editor panel is COMPLETELY HIDDEN!
        if is_compiled:
            left_container.visible = False
            right_container.expand = 10
            preview_caption_text.value = f"Immutable Executive Document ({os.path.basename(target_path)})"
            preview_caption_sub.value = "Editing Permanently Locked"
            preview_caption_sub.color = ft.Colors.GREEN_400
        else:
            left_container.visible = True
            left_container.expand = 5
            right_container.expand = 5
            preview_caption_text.value = "Executive Sheet Preview"
            preview_caption_sub.value = "Drafting Mode Active"
            preview_caption_sub.color = ACCENT_BLUE

        update_status_bar(meta, is_valid, has_tamper, rec_signed)
        apply_contingency_borders(has_tamper, rec_signed)
        update_toolbar_buttons(mode, require_cosigner, rec_signed, has_property, has_tamper)
        toast_text.value = f"Synchronized: {os.path.basename(target_path)}"
        page.update()

    def on_editor_input(e):
        raw_text = source_editor.value
        meta, body_text, require_cosigner, has_property = parse_bmd_metadata(raw_text)
        mode = (meta.get("mode") or "draft").lower()
        is_compiled = (mode == "transfer")

        clean_formatted_text = render_formal_executive_markdown(body_text, meta, is_compiled)
        preview_markdown.value = clean_formatted_text

        try:
            doc = bmd_ffi.BMDWrapper.from_string(raw_text)
            is_valid, _ = doc.verify()
            has_tamper = (not is_valid and is_compiled)
            rec_signed = bool(doc.receiver_signature)
        except Exception:
            is_valid = False
            has_tamper = is_compiled
            rec_signed = False

        update_status_bar(meta, is_valid, has_tamper, rec_signed)
        apply_contingency_borders(has_tamper, rec_signed)
        update_toolbar_buttons(mode, require_cosigner, rec_signed, has_property, has_tamper)
        preview_markdown.update()

    source_editor.on_change = on_editor_input

    def on_file_selected(e):
        nonlocal current_file_path
        current_file_path = os.path.join(EXAMPLES_DIR, file_dropdown.value)
        sync_views()

    file_dropdown.on_change = on_file_selected

    page.add(
        sleek_top_bar,
        workspace_split,
        action_toolbar,
    )

    sync_views()


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    elif hasattr(ft, "app"):
        ft.app(target=main)
