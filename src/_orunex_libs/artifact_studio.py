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
    "bmd": "Blockchain Markdown",
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
    "bmd": ".bmd",
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
        # Cut the request at the first data-introduction marker.  A title must
        # never absorb "con investigación de mercado y estas métricas: ...".
        value = re.split(
            r"(?i)\s+(?:con|with)\s+(?:investigaci[oó]n|research|datos|data|"
            r"m[eé]tricas|metrics|estas|estos|las siguientes|los siguientes)\b.*$",
            value,
        )[0]
        value = re.split(
            r"(?i)\s+(?:y|and)\s+(?:estas|estos|las siguientes|los siguientes)\s+"
            r"(?:m[eé]tricas|metricas|datos|data)\b.*$",
            value,
        )[0]
        value = re.split(
            r"(?i)\b(?:m[eé]tricas|metricas|datos|data)\s*:.*$", value
        )[0]
        # "con ventas 1250000 USD" / "con inversión USD 45000": a connector
        # followed by a metric name and a material number is data, not title.
        value = re.split(
            r"(?i)\s+(?:con|with)\s+[\wáéíóúüñ ]{2,30}?\s+\$?\d{2,}", value
        )[0]
        # Cut the request at the first list/metric marker so data dictated by
        # the user ("incluye: a, b, ventas: 100") never pollutes the title.
        value = re.split(
            r"(?i)[,;]?\s*(?:incluye|temas|contenido|secciones|apartados)\s*[:;,]",
            value,
        )[0]
        value = re.split(
            r"(?i)[,;]?\s*(?:incluye|incluyendo|que incluya|temas|contenido|secciones|apartados)\b.*$",
            value,
        )[0]
        value = re.split(
            r"(?i)\s+(?:with|con)\s+[\wáéíóúüñ ]{2,30}:\s*\$?\d",
            value,
        )[0]
        value = re.split(
            r"(?i)[,;]\s*[\wáéíóúüñ ]{2,30}:\s*\$?\d",
            value,
        )[0]
        value = re.split(r"(?i)\b[\wáéíóúüñ ]{2,30}:\s*\$?\d", value)[0]
        # Remove the command and file-type wording while preserving the topic.
        words = _strip_accents(value)
        for kind_word in dict(_KIND_WORDS).get(kind, ()):
            words = re.sub(
                rf"(?i)(?<!\w){re.escape(kind_word)}(?!\w)", " ", words
            )
        for generic in ("report", "informe", "document", "documento", "presentation", "presentación"):
            words = re.sub(rf"(?i)(?<!\w){re.escape(generic)}(?!\w)", " ", words)
        for verb in _CREATE_VERBS + _SOFT_INTENT:
            words = re.sub(rf"(?i)(?<!\w){re.escape(verb)}(?!\w)", " ", words)
        words = re.sub(
            r"(?i)\b(?:un|una|uno|el|la|los|las|de|del|sobre|acerca de|"
            r"for|about|on|the|a|an|please|por favor|que|con)\b",
            " ",
            words,
        )
        words = re.sub(r"\s+", " ", words).strip()
        # A deck title should name the subject, not its format adjective.
        adjectives = (
            r"(?:ejecutiva|ejecutivo|profesional|profesionales|completa|completo|"
            r"detallada|detallado|breve|visual|moderna|moderno|innovadora|"
            r"innovador|persuasiva|persuasivo|estrat[eé]gica|estrat[eé]gico)"
        )
        previous = None
        while previous != words:
            previous = words
            words = re.sub(rf"(?i)^{adjectives}\s+", "", words)
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


# ---------------------------------------------------------------------------
# Real information extraction.
#
# The old studio only received the *title* of a request, so every file came
# out with the same filler text.  These helpers mine the user's own words:
# labelled metrics ("ventas: 120000", "crecimiento 15%"), topic lists after
# "incluye/temas:" and plain sentences become the actual content of the file.
# ---------------------------------------------------------------------------
_NUMBER = r"(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
_METRIC_LABELLED = re.compile(
    r"([A-Za-zÁÉÍÓÚÜÑáéíóúüñ][\wÁÉÍÓÚÜÑáéíóúüñ /\-]{2,38}?)\s*[:=]\s*\$?\s*"
    + _NUMBER + r"\s*(%|por ciento|usd|mxn|eur|€)?",
    flags=re.IGNORECASE,
)
_METRIC_PLAIN = re.compile(
    r"\b(ventas|ingresos|ganancias|beneficio|clientes|usuarios|pedidos|"
    r"unidades|crecimiento|conversion|conversión|margen|ahorro|costo|coste|"
    r"precio|presupuesto|empleados|proyectos|entregas|satisfaccion|satisfacción)"
    r"\s+(?:de\s+|en\s+|del\s+)?\$?\s*"
    + _NUMBER + r"\s*(%|por ciento|usd|mxn|eur|€)?",
    flags=re.IGNORECASE,
)
# Strong metrics: a number followed (or preceded) by an explicit unit.  This
# catches real business phrasing such as "Inversión publicitaria 45.000 USD",
# "Ingresos generados 187.500 USD", "CAC 420 USD" or "Tasa de conversión 3,2%"
# that the label-anchored patterns above cannot see.
_METRIC_NUMBER = r"(?:\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
_STRONG_UNIT = r"(?:%|por\s+ciento|usd|mxn|eur|€|d[oó]lares?|pesos?|euros?)"
_STRONG_NUMBER = re.compile(
    r"(?<![\w.,])(?:\$\s*)?(?P<number>" + _METRIC_NUMBER + r")"
    r"\s*(?P<unit>" + _STRONG_UNIT + r")(?![a-z])",
    flags=re.IGNORECASE,
)
_STRONG_PREFIX = re.compile(
    r"(?<![\w.,])(?P<unit>usd|mxn|eur|€)\s*(?:\$\s*)?"
    r"(?P<number>" + _METRIC_NUMBER + r")(?![0-9])",
    flags=re.IGNORECASE,
)
_METRIC_LABEL_NOISE = {
    "estas", "estos", "siguientes", "siguiente", "los", "las", "el", "la",
    "un", "una", "unos", "unas", "del", "de", "en", "con", "para", "que",
    "fueron", "fue", "es", "son", "alcanzo", "alcanzó", "alcanzaron",
    "registro", "registró", "registraron", "totalizo", "totalizó",
    "totalizaron", "generados", "generadas", "obtenidos", "obtenidas",
    "alcanzados", "alcanzadas", "and", "with", "for", "the", "a", "an",
}
_LIST_MARKERS = (
    "incluye", "temas", "contenido", "puntos", "secciones", "apartados",
    "debe incluir", "con los temas", "sobre",
)
_STOP_LABELS = {
    "crea", "crear", "genera", "generar", "haz", "una", "uno", "un", "el", "la",
    "presentacion", "presentación", "excel", "word", "documento", "pptx", "xlsx",
    "docx", "powerpoint", "quiero", "necesito", "report", "informe", "sobre",
    "acerca", "para", "que", "con", "the", "about", "for", "and",
}


def _clean_metric_label(label: str) -> str:
    """Keep the actual metric name, not the whole request sentence.

    A user may write "Crea un Excel de ventas B2B con ingresos: 250000"; the
    label must be "Ingresos", not the command plus the file type.
    """
    text = _normalise(label).strip(" ,.;:-")
    text = re.split(r"[,\n;:]+", text)[-1]
    text = re.split(r"(?i)\s+(?:con|with)\s+", text)[-1]
    words = text.split()
    while words and _strip_accents(words[0].lower()) in _STOP_LABELS:
        words.pop(0)
    while words and _strip_accents(words[0].lower()) in {"de", "del", "en", "los", "las"}:
        words.pop(0)
    while words and _strip_accents(words[-1].lower()) in _METRIC_LABEL_NOISE:
        words.pop()
    if len(words) > 5:
        words = words[-4:]
    return " ".join(words)


def _label_before(text: str, position: int) -> str:
    """Recover the metric label that precedes a number in a sentence."""
    prefix = str(text or "")[:position]
    segment = re.split(r"[,;:\n]|\s+(?:y|and)\s+", prefix)[-1]
    words = segment.strip().split()
    if len(words) > 6:
        words = words[-6:]
    while words and _strip_accents(words[0].lower().strip(".,;:$")) in (
        _STOP_LABELS | _METRIC_LABEL_NOISE
    ):
        words.pop(0)
    while words and (
        _strip_accents(words[-1].lower().strip(".,;:$")) in _METRIC_LABEL_NOISE
        or re.fullmatch(r"(?:19|20)\d{2}", words[-1])
    ):
        words.pop()
    return " ".join(words).strip(" .,;:$")


def _metric_label_contains(long_label: str, short_label: str) -> bool:
    if not short_label:
        return False
    return (
        re.search(rf"(?<!\w){re.escape(short_label)}(?!\w)", long_label)
        is not None
    )


def _parse_number(raw: str) -> float:
    """Parse Spanish/English business numbers without losing thousands.

    "45.000" and "187.500" are thousands in Spanish; "3,2" is a decimal comma;
    "1,234.56" and "1.234,56" both mean 1234.56.  Treating every dot as a
    decimal point turned 45.000 USD into 45 USD.
    """
    value = str(raw or "").replace("\u00a0", "").replace(" ", "").strip()
    if not value:
        return 0.0
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        parts = value.split(",")
        if len(parts) > 2 or (
            len(parts) == 2
            and len(parts[1]) == 3
            and 0 < len(parts[0]) <= 3
            and parts[0] != "0"
        ):
            value = value.replace(",", "")
        else:
            value = value.replace(",", ".")
    elif "." in value:
        parts = value.split(".")
        if len(parts) > 2 or (
            len(parts) == 2
            and len(parts[1]) == 3
            and 0 < len(parts[0]) <= 3
            and parts[0] != "0"
        ):
            value = value.replace(".", "")
    try:
        return float(value)
    except ValueError:
        return 0.0


def _format_metric_value(value: float, unit: str) -> str:
    unit = (unit or "").strip().lower()
    if unit in {"%", "por ciento"}:
        return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " %"
    text = f"{value:,.2f}".rstrip("0").rstrip(".")
    text = text.replace(",", " ")
    return f"{text} {unit.upper()}".strip() if unit else text


def _metric_record(label: str, value: float, unit: str) -> Optional[dict]:
    clean = _clean_metric_label(label)
    if not clean:
        return None
    first = _strip_accents(clean.split()[0].lower())
    if first in _STOP_LABELS or first in _METRIC_LABEL_NOISE:
        return None
    if not any(ch.isalpha() for ch in clean):
        return None
    return {
        "label": clean[:1].upper() + clean[1:],
        "value": value,
        "unit": unit,
        "display": _format_metric_value(value, unit),
    }


def extract_metrics(text: str) -> list[dict]:
    """Return [{label, value, unit, display}] mined from the request text.

    Three passes are merged: explicit unit-bearing values ("CAC 420 USD"),
    labelled values ("ventas: 120000") and the classic keyword pattern.  When
    two labels overlap, the more specific one wins ("Tasa de conversión" over
    "Conversión") and duplicate values are collapsed.
    """
    raw = str(text or "")
    candidates: list[dict] = []

    for match in _STRONG_NUMBER.finditer(raw):
        label = _label_before(raw, match.start())
        record = _metric_record(
            label, _parse_number(match.group("number")), match.group("unit")
        )
        if record:
            candidates.append(record)

    for match in _STRONG_PREFIX.finditer(raw):
        label = _label_before(raw, match.start())
        record = _metric_record(
            label, _parse_number(match.group("number")), match.group("unit")
        )
        if record:
            candidates.append(record)

    for pattern in (_METRIC_LABELLED, _METRIC_PLAIN):
        for match in pattern.finditer(raw):
            record = _metric_record(
                match.group(1),
                _parse_number(match.group(2)),
                (match.group(3) or "").strip(),
            )
            if record:
                candidates.append(record)

    found: list[dict] = []
    for candidate in candidates:
        key = _strip_accents(candidate["label"].lower())
        duplicate = False
        for index, existing in enumerate(found):
            other = _strip_accents(existing["label"].lower())
            if key == other:
                duplicate = True
                break
            if _metric_label_contains(key, other) or _metric_label_contains(other, key):
                if len(key) > len(other):
                    found[index] = candidate
                duplicate = True
                break
        if not duplicate:
            found.append(candidate)
        if len(found) >= 8:
            break
    return found


def extract_bullets(text: str, limit: int = 8) -> list[str]:
    """Pull a topic list out of the request ("incluye: A, B y C")."""
    raw = _normalise(text)
    lowered = _strip_accents(raw.lower())
    segment = ""
    for marker in _LIST_MARKERS:
        index = lowered.find(marker)
        if index >= 0:
            segment = raw[index + len(marker):].lstrip(" :.-")
            break
    items: list[str] = []
    if segment:
        parts = re.split(r"[,;•\n]| y | e ", segment)
        for part in parts:
            clean = part.strip(" .:-")
            if len(clean) < 3:
                continue
            # "ventas: 1250000" is a metric, not a topic/section.
            if _METRIC_LABELLED.search(clean) or _METRIC_PLAIN.search(clean):
                continue
            # Drop trailing file/command words the splitter may keep.
            clean = re.sub(
                r"(?i)\b(?:en|con|para|formato)?\s*(?:powerpoint|pptx|excel|xlsx|word|docx|pdf)\b.*$",
                "",
                clean,
            ).strip(" .:-")
            if len(clean) >= 3:
                items.append(clean[:1].upper() + clean[1:])
            if len(items) >= limit:
                break
    return items


def extract_request_data(text: str, title: str) -> dict:
    """Assemble everything the builders need from one user request."""
    metrics = extract_metrics(text)
    bullets = extract_bullets(text)
    return {"title": title, "metrics": metrics, "bullets": bullets, "raw": text}



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


def _excel_rows(title: str, data: Optional[dict] = None) -> list[list[object]]:
    metrics = (data or {}).get("metrics") or []
    if metrics:
        rows: list[list[object]] = [["Metrica", "Valor", "Unidad"]]
        for metric in metrics:
            rows.append([metric["label"], metric["value"], metric["unit"] or ""])
        return rows
    return [
        ["Elemento", "Detalle", "Cantidad", "Valor"],
        ["Objetivo", f"Definir el alcance de {title}", 1, 0],
        ["Contexto", "Reunir informacion y fuentes relevantes", 3, 0],
        ["Analisis", "Comparar alternativas y riesgos", 4, 0],
        ["Ejecucion", "Preparar el entregable principal", 5, 0],
        ["Validacion", "Revisar resultados con criterios de aceptacion", 2, 0],
        ["Seguimiento", "Registrar avances y proximos pasos", 2, 0],
    ]


_PPTX_THEMES = (
    {
        "name": "Ejecutivo Azul",
        "bg": (13, 27, 62),
        "panel": (21, 42, 92),
        "accent": (30, 102, 245),
        "accent2": (56, 189, 248),
        "text": (255, 255, 255),
        "muted": (170, 196, 240),
        "content_bg": (255, 255, 255),
        "content_text": (20, 33, 61),
        "content_muted": (90, 106, 133),
    },
    {
        "name": "Corporativo Claro",
        "bg": (238, 244, 252),
        "panel": (255, 255, 255),
        "accent": (0, 128, 128),
        "accent2": (30, 102, 245),
        "text": (15, 42, 67),
        "muted": (84, 110, 138),
        "content_bg": (255, 255, 255),
        "content_text": (15, 42, 67),
        "content_muted": (84, 110, 138),
    },
    {
        "name": "Premium Oscuro",
        "bg": (16, 16, 22),
        "panel": (28, 28, 38),
        "accent": (212, 175, 55),
        "accent2": (245, 197, 66),
        "text": (255, 255, 255),
        "muted": (196, 188, 160),
        "content_bg": (22, 22, 30),
        "content_text": (245, 245, 245),
        "content_muted": (168, 168, 178),
    },
)


def pick_theme(raw: str, title: str) -> dict:
    """Choose a deck design: explicit style words win, else vary by topic."""
    lowered = _strip_accents(f"{raw} {title}".lower())
    if any(word in lowered for word in ("dorado", "gold", "premium", "lujo")):
        return _PPTX_THEMES[2]
    if any(word in lowered for word in ("claro", "light", "blanco", "simple")):
        return _PPTX_THEMES[1]
    if any(word in lowered for word in ("oscuro", "dark", "negro")):
        return _PPTX_THEMES[2]
    # Different topics get different looks instead of one fixed template.
    return _PPTX_THEMES[sum(ord(c) for c in title) % len(_PPTX_THEMES)]


def _slides(title: str, data: Optional[dict] = None) -> list[dict]:
    """Build a deck outline from the real request data, not filler text."""
    data = data or {}
    metrics: list[dict] = data.get("metrics") or []
    topics: list[str] = data.get("bullets") or []
    theme = pick_theme(str(data.get("raw") or ""), title)

    slides: list[dict] = [
        {
            "layout": "cover",
            "title": title,
            "subtitle": f"Presentacion profesional - {_date_label()}",
            "bullets": [],
            "theme": theme["name"],
        }
    ]
    if topics:
        slides.append(
            {
                "layout": "agenda",
                "title": "Agenda",
                "bullets": [f"{i + 1}. {topic}" for i, topic in enumerate(topics)],
            }
        )
    intro_bullets = topics[:4] or [
        f"Tema central: {title}.",
        "Objetivos, alcance y resultados esperados.",
        "Datos y metricas que respaldan las decisiones.",
    ]
    slides.append({"layout": "bullets", "title": "Contexto y objetivos", "bullets": intro_bullets})
    if metrics:
        slides.append(
            {
                "layout": "kpis",
                "title": "Metricas clave",
                "bullets": [],
                "metrics": metrics,
            }
        )
        slides.append(
            {
                "layout": "bullets",
                "title": "Lectura de los datos",
                "bullets": [
                    f"{m['label']}: {m['display']}." for m in metrics[:5]
                ],
            }
        )
    for topic in topics[:5]:
        slides.append(
            {
                "layout": "bullets",
                "title": topic,
                "bullets": [
                    f"Que es: {topic} dentro de {title}.",
                    "Por que importa: impacto directo en el resultado.",
                    "Como se ejecuta: responsable, fecha y criterio de exito.",
                ],
            }
        )
    slides.append(
        {
            "layout": "bullets",
            "title": "Plan de accion",
            "bullets": [
                "1. Confirmar objetivos y responsables.",
                "2. Ejecutar por fases con hitos medibles.",
                "3. Revisar metricas y ajustar cada semana.",
                "4. Documentar decisiones y resultados.",
            ],
        }
    )
    slides.append(
        {
            "layout": "closing",
            "title": "Conclusiones",
            "subtitle": "Gracias - Preguntas y siguientes pasos",
            "bullets": [
                f"{title}: decision informada, no improvisada.",
                "Siguiente paso: aprobar el plan y asignar responsables.",
            ],
        }
    )
    return slides


def _content_from_data(title: str, data: Optional[dict], kind_label: str) -> str:
    """Executive body text built from the extracted request data."""
    data = data or {}
    metrics: list[dict] = data.get("metrics") or []
    topics: list[str] = data.get("bullets") or []
    lines = [f"# Resumen ejecutivo", ""]
    if metrics:
        kpi_text = "; ".join(f"{m['label']} {m['display']}" for m in metrics[:4])
        lines.append(
            f"Este {kind_label} presenta {title} con datos concretos: {kpi_text}. "
            "Las cifras proceden de la solicitud y deben validarse antes de "
            "compartirse fuera del equipo."
        )
    elif topics:
        lines.append(
            f"Este {kind_label} desarrolla {title} a partir de los temas "
            f"solicitados: {', '.join(topics[:4])}."
        )
    else:
        lines.append(
            f"Este {kind_label} presenta {title} de forma estructurada: "
            "contexto, analisis y un plan de accion verificable."
        )
    lines += ["", "## Datos y metricas", ""]
    if metrics:
        for metric in metrics:
            lines.append(f"- {metric['label']}: {metric['display']}")
    else:
        lines.append("- Sin metricas en la solicitud: se deja la estructura lista para completarlas.")
    lines += ["", "## Desarrollo", ""]
    for topic in (topics or ["Contexto", "Analisis", "Riesgos y mitigacion"]):
        lines.append(f"### {topic}")
        lines.append(
            f"{topic} se aborda dentro de {title} con responsable, fecha y "
            "criterio de aceptacion definidos antes de ejecutar."
        )
        lines.append("")
    lines += [
        "## Conclusiones y recomendaciones",
        "",
        f"- Priorizar lo que las metricas de {title} ya muestran, no opiniones.",
        "- Asignar un responsable y una fecha a cada accion.",
        "- Revisar el avance semanalmente y registrar las decisiones.",
    ]
    return "\n".join(lines)



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


def _write_docx(path: str, title: str, content: Optional[str], data: Optional[dict] = None) -> None:
    import docx  # type: ignore
    from docx.enum.text import WD_ALIGN_PARAGRAPH  # type: ignore
    from docx.oxml.ns import qn  # type: ignore
    from docx.shared import Pt, RGBColor  # type: ignore

    document = docx.Document()
    metrics = (data or {}).get("metrics") or []

    # Base executive styling.
    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    for section in document.sections:
        footer = section.footer.paragraphs[0]
        footer.text = f"Orunex - Informe ejecutivo - {_date_label()}"
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if footer.runs:
            footer.runs[0].font.size = Pt(8)
            footer.runs[0].font.color.rgb = RGBColor(0x5A, 0x6A, 0x85)

    # Cover.
    cover_title = document.add_heading(title, level=0)
    cover_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle = document.add_paragraph("Informe ejecutivo")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.runs[0].font.size = Pt(14)
    subtitle.runs[0].font.color.rgb = RGBColor(0x1E, 0x66, 0xF5)
    meta = document.add_paragraph(f"Orunex - {_date_label()}")
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.runs[0].font.size = Pt(10)
    meta.runs[0].italic = True
    document.add_page_break()

    # Simple index of what the document contains.
    document.add_heading("Indice", level=1)
    index_items = ["Resumen ejecutivo", "Datos y metricas", "Desarrollo",
                   "Conclusiones y recomendaciones"]
    for item in index_items:
        document.add_paragraph(item, style="List Bullet")

    def shade(cell, hex_color: str) -> None:
        tc_pr = cell._tc.get_or_add_tcPr()
        shd = tc_pr.makeelement(qn("w:shd"), {
            qn("w:val"): "clear", qn("w:color"): "auto", qn("w:fill"): hex_color,
        })
        tc_pr.append(shd)

    lines = _content_lines(content, title)
    in_metrics_section = False
    table_done = False
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            heading = line[3:].strip()
            in_metrics_section = "metrica" in heading.lower() or "datos" in heading.lower()
            document.add_heading(heading, level=1)
            # The KPI table goes right inside the metrics section.
            if in_metrics_section and metrics and not table_done:
                table_done = True
                table = document.add_table(rows=1, cols=3)
                table.style = "Table Grid"
                header = table.rows[0].cells
                for cell, text in zip(header, ("Metrica", "Valor", "Unidad")):
                    cell.text = text
                    shade(cell, "1E66F5")
                    for run in cell.paragraphs[0].runs:
                        run.font.bold = True
                        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                for metric in metrics:
                    cells = table.add_row().cells
                    cells[0].text = str(metric["label"])
                    cells[1].text = str(metric["display"])
                    cells[2].text = str(metric["unit"] or "")
            continue
        if line.startswith("### "):
            document.add_heading(line[4:].strip(), level=2)
        elif line.startswith("# "):
            document.add_heading(line[2:].strip(), level=1)
        elif re.match(r"^\d+[\.\)]\s", line):
            document.add_paragraph(line, style="List Number")
        elif line.startswith(("- ", "* ")):
            # Metric bullets are already in the table; do not duplicate.
            if in_metrics_section and metrics and table_done:
                continue
            document.add_paragraph(line[2:].strip(), style="List Bullet")
        else:
            document.add_paragraph(line)

    # Recommendations always close an executive document.
    if not any("recomend" in line.lower() for line in lines):
        document.add_heading("Recomendaciones", level=1)
        for recommendation in (
            f"Priorizar lo que las metricas de {title} ya muestran.",
            "Asignar responsable y fecha a cada accion aprobada.",
            "Revisar el avance semanalmente y registrar las decisiones.",
        ):
            document.add_paragraph(recommendation, style="List Bullet")
    document.save(path)



def _write_xlsx(path: str, title: str, rows: Optional[Sequence[Sequence[object]]], data: Optional[dict] = None) -> None:
    data_rows = list(rows) if rows else _excel_rows(title, data)
    if not data_rows:
        data_rows = _excel_rows(title, data)
    metrics = (data or {}).get("metrics") or []
    try:
        from openpyxl import Workbook  # type: ignore
        from openpyxl.chart import BarChart, Reference  # type: ignore
        from openpyxl.formatting.rule import CellIsRule  # type: ignore
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # type: ignore
        from openpyxl.utils import get_column_letter  # type: ignore

        workbook = Workbook()
        navy = "0D1B3E"
        blue = "1E66F5"
        light = "EDF4FF"
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill("solid", fgColor=blue)
        thin = Side(style="thin", color="D5E1F5")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        def style_header(sheet, row_index=1):
            for cell in sheet[row_index]:
                if cell.value is None:
                    continue
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = border

        def auto_width(sheet, limit=46):
            for col_index, column in enumerate(sheet.columns, start=1):
                letter = get_column_letter(col_index)
                width = max(12, min(limit, max(len(str(c.value or "")) for c in column) + 3))
                sheet.column_dimensions[letter].width = width

        def format_numbers(sheet, start_row=2):
            for row in sheet.iter_rows(min_row=start_row):
                for cell in row:
                    if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                        cell.number_format = '#,##0.00'
                        cell.alignment = Alignment(horizontal="right")

        # ---- Resumen: portada de KPIs -------------------------------------
        summary = workbook.active
        summary.title = "Resumen"
        summary.merge_cells("A1:D1")
        title_cell = summary["A1"]
        title_cell.value = title
        title_cell.font = Font(bold=True, color="FFFFFF", size=16)
        title_cell.fill = PatternFill("solid", fgColor=navy)
        title_cell.alignment = Alignment(horizontal="left", vertical="center")
        summary.row_dimensions[1].height = 30
        summary["A2"] = f"Informe de metricas - Orunex - {_date_label()}"
        summary["A2"].font = Font(italic=True, color="5A6A85", size=10)
        summary.append([])
        summary.append(["Metrica", "Valor", "Unidad", "Lectura"])
        style_header(summary, 4)
        if metrics:
            for metric in metrics:
                lectura = "Dato de la solicitud" if metric["value"] else "A completar"
                summary.append([metric["label"], metric["value"], metric["unit"] or "", lectura])
        else:
            summary.append(["Sin metricas en la solicitud", "", "", "Completar con datos reales"])
        format_numbers(summary, 5)
        # Percent units read as percentages, never as raw decimals.
        for row in summary.iter_rows(min_row=5):
            unit = str(row[2].value or "").lower()
            if unit in {"%", "por ciento"} and isinstance(row[1].value, (int, float)):
                row[1].number_format = '0.00" %"'
        summary.freeze_panes = "A5"
        auto_width(summary)

        # ---- Datos: la tabla fuente --------------------------------------
        data_sheet = workbook.create_sheet("Datos")
        for row in data_rows:
            data_sheet.append(list(row))
        style_header(data_sheet, 1)
        format_numbers(data_sheet, 2)
        data_sheet.freeze_panes = "A2"
        # Real totals: a SUM formula over the first numeric column of data.
        if len(data_rows) > 1:
            header = [str(v or "") for v in data_rows[0]]
            numeric_col = None
            for col_index in range(len(header)):
                values = [r[col_index] for r in data_rows[1:] if col_index < len(r)]
                if sum(isinstance(v, (int, float)) for v in values) >= max(1, len(values) // 2):
                    numeric_col = col_index
                    break
            if numeric_col is not None:
                letter = get_column_letter(numeric_col + 1)
                total_row = len(data_rows) + 1
                data_sheet.cell(row=total_row, column=1, value="TOTAL").font = Font(bold=True)
                total_cell = data_sheet.cell(
                    row=total_row, column=numeric_col + 1,
                    value=f"=SUM({letter}2:{letter}{len(data_rows)})",
                )
                total_cell.font = Font(bold=True)
                total_cell.number_format = '#,##0.00'
        auto_width(data_sheet)

        # ---- Grafico: solo si hay serie numerica que graficar -------------
        chart_source = metrics if metrics else None
        if chart_source and len(chart_source) >= 2:
            chart_sheet = workbook.create_sheet("Grafico")
            chart_sheet.append(["Metrica", "Valor"])
            style_header(chart_sheet, 1)
            for metric in chart_source:
                chart_sheet.append([metric["label"], metric["value"]])
            format_numbers(chart_sheet, 2)
            chart = BarChart()
            chart.type = "col"
            chart.title = f"Metricas - {title}"
            chart.y_axis.title = "Valor"
            chart.x_axis.title = "Metrica"
            chart.style = 10
            chart.height = 9
            chart.width = 17
            values = Reference(chart_sheet, min_col=2, min_row=1, max_row=len(chart_source) + 1)
            categories = Reference(chart_sheet, min_col=1, min_row=2, max_row=len(chart_source) + 1)
            chart.add_data(values, titles_from_data=True)
            chart.set_categories(categories)
            chart.shape = 4
            chart_sheet.add_chart(chart, "D2")
            auto_width(chart_sheet)
        workbook.save(path)
        return
    except Exception:
        pass
    # Dependency-free fallback: a small but valid OOXML workbook.
    _write_minimal_xlsx(path, data_rows)


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
    from pptx.dml.color import RGBColor  # type: ignore
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore
    from pptx.enum.text import PP_ALIGN  # type: ignore
    from pptx.util import Emu, Inches, Pt  # type: ignore

    deck = Presentation()
    deck.slide_width = Inches(13.333)
    deck.slide_height = Inches(7.5)
    items = list(slides) if slides else _slides(title)
    theme_name = str(items[0].get("theme") or "") if items else ""
    theme = next(
        (t for t in _PPTX_THEMES if t["name"] == theme_name), _PPTX_THEMES[0]
    )
    blank = deck.slide_layouts[6]
    width = float(deck.slide_width)
    height = float(deck.slide_height)

    def rgb(triple) -> RGBColor:
        return RGBColor(int(triple[0]), int(triple[1]), int(triple[2]))

    def add_rect(slide, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE):
        shape_obj = slide.shapes.add_shape(shape, Emu(int(x)), Emu(int(y)), Emu(int(w)), Emu(int(h)))
        shape_obj.fill.solid()
        shape_obj.fill.fore_color.rgb = rgb(color)
        shape_obj.line.fill.background()
        shape_obj.shadow.inherit = False
        return shape_obj

    def add_text(slide, x, y, w, h, text, size, color, bold=False, align=PP_ALIGN.LEFT):
        box = slide.shapes.add_textbox(Emu(int(x)), Emu(int(y)), Emu(int(w)), Emu(int(h)))
        frame = box.text_frame
        frame.word_wrap = True
        paragraph = frame.paragraphs[0]
        paragraph.text = str(text)
        paragraph.font.size = Pt(size)
        paragraph.font.bold = bold
        paragraph.font.color.rgb = rgb(color)
        paragraph.alignment = align
        return box

    def bg(slide, color):
        add_rect(slide, 0, 0, width, height, color)

    total = len(items)
    for index, item in enumerate(items):
        item_title = str(item.get("title") or title)
        subtitle = str(item.get("subtitle") or "")
        bullets = [str(b) for b in item.get("bullets", []) if str(b).strip()]
        layout = str(item.get("layout") or ("cover" if index == 0 else "bullets"))
        slide = deck.slides.add_slide(blank)

        if layout == "cover":
            bg(slide, theme["bg"])
            add_rect(slide, 0, height * 0.62, width, Inches(0.09), theme["accent"])
            add_rect(slide, Inches(0.9), Inches(1.15), Inches(0.85), Inches(0.12), theme["accent2"])
            add_text(slide, Inches(0.9), Inches(1.55), Inches(11.4), Inches(2.2), item_title, 40, theme["text"], bold=True)
            add_text(slide, Inches(0.9), Inches(3.6), Inches(10.5), Inches(1.0),
                     subtitle or f"Presentacion profesional - {_date_label()}", 20, theme["muted"])
            add_text(slide, Inches(0.9), Inches(6.55), Inches(8.0), Inches(0.5),
                     f"Orunex - {theme['name']} - {_date_label()}", 12, theme["muted"])
            continue

        if layout == "closing":
            bg(slide, theme["bg"])
            add_rect(slide, 0, Inches(1.0), width, Inches(0.09), theme["accent"])
            add_text(slide, Inches(0.9), Inches(1.6), Inches(11.4), Inches(1.2), item_title, 36, theme["text"], bold=True)
            y = 3.1
            for bullet in bullets:
                add_text(slide, Inches(1.1), Inches(y), Inches(10.8), Inches(0.7), f"•  {bullet}", 18, theme["muted"])
                y += 0.85
            add_text(slide, Inches(0.9), Inches(6.4), Inches(11.0), Inches(0.6),
                     subtitle or "Gracias", 16, theme["accent2"], bold=True)
            continue

        # Content slides: light/dark surface with an accent header band.
        bg(slide, theme["content_bg"])
        add_rect(slide, 0, 0, width, Inches(1.18), theme["bg"])
        add_rect(slide, 0, Inches(1.18), width, Inches(0.07), theme["accent"])
        add_text(slide, Inches(0.6), Inches(0.28), Inches(10.8), Inches(0.7), item_title, 26, theme["text"], bold=True)
        add_text(slide, Inches(11.7), Inches(0.36), Inches(1.0), Inches(0.5),
                 f"{index + 1}/{total}", 12, theme["muted"], align=PP_ALIGN.RIGHT)

        if layout == "kpis":
            metrics = list(item.get("metrics") or [])[:4]
            card_w, card_h = Inches(2.95), Inches(2.0)
            gap, start_x, start_y = Inches(0.32), Inches(0.6), 1.75
            for m_index, metric in enumerate(metrics):
                x = start_x + m_index * (card_w + gap)
                add_rect(slide, Inches(x), Inches(start_y), card_w, card_h,
                         theme["panel"], MSO_SHAPE.ROUNDED_RECTANGLE)
                add_rect(slide, Inches(x), Inches(start_y), card_w, Inches(0.10), theme["accent"])
                add_text(slide, Inches(x + 0.25), Inches(start_y + 0.35), card_w - Inches(0.5), Inches(0.8),
                         str(metric.get("display") or metric.get("value") or ""), 30, theme["accent2"], bold=True)
                add_text(slide, Inches(x + 0.25), Inches(start_y + 1.25), card_w - Inches(0.5), Inches(0.6),
                         str(metric.get("label") or ""), 14, theme["text"])
            add_text(slide, Inches(0.6), Inches(4.3), Inches(12.0), Inches(0.6),
                     "Cifras extraidas de la solicitud. Validar antes de compartir externamente.",
                     13, theme["content_muted"])
            continue

        y = 1.62
        for bullet in bullets[:7]:
            add_rect(slide, Inches(0.68), Inches(y + 0.10), Inches(0.16), Inches(0.16),
                     theme["accent"], MSO_SHAPE.OVAL)
            add_text(slide, Inches(1.05), Inches(y), Inches(11.4), Inches(0.75), bullet, 18, theme["content_text"])
            y += 0.78
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
    data: Optional[dict] = None,
    plan: Optional[dict] = None,
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

    if plan is not None and kind in {"pptx", "xlsx", "docx", "md", "html", "txt"}:
        from . import office_expert as _office

        _office.build_artifact(path, kind, plan)
        return os.path.abspath(path)

    if plan is not None and kind == "pdf":
        from . import office_expert as _office

        content = _office.plan_to_markdown(plan)

    if kind == "pdf":
        _write_pdf(path, title, content)
    elif kind == "docx":
        _write_docx(path, title, content, data)
    elif kind == "xlsx":
        _write_xlsx(path, title, rows, data)
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
    kind, title = request["kind"], request["title"]
    data = extract_request_data(request["raw"], title)
    lang = "es"
    plan = None
    if kind in {"pptx", "xlsx", "docx", "pdf", "md", "html", "txt"}:
        try:
            from . import office_expert as _office

            lang = _office.detect_language(request["raw"])
            title = _office.polish_title(title, lang)
            plan = _office.build_plan(title, request["raw"], data, lang, research_enabled=True)
        except Exception:
            plan = None
    es = lang == "es"

    content = rows = slides = None
    summary_bits: list[str] = []
    if plan is not None:
        from . import office_expert as _office

        data["metrics"] = plan["metrics"]
        if kind == "pptx":
            slide_count = len(_office._select_slides(plan))
            theme_name = _office.THEMES.get(plan.get("theme", "navy"), _office.THEMES["navy"])["name"]
            summary_bits.append(f"{slide_count} diapositivas" if es else f"{slide_count} slides")
            summary_bits.append(f"tema {theme_name}" if es else f"{theme_name} theme")
            summary_bits.append("animaciones y notas del orador" if es else "animations and speaker notes")
        elif kind == "xlsx":
            summary_bits.append("hojas Dashboard, Datos, Análisis, Plan e Investigación" if es
                                else "Dashboard, Data, Analysis, Plan and Research sheets")
            if _office._chart_metrics(plan["metrics"]):
                summary_bits.append("gráfico nativo" if es else "native chart")
        elif kind == "docx":
            summary_bits.append("informe con portada, índice, tablas y gráfico" if es
                                else "report with cover, table of contents, tables and chart")
        elif kind in {"pdf", "md", "html", "txt"}:
            summary_bits.append("informe ejecutivo con índice y recomendaciones" if es
                                else "executive report with contents and recommendations")
    else:
        if kind == "pptx":
            slides = _slides(title, data)
            summary_bits.append(f"{len(slides)} diapositivas" if es else f"{len(slides)} slides")
            summary_bits.append(f"tema {slides[0].get('theme', 'Ejecutivo Azul')}" if es
                                else f"theme {slides[0].get('theme', 'Executive Blue')}")
        elif kind == "xlsx":
            rows = _excel_rows(title, data)
            summary_bits.append("hojas Resumen, Datos" + (", Grafico" if len(data["metrics"]) >= 2 else "")
                                if es else
                                "Summary and Data sheets" + (", Chart" if len(data["metrics"]) >= 2 else ""))
        elif kind in {"docx", "pdf", "md", "html", "txt"}:
            content = _content_from_data(title, data, "documento" if es else "document")
            summary_bits.append("informe ejecutivo con indice y recomendaciones" if es
                                else "executive report with contents and recommendations")

    if data["metrics"]:
        metric_names = ", ".join(m["label"] for m in data["metrics"][:4])
        summary_bits.append(f"{len(data['metrics'])} métricas de la solicitud: {metric_names}" if es
                            else f"{len(data['metrics'])} metrics from the request: {metric_names}")
    elif kind in {"pptx", "xlsx", "docx"}:
        summary_bits.append("sin métricas en la solicitud (estructura lista para completar)" if es
                            else "no metrics in the request (structure ready to complete)")

    path = create_artifact(
        kind,
        title,
        content=content,
        rows=rows,
        slides=slides,
        out_dir=out_dir,
        data=data,
        plan=plan,
    )
    return {
        "path": path,
        "kind": kind,
        "title": title,
        "lang": lang,
        "tag": artifact_tag(path, kind, title),
        "label": KIND_LABELS.get(kind, kind.upper()),
        "summary": " · ".join(summary_bits),
        "metrics": data["metrics"],
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
