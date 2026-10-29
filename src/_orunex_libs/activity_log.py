"""Thread-safe activity stream shared by the agent, tools and desktop UI.

The reasoning loop, the OS executor and the screen-capture helpers all run on
worker threads.  Keeping their short operational messages in one small bus
means the Tk UI can render an OpenCode-style activity log without every module
importing ``main`` or touching Tk widgets directly.

Events are intentionally small dictionaries::

    {
        "kind": "tool_call",
        "message": "Read src/main.py",
        "level": "info",
        "ts": 1712345678.9,
        "tool": "read_file",
    }

Subscribers are called synchronously on the emitting thread.  A Tk subscriber
must marshal the event to the main thread with ``after(0, ...)``.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List

ActivityCallback = Callable[[Dict[str, Any]], None]

_subscribers: List[ActivityCallback] = []
_lock = threading.Lock()


def subscribe(callback: ActivityCallback) -> None:
    """Register a callback once.  Returns silently for invalid callbacks."""
    if not callable(callback):
        return
    with _lock:
        if callback not in _subscribers:
            _subscribers.append(callback)


def unsubscribe(callback: ActivityCallback) -> None:
    with _lock:
        try:
            _subscribers.remove(callback)
        except ValueError:
            pass


def emit(
    kind: str,
    message: str,
    level: str = "info",
    **data: Any,
) -> Dict[str, Any]:
    """Publish one activity event.

    Publishing never raises into the caller: a broken UI subscriber must not
    stop a desktop action or a model request.
    """

    event: Dict[str, Any] = {
        "kind": str(kind or "activity"),
        "message": str(message or "").strip(),
        "level": str(level or "info").lower(),
        "ts": time.time(),
    }
    event.update(data)
    if not event["message"]:
        return event

    with _lock:
        subscribers = list(_subscribers)

    for callback in subscribers:
        try:
            callback(event)
        except Exception:
            # Activity logging is observability, never a critical path.
            pass

    try:
        print(f"[ACTIVITY:{event['kind']}] {event['message']}", flush=True)
    except Exception:
        pass
    return event
