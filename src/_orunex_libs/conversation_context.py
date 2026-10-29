"""Bounded conversation context for Orunex reasoning.

The desktop chat store keeps the full conversation, but Muse should not receive
an unbounded transcript.  This module mirrors the useful part of
OpenCodeInterpreter's token-aware history slicing: keep the newest turns,
reserve room for the answer, and make any omission explicit instead of
silently losing the thread.

The window is measured in characters, not tokens, because Orunex talks to
several providers and a character budget is stable across tokenizers.  The
default is deliberately conservative: the primary model has a 8192-token
output ceiling, so a few thousand characters of history still leave plenty of
room for a complete answer.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

MAX_HISTORY_CHARS = 12_000
MAX_MESSAGE_CHARS = 6_000
OMISSION_NOTE = (
    "[CONTEXT NOTE] Earlier turns were omitted to keep the context window "
    "bounded. Ask for a missing detail instead of guessing."
)


def _content(item: Any) -> str:
    if isinstance(item, dict):
        value = item.get("content")
        if value is None:
            value = item.get("text")
        return str(value or "").strip()
    if isinstance(item, (tuple, list)) and len(item) >= 2:
        return str(item[1] or "").strip()
    return ""


def _role(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("role") or "").strip().lower()
    if isinstance(item, (tuple, list)) and item:
        return str(item[0] or "").strip().lower()
    return ""


def _normalise(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def normalize_history(
    history: Iterable[Any] | None,
    *,
    current_task: str = "",
    max_chars: int = MAX_HISTORY_CHARS,
) -> Tuple[List[Dict[str, str]], int]:
    """Return ``(messages, omitted_count)`` for a bounded history window.

    Only user/assistant turns are sent back to the model.  System notices and
    tool output are internal state and must not be replayed as instructions.
    If the newest user turn is the task that is about to be sent, it is removed
    to avoid duplicating the current request.
    """

    messages: List[Dict[str, str]] = []
    for item in history or []:
        role = _role(item)
        if role not in {"user", "assistant"}:
            continue
        content = _content(item)
        if not content:
            continue
        if len(content) > MAX_MESSAGE_CHARS:
            content = content[:MAX_MESSAGE_CHARS] + "\n...[message truncated]"
        messages.append({"role": role, "content": content})

    if current_task and messages:
        wanted = _normalise(current_task)
        for index in range(len(messages) - 1, -1, -1):
            if messages[index]["role"] == "user":
                if _normalise(messages[index]["content"]) == wanted:
                    messages.pop(index)
                break

    if not messages:
        return [], 0

    selected: List[Dict[str, str]] = []
    used = 0
    omitted = 0
    for message in reversed(messages):
        content = message["content"]
        if selected and used + len(content) > max(1, max_chars):
            omitted += 1
            continue
        selected.append(message)
        used += len(content)

    selected.reverse()
    return selected, omitted


def omission_note(omitted: int) -> str:
    """Return the prompt note that makes an omitted-history window explicit."""

    return f"\n\n{OMISSION_NOTE}" if omitted else ""
