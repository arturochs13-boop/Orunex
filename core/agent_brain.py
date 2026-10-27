"""AgentBrain — multithreaded orchestrator powered exclusively by Muse Spark.

Responsibilities:
* own every bridge/memory/task (single dependency graph, UI stays dumb);
* run work on a bounded ``ThreadPoolExecutor`` so the UI never freezes;
* route encrypted Simplex commands: deterministic safety verbs are handled
  locally (``!stop``, ``!estado``), every *semantic* routing decision is
  made by Muse Spark via :mod:`core.meta_api`;
* expose an immutable status snapshot for the UI status panel.
"""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Optional

from bridges.adb_bridge import AndroidADBBridge
from bridges.simplex_bridge import RemoteCommand, SimplexBridgeListener
from bridges.vscode_bridge import VSCodeBridge
from core.config import Settings, get_settings
from core.events import BRAIN, SIMPLEX, EventBus, console_printer
from core.faiss_memory import FAISSMemory
from core.meta_api import MetaAPIClient
from tasks.bugfix_task import AndroidBugfixTask, BugfixRequest
from tasks.base import TaskResult, TaskState
from tasks.trading_task import PaperTradingEngine, TradingRequest, TradingTask

ROUTE_SCHEMA = (
    '{"intent": "bugfix|trading|question|ignore", "confidence": 0.0, '
    '"reason": str, "answer": str}'
)
ROUTE_SYSTEM = (
    "You are Muse Spark, the router of an autonomous agent. Classify the "
    "remote message. 'bugfix' = inspect/fix the Android app screen. "
    "'trading' = TradingView alert or paper-trading order. 'question' = "
    "answer directly in 'answer'. 'ignore' = noise/unsafe. When unsure, "
    "choose 'question' with a clarifying answer."
)


class AgentBrain:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        bus: Optional[EventBus] = None,
        *,
        autostart_simplex: bool = False,
    ) -> None:
        self.settings = settings or get_settings()
        self.bus = bus or EventBus()
        self.bus.subscribe(console_printer)

        self.meta = MetaAPIClient(self.settings, self.bus)
        self.memory = FAISSMemory(settings=self.settings, bus=self.bus)
        self.adb = AndroidADBBridge(self.settings, self.bus)
        self.vscode = VSCodeBridge(self.settings, self.bus)
        self.paper = PaperTradingEngine(self.settings, self.bus)
        self.simplex = SimplexBridgeListener(
            on_command=self._on_remote_command, settings=self.settings, bus=self.bus
        )
        self.bugfix = AndroidBugfixTask(
            meta=self.meta, memory=self.memory, adb=self.adb, vscode=self.vscode,
            settings=self.settings, bus=self.bus,
        )
        self.trading = TradingTask(
            meta=self.meta, memory=self.memory, engine=self.paper,
            settings=self.settings, bus=self.bus,
            notifier=self.simplex.send_message,
        )
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="AgentWorker")
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()
        self._log("Orchestrator ready (workers=4, model=muse-spark only)")
        for problem in self.settings.validate():
            self._log(f"Config: {problem}", level="WARN")
        if autostart_simplex and self.settings.simplex_enabled:
            self.start_simplex()

    # ------------------------------------------------------------------- util
    def _log(self, message: str, *, level: str = "INFO", nxt: str = "") -> None:
        self.bus.log(BRAIN, message, level=level, next_stage=nxt)

    def _submit(self, kind: str, fn: Callable[..., TaskResult], *args: Any) -> Future:
        def wrapped() -> TaskResult:
            result = fn(*args)
            self.bus.task(result.task_id, result.state.value, result.summary, kind=kind)
            return result

        future = self._executor.submit(wrapped)
        with self._lock:
            self._futures[kind + ":" + str(id(future))] = future
        self._log(f"Submitted {kind} on worker pool", nxt="ADB Bridge" if kind == "bugfix" else "Meta API")
        return future

    # --------------------------------------------------------------- use cases
    def submit_bugfix(self, request: Optional[BugfixRequest] = None) -> Future:
        return self._submit("bugfix", self.bugfix.run, request or BugfixRequest())

    def submit_trading(self, request: TradingRequest) -> Future:
        return self._submit("trading", self.trading.run, request)

    def submit_index_codebase(self) -> Future:
        def work() -> TaskResult:
            result = TaskResult(kind="index_codebase")
            added = self.memory.index_codebase()
            return result.finish(
                TaskState.COMPLETED,
                f"Indexed {added} new code chunk(s); memory total={self.memory.count}",
            )

        return self._submit("index", lambda: work())

    def start_simplex(self) -> bool:
        return self.simplex.start()

    def stop_simplex(self) -> None:
        self.simplex.stop()

    def set_kill_switch(self, active: bool) -> None:
        self.paper.kill_switch = bool(active)
        self._log(f"Paper-trading kill switch {'ON' if active else 'OFF'}", level="WARN")

    # ---------------------------------------------------------- remote routing
    def _on_remote_command(self, command: RemoteCommand) -> None:
        text = command.text.strip()
        lowered = text.lower()
        # Deterministic safety/status verbs: no model call needed.
        if lowered in {"!stop", "stop", "kill"}:
            self.set_kill_switch(True)
            self.simplex.send_message("Kill switch ON. Paper trading halted.", command.contact)
            return
        if lowered in {"!estado", "!status"}:
            snap = self.status()
            self.simplex.send_message(
                "Orunex Agent: Meta={meta} FAISS={faiss} ADB={adb} "
                "Simplex={simplex} Paper={paper}".format(**snap),
                command.contact,
            )
            return
        if lowered.startswith(("!fix", "!bugfix")):
            instruction = text.split(None, 1)[1] if " " in text else ""
            self.submit_bugfix(BugfixRequest(instruction=instruction))
            self.simplex.send_message("Android bugfix pipeline started.", command.contact)
            return
        # Everything semantic is decided by Muse Spark.
        try:
            route = self.meta.reason_json(
                system=ROUTE_SYSTEM,
                user=f"Remote message from {command.contact or 'user'}: {text}",
                schema_hint=ROUTE_SCHEMA,
            )
        except Exception as exc:
            self._log(f"Routing failed: {exc}", level="ERROR")
            self.simplex.send_message(
                "Agent could not process that message (Meta API unavailable).", command.contact
            )
            return
        intent = str(route.get("intent") or "question").lower()
        self._log(f"Route intent={intent} confidence={route.get('confidence')}", nxt=SIMPLEX)
        if intent == "trading":
            self.submit_trading(TradingRequest(raw=text, source="simplex"))
        elif intent == "bugfix":
            self.submit_bugfix(BugfixRequest(instruction=text))
        elif intent == "question":
            answer = str(route.get("answer") or "Recibido. ¿En qué te ayudo?")
            self.simplex.send_message(answer, command.contact)
        else:
            self._log(f"Ignored remote message: {route.get('reason')}")

    # ------------------------------------------------------------------ status
    def status(self) -> dict[str, str]:
        with self._lock:
            running = sum(1 for f in self._futures.values() if not f.done())
        return {
            "meta": f"{self.meta.model} ({'ready' if self.meta.configured else 'NO KEY'})",
            "faiss": str(self.memory.count),
            "adb": self.adb.serial or ("ready" if self.adb.available else "not found"),
            "simplex": "connected" if self.simplex.connected else "offline",
            "paper": (
                f"{self.paper.snapshot()['balance']:.2f} {self.settings.paper_currency}"
                f"{' [KILL]' if self.paper.kill_switch else ''}"
            ),
            "workers": str(running),
        }

    def diagnostics(self) -> dict[str, Any]:
        return {
            "settings_problems": self.settings.validate(),
            "status": self.status(),
            "memory": self.memory.stats(),
            "adb_devices": self.adb.devices() if self.adb.available else [],
            "paper": self.paper.snapshot(),
        }

    def shutdown(self) -> None:
        self.stop_simplex()
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._log("Orchestrator stopped")
