"""Local chat history for the Orunex desktop UI.

The file is intentionally small and human-readable. It lives next to the
other local configuration so the desktop app can keep conversations between
launches without a database server.
"""

from __future__ import annotations

import json
import os
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
        chats.append(
            {
                "id": chat_id,
                "title": str(raw.get("title") or "New chat"),
                "created_at": str(raw.get("created_at") or now()),
                "updated_at": str(raw.get("updated_at") or now()),
                "messages": [m for m in messages if isinstance(m, dict)],
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
