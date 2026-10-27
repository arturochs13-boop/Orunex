"""Fast, deterministic understanding of short desktop commands.

Live mode needs two things that a remote LLM is bad at:

* instant reactions to short, unambiguous commands such as "abre YouTube en
  Chrome" (no network round-trip), and
* refusing to act when the command is ambiguous.  The old path sent a bare
  "abre" to the model and the model guessed an application, once opening Word.

``parse_command`` is deliberately local, pure Python and cheap enough to run on
every message.  It only handles high-confidence desktop intents.  Everything
that needs reasoning, current information, or file work still goes to the
normal agent pipeline.  Context (the last opened website/browser and the last
app) lets short follow-ups such as "en Chrome" or "otra vez" work naturally.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Intent:
    kind: str
    label: str = ""
    url: str = ""
    browser: str = ""
    app: str = ""
    query: str = ""
    message: str = ""
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Normalisation and vocabularies

def _fold(text: str) -> str:
    """Lower-case, de-accent and collapse punctuation for tolerant matching."""
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("_", " ")
    value = re.sub(r"[^\w\sáéíóúüñ@.:/+-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


SITES = {
    "youtube": ("https://www.youtube.com", "YouTube"),
    "google": ("https://www.google.com", "Google"),
    "gmail": ("https://mail.google.com", "Gmail"),
    "whatsapp": ("https://web.whatsapp.com", "WhatsApp Web"),
    "chatgpt": ("https://chatgpt.com", "ChatGPT"),
    "gemini": ("https://gemini.google.com", "Gemini"),
    "facebook": ("https://www.facebook.com", "Facebook"),
    "instagram": ("https://www.instagram.com", "Instagram"),
    "twitter": ("https://x.com", "X"),
    " x ": ("https://x.com", "X"),
    "github": ("https://github.com", "GitHub"),
    "stackoverflow": ("https://stackoverflow.com", "Stack Overflow"),
    "netflix": ("https://www.netflix.com", "Netflix"),
    "spotify": ("https://open.spotify.com", "Spotify"),
    "amazon": ("https://www.amazon.com", "Amazon"),
    "wikipedia": ("https://www.wikipedia.org", "Wikipedia"),
    "mercadolibre": ("https://www.mercadolibre.com", "Mercado Libre"),
    "outlook": ("https://outlook.live.com", "Outlook"),
    "drive": ("https://drive.google.com", "Google Drive"),
    "docs": ("https://docs.google.com", "Google Docs"),
    "sheets": ("https://sheets.google.com", "Google Sheets"),
    "maps": ("https://maps.google.com", "Google Maps"),
    "translate": ("https://translate.google.com", "Google Translate"),
    "twitch": ("https://www.twitch.tv", "Twitch"),
    "tiktok": ("https://www.tiktok.com", "TikTok"),
    "openai": ("https://openai.com", "OpenAI"),
    "orunex": ("", ""),
}

SITE_ALIASES = {
    "youtube": ("youtube", "yt", "you tube"),
    "google": ("google",),
    "gmail": ("gmail", "correo de google"),
    "whatsapp": ("whatsapp", "wasap"),
    "chatgpt": ("chatgpt", "chat gpt"),
    "gemini": ("gemini",),
    "facebook": ("facebook", "face"),
    "instagram": ("instagram", "insta"),
    "twitter": ("twitter",),
    "x": ("x com", "x.com"),
    "github": ("github",),
    "stackoverflow": ("stackoverflow", "stack overflow"),
    "netflix": ("netflix",),
    "spotify": ("spotify",),
    "amazon": ("amazon",),
    "wikipedia": ("wikipedia", "wiki"),
    "mercadolibre": ("mercadolibre", "mercado libre"),
    "outlook": ("outlook", "hotmail"),
    "drive": ("google drive", "drive"),
    "docs": ("google docs", "documentos de google"),
    "sheets": ("google sheets", "hojas de calculo de google"),
    "maps": ("google maps", "mapas"),
    "translate": ("google translate", "traductor de google"),
    "twitch": ("twitch",),
    "tiktok": ("tiktok",),
    "openai": ("openai",),
}

BROWSERS = {
    "chrome": ("chrome", "google chrome", "crome", "crom"),
    "edge": ("edge", "microsoft edge", "msedge"),
    "firefox": ("firefox", "mozilla firefox", "mozzila"),
    "brave": ("brave", "brave browser"),
    "opera": ("opera",),
    "vivaldi": ("vivaldi",),
}

BROWSER_LABELS = {
    "chrome": "Chrome",
    "edge": "Edge",
    "firefox": "Firefox",
    "brave": "Brave",
    "opera": "Opera",
    "vivaldi": "Vivaldi",
}

APPS = {
    "word": ("word", "winword", "microsoft word"),
    "excel": ("excel", "microsoft excel"),
    "powerpoint": ("powerpoint", "power point", "microsoft powerpoint", "ppt"),
    "notepad": ("notepad", "bloc de notas", "notas"),
    "calculator": ("calculadora", "calculator", "calc"),
    "chrome": ("chrome", "google chrome"),
    "edge": ("edge", "microsoft edge", "msedge"),
    "firefox": ("firefox", "mozilla firefox"),
    "explorer": ("explorador", "explorer", "archivos"),
    "taskmgr": ("administrador de tareas", "task manager", "taskmgr"),
    "terminal": ("terminal", "cmd", "simbolo del sistema", "powershell"),
    "vscode": ("vscode", "visual studio code", "vs code", "code"),
    "spotify": ("spotify",),
    "whatsapp": ("whatsapp",),
    "telegram": ("telegram",),
    "discord": ("discord",),
    "steam": ("steam",),
    "orunex": ("orunex",),
}

OPEN_VERBS = (
    "abre", "abrir", "abreme", "abrirme", "abrime", "abrelo", "abrela",
    "abrirla", "abrirlo", "open", "abrir app", "lanza", "lanzar", "inicia",
    "iniciar", "ejecuta", "ejecutar", "entra", "entrar", "ir a", "ve a",
    "navega", "navegar", "llevame", "llévame",
)

CREATE_HINTS = (
    "crea", "crear", "creame", "haz", "hazme", "genera", "generar",
    "escribe", "escribir", "documento", "archivo", "pdf", "informe",
    "presentacion", "presentación", "hoja de calculo", "hoja de cálculo",
    "make", "create", "write",
)

CONTEXT_REPEAT = (
    "otra vez", "de nuevo", "hazlo otra vez", "hazlo de nuevo", "repite",
    "repetir", "again", "repeat", "lo mismo", "el mismo",
)

CONTEXT_PRONOUN = {
    "lo", "eso", "esto", "el mismo", "la misma", "that", "it", "this", "same",
}


def _has_word(text: str, words) -> bool:
    for word in words:
        if re.search(r"(?<!\w)" + re.escape(_fold(word)) + r"(?!\w)", text):
            return True
    return False


def _browser_from_text(text: str) -> str:
    for canonical, aliases in BROWSERS.items():
        if _has_word(text, aliases):
            return canonical
    return ""


def _site_from_text(text: str) -> Optional[tuple[str, str, str]]:
    # Longest aliases first so "google drive" wins over "drive".
    matches = []
    for key, aliases in SITE_ALIASES.items():
        for alias in aliases:
            if _has_word(text, (alias,)):
                matches.append((len(alias), key, alias))
    if not matches:
        return None
    matches.sort(reverse=True)
    _, key, _ = matches[0]
    url, label = SITES[key]
    return key, url, label


def _app_from_text(text: str) -> str:
    matches = []
    for key, aliases in APPS.items():
        for alias in aliases:
            if _has_word(text, (alias,)):
                matches.append((len(alias), key))
    if not matches:
        return ""
    matches.sort(reverse=True)
    return matches[0][1]


def _explicit_url(text: str) -> str:
    match = re.search(
        r"(https?://[^\s]+|www\.[^\s]+|(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s]*)?)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return ""
    return match.group(1).rstrip(".,;:!?)]}")


def _open_verb_present(text: str) -> bool:
    return _has_word(text, OPEN_VERBS)


def _is_create_request(text: str) -> bool:
    return _has_word(text, CREATE_HINTS)


def _language(text: str, context: Optional[Dict[str, Any]] = None) -> str:
    folded = _fold(text)
    if re.search(r"[áéíóúñ¿¡]", str(text).lower()) or _has_word(
        folded, ("hola", "abre", "abrir", "gracias", "quiero", "puedes", "en")
    ):
        return "es"
    if context and context.get("language") in ("es", "en"):
        return context["language"]
    return "en" if _has_word(folded, ("the", "open", "please", "browser")) else "es"


def _clarify(text: str, context: Optional[Dict[str, Any]]) -> Intent:
    spanish = _language(text, context) == "es"
    message = (
        "¿Qué quieres que abra? Dime el sitio o la aplicación."
        if spanish
        else "What should I open? Tell me the website or application."
    )
    return Intent("clarify", message=message, confidence=1.0)


def _context_url(context: Optional[Dict[str, Any]]) -> str:
    if not context:
        return ""
    return str(context.get("last_url") or "").strip()


def parse_command(
    text: str, context: Optional[Dict[str, Any]] = None
) -> Optional[Intent]:
    """Return a high-confidence local intent, or ``None`` for the agent.

    The parser intentionally errs on the side of doing nothing.  A false
    positive here is much worse than passing the request to the reasoning
    agent: opening Word when the user only said "abre" is the canonical
    example.
    """
    original = str(text or "").strip()
    folded = _fold(original)
    if not folded:
        return None
    context = context or {}
    browser = _browser_from_text(folded)
    open_verb = _open_verb_present(folded)

    # Follow-ups that use context rather than a model call.
    if not open_verb:
        only_browser = re.fullmatch(
            r"(?:en|con|usando|in|on|por)\s+(?:el\s+|la\s+|un\s+)?"
            r"(?:navegador\s+)?(chrome|edge|firefox|brave|opera|vivaldi)"
            r"(?:\s+por favor)?",
            folded,
        )
        if only_browser:
            target = _context_url(context)
            if target:
                chosen = only_browser.group(1)
                label = context.get("last_label") or _label_for_url(target)
                spanish = _language(original, context) == "es"
                prefix = "Abriendo" if spanish else "Opening"
                prep = "en" if spanish else "in"
                return Intent(
                    "open_url",
                    label=label,
                    url=target,
                    browser=chosen,
                    message=f"{prefix} {label} {prep} {BROWSER_LABELS.get(chosen, chosen.title())}.",
                    confidence=0.97,
                )
        if _has_word(folded, CONTEXT_REPEAT) and context.get("last_kind"):
            last_url = _context_url(context)
            if last_url:
                chosen = browser or str(context.get("last_browser") or "")
                label = context.get("last_label") or _label_for_url(last_url)
                spanish = _language(original, context) == "es"
                where = (
                    f" en {BROWSER_LABELS.get(chosen, chosen.title())}"
                    if chosen and spanish
                    else f" in {BROWSER_LABELS.get(chosen, chosen.title())}"
                    if chosen
                    else (" en tu navegador" if spanish else " in your browser")
                )
                prefix = "Abriendo" if spanish else "Opening"
                return Intent(
                    "open_url",
                    label=label,
                    url=last_url,
                    browser=chosen,
                    message=f"{prefix} {label}{where}.",
                    confidence=0.9,
                )

    if not open_verb:
        return None

    # A bare verb is not permission to guess an application.
    stripped = re.sub(r"\b(por favor|please|ya|ahora|rapido|rápido)\b", " ", folded)
    stripped = re.sub(r"\s+", " ", stripped).strip(" .,!?;:")
    if stripped in {
        "abre", "abrir", "abreme", "abrirme", "open", "abrime", "lanza",
        "inicia", "ejecuta", "abre eso", "abre esto", "open it",
    }:
        if context.get("last_url") and _has_word(folded, CONTEXT_PRONOUN):
            target = _context_url(context)
            chosen = browser or str(context.get("last_browser") or "")
            label = context.get("last_label") or _label_for_url(target)
            spanish = _language(original, context) == "es"
            where = (
                f" en {BROWSER_LABELS.get(chosen, chosen.title())}"
                if chosen and spanish
                else f" in {BROWSER_LABELS.get(chosen, chosen.title())}"
                if chosen
                else (" en tu navegador" if spanish else " in your browser")
            )
            return Intent(
                "open_url",
                label=label,
                url=target,
                browser=chosen,
                message=("Abriendo" if spanish else "Opening") + f" {label}{where}.",
                confidence=0.9,
            )
        return _clarify(original, context)
    if _is_create_request(folded):
        # "crea una hoja de Excel" belongs to the document agent.
        return None

    url = _explicit_url(folded)
    label = _label_for_url(url) if url else ""
    site_text = re.sub(r"\bgoogle\s+chrome\b", " ", folded)
    site = _site_from_text(site_text)
    if site and not url:
        _, url, label = site

    # If the target is a pronoun/repeat and we have a URL in context, use it.
    if not url and context and (
        _has_word(folded, CONTEXT_PRONOUN)
        or _has_word(folded, CONTEXT_REPEAT)
        or re.search(r"\b(abrelo|abrela|abrirla|abrirlo|abrime|abreme)\b", folded)
    ):
        candidate = _context_url(context)
        if candidate:
            url = candidate
            label = context.get("last_label") or _label_for_url(candidate)

    # Generic "abre el navegador" opens the OS default browser.
    if not url and re.search(r"\b(navegador|browser)\b", folded) and not site and not browser:
        return Intent(
            "open_app",
            app="browser",
            label="el navegador" if _language(original, context) == "es" else "the browser",
            confidence=0.82,
        )

    # An open request with only a browser name means "open that browser",
    # unless a site target was also supplied.
    if not url:
        app_key = _app_from_text(folded)
        if app_key:
            return Intent(
                "open_app",
                app=app_key,
                label=app_key.title(),
                message="",
                confidence=0.93,
            )
        # "abre YouTube en Chrome": site detection wins above; a browser alone
        # must not be mistaken for a search engine (the old Bing failure).
        if browser and len(stripped.split()) <= 4:
            return Intent(
                "open_app",
                app=browser,
                label=BROWSER_LABELS.get(browser, browser.title()),
                confidence=0.88,
            )
        if len(stripped.split()) <= 3:
            return _clarify(original, context)
        return None

    if not url:
        return None

    chosen = browser
    if not chosen:
        # Reuse the last browser for a short follow-up such as "abre Google"
        # after the user explicitly used Chrome.  Do not force it for a site
        # the user did not mention before; the default browser is still fine.
        if context.get("last_browser") and len(stripped.split()) <= 5:
            chosen = str(context["last_browser"])

    chosen_label = BROWSER_LABELS.get(chosen, chosen.title()) if chosen else ""
    spanish = _language(original, context) == "es"
    prefix = "Abriendo" if spanish else "Opening"
    where = (
        f" en {chosen_label}"
        if chosen and spanish
        else f" in {chosen_label}"
        if chosen
        else (" en tu navegador" if spanish else " in your browser")
    )
    return Intent(
        "open_url",
        label=label,
        url=url,
        browser=chosen,
        message=f"{prefix} {label}{where}.",
        confidence=0.98,
    )


def _label_for_url(url: str) -> str:
    value = re.sub(r"^https?://", "", str(url or ""), flags=re.IGNORECASE)
    value = value.split("/")[0].split("?")[0]
    if value.lower().startswith("www."):
        value = value[4:]
    return value or "el sitio"
