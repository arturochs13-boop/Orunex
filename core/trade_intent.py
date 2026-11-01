"""Deterministic detection of explicit paper-entry orders.

The desktop UI and the headless trading task must agree on what counts as an
explicit order.  This module is dependency-free so both entry points can use
it without importing the trading stack.  It never chooses a side: Muse still
decides BUY/SELL; this only distinguishes "do it now" from "analyse it".
"""

from __future__ import annotations

import json
import re
import unicodedata

_ANALYSIS_WORDS = (
    "analiza", "analizar", "analisis", "analysis", "analyse", "analyze",
    "revisa", "revisar", "evalua", "evaluar", "diagnostica", "diagnosticar",
    "explica", "explicar", "dime", "decime", "propone", "proponer",
    "sugiere", "sugerir", "recomienda", "recomendar", "opina", "opinar",
    "que opinas", "vale la pena", "conviene",
)

_QUESTION_START = re.compile(
    r"^\s*(?:que\b|como\b|cuando\b|debo\b|deberia\b|should\b|can\b|"
    r"could\b|puedes\b|podrias\b|me recomiendas\b|conviene\b|"
    r"vale la pena\b)"
)

_STRONG_ACTION = re.compile(
    r"\b(ejecuta|ejecutar|execute|compra|comprar|buy|vende|vender|sell)\b"
)

_ENTRY_ACTION = re.compile(
    r"\b(haz|hazme|abre|abrir|pon|poner|coloca|colocar|toma|tomar|"
    r"ordena|ordenar|lanza|lanzar|realiza|realizar|make|place|open|take|"
    r"enter)\b"
    r"[^.;!?]{0,60}\b(entrada|entry|orden|order|posicion|position|trade|"
    r"operacion)\b"
)

_LONG_SHORT = re.compile(
    r"\b(entra|entrar|abre|abrir|toma|tomar|pon|poner)\b"
    r"[^.;!?]{0,40}\b(largo|corto|long|short)\b"
)

_IMPERATIVE = re.compile(
    r"\b(haz|hazme|abre|ejecuta|pon|toma|coloca|ordena|realiza)\b"
)


def _fold(text: str) -> str:
    """Lower-case and strip accents without losing word boundaries."""
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("_", " ")
    value = re.sub(r"[^\w\s@.:/+-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _has_word(text: str, word: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text))


def symbol_from_title(title: str) -> str:
    """Extract a crypto symbol from a TradingView window title."""
    match = re.search(
        r"\b([A-Z]{2,12}(?:USDT|USDC|USD|BTC|ETH))\b",
        str(title or "").upper(),
    )
    return match.group(1) if match else ""


# Common function words are enough to tell a Spanish instruction from an
# English one without a heavyweight language detector.  Keep the sets
# disjoint: ambiguous tokens such as "a" and "no" are deliberately omitted.
_ENGLISH_HINTS = {
    "the", "and", "open", "make", "place", "entry", "trade", "buy", "sell",
    "please", "with", "for", "this", "that", "chart", "order", "paper",
    "analyze", "analyse", "analysis", "position", "close", "start", "stop",
    "take", "profit", "loss", "now", "can", "you", "your", "my", "me", "is",
    "are", "do", "does", "what", "how", "should", "could", "would", "it",
    "on", "in", "to", "of", "an", "hello", "thanks", "fix", "android",
}
_SPANISH_HINTS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
    "que", "y", "o", "abre", "abrir", "haz", "hacer", "entrada", "orden",
    "compra", "comprar", "vende", "vender", "por", "para", "con", "en",
    "es", "son", "puedes", "quiero", "gracias", "hola", "mi", "tu", "al",
    "posicion", "analisis", "analiza", "analizar", "cierra", "cerrar",
    "ahora", "como", "debo", "puedo", "corrige", "arregla", "emulador",
}


def detect_language(text: str, *, default: str = "es") -> str:
    """Return ``"es"`` or ``"en"`` for a user instruction.

    This is a routing hint for user-facing replies, not a linguistic
    classifier.  It intentionally favours the user's latest message so an
    English instruction never receives a canned Spanish delegation reply.
    """
    raw = str(text or "")
    folded = _fold(raw)
    if not folded:
        return default
    if re.search(r"[áéíóúñ¿¡]", raw.lower()):
        return "es"
    words = set(re.findall(r"[a-z]+", folded))
    english = len(words & _ENGLISH_HINTS)
    spanish = len(words & _SPANISH_HINTS)
    if english > spanish:
        return "en"
    if spanish > english:
        return "es"
    if re.match(
        r"^(open|make|place|buy|sell|close|start|analyze|analyse)\b", folded
    ):
        return "en"
    return default


def is_explicit_entry_request(
    text: str,
    *,
    note: str = "",
    execute: bool = False,
) -> bool:
    """True when the user ordered an entry, not merely an analysis.

    ``execute`` is the structured flag from a delegated alert.  The function
    also understands the natural-language forms used by the desktop UI:
    "haz una entrada", "abre una orden", "toma posición", "compra", "vende".
    A question or an analysis request is never treated as an order.
    """
    if execute:
        return True
    raw = str(text or "")
    # A delegated alert is JSON.  Inspect its values, never its keys: the
    # literal key "execute" made every analysis alert look like an order.
    payload = None
    if raw.lstrip().startswith("{"):
        try:
            payload = json.loads(raw)
        except Exception:
            payload = None
    if isinstance(payload, dict):
        flag = payload.get("execute")
        if flag is True or str(flag).strip().lower() in {
            "1", "true", "yes", "si", "sí",
        }:
            return True
        raw = " ".join(
            str(value) for value in payload.values() if isinstance(value, str)
        )
    combined = _fold(f"{raw} {note}")
    if not combined:
        return False
    if re.search(r'"execute"\s*:\s*true\b', combined):
        return True

    analysis = any(_has_word(combined, word) for word in _ANALYSIS_WORDS)
    strong = bool(_STRONG_ACTION.search(combined))
    entry = bool(_ENTRY_ACTION.search(combined)) or bool(_LONG_SHORT.search(combined))

    if not (strong or entry):
        return False
    # "Haz un análisis para una entrada" is still analysis.  A direct
    # "ejecuta" or "compra/vende" overrides that.
    if analysis and not strong:
        return False
    # A genuine question ("¿debo comprar?") is not an execution order.
    if _QUESTION_START.match(combined) and not _IMPERATIVE.search(combined):
        return False
    return True
