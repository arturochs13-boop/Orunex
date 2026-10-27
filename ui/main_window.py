"""Meta-style desktop UI (CustomTkinter) for the Muse Spark agent.

Threading contract: this window NEVER calls Meta/ADB/FAISS directly.
Buttons only submit work to :class:`core.agent_brain.AgentBrain` (worker
pool) and render :class:`core.events.AgentEvent` objects polled from a
queue — the interface stays responsive during captures, model calls and
Gradle builds.
"""

from __future__ import annotations

import queue
from typing import Optional

try:
    import customtkinter as ctk
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "CustomTkinter is required for the UI: pip install customtkinter\n"
        "Headless alternative: python app.py --check"
    ) from exc

from core.agent_brain import AgentBrain
from core.events import AgentEvent
from tasks.bugfix_task import BugfixRequest
from tasks.trading_task import TradingRequest

META_BLUE = "#0082FB"
META_CYAN = "#00C6FF"
BG = "#0A0F1E"
CARD = "#111A2E"
CARD_2 = "#16233F"
TEXT = "#EAF2FF"
MUTED = "#8EA6C8"
OK = "#2ECC71"
WARN = "#F5B041"
BAD = "#E74C3C"


class MainWindow(ctk.CTk):
    def __init__(self, brain: Optional[AgentBrain] = None) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.brain = brain or AgentBrain()
        self.title("Orunex — Muse Spark Autonomous Agent")
        self.geometry("1240x630+0+0")
        self.minsize(1024, 620)
        self.configure(fg_color=BG)
        self._status_labels: dict[str, ctk.CTkLabel] = {}
        self._build()
        self.after(120, self._drain_events)
        self.after(1000, self._refresh_status)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._append_log("UI ready. All reasoning runs on Meta muse-spark only.")

    # ------------------------------------------------------------- construction
    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color=META_BLUE, corner_radius=0, height=66)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header, text="⬢  ORUNEX  ·  Muse Spark Agent",
            font=ctk.CTkFont(size=21, weight="bold"), text_color="white",
        ).pack(side="left", padx=18, pady=10)
        ctk.CTkLabel(
            header, text="Meta Global AI Developer Hackathon",
            font=ctk.CTkFont(size=12), text_color="#D8ECFF",
        ).pack(side="right", padx=18)

        status = ctk.CTkFrame(self, fg_color=CARD, corner_radius=14)
        status.pack(fill="x", padx=16, pady=6)
        for key, label in [
            ("meta", "Meta"), ("faiss", "FAISS"), ("adb", "ADB"),
            ("simplex", "Simplex"), ("paper", "Paper"), ("workers", "Workers"),
        ]:
            cell = ctk.CTkFrame(status, fg_color="transparent")
            cell.pack(side="left", expand=True, fill="x", padx=8, pady=4)
            ctk.CTkLabel(cell, text=label.upper(), text_color=MUTED,
                         font=ctk.CTkFont(size=9, weight="bold")).pack(anchor="w")
            value = ctk.CTkLabel(cell, text="…", text_color=TEXT,
                                 font=ctk.CTkFont(size=11, weight="bold"))
            value.pack(anchor="w")
            self._status_labels[key] = value

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        left = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14, width=390)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        right = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14)
        right.pack(side="left", fill="both", expand=True)
        self._build_controls(left)
        self._build_console(right)

    def _section(self, parent, title: str) -> ctk.CTkFrame:
        ctk.CTkLabel(parent, text=title, text_color="white",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            anchor="w", padx=16, pady=(8, 3))
        frame = ctk.CTkFrame(parent, fg_color=CARD_2, corner_radius=10)
        frame.pack(fill="x", padx=12, pady=(0, 3))
        return frame

    def _build_controls(self, parent) -> None:
        android = self._section(parent, "TASK 1 · Android ⇄ Laptop Bugfix")
        self.fix_instruction = ctk.CTkEntry(
            android, placeholder_text="Voice/text instruction (optional)…")
        self.fix_instruction.pack(fill="x", padx=10, pady=(6, 4))
        self.fix_instruction.insert(
            0, "The blue send button label is misspelled as 'Sned'; it should say 'Send'. Fix it.")
        self.auto_apply = ctk.CTkSwitch(android, text="Auto-apply patch (guarded)")
        self.auto_apply.pack(anchor="w", padx=10, pady=3)
        self.auto_apply.select()  # demo autonomy on; the patch guard still applies
        ctk.CTkButton(
            android, text="Capture → Diagnose → Fix (Live)",
            fg_color=META_BLUE, hover_color="#0064D1",
            command=self._run_bugfix,
        ).pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(
            android, text="Index codebase into FAISS",
            fg_color="#24365E", command=self._run_index,
        ).pack(fill="x", padx=10, pady=(0, 5))

        trading = self._section(parent, "TASK 2 · TradingView → Paper Trading")
        self.trade_raw = ctk.CTkTextbox(trading, height=72)
        self.trade_raw.pack(fill="x", padx=10, pady=(6, 4))
        self.trade_raw.insert(
            "1.0",
            '{"symbol":"BTCUSDT","timeframe":"1h","side":"BUY","price":67000,'
            '"indicators":{"ema_trend":"up, EMAs stacked and rising","rsi":61,'
            '"macd":"bullish, histogram expanding","volume":"1.8x average, '
            'breakout above 66800 with retest held","support":65200,'
            '"resistance":69500},"note":"TradingView multi-confluence alert"}',
        )
        ctk.CTkButton(
            trading, text="Analyse with Muse → Paper Order",
            fg_color=META_BLUE, hover_color="#0064D1",
            command=self._run_trading,
        ).pack(fill="x", padx=10, pady=(0, 4))
        self.kill_switch = ctk.CTkSwitch(
            trading, text="Kill switch (halt paper trading)",
            command=self._toggle_kill,
        )
        self.kill_switch.pack(anchor="w", padx=10, pady=(0, 6))

        remote = ctk.CTkFrame(parent, fg_color=CARD_2, corner_radius=10)
        remote.pack(fill="x", padx=12, pady=(0, 3))
        ctk.CTkLabel(
            remote, text="Simplex · Encrypted Remote", text_color=MUTED,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left", padx=(10, 6), pady=5)
        ctk.CTkButton(
            remote, text="Start", width=68, height=26, fg_color="#24365E",
            command=self._start_simplex,
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            remote, text="Stop", width=60, height=26, fg_color="#24365E",
            command=self._stop_simplex,
        ).pack(side="left", padx=(0, 8))

    def _build_console(self, parent) -> None:
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(bar, text="Real-time agent console",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="white").pack(side="left")
        ctk.CTkButton(bar, text="Clear", width=70, fg_color="#24365E",
                      command=lambda: self.console.delete("1.0", "end")).pack(side="right")
        self.console = ctk.CTkTextbox(
            parent, fg_color="#081020", text_color="#CDE6FF",
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.console.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ----------------------------------------------------------------- actions
    def _run_bugfix(self) -> None:
        self.brain.submit_bugfix(BugfixRequest(
            instruction=self.fix_instruction.get().strip(),
            auto_apply=bool(self.auto_apply.get()),
        ))
        self._append_log("[UI] -> [MuseSpark Brain] Bugfix submitted to worker pool")

    def _run_index(self) -> None:
        self.brain.submit_index_codebase()
        self._append_log("[UI] -> [FAISS Memory] Codebase indexing submitted")

    def _run_trading(self) -> None:
        raw = self.trade_raw.get("1.0", "end").strip()
        if raw:
            self.brain.submit_trading(TradingRequest(raw=raw, source="ui"))
            self._append_log("[UI] -> [MuseSpark Brain] Paper-trading analysis submitted")

    def _toggle_kill(self) -> None:
        self.brain.set_kill_switch(bool(self.kill_switch.get()))

    def _start_simplex(self) -> None:
        self.brain.start_simplex()

    def _stop_simplex(self) -> None:
        self.brain.stop_simplex()

    # ------------------------------------------------------------------- events
    def _drain_events(self) -> None:
        try:
            while True:
                event: AgentEvent = self.brain.bus.ui_queue.get_nowait()
                if event.kind == "log":
                    self._append_log(event.render())
                elif event.kind == "task":
                    self._append_log(
                        f"[MuseSpark Brain] Task {event.task_id} "
                        f"{event.data.get('state')}: {event.message}"
                    )
        except queue.Empty:
            pass
        self.after(120, self._drain_events)

    def _refresh_status(self) -> None:
        try:
            for key, value in self.brain.status().items():
                if key in self._status_labels:
                    self._status_labels[key].configure(text=value)
            remote_kill = bool(self.brain.paper.kill_switch)
            if remote_kill != bool(self.kill_switch.get()):
                if remote_kill:
                    self.kill_switch.select()
                else:
                    self.kill_switch.deselect()
        except Exception:
            pass
        self.after(1000, self._refresh_status)

    def _append_log(self, line: str) -> None:
        self.console.insert("end", line.rstrip() + "\n")
        self.console.see("end")

    def _on_close(self) -> None:
        try:
            self.brain.shutdown()
        finally:
            self.destroy()


def launch_ui(brain: Optional[AgentBrain] = None) -> None:
    MainWindow(brain).mainloop()
