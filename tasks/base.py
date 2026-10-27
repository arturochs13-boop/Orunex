"""Shared task primitives. Tasks run on worker threads, never on the UI."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    kind: str = ""
    state: TaskState = TaskState.RUNNING
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0

    def finish(self, state: TaskState, summary: str) -> "TaskResult":
        self.state = state
        self.summary = summary
        self.finished_at = time.time()
        return self

    @property
    def elapsed(self) -> float:
        end = self.finished_at or time.time()
        return max(0.0, end - self.started_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "state": self.state.value,
            "summary": self.summary,
            "error": self.error,
            "elapsed_s": round(self.elapsed, 2),
            "data": self.data,
        }
