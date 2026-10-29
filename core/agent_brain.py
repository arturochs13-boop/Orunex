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

import hashlib
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Optional

from bridges.adb_bridge import AndroidADBBridge
from bridges.simplex_bridge import RemoteCommand, SimplexBridgeListener
from bridges.tradingview_bridge import TradingViewBridge
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
    "You are Muse, the router of an autonomous agent. Classify the "
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
        self.tradingview = TradingViewBridge(self.settings, self.bus)
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
            tradingview=self.tradingview,
        )
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="AgentWorker")
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()
        self._warmup_lock = threading.Lock()
        self._warmup_future: Optional[Future] = None
        self._seen_remote: dict[str, float] = {}
        self._log(
            "Orchestrator ready (workers=4, primary="
            f"{self.settings.meta_model}, fast={self.settings.meta_fast_model})"
        )
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

    def warmup_async(self, reason: str = "manual") -> Future:
        """Pre-open emulator + TradingView in background (idempotent)."""
        with self._warmup_lock:
            if self._warmup_future and not self._warmup_future.done():
                return self._warmup_future

            def work() -> TaskResult:
                result = TaskResult(kind="warmup")
                started = time.monotonic()
                steps: dict[str, Any] = {}
                tv_enabled = bool(self.settings.tradingview_enabled)
                with ThreadPoolExecutor(max_workers=2, thread_name_prefix="Warmup") as pool:
                    adb_future = pool.submit(self.adb.prepare_for_task)
                    tv_future = (
                        pool.submit(self.tradingview.warmup) if tv_enabled else None
                    )
                    try:
                        steps["adb_focus"] = adb_future.result()
                    except Exception as exc:
                        steps["adb_error"] = f"{type(exc).__name__}: {exc}"
                    if tv_future is None:
                        steps["tradingview"] = {"ready": True, "disabled": True}
                    else:
                        try:
                            steps["tradingview"] = tv_future.result()
                        except Exception as exc:
                            steps["tradingview_error"] = f"{type(exc).__name__}: {exc}"
                result.data.update(steps)
                result.data["elapsed_s"] = round(time.monotonic() - started, 2)
                tv_ready = (
                    not tv_enabled
                    or steps.get("tradingview", {}).get("ready") is True
                )
                ready = "adb_focus" in steps and tv_ready
                self._log(
                    f"Warm-up ({reason}) {'ready' if ready else 'partial'} "
                    f"in {result.data['elapsed_s']}s",
                    level="INFO" if ready else "WARN",
                )
                return result.finish(
                    TaskState.COMPLETED if ready else TaskState.FAILED,
                    f"Warm-up {'ready' if ready else 'partial'} "
                    f"in {result.data['elapsed_s']}s "
                    f"(ADB={'ok' if 'adb_focus' in steps else 'failed'}, "
                    f"TradingView={'ok' if tv_ready else 'failed'})",
                )

            self._warmup_future = self._submit("warmup", work)
            return self._warmup_future

    def submit_tradingview(self, symbol: str = "BTCUSDT", timeframe: str = "1h") -> Future:
        def work() -> TaskResult:
            result = TaskResult(kind="tradingview")
            if not self.settings.tradingview_enabled:
                return result.finish(
                    TaskState.FAILED, "TradingView is disabled (TRADINGVIEW_ENABLED=false)."
                )
            status = self.tradingview.open_chart(symbol, timeframe)
            result.data["tradingview"] = status
            return result.finish(
                TaskState.COMPLETED if status.get("opened") else TaskState.FAILED,
                f"TradingView chart {status.get('symbol', symbol)} "
                f"{'opened' if status.get('opened') else 'not opened'}",
            )

        return self._submit("tradingview", work)

    def completed_summaries(self) -> list[tuple[str, str, str]]:
        """Summaries of finished worker tasks (for CLI/result relay)."""
        with self._lock:
            futures = list(self._futures.values())
        summaries: list[tuple[str, str, str]] = []
        for future in futures:
            if not future.done():
                continue
            try:
                result = future.result(timeout=0)
            except Exception as exc:
                summaries.append(("task", "failed", f"{type(exc).__name__}: {exc}"))
                continue
            summaries.append((result.kind, result.state.value, result.summary))
        return summaries

    def wait_for_idle(self, timeout: float = 600.0) -> bool:
        """Wait until submitted worker tasks finish (CLI/headless helper)."""
        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < deadline:
            with self._lock:
                futures = list(self._futures.values())
            if not futures or all(f.done() for f in futures):
                return True
            time.sleep(0.2)
        return False

    def start_simplex(self) -> bool:
        started = self.simplex.start()
        if started and self.settings.agent_warmup_on_start:
            # The first remote order should find the emulator and TradingView
            # already open; warming them now removes cold-start latency.
            self.warmup_async("simplex")
        return started

    def stop_simplex(self) -> None:
        self.simplex.stop()

    def set_kill_switch(self, active: bool) -> None:
        self.paper.kill_switch = bool(active)
        self._log(f"Paper-trading kill switch {'ON' if active else 'OFF'}", level="WARN")

    # ---------------------------------------------------------- remote routing
    def _is_duplicate_remote(self, contact: str, text: str) -> bool:
        window = max(0, int(self.settings.remote_duplicate_window_s))
        if window == 0:
            return False
        key = hashlib.sha256(
            f"{contact}\n{' '.join(text.lower().split())}".encode("utf-8")
        ).hexdigest()
        now = time.monotonic()
        with self._lock:
            self._seen_remote = {
                k: ts for k, ts in self._seen_remote.items() if now - ts < window
            }
            if key in self._seen_remote:
                return True
            self._seen_remote[key] = now
        return False

    def _attach_remote_completion(self, future: Future, contact: str, label: str) -> None:
        def done(completed: Future) -> None:
            try:
                result = completed.result()
                message = f"{label} {result.state.value}: {result.summary}"[:950]
            except Exception as exc:
                message = f"{label} failed: {type(exc).__name__}: {exc}"[:950]
            self.simplex.send_message(message, contact)

        future.add_done_callback(done)

    def submit_remote_text(self, text: str, contact: str = "") -> Future:
        """Queue remote-text handling off the caller's (often UI) thread."""
        return self._executor.submit(self.handle_remote_text, text, contact)

    def _on_remote_command(self, command: RemoteCommand) -> None:
        self.handle_remote_text(command.text, command.contact)

    def handle_remote_text(self, raw_text: str, contact: str = "") -> None:
        """Handle one remote order; also used by the CLI for rehearsal."""
        text = str(raw_text or "").strip()
        lowered = text.lower()
        # When a paired Simplex contact is configured, it is the allowlist
        # for state-changing remote orders.  Local CLI/Live entry points use
        # reserved contacts and are already inside the user's machine.
        configured_contact = (self.settings.simplex_contact or "").strip()
        if (
            configured_contact
            and contact
            and contact not in {"cli", "live"}
            and contact != configured_contact
        ):
            self._log(
                f"Ignored remote message from unauthorized contact {contact!r}",
                level="WARN",
            )
            return
        # Deterministic safety/status verbs: no model call needed.
        if lowered in {"!stop", "stop", "kill"}:
            self.set_kill_switch(True)
            self.simplex.send_message("Kill switch ON. Paper trading halted.", contact)
            return
        if lowered in {"!estado", "!status", "!estado agente"}:
            snap = self.status()
            self.simplex.send_message(
                "Orunex Agent: Meta={meta} FAISS={faiss} ADB={adb} TV={tv} "
                "Simplex={simplex} Paper={paper}".format(**snap),
                contact,
            )
            return
        if lowered.startswith("!close"):
            parts = text.split()
            symbol = parts[1] if len(parts) > 1 else ""
            closed = self.paper.close_open_orders(symbol)
            self.simplex.send_message(
                f"Closed {closed} open paper order(s){f' for {symbol}' if symbol else ''}.",
                contact,
            )
            return
        if lowered in {"!warmup", "!preparar", "!ready"}:
            self.warmup_async("simplex")
            self.simplex.send_message(
                "Preparando emulador y TradingView en segundo plano.", contact
            )
            return
        if lowered.startswith(("!tv", "!tradingview")):
            parts = text.split()
            symbol = parts[1] if len(parts) > 1 else "BTCUSDT"
            timeframe = parts[2] if len(parts) > 2 else "1h"
            future = self.submit_tradingview(symbol, timeframe)
            self._attach_remote_completion(future, contact, "TradingView")
            self.simplex.send_message(f"Abriendo TradingView en {symbol}…", contact)
            return
        if lowered.startswith(("!fix", "!bugfix", "!corregir")):
            if self._is_duplicate_remote(contact, text):
                self.simplex.send_message("Orden duplicada ignorada (bugfix).", contact)
                return
            instruction = text.split(None, 1)[1] if " " in text else ""
            # An explicit remote "fix it" order is the user's authorization;
            # the VS Code bridge guards still enforce exact, reversible edits.
            future = self.submit_bugfix(
                BugfixRequest(instruction=instruction, auto_apply=True)
            )
            self._attach_remote_completion(future, contact, "Bugfix")
            self.simplex.send_message(
                "Orden recibida: abriendo emulador y corrigiendo la app.", contact
            )
            return
        explicit_trade = lowered.startswith(
            ("!trade", "!order", "!orden", "!comprar", "!vender")
        )
        json_trade = text.startswith("{") and '"symbol"' in lowered
        if explicit_trade or json_trade:
            if self._is_duplicate_remote(contact, text):
                self.simplex.send_message("Orden duplicada ignorada (trading).", contact)
                return
            payload = text
            if explicit_trade and " " in text:
                payload = text.split(None, 1)[1] or text
            self.submit_trading(TradingRequest(raw=payload, source="simplex"))
            self.simplex.send_message(
                "Orden recibida: abriendo TradingView; Muse decide y ejecuta solo PAPER.",
                contact,
            )
            return
        # Everything semantic is decided by Muse.  Routing is a small,
        # latency-sensitive classification, so it stays on the fast model.
        try:
            route = self.meta.reason_json(
                system=ROUTE_SYSTEM,
                user=f"Remote message from {contact or 'user'}: {text}",
                schema_hint=ROUTE_SCHEMA,
                max_tokens=self.settings.meta_fast_max_tokens,
                model=self.settings.meta_fast_model,
                reasoning_effort=self.settings.meta_fast_reasoning_effort,
            )
        except Exception as exc:
            self._log(f"Routing failed: {exc}", level="ERROR")
            self.simplex.send_message(
                "Agent could not process that message (Meta API unavailable).", contact
            )
            return
        intent = str(route.get("intent") or "question").lower()
        try:
            route_confidence = float(route.get("confidence") or 0)
        except (TypeError, ValueError):
            route_confidence = 0.0
        self._log(f"Route intent={intent} confidence={route.get('confidence')}", nxt=SIMPLEX)
        if intent in {"trading", "bugfix"} and route_confidence < 0.65:
            self.simplex.send_message(
                "No estoy seguro de la orden. Repítela con !fix <instrucción> "
                "o !trade <alerta JSON> para ejecutarla.",
                contact,
            )
            return
        if intent == "trading":
            if self._is_duplicate_remote(contact, text):
                self.simplex.send_message("Orden duplicada ignorada (trading).", contact)
                return
            self.submit_trading(TradingRequest(raw=text, source="simplex"))
            self.simplex.send_message(
                "Orden recibida: abriendo TradingView; Muse decide y ejecuta solo PAPER.",
                contact,
            )
        elif intent == "bugfix":
            if self._is_duplicate_remote(contact, text):
                self.simplex.send_message("Orden duplicada ignorada (bugfix).", contact)
                return
            # A merely *classified* message is not an explicit authorization
            # to write code: keep the configured approval gate (proposal by
            # default).  Only the explicit !fix verb above auto-applies.
            future = self.submit_bugfix(BugfixRequest(instruction=text))
            self._attach_remote_completion(future, contact, "Bugfix")
            self.simplex.send_message(
                "Orden recibida: revisando la app en el emulador.", contact
            )
        elif intent == "question":
            answer = str(route.get("answer") or "Recibido. ¿En qué te ayudo?")
            self.simplex.send_message(answer, contact)
        else:
            self._log(f"Ignored remote message: {route.get('reason')}")

    # ------------------------------------------------------------------ status
    def status(self) -> dict[str, str]:
        with self._lock:
            running = sum(1 for f in self._futures.values() if not f.done())
        if self.settings.tradingview_enabled:
            tv = self.tradingview.status()
            tv_text = (
                "ready" if tv.running else ("installed" if tv.installed else "not found")
            )
            if tv.window_title:
                tv_text = tv.window_title[:28]
        else:
            tv_text = "disabled"
        return {
            "meta": f"{self.meta.model} ({'ready' if self.meta.configured else 'NO KEY'})",
            "faiss": str(self.memory.count),
            "adb": self.adb.serial or ("ready" if self.adb.available else "not found"),
            "tv": tv_text,
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
            "tradingview": (
                self.tradingview.status().to_dict()
                if self.settings.tradingview_enabled
                else {"enabled": False}
            ),
            "paper": self.paper.snapshot(),
        }

    def shutdown(self) -> None:
        self.stop_simplex()
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._log("Orchestrator stopped")
