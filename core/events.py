"""Thread-safe event bus + structured stage logging.

Workers never touch the UI.  They publish :class:`AgentEvent` objects here;
the UI (or a console printer) subscribes and renders them.  Log lines keep
the hackathon trace format, for example::

    12:04:31 | INFO  | [MuseSpark Brain] -> [ADB Bridge] Capture requested
    12:04:33 | INFO  | [ADB Bridge] -> [Meta API] Screenshot ready (182 KB)
    12:04:38 | INFO  | [Meta API] -> [FAISS Match] Component: LoginButton
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

# Canonical stage names used across the whole system.
BRAIN = "MuseSpark Brain"
META = "Meta API"
ADB = "ADB Bridge"
FAISS = "FAISS Match"
VSCODE = "VS Code"
SIMPLEX = "Simplex"
TRADING = "Paper Trading"
MEMORY = "FAISS Memory"
UI = "UI"


@dataclass
class AgentEvent:
    kind: str  # "log" | "status" | "task"
    stage: str
    message: str
    level: str = "INFO"
    next_stage: str = ""
    task_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def render(self) -> str:
        clock = time.strftime("%H:%M:%S", time.localtime(self.ts))
        arrow = f"[{self.stage}] -> [{self.next_stage}]" if self.next_stage else f"[{self.stage}]"
        return f"{clock} | {self.level:<5} | {arrow} {self.message}"


class EventBus:
    """Fan-out hub safe to publish to from any worker thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[Callable[[AgentEvent], None]] = []
        self.ui_queue: "queue.SimpleQueue[AgentEvent]" = queue.SimpleQueue()

    def subscribe(self, callback: Callable[[AgentEvent], None]) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def publish(self, event: AgentEvent) -> None:
        self.ui_queue.put(event)
        with self._lock:
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(event)
            except Exception:
                pass  # a broken subscriber must never kill a worker

    # -- convenience emitters -------------------------------------------------
    def log(
        self,
        stage: str,
        message: str,
        *,
        level: str = "INFO",
        next_stage: str = "",
        task_id: str = "",
        **data: Any,
    ) -> None:
        self.publish(
            AgentEvent(
                kind="log",
                stage=stage,
                message=message,
                level=level,
                next_stage=next_stage,
                task_id=task_id,
                data=dict(data),
            )
        )

    def status(self, component: str, state: str, **data: Any) -> None:
        self.publish(
            AgentEvent(kind="status", stage=component, message=state, data=dict(data))
        )

    def task(self, task_id: str, state: str, message: str = "", **data: Any) -> None:
        self.publish(
            AgentEvent(
                kind="task", stage=BRAIN, message=message or state,
                task_id=task_id, data={"state": state, **data},
            )
        )


def console_printer(event: AgentEvent) -> None:
    if event.kind == "log":
        print(event.render(), flush=True)
