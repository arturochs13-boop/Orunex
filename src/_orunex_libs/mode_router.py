"""Chat mode routing for Orunex.

Modes are *preference hints*, not hard gates.  If the user leaves the selector
on ``Default`` we infer the most useful mode from the request.  The selected
mode is forwarded to the agent as a hint, while every task remains executable
even when no mode was picked.
"""

from __future__ import annotations

import re

MODE_DEFAULT = "Default"
MODE_PROGRAMMER = "Programmer"
MODE_RESEARCH = "Deep Research"
MODE_SWAPPING = "Agent Swapping"

MODE_ORDER = (MODE_DEFAULT, MODE_PROGRAMMER, MODE_RESEARCH, MODE_SWAPPING)
MODE_ICONS = {
    MODE_DEFAULT: "",
    MODE_PROGRAMMER: "\u2726",
    MODE_RESEARCH: "\u2726",
    MODE_SWAPPING: "\u2726",
}
MODE_LABELS = {
    mode: (f"{MODE_ICONS[mode]} {mode}".strip()) for mode in MODE_ORDER
}

_PROGRAMMER_HINTS = (
    "programa", "programar", "programacion", "programación", "codigo",
    "código", "code", "coding", "script", "python", "javascript", "typescript",
    "html", "css", "react", "node", "java", "c#", "c++", "golang", "rust",
    "vscode", "vs code", "terminal", "consola", "test", "tests", "prueba",
    "bug", "debug", "api", "endpoint", "backend", "frontend", "app",
    "aplicacion", "aplicación", "web", "landing", "repo", "repositorio",
    "funcion", "función", "clase", "database", "sql", "git", "deploy",
    "compila", "compilar", "refactor", "refactoriza", "arregla", "corrige",
)

_RESEARCH_HINTS = (
    "investiga", "investigar", "investigacion", "investigación", "research",
    "fuentes", "sources", "cita", "citas", "cite", "paper", "papers",
    "estudio", "analisis profundo", "análisis profundo", "deep research",
    "benchmark", "comparativa", "compare", "mercado", "market research",
    "noticias", "news", "documentacion", "documentación", "aprende sobre",
    "explica en profundidad", "state of the art", "literatura",
)

_SWAPPING_HINTS = (
    "agent swapping", "swap agents", "multiagente", "multi-agente",
    "multi agent", "multi-agent", "swarm", "enjambre", "delegar", "delegate",
    "divide el trabajo", "divide the work", "varios agentes", "several agents",
    "equipo de agentes", "agent team", "debate", "consenso", "consensus",
    "orquesta", "orchestrate", "paralelo", "parallel",
)

_QUESTION_PREFIXES = (
    "como ", "cómo ", "how ", "que es ", "qué es ", "what is ",
    "por que ", "por qué ", "why ", "when ", "cuando ", "cuándo ",
)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)


def resolve_mode(task: str, selected: str = MODE_DEFAULT) -> str:
    """Return the mode that should run for this task.

    A selected non-default mode always wins.  ``Default`` auto-detects in this
    order: Agent Swapping, Programmer, Deep Research.  This ordering lets an
    explicit orchestration request keep its multi-agent intent even when the
    task also mentions code or research.
    """
    selected = selected if selected in MODE_ORDER else MODE_DEFAULT
    if selected != MODE_DEFAULT:
        return selected

    text = _normalise(task)
    if not text:
        return MODE_DEFAULT

    if _contains_any(text, _SWAPPING_HINTS):
        return MODE_SWAPPING
    if _contains_any(text, _PROGRAMMER_HINTS):
        return MODE_PROGRAMMER
    if _contains_any(text, _RESEARCH_HINTS):
        return MODE_RESEARCH
    return MODE_DEFAULT


def is_programming_request(task: str, selected: str = MODE_DEFAULT) -> bool:
    """True when the task should connect to VS Code and run code checks."""
    text = _normalise(task)
    if not text:
        return False
    # A selected mode is a hint, not a gate.  Do not launch a coding session
    # for plain greetings just because Programmer is selected.
    if text in {
        "hola", "hello", "hi", "hey", "gracias", "thanks", "thank you",
        "ok", "okay", "listo", "bien", "good", "great", "who are you",
        "quien eres", "qué eres", "que eres", "como te llamas",
    }:
        return False
    if selected == MODE_PROGRAMMER:
        return True
    # A request such as "how do I program X" is still a programming question,
    # but we only open VS Code when the user wants work performed.
    if text.startswith(_QUESTION_PREFIXES) and not any(
        verb in text for verb in ("crea", "create", "haz", "make", "genera", "generate", "programa")
    ):
        return False
    return _contains_any(text, _PROGRAMMER_HINTS)


def is_research_request(task: str, selected: str = MODE_DEFAULT) -> bool:
    if selected == MODE_RESEARCH:
        return True
    return _contains_any(_normalise(task), _RESEARCH_HINTS)


def is_swapping_request(task: str, selected: str = MODE_DEFAULT) -> bool:
    if selected == MODE_SWAPPING:
        return True
    return _contains_any(_normalise(task), _SWAPPING_HINTS)


def mode_prompt(mode: str) -> str:
    """Short instruction injected into the agent prompt."""
    if mode == MODE_PROGRAMMER:
        return (
            "ACTIVE CHAT MODE: Programmer. Work directly in VS Code. "
            "Use the Orunex VS Code bridge/CLI to open the workspace, create or "
            "edit files, run tests and use the integrated terminal. Prefer real "
            "verification over prose. Finish by reporting files, commands and "
            "test results."
        )
    if mode == MODE_RESEARCH:
        return (
            "ACTIVE CHAT MODE: Deep Research. Investigate the request carefully, "
            "compare sources, separate facts from assumptions and cite the URLs "
            "or documents used. Produce a structured synthesis with next steps."
        )
    if mode == MODE_SWAPPING:
        return (
            "ACTIVE CHAT MODE: Agent Swapping. Split the task into specialist "
            "roles, let each role contribute, then merge the best result into "
            "one definitive answer. Keep the execution plan explicit."
        )
    return (
        "ACTIVE CHAT MODE: Default. Choose the most useful approach for the "
        "request. If it is a coding task, use VS Code; if it needs research, "
        "verify sources; if it is complex, orchestrate multiple steps."
    )
