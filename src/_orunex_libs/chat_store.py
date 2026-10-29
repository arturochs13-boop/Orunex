"""Local chat history for the Orunex desktop UI.

The file is intentionally small and human-readable. It lives next to the
other local configuration so the desktop app can keep conversations between
launches without a database server.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
CHATS_PATH = os.path.join(CONFIG_DIR, "chats.json")

_LOCK = threading.Lock()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def new_chat(title: str = "New chat") -> Dict[str, Any]:
    timestamp = now()
    return {
        "id": new_id(),
        "title": title,
        "created_at": timestamp,
        "updated_at": timestamp,
        "messages": [],
    }


def _normalise_message_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_duplicate_system_echo(
    previous: Dict[str, Any], message: Dict[str, Any]
) -> bool:
    """Detect the old executor echo that duplicated an assistant answer.

    Older builds appended the executor's unchanged answer as a ``sys`` message
    after the assistant bubble.  That is the blue repeated text users saw.
    Only a system message with tag ``sys`` immediately following an assistant
    message is eligible, so genuine notices are preserved.
    """

    if str(previous.get("role") or "").lower() != "assistant":
        return False
    if str(message.get("role") or "").lower() != "system":
        return False
    if str(message.get("tag") or "").lower() != "sys":
        return False

    left = _normalise_message_text(previous.get("text") or previous.get("content"))
    right = _normalise_message_text(message.get("text") or message.get("content"))
    if not left or not right:
        return False
    if left == right:
        return True
    if min(len(left), len(right)) / max(len(left), len(right)) < 0.92:
        return False
    # The executor's cleaner often removed a prefix or a few markdown chars.
    return left.startswith(right[:160]) and left.endswith(right[-160:])


def _drop_duplicate_system_echoes(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for message in messages:
        if cleaned and _is_duplicate_system_echo(cleaned[-1], message):
            continue
        cleaned.append(message)
    return cleaned


def load_chats() -> List[Dict[str, Any]]:
    """Load chats, ignoring corrupt entries instead of breaking the UI."""
    if not os.path.exists(CHATS_PATH):
        return []
    try:
        with open(CHATS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return []

    raw_chats = data.get("chats", []) if isinstance(data, dict) else []
    if not isinstance(raw_chats, list):
        return []

    chats: List[Dict[str, Any]] = []
    for raw in raw_chats:
        if not isinstance(raw, dict):
            continue
        chat_id = str(raw.get("id") or new_id())
        messages = raw.get("messages", [])
        if not isinstance(messages, list):
            messages = []
        clean_messages = _drop_duplicate_system_echoes(
            [m for m in messages if isinstance(m, dict)]
        )
        chats.append(
            {
                "id": chat_id,
                "title": str(raw.get("title") or "New chat"),
                "created_at": str(raw.get("created_at") or now()),
                "updated_at": str(raw.get("updated_at") or now()),
                "messages": clean_messages,
            }
        )
    return chats


def save_chats(chats: List[Dict[str, Any]]) -> bool:
    """Atomically persist the chat list. Returns False on write errors."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    payload = {"version": 1, "chats": chats}
    temp_path = CHATS_PATH + ".tmp"
    try:
        with _LOCK:
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(temp_path, CHATS_PATH)
        return True
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        return False


def message(
    text: str,
    role: str,
    tag: str = "info",
    color: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "role": role,
        "text": text,
        "tag": tag,
        "color": color,
        "time": now(),
    }
