"""Deterministic document/artifact studio for Orunex.

The studio is intentionally independent from the language model.  It turns an
explicit request such as "create a PDF about solar energy" into a real file
that can be previewed and opened from the chat.  When the AI is available it
can still supply richer content through the ``content``/``rows``/``slides``
arguments.
"""

from __future__ import annotations

import csv
import datetime as _dt
import html
import os
import re
import textwrap
from typing import Iterable, Optional, Sequence

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "orunex_outputs", "artifacts")

KIND_LABELS = {
    "pdf": "PDF",
    "docx": "Word",
    "xlsx": "Excel",
    "pptx": "PowerPoint",
    "csv": "CSV",
    "md": "Markdown",
    "html": "HTML",
    "txt": "Text",
}
EXTENSIONS = {
    "pdf": ".pdf",
    "docx": ".docx",
    "xlsx": ".xlsx",
    "pptx": ".pptx",
    "csv": ".csv",
    "md": ".md",
    "html": ".html",
    "txt": ".txt",
}

_KIND_WORDS = (
    ("pptx", ("powerpoint", "power point", "pptx", "ppt", "presentacion", "presentación", "slides", "diapositivas")),
    ("xlsx", ("excel", "xlsx", "xls", "hoja de calculo", "hoja de cálculo", "spreadsheet")),
    ("docx", ("word", "docx", "documento de word", "documento word")),
    ("pdf", ("pdf",)),
    ("csv", ("csv",)),
    ("md", ("markdown", "md")),
    ("html", ("html", "pagina web", "página web", "landing", "web page")),
)

_CREATE_VERBS = (
    "crea", "crear", "creame", "créame", "genera", "generar", "haz", "hazme",
    "elabora", "elaborar", "prepara", "preparar", "exporta", "exportar",
    "construye", "construir", "disena", "diseña", "disenar", "diseñar",
    "make", "create", "generate", "build", "produce", "export", "write",
)
_SOFT_INTENT = ("necesito", "quiero", "me gustaria", "me gustaría", "i need", "i want")
_QUESTION_PREFIXES = ("como ", "cómo ", "how ", "que es ", "qué es ", "what is ")

_NUMBER_WORDS = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u00a0", " ").strip())


def _strip_accents(value: str) -> str:
    return (
        value.replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ü", "u")
        .replace("ñ", "n")
    )


def _safe_filename(title: str, extension: str) -> str:
    clean = re.sub(r"[^\w\s\-\.]", "", _strip_accents(title), flags=re.UNICODE)
    clean = re.sub(r"\s+", "_", clean).strip("._-")
    if not clean:
        clean = "Artifacto_Orunex"
    clean = clean[:64]
    return f"{clean}_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}{extension}"


def detect_kind(text: str) -> Optional[str]:
    """Return a supported artifact kind if the request names one."""
    lower = _strip_accents(_normalise(text).lower())
    for kind, words in _KIND_WORDS:
        if any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", lower) for word in words):
            return kind
    return None


def _has_creation_intent(lower: str) -> bool:
    if lower.startswith(_QUESTION_PREFIXES):
        return False
    words = re.findall(r"[a-záéíóúüñ]+", lower)
    if any(word in _CREATE_VERBS for word in words):
        return True
    if any(phrase in lower for phrase in _SOFT_INTENT):
        # "Necesito un PDF sobre..." is an actionable request.  Avoid treating
        # "necesito saber como crear un PDF" as one.
        return not any(q in lower for q in ("como ", "cómo ", "how "))
    return False


def extract_title(text: str, kind: str) -> str:
    """Pull a human title out of a natural-language artifact request."""
    value = _normalise(text)
    lower = _strip_accents(value.lower())

    # Explicit title wins.
    explicit = re.search(
        r"(?:titulo|título|title)\s*[:=]\s*[\"']?(.+?)[\"']?(?:$|\n)",
        value,
        flags=re.IGNORECASE,
    )
    if explicit:
        value = explicit.group(1).strip()
    else:
        # Remove the command and file-type wording while preserving the topic.
        words = _strip_accents(value)
        for kind_word in dict(_KIND_WORDS).get(kind, ()):
            words = re.sub(
                rf"(?i)(?<!\w){re.escape(kind_word)}(?!\w)", " ", words
            )
        for verb in _CREATE_VERBS + _SOFT_INTENT:
            words = re.sub(rf"(?i)(?<!\w){re.escape(verb)}(?!\w)", " ", words)
        words = re.sub(
            r"(?i)\b(?:un|una|uno|el|la|los|las|de|del|sobre|acerca de|"
            r"for|about|on|the|a|an|please|por favor|que|con)\b",
            " ",
            words,
        )
        words = re.sub(r"(?i)\b\d+\s*(?:diapositivas?|slides?|paginas?|páginas?|hojas?)\b", " ", words)
        words = re.sub(r"\s+", " ", words).strip(" .,:;-_")
        value = words or "Artifacto Orunex"

    value = re.sub(r"\s+", " ", value).strip(" .,:;-_")
    if len(value) > 80:
        value = value[:77].rstrip() + "..."
    return value[:1].upper() + value[1:] if value else "Artifacto Orunex"


def detect_request(text: str) -> Optional[dict]:
    """Return ``{kind, title, raw}`` for a creation request, else ``None``."""
    raw = _normalise(text)
    if not raw:
        return None
    kind = detect_kind(raw)
    if not kind:
        return None
    lower = _strip_accents(raw.lower())
    if not _has_creation_intent(lower):
        return None
    return {"kind": kind, "title": extract_title(raw, kind), "raw": raw}


def _date_label() -> str:
    return _dt.datetime.now().strftime("%d/%m/%Y")


def _sections(title: str, notes: Optional[str] = None) -> list[tuple[str, list[str]]]:
    """Generic, useful structure for a document with no LLM available."""
    intro = (
        notes.strip()
        if notes and notes.strip()
        else (
            f"Este documento presenta una vision estructurada de {title}. "
            "Su objetivo es convertir la solicitud en un entregable claro, "
            "revisable y listo para compartir."
        )
    )
    return [
        (
            "Resumen ejecutivo",
            [
                intro,
                "El contenido esta organizado en contexto, puntos clave y un plan "
                "de accion verificable.",
            ],
        ),
        (
            "Contexto",
            [
                f"El tema central es {title}.",
                "Antes de ejecutar cualquier decision conviene validar el alcance, "
                "las personas implicadas y los recursos disponibles.",
            ],
        ),
        (
            "Puntos clave",
            [
                f"Definir con precision que significa exito para {title}.",
                "Separar hechos, supuestos y decisiones pendientes.",
                "Documentar responsables, fechas y criterios de aceptacion.",
                "Revisar el resultado con una persona o fuente independiente.",
            ],
        ),
        (
            "Plan de accion",
            [
                "1. Confirmar el objetivo y el publico destinatario.",
                "2. Reunir la informacion y las fuentes necesarias.",
                "3. Preparar una primera version del entregable.",
                "4. Validar, corregir y registrar la version final.",
            ],
        ),
        (
            "Conclusion",
            [
                f"{title} queda preparado como un punto de partida concreto. "
                "El siguiente paso es asignar responsables y revisar el avance "
                "con una cadencia definida.",
            ],
        ),
    ]


def _excel_rows(title: str) -> list[list[object]]:
    return [
        ["Elemento", "Detalle", "Cantidad", "Valor"],
        ["Objetivo", f"Definir el alcance de {title}", 1, 0],
        ["Contexto", "Reunir informacion y fuentes relevantes", 3, 0],
        ["Analisis", "Comparar alternativas y riesgos", 4, 0],
        ["Ejecucion", "Preparar el entregable principal", 5, 0],
        ["Validacion", "Revisar resultados con criterios de aceptacion", 2, 0],
        ["Seguimiento", "Registrar avances y proximos pasos", 2, 0],
    ]


def _slides(title: str) -> list[dict]:
    return [
        {
            "title": title,
            "subtitle": "Documento generado por Orunex",
            "bullets": [],
        },
        {
            "title": "Contexto",
            "bullets": [
                f"Tema: {title}",
                "Objetivo: convertir la solicitud en un entregable claro.",
                "Alcance: primera version revisable y accionable.",
            ],
        },
        {
            "title": "Puntos clave",
            "bullets": [
                "Definir que significa exito.",
                "Separar hechos, supuestos y decisiones.",
                "Asignar responsables y fechas.",
            ],
        },
        {
            "title": "Plan de accion",
            "bullets": [
                "1. Confirmar objetivo y publico.",
                "2. Reunir informacion y fuentes.",
                "3. Preparar y validar el entregable.",
                "4. Registrar la version final.",
            ],
        },
        {
            "title": "Siguiente paso",
            "bullets": [
                "Revisar esta propuesta.",
                "Ajustar el contenido con el equipo.",
                "Programar la ejecucion y el seguimiento.",
            ],
        },
    ]


def _content_lines(content: Optional[str], title: str) -> list[str]:
    if content and content.strip():
        return [line.rstrip() for line in content.strip().splitlines()]
    lines: list[str] = []
    for heading, paragraphs in _sections(title):
        lines.append(f"## {heading}")
        lines.extend(paragraphs)
        lines.append("")
    return lines


def _safe_pdf_text(value: str) -> str:
    return str(value).encode("latin-1", "replace").decode("latin-1")


def _write_pdf(path: str, title: str, content: Optional[str]) -> None:
    from fpdf import FPDF  # type: ignore

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_font("helvetica", "B", 22)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(width, 12, _safe_pdf_text(title))
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(100, 110, 125)
    pdf.set_x(pdf.l_margin)
    pdf.cell(width, 8, _safe_pdf_text(f"Orunex - {_date_label()}"), ln=True)
    pdf.ln(4)
    pdf.set_text_color(30, 35, 45)

    lines = _content_lines(content, title)
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            pdf.ln(3)
            continue
        pdf.set_x(pdf.l_margin)
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            pdf.ln(3)
            pdf.set_font("helvetica", "B", 14)
            pdf.multi_cell(width, 8, _safe_pdf_text(heading))
            pdf.set_font("helvetica", "", 11)
        elif re.match(r"^\d+[\.\)]\s", line) or line.startswith(("- ", "* ")):
            pdf.set_font("helvetica", "", 11)
            pdf.multi_cell(width, 6, _safe_pdf_text("  " + line))
        else:
            pdf.set_font("helvetica", "", 11)
            pdf.multi_cell(width, 6, _safe_pdf_text(line))
    pdf.output(path)


def _write_docx(path: str, title: str, content: Optional[str]) -> None:
    import docx  # type: ignore
    from docx.shared import Pt  # type: ignore

    document = docx.Document()
    document.add_heading(title, level=0)
    meta = document.add_paragraph(f"Orunex - {_date_label()}")
    meta.runs[0].font.size = Pt(9)
    meta.runs[0].italic = True
    for raw_line in _content_lines(content, title):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            document.add_heading(line[3:].strip(), level=2)
        elif line.startswith("# "):
            document.add_heading(line[2:].strip(), level=1)
        elif re.match(r"^\d+[\.\)]\s", line):
            document.add_paragraph(line, style="List Number")
        elif line.startswith(("- ", "* ")):
            document.add_paragraph(line[2:].strip(), style="List Bullet")
        else:
            document.add_paragraph(line)
    document.save(path)


def _write_xlsx(path: str, title: str, rows: Optional[Sequence[Sequence[object]]]) -> None:
    data = list(rows) if rows else _excel_rows(title)
    if not data:
        data = _excel_rows(title)
    try:
        from openpyxl import Workbook  # type: ignore
        from openpyxl.styles import Alignment, Font, PatternFill  # type: ignore

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Orunex"
        for row in data:
            sheet.append(list(row))
        sheet.freeze_panes = "A2"
        header_fill = PatternFill("solid", fgColor="1E66F5")
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for column in sheet.columns:
            letter = column[0].column_letter
            width = max(12, min(44, max(len(str(c.value or "")) for c in column) + 3))
            sheet.column_dimensions[letter].width = width
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value, (int, float)):
                    cell.alignment = Alignment(horizontal="right")
        workbook.save(path)
        return
    except Exception:
        pass
    # Dependency-free fallback: a small but valid OOXML workbook.
    _write_minimal_xlsx(path, data)


def _xml_escape(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=False)


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name or "A"


def _write_minimal_xlsx(path: str, rows: Sequence[Sequence[object]]) -> None:
    import zipfile

    sheet_rows = []
    for r_index, row in enumerate(rows, start=1):
        cells = []
        for c_index, value in enumerate(row, start=1):
            ref = f"{_column_name(c_index)}{r_index}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{_xml_escape(value)}</t></is></c>'
                )
        sheet_rows.append(f'<row r="{r_index}">{"".join(cells)}</row>')
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Orunex" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        '</styleSheet>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", styles)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)


def _write_pptx(path: str, title: str, slides: Optional[Sequence[dict]]) -> None:
    from pptx import Presentation  # type: ignore
    from pptx.util import Inches, Pt  # type: ignore

    deck = Presentation()
    deck.slide_width = Inches(13.333)
    deck.slide_height = Inches(7.5)
    items = list(slides) if slides else _slides(title)

    for index, item in enumerate(items):
        item_title = str(item.get("title") or title)
        subtitle = str(item.get("subtitle") or "")
        bullets = [str(b) for b in item.get("bullets", []) if str(b).strip()]
        if index == 0:
            slide = deck.slides.add_slide(deck.slide_layouts[0])
            slide.shapes.title.text = item_title
            slide.placeholders[1].text = subtitle or f"Orunex - {_date_label()}"
            continue
        slide = deck.slides.add_slide(deck.slide_layouts[1])
        slide.shapes.title.text = item_title
        body = slide.placeholders[1].text_frame
        body.clear()
        for b_index, bullet in enumerate(bullets):
            paragraph = body.paragraphs[0] if b_index == 0 else body.add_paragraph()
            paragraph.text = bullet
            paragraph.level = 0
            paragraph.font.size = Pt(20)
    deck.save(path)


def _write_csv(path: str, rows: Optional[Sequence[Sequence[object]]], title: str) -> None:
    data = list(rows) if rows else _excel_rows(title)
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(data)


def _write_markdown(path: str, title: str, content: Optional[str]) -> None:
    lines = [f"# {title}", "", f"_Orunex - {_date_label()}_", ""]
    lines.extend(_content_lines(content, title))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).strip() + "\n")


def _write_html(path: str, title: str, content: Optional[str]) -> None:
    body: list[str] = []
    for raw_line in _content_lines(content, title):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif re.match(r"^\d+[\.\)]\s", line):
            body.append(f"<p class=\"item\">{html.escape(line)}</p>")
        elif line.startswith(("- ", "* ")):
            body.append(f"<li>{html.escape(line[2:])}</li>")
        else:
            body.append(f"<p>{html.escape(line)}</p>")
    # Merge adjacent <li> nodes into lists.
    merged: list[str] = []
    in_list = False
    for fragment in body:
        if fragment.startswith("<li>"):
            if not in_list:
                merged.append("<ul>")
                in_list = True
            merged.append(fragment)
        else:
            if in_list:
                merged.append("</ul>")
                in_list = False
            merged.append(fragment)
    if in_list:
        merged.append("</ul>")
    document = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin: 0; background: #f5f8ff; color: #14213d;
    font-family: "Segoe UI", system-ui, sans-serif; line-height: 1.65; }}
  main {{ max-width: 860px; margin: 48px auto; padding: 48px;
    background: #fff; border: 1px solid #e3eaf7; border-radius: 22px;
    box-shadow: 0 24px 60px rgba(21, 64, 137, .10); }}
  .meta {{ color: #64748b; font-size: 13px; margin-bottom: 28px; }}
  h1 {{ font-size: 38px; line-height: 1.15; margin: 0 0 8px; }}
  h2 {{ color: #1e66f5; margin-top: 32px; }}
  li, .item {{ margin: 6px 0; }}
  ul {{ padding-left: 22px; }}
  @media (max-width: 640px) {{ main {{ margin: 16px; padding: 24px; }} h1 {{ font-size: 28px; }} }}
</style>
</head>
<body><main>
<h1>{html.escape(title)}</h1>
<div class="meta">Orunex - {_date_label()}</div>
{''.join(merged)}
</main></body></html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(document)


def _write_text(path: str, title: str, content: Optional[str]) -> None:
    lines = [title, "=" * len(title), f"Orunex - {_date_label()}", ""]
    lines.extend(_content_lines(content, title))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).strip() + "\n")


def create_artifact(
    kind: str,
    title: str,
    content: Optional[str] = None,
    rows: Optional[Sequence[Sequence[object]]] = None,
    slides: Optional[Sequence[dict]] = None,
    filename: Optional[str] = None,
    out_dir: Optional[str] = None,
) -> str:
    """Create a real file and return its absolute path."""
    kind = str(kind or "").lower().strip().lstrip(".")
    if kind not in EXTENSIONS:
        raise ValueError(f"Unsupported artifact kind: {kind}")
    title = _normalise(title) or "Artifacto Orunex"
    target_dir = os.path.abspath(out_dir or OUTPUT_DIR)
    os.makedirs(target_dir, exist_ok=True)
    if filename:
        safe = re.sub(r"[\\/:*?\"<>|]", "_", os.path.basename(filename))
        if not safe.lower().endswith(EXTENSIONS[kind]):
            safe += EXTENSIONS[kind]
        path = os.path.join(target_dir, safe)
    else:
        path = os.path.join(target_dir, _safe_filename(title, EXTENSIONS[kind]))

    if kind == "pdf":
        _write_pdf(path, title, content)
    elif kind == "docx":
        _write_docx(path, title, content)
    elif kind == "xlsx":
        _write_xlsx(path, title, rows)
    elif kind == "pptx":
        _write_pptx(path, title, slides)
    elif kind == "csv":
        _write_csv(path, rows, title)
    elif kind == "md":
        _write_markdown(path, title, content)
    elif kind == "html":
        _write_html(path, title, content)
    elif kind == "txt":
        _write_text(path, title, content)
    return os.path.abspath(path)


def artifact_tag(path: str, kind: str, title: str) -> str:
    clean_title = re.sub(r"[|\r\n]+", " ", str(title or "")).strip()
    return f"[ARTIFACT: {os.path.abspath(path)}|{kind}|{clean_title}]"


def generate_from_request(text: str, out_dir: Optional[str] = None) -> Optional[dict]:
    """Detect and materialise an artifact request.

    Returns a dict with ``path``, ``kind``, ``title`` and ``tag`` or ``None``
    when the message is not an artifact creation request.
    """
    request = detect_request(text)
    if not request:
        return None
    path = create_artifact(
        request["kind"],
        request["title"],
        out_dir=out_dir,
    )
    return {
        "path": path,
        "kind": request["kind"],
        "title": request["title"],
        "tag": artifact_tag(path, request["kind"], request["title"]),
        "label": KIND_LABELS.get(request["kind"], request["kind"].upper()),
    }


def parse_artifact_requests(text: str) -> list[dict]:
    """Parse ``[ARTIFACT: path|kind|title]`` tags from model output."""
    results = []
    for match in re.findall(r"\[ARTIFACT:\s*(.*?)\]", text or "", flags=re.DOTALL):
        parts = [part.strip() for part in match.split("|")]
        if not parts or not parts[0]:
            continue
        path = parts[0]
        kind = (parts[1] if len(parts) > 1 else os.path.splitext(path)[1].lstrip(".")).lower()
        title = parts[2] if len(parts) > 2 else os.path.splitext(os.path.basename(path))[0]
        results.append({"path": path, "kind": kind, "title": title})
    return results


def create_from_tag(meta: str, out_dir: Optional[str] = None) -> Optional[str]:
    """Create an artifact from ``kind|title|content`` (content optional).

    This helper is used by the OS executor for AI-emitted artifact tags.
    """
    parts = [part.strip() for part in str(meta or "").split("|", 2)]
    if len(parts) < 2:
        return None
    kind, title = parts[0], parts[1]
    content = parts[2] if len(parts) > 2 else None
    return create_artifact(kind, title, content=content, out_dir=out_dir)
