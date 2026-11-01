"""TASK 2 — TradingView operative via Simplex (PAPER TRADING ONLY).

Flow::

    [Simplex] TradingView alert / remote order
        -> parse alert payload (data extraction only, no decision)
        -> [FAISS Memory] recall stored strategies
        -> [Meta API] Muse technical decision (JSON, may read a chart image)
        -> deterministic risk gate (limits Muse cannot exceed)
        -> [Paper Trading] simulate order with Stop Loss / Take Profit
        -> [Simplex] structured confirmation back to the user
        -> [FAISS Memory] remember the episode

There is deliberately NO real broker integration in this module.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from core.config import Settings, get_settings
from core.events import BRAIN, FAISS, META, SIMPLEX, TRADING, TRADINGVIEW, EventBus
from core.faiss_memory import FAISSMemory
from core.meta_api import MetaAPIClient
from core.trade_intent import is_explicit_entry_request, symbol_from_title
from tasks.base import TaskResult, TaskState

DECISION_SCHEMA = (
    '{"action": "BUY|SELL|HOLD|REJECT", "symbol": str, "entry": number, '
    '"stop_loss": number, "take_profit": number, "confidence": 0.0, '
    '"rationale": str, "strategy_refs": [str]}'
)
DECISION_SYSTEM = (
    "You are Muse, a disciplined trading analyst operating ONLY in "
    "paper-trading mode. Analyse the supplied market snapshot, the chart and "
    "recalled strategies. Prefer HOLD over a weak trade. Any BUY/SELL must "
    "include a coherent stop_loss and take_profit. Never promise profit."
)
EXPLICIT_DECISION_SCHEMA = (
    '{"action": "BUY|SELL", "symbol": str, "entry": number, '
    '"stop_loss": number, "take_profit": number, "confidence": 0.0, '
    '"rationale": str, "strategy_refs": [str]}'
)
EXPLICIT_DECISION_SYSTEM = (
    "You are Muse, a disciplined trading analyst operating ONLY in "
    "paper-trading mode. The user has given an explicit paper-entry order, "
    "so HOLD and REJECT are not available actions. Read the chart and choose "
    "BUY or SELL. Use the live chart price as entry and visible support or "
    "resistance for stop_loss and take_profit. If the setup is not ideal, "
    "choose the side with the clearest invalidation and a tight stop. "
    "Confidence is your calibrated conviction in the side you chose, not the "
    "probability of profit; the explicit-order execution floor is 0.50, so a "
    "readable chart with a clear invalidation should score at or above it. "
    "Never promise profit."
)
EXPLICIT_EXECUTION_NOTE = (
    "\nEXPLICIT USER EXECUTION ORDER: the user ordered a paper entry now. "
    "HOLD and REJECT are not available actions. Choose BUY or SELL from the "
    "chart evidence. Use the live chart price as entry and visible "
    "support/resistance for stop_loss/take_profit. Never promise profit.\n"
)
EXPLICIT_RETRY_NOTE = (
    "\nCORRECTION: your previous answer was not an executable entry. That is "
    "invalid for this explicit order. Re-read the chart and return BUY or "
    "SELL with a coherent stop_loss and take_profit. HOLD and REJECT are not "
    "allowed. The explicit-order confidence floor is 0.50; score your "
    "calibrated conviction in the chosen side. Return only the JSON object.\n"
)


class DuplicatePaperOrderError(RuntimeError):
    """Raised when an equivalent paper order is already open recently."""

    def __init__(self, order: "PaperOrder") -> None:
        super().__init__(f"Duplicate open paper order {order.order_id}")
        self.order = order


def canonical_symbol(symbol: object) -> str:
    raw = str(symbol or "").strip().upper().replace(" ", "").replace("/", "")
    if ":" in raw:
        raw = raw.split(":", 1)[1]
    if raw.endswith(".P"):
        raw = raw[:-2]
    return raw


_DEMO_CHART_ROOT = Path(__file__).resolve().parent.parent / "demo" / "charts"


def _load_demo_chart() -> Optional[Path]:
    """Optional controlled chart for rehearsed demos, never used by default.

    ``ORUNEX_DEMO_CHART`` must point at a file inside ``demo/charts``.  This
    keeps the hook bounded to demo artifacts; normal runs still capture the
    live TradingView window.
    """
    raw = os.environ.get("ORUNEX_DEMO_CHART", "").strip()
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = Path(__file__).resolve().parent.parent / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(_DEMO_CHART_ROOT.resolve())
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


# --------------------------------------------------------------------------
# Paper broker
# --------------------------------------------------------------------------
@dataclass
class PaperOrder:
    order_id: str
    symbol: str
    side: str  # BUY | SELL
    quantity: float
    entry: float
    stop_loss: float
    take_profit: float
    status: str = "OPEN"
    opened_at: float = field(default_factory=time.time)
    rationale: str = ""
    # Execution provenance.  ``ui_verified`` is only true after the native
    # TradingView paper ticket was visually confirmed by the GUI agent.
    source: str = "paper_engine"
    ui_verified: bool = False
    ui_reference: str = ""
    ui_price: float = 0.0
    ui_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self))


class PaperTradingEngine:
    """Simulated account. Thread-safe, persistent, and impossible to arm live."""

    def __init__(self, settings: Optional[Settings] = None, bus: Optional[EventBus] = None):
        self.settings = settings or get_settings()
        self.bus = bus
        self._lock = threading.RLock()
        self.kill_switch = False
        self.balance = float(self.settings.paper_initial_balance)
        self.orders: dict[str, PaperOrder] = {}
        self._load()

    def _log(self, message: str, *, level: str = "INFO", nxt: str = "") -> None:
        if self.bus:
            self.bus.log(TRADING, message, level=level, next_stage=nxt)

    # ------------------------------------------------------------- risk gate
    def position_size(self, entry: float, stop_loss: float) -> float:
        """Quantity whose loss at the stop equals the allowed risk budget."""
        risk_cash = self.balance * (self.settings.max_risk_per_trade_pct / 100.0)
        per_unit = abs(float(entry) - float(stop_loss))
        if per_unit <= 0:
            return 0.0
        quantity = risk_cash / per_unit
        max_notional = self.balance * (self.settings.max_position_pct / 100.0)
        if quantity * float(entry) > max_notional:
            quantity = max_notional / float(entry)
        return round(float(quantity), 6)

    def _prepare_locked(
        self, decision: dict[str, Any], *, quantity: float | None = None
    ) -> tuple[str, str, float, float, float, float]:
        """Validate a decision and return the exact values to persist."""
        if self.kill_switch:
            raise RuntimeError("Paper trading kill switch is active.")
        side = str(decision.get("action") or "").upper()
        entry = float(decision["entry"]); stop = float(decision["stop_loss"])
        take = float(decision["take_profit"])
        if side not in {"BUY", "SELL"}:
            raise ValueError(f"Action {side!r} is not executable.")
        if entry <= 0 or stop <= 0 or take <= 0:
            raise ValueError("Entry, stop_loss and take_profit must be positive.")
        if side == "BUY" and not (stop < entry < take):
            raise ValueError("BUY requires stop_loss < entry < take_profit.")
        if side == "SELL" and not (take < entry < stop):
            raise ValueError("SELL requires take_profit < entry < stop_loss.")
        symbol = canonical_symbol(decision.get("symbol") or "UNKNOWN")
        existing = self.find_open_order(
            symbol,
            side,
            max_age_s=float(self.settings.paper_duplicate_window_s),
        )
        if existing is not None:
            raise DuplicatePaperOrderError(existing)
        if quantity is None:
            quantity = self.position_size(entry, stop)
        quantity = round(float(quantity), 6)
        if quantity <= 0:
            raise ValueError("Computed position size is zero; trade rejected.")
        return side, symbol, entry, stop, take, quantity

    def _create_locked(
        self,
        decision: dict[str, Any],
        *,
        quantity: float | None = None,
        status: str = "OPEN",
        source: str = "paper_engine",
    ) -> PaperOrder:
        side, symbol, entry, stop, take, quantity = self._prepare_locked(
            decision, quantity=quantity
        )
        order = PaperOrder(
            order_id="PAPER-" + uuid.uuid4().hex[:10].upper(),
            symbol=symbol,
            side=side, quantity=quantity, entry=entry,
            stop_loss=stop, take_profit=take,
            rationale=str(decision.get("rationale") or "")[:500],
            status=status,
            source=source,
        )
        self.orders[order.order_id] = order
        self._save_locked()
        return order

    def execute(
        self, decision: dict[str, Any], *, quantity: float | None = None
    ) -> PaperOrder:
        """Open a simulated position after hard risk validation."""
        with self._lock:
            order = self._create_locked(decision, quantity=quantity, status="OPEN")
        self._log(
            f"{order.order_id} {order.side} {order.quantity} {order.symbol} "
            f"@ {order.entry} (SL {order.stop_loss} / TP {order.take_profit})",
            nxt=SIMPLEX,
        )
        return order

    def reserve(
        self, decision: dict[str, Any], *, quantity: float | None = None
    ) -> PaperOrder:
        """Create a PENDING_UI order while the GUI fills the paper ticket.

        The order is not treated as open until :meth:`confirm_ui` sees the
        position in TradingView.  Reserving first prevents a retry from
        submitting the same order twice while the GUI is still working.
        """
        with self._lock:
            return self._create_locked(
                decision,
                quantity=quantity,
                status="PENDING_UI",
                source="tradingview_gui",
            )

    def confirm_ui(
        self,
        order: PaperOrder,
        *,
        reference: str = "",
        price: float = 0.0,
        verified: bool = True,
    ) -> PaperOrder:
        """Promote a reserved order to OPEN after visual UI confirmation."""
        with self._lock:
            if order.order_id not in self.orders:
                raise KeyError(f"Unknown paper order {order.order_id}")
            order.status = "OPEN"
            order.ui_verified = bool(verified)
            order.ui_reference = str(reference or "")[:120]
            if price and float(price) > 0:
                order.ui_price = round(float(price), 8)
            order.ui_error = ""
            self._save_locked()
        self._log(
            f"{order.order_id} {order.side} {order.quantity} {order.symbol} "
            f"@ {order.entry} confirmed in TradingView Paper Trading",
            nxt=SIMPLEX,
        )
        return order

    def fail_ui(
        self, order: PaperOrder, reason: str, *, submitted: bool = False
    ) -> PaperOrder:
        """Close a reserved order that never reached a confirmed UI state."""
        with self._lock:
            if order.order_id in self.orders:
                order.status = "UNCONFIRMED" if submitted else "UI_FAILED"
                order.ui_verified = False
                order.ui_error = str(reason or "")[:300]
                self._save_locked()
        self._log(
            f"{order.order_id} not confirmed in TradingView: {reason}",
            level="WARN" if submitted else "ERROR",
            nxt=TRADING,
        )
        return order

    def expire_stale_reservations(self, max_age_s: float = 450.0) -> int:
        """Fail reservations left behind by a stopped GUI executor.

        A ``PENDING_UI`` row older than the GUI timeout cannot still have a
        live loop behind it.  Without this, a killed/crashed run would block
        every future entry on the same symbol/side as a phantom duplicate.
        """
        now = time.time()
        expired = 0
        with self._lock:
            for order in self.orders.values():
                if order.status != "PENDING_UI":
                    continue
                if now - order.opened_at <= max_age_s:
                    continue
                order.status = "UI_FAILED"
                order.ui_verified = False
                order.ui_error = "stale reservation: the GUI executor stopped before confirming"
                expired += 1
            if expired:
                self._save_locked()
        if expired:
            self._log(
                f"Expired {expired} stale PENDING_UI reservation(s)",
                level="WARN",
                nxt=TRADING,
            )
        return expired

    def find_open_order(
        self,
        symbol: str,
        side: str,
        *,
        max_age_s: float | None = None,
    ) -> PaperOrder | None:
        """Return a recent OPEN/PENDING order for the canonical symbol/side."""
        wanted_symbol = canonical_symbol(symbol)
        wanted_side = str(side or "").upper()
        now = time.time()
        with self._lock:
            for order in self.orders.values():
                if max_age_s is not None and now - order.opened_at > max_age_s:
                    continue
                if (
                    order.status in {"OPEN", "PENDING_UI"}
                    and canonical_symbol(order.symbol) == wanted_symbol
                    and order.side.upper() == wanted_side
                ):
                    return order
        return None

    def close_open_orders(self, symbol: str = "") -> int:
        """Mark OPEN paper orders as CLOSED (manual exposure reset)."""
        wanted = canonical_symbol(symbol) if symbol else ""
        closed = 0
        with self._lock:
            for order in self.orders.values():
                if order.status != "OPEN":
                    continue
                if wanted and canonical_symbol(order.symbol) != wanted:
                    continue
                order.status = "CLOSED"
                closed += 1
            if closed:
                self._save_locked()
        if closed:
            self._log(f"Closed {closed} paper order(s)", level="WARN")
        return closed

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": "PAPER_ONLY",
                "balance": self.balance,
                "currency": self.settings.paper_currency,
                "kill_switch": self.kill_switch,
                "open_orders": [o.to_dict() for o in self.orders.values()
                                if o.status == "OPEN"],
            }

    # ------------------------------------------------------------ persistence
    def _save_locked(self) -> None:
        try:
            self.settings.paper_state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"balance": self.balance,
                       "orders": [o.to_dict() for o in self.orders.values()]}
            tmp = self.settings.paper_state_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.settings.paper_state_path)
        except Exception as exc:
            self._log(f"Could not persist paper state: {exc}", level="WARN")

    def _load(self) -> None:
        path = self.settings.paper_state_path
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.balance = float(payload.get("balance", self.balance))
            for raw in payload.get("orders", []):
                order = PaperOrder(**raw)
                self.orders[order.order_id] = order
        except Exception:
            pass


# --------------------------------------------------------------------------
# Alert parsing (data extraction only — Muse decides)
# --------------------------------------------------------------------------
def parse_tradingview_alert(raw: str) -> dict[str, Any]:
    """Accept a TradingView JSON alert or a plain-text order description."""
    text = str(raw or "").strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except Exception:
        pass
    parsed: dict[str, Any] = {"raw_text": text}
    for token in text.replace(",", " ").split():
        if "=" in token:
            key, val = token.split("=", 1)
            parsed[key.strip().lower()] = val.strip()
    return parsed


@dataclass
class TradingRequest:
    raw: str
    chart_image: bytes | str | Path | None = None
    source: str = "simplex"


@dataclass
class TradingTask:
    meta: MetaAPIClient
    memory: FAISSMemory
    engine: PaperTradingEngine
    settings: Settings = field(default_factory=get_settings)
    bus: Optional[EventBus] = None
    notifier: Any = None  # callable(str) -> bool, usually Simplex send_message
    tradingview: Any = None  # TradingViewBridge; chart context only, never a broker
    gui_agent: Any = None  # TradingViewGuiAgent (or a fake in tests)

    def _log(self, stage: str, message: str, *, nxt: str = "", level: str = "INFO") -> None:
        if self.bus:
            self.bus.log(stage, message, level=level, next_stage=nxt)

    def _reason_json(self, **kwargs: Any) -> dict[str, Any]:
        try:
            return self.meta.reason_json(**kwargs)
        except TypeError:
            # Minimal Muse adapters in offline tests may not accept the newer
            # budget/effort overrides.
            for key in ("max_tokens", "reasoning_effort", "model"):
                kwargs.pop(key, None)
            return self.meta.reason_json(**kwargs)

    # ------------------------------------------------------- visual evidence
    def _screen_dir(self) -> Path:
        return self.settings.paper_state_path.parent / "screens"

    def _capture_screen(self, label: str) -> dict[str, Any]:
        """Save a full-desktop screenshot; never raise into the order path.

        The user requires a screen capture for every paper-entry phase, so
        this runs even when TradingView or the virtual cursor is unavailable.
        """
        try:
            from PIL import ImageGrab

            image = ImageGrab.grab(all_screens=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            path = self._screen_dir() / f"{stamp}_{int(time.time() * 1000) % 1000:03d}_{label}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save(path, format="PNG")
            self._log(TRADING, f"Screen captured: {path.name}", nxt=META)
            return {"ok": True, "path": str(path), "size": list(image.size)}
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self._log(TRADING, f"Screen capture failed: {error}", level="WARN")
            return {"ok": False, "error": error}

    def _agent_cursor_chart(
        self,
        symbol: str,
        *,
        stage: str,
        click: bool = True,
        allow_gui: bool = True,
    ) -> dict[str, Any]:
        """Drive TradingView with Orunex's own cursor, then capture the screen.

        This is intentionally best-effort: the paper order must still be
        decided if the desktop app is missing, but every GUI action goes
        through :mod:`_orunex_libs.virtual_input` first so the physical mouse
        is never used to aim the agent.
        """
        started = time.monotonic()
        evidence: dict[str, Any] = {
            "stage": stage,
            "symbol": symbol,
            "cursor_used": False,
            "clicked": False,
        }
        try:
            if not allow_gui:
                evidence["error"] = "no live chart opened"
            elif self.tradingview is None:
                evidence["error"] = "TradingView bridge not configured"
            elif not self.settings.tradingview_enabled:
                evidence["error"] = "TradingView disabled"
            else:
                try:
                    from _orunex_libs import virtual_input as vin  # type: ignore
                except ImportError:
                    # The delegated ``app.py --command`` process historically
                    # did not put ``src`` on sys.path, so the cursor layer was
                    # reported as unavailable even though TradingView opened.
                    import sys

                    src_dir = Path(__file__).resolve().parent.parent / "src"
                    if str(src_dir) not in sys.path:
                        sys.path.insert(0, str(src_dir))
                    from _orunex_libs import virtual_input as vin  # type: ignore

                agent = vin.get_input()
                if not agent.available:
                    evidence["error"] = "virtual input unavailable"
                else:
                    window = vin.find_tradingview_window()
                    if window is None:
                        # Launch TradingView Desktop automatically so the user
                        # never has to open it manually before a trade.
                        self._log(
                            TRADINGVIEW,
                            "TradingView not running; launching desktop app",
                            nxt=TRADING,
                        )
                        # Ensure the bridge exists even in the delegated process
                        # (app.py --command), where it may not have been set.
                        if self.tradingview is None:
                            try:
                                from bridges.tradingview_bridge import (
                                    TradingViewBridge,
                                )

                                self.tradingview = TradingViewBridge(
                                    self.settings, self.bus
                                )
                            except Exception:
                                self.tradingview = None
                        launched = False
                        if self.tradingview is not None:
                            # Try the AppX package launcher (shell:AppsFolder),
                            # the reliable way to start the MSIX package from
                            # the Microsoft Store.
                            try:
                                app_id = self.tradingview.find_app_id()
                                if app_id and os.name == "nt":
                                    subprocess.Popen(
                                        [
                                            "explorer.exe",
                                            f"shell:AppsFolder\\{app_id}",
                                        ],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL,
                                    )
                                    launched = True
                                    self._log(
                                        TRADINGVIEW,
                                        f"Launched TradingView package {app_id}",
                                        nxt=TRADING,
                                    )
                            except Exception:
                                pass
                            # Fall back to the direct exe path.
                            if not launched:
                                try:
                                    ok = self.tradingview.launch(timeout=25.0)
                                    if ok:
                                        launched = True
                                except Exception:
                                    pass
                        # If the bridge is None or both launch methods failed,
                        # try launching the exe from common Windows locations.
                        if not launched and vin.find_tradingview_window() is None:
                            common_paths = [
                                os.path.expandvars(
                                    r"%LOCALAPPDATA%\Programs\TradingView\TradingView.exe"
                                ),
                                os.path.expandvars(
                                    r"%PROGRAMFILES%\TradingView\TradingView.exe"
                                ),
                                os.path.expandvars(
                                    r"%PROGRAMFILES(x86)%\TradingView\TradingView.exe"
                                ),
                            ]
                            for exe_path in common_paths:
                                if os.path.exists(exe_path):
                                    try:
                                        subprocess.Popen(
                                            [exe_path],
                                            stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL,
                                        )
                                        launched = True
                                        self._log(
                                            TRADINGVIEW,
                                            f"Launched TradingView from {exe_path}",
                                            nxt=TRADING,
                                        )
                                        break
                                    except OSError:
                                        continue
                        # Wait for the window to appear (up to 180s total).
                        # A cold MSIX start can spend 60-90s restoring the
                        # workspace, and TradingView may start minimized.
                        launched_ok = False
                        for _launch_attempt in range(2):
                            deadline = time.monotonic() + 90.0
                            while time.monotonic() < deadline:
                                window = vin.find_tradingview_window()
                                if window is not None:
                                    launched_ok = True
                                    break
                                time.sleep(0.7)
                            if launched_ok:
                                break
                            # Second attempt: re-launch with the bridge.
                            if self.tradingview is not None:
                                self._log(
                                    TRADINGVIEW,
                                    "TradingView window still not visible; "
                                    "re-launching desktop app",
                                    nxt=TRADING,
                                )
                                try:
                                    self.tradingview.launch(timeout=30.0)
                                except Exception:
                                    pass
                        if not launched_ok:
                            evidence["error"] = "TradingView window not found"
                        else:
                            window = vin.find_tradingview_window()
                    if window is None:
                        evidence["error"] = "TradingView window not found"
                    else:
                        agent.attach_window(window)
                        placement = agent.maximize()
                        focused = agent.focus()
                        point = agent.client_point(0.52, 0.52)
                        move = agent.move_to(*point, duration=0.30)
                        click_result: dict[str, Any] = {}
                        if click:
                            click_result = agent.click(
                                *point, ensure_focus=True, duration=0.24
                            )
                        # Let the overlay paint before the screenshot so the
                        # evidence shows the agent pointer over the chart.
                        time.sleep(0.40)
                        evidence.update(
                            {
                                "cursor_used": True,
                                "clicked": bool(click_result.get("ok")),
                                "focused": bool(focused),
                                "maximized": bool(placement.get("ok")),
                                "point": [int(point[0]), int(point[1])],
                                "move_s": round(
                                    float(move.get("duration") or 0.0), 3
                                ),
                                "click": click_result,
                            }
                        )
        except Exception as exc:
            evidence["error"] = f"{type(exc).__name__}: {exc}"
        evidence["screen"] = self._capture_screen(f"{stage}_{symbol or 'chart'}")
        evidence["elapsed_s"] = round(time.monotonic() - started, 2)
        self._log(
            TRADINGVIEW,
            "Agent cursor "
            + ("used" if evidence.get("cursor_used") else "unavailable")
            + f" ({stage}); screen capture "
            + ("saved" if evidence["screen"].get("ok") else "failed"),
            level="INFO" if evidence["screen"].get("ok") else "WARN",
            nxt=META,
        )
        return evidence

    # ------------------------------------------------------- GUI execution
    def _make_gui_agent(self) -> Any:
        """Return the injected agent or build the real native executor."""
        if self.gui_agent is not None:
            return self.gui_agent
        if not self.settings.tradingview_gui_enabled:
            return None
        try:
            from tasks.tradingview_gui import TradingViewGuiAgent

            self.gui_agent = TradingViewGuiAgent(
                meta=self.meta,
                settings=self.settings,
                bus=self.bus,
                screen_dir=self._screen_dir(),
            )
            return self.gui_agent
        except Exception as exc:
            self._log(
                TRADINGVIEW,
                f"GUI executor unavailable: {type(exc).__name__}: {exc}",
                level="WARN",
                nxt=TRADING,
            )
            return None

    def _run_gui_order(
        self,
        decision: dict[str, Any],
        *,
        quantity: float,
        live_chart: bool,
    ) -> tuple[Any, dict[str, Any]]:
        """Fill and submit the native TradingView paper ticket with Muse."""
        # Without an injected agent, only drive the GUI when the native chart
        # was actually opened.  Never construct a real executor just to fail
        # in a headless/simulation context.
        if self.gui_agent is None and not live_chart:
            return None, {
                "available": False,
                "reason": "TradingView chart is not live in the native app",
            }
        agent = self._make_gui_agent()
        if agent is None:
            return None, {
                "available": False,
                "reason": "TradingView GUI executor is disabled or unavailable",
            }
        try:
            result = agent.place_order(
                symbol=str(decision.get("symbol") or ""),
                side=str(decision.get("action") or ""),
                quantity=float(quantity),
                entry=float(decision["entry"]),
                stop_loss=float(decision["stop_loss"]),
                take_profit=float(decision["take_profit"]),
                rationale=str(decision.get("rationale") or ""),
            )
        except Exception as exc:
            self._log(
                TRADINGVIEW,
                f"GUI execution failed: {type(exc).__name__}: {exc}",
                level="ERROR",
                nxt=TRADING,
            )
            return None, {
                "available": True,
                "error": f"{type(exc).__name__}: {exc}",
                "reason": "GUI executor raised an exception",
            }
        data = result.to_dict() if hasattr(result, "to_dict") else {"result": result}
        self._log(
            TRADINGVIEW,
            "GUI paper ticket "
            + (
                "confirmed in Paper Trading"
                if getattr(result, "ok", False)
                else f"did not confirm ({getattr(result, 'status', 'unknown')})"
            ),
            level="INFO" if getattr(result, "ok", False) else "WARN",
            nxt=TRADING,
        )
        return result, data

    def run(self, request: TradingRequest) -> TaskResult:
        result = TaskResult(kind="paper_trading")
        started = time.monotonic()
        timings: dict[str, float] = {}
        result.data["timings_s"] = timings
        tv_pool: ThreadPoolExecutor | None = None
        tv_future = None
        tv_status: dict[str, Any] = {}
        try:
            alert = parse_tradingview_alert(request.raw)
            # The desktop delegation passes the user's language so every
            # user-facing summary mirrors the instruction (English in, English
            # out) instead of a canned Spanish reply.
            self._language = (
                "en"
                if str(alert.get("language") or "").lower().startswith("en")
                else "es"
            )
            symbol_value = str(
                alert.get("symbol") or alert.get("ticker") or ""
            ).strip()
            # A delegated "haz una entrada" has no symbol of its own.  Prefer
            # the chart already visible in TradingView instead of defaulting
            # to BTCUSDT and then forcing Muse to reject a symbol mismatch.
            symbol_explicit = bool(
                alert.get("symbol_explicit", bool(symbol_value))
            )
            if (
                not symbol_value
                and self.tradingview is not None
                and self.settings.tradingview_enabled
            ):
                try:
                    symbol_value = symbol_from_title(
                        self.tradingview.window_title()
                    )
                except Exception:
                    symbol_value = ""
            symbol_hint = symbol_value or "BTCUSDT"
            alert["symbol"] = symbol_hint
            result.data["screen_start"] = self._capture_screen("paper_start")
            timeframe = str(
                alert.get("timeframe") or alert.get("interval") or alert.get("tf") or "1h"
            )
            demo_chart = _load_demo_chart() if request.chart_image is None else None
            chart_image = request.chart_image or demo_chart
            if demo_chart is not None:
                result.data["demo_chart"] = str(demo_chart)
                self._log(
                    TRADING,
                    f"Controlled demo chart: {demo_chart.name}",
                    level="WARN",
                    nxt=META,
                )
            # Open the installed TradingView chart in parallel with FAISS
            # recall.  This is the low-latency path: while Muse is still
            # deciding, the desktop app is already loading the symbol.
            if chart_image is None and self.tradingview is not None and self.settings.tradingview_enabled:
                tv_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="TradingView")
                open_and_capture = getattr(self.tradingview, "open_and_capture", None)
                if callable(open_and_capture):
                    tv_future = tv_pool.submit(
                        open_and_capture,
                        symbol_hint,
                        timeframe,
                        capture=(
                            chart_image is None
                            and self.settings.tradingview_capture_chart
                        ),
                    )
                else:
                    tv_future = tv_pool.submit(
                        self.tradingview.open_chart, symbol_hint, timeframe
                    )
                self._log(
                    TRADINGVIEW, f"Opening chart {symbol_hint} in background",
                    nxt=META,
                )
            strategies = self.memory.search(
                f"trading strategy {symbol_hint} {request.raw[:300]}",
                top_k=4, kind="strategy",
            )
            strategy_block = "\n".join(
                f"- ({s['score']:.2f}) {s['text'][:500]}" for s in strategies
            ) or "(no stored strategies; apply conservative defaults)"
            self._log(FAISS, f"Recalled {len(strategies)} strateg(ies)", nxt=META)
            timings["faiss_recall"] = round(time.monotonic() - started, 2)

            # chart_image was resolved above (request image or controlled demo).
            if tv_future is not None:
                try:
                    # The chart had the whole FAISS recall to load.  Wait a
                    # short bounded time before Muse decides so the decision
                    # can use pixels, but never let a slow desktop app stall
                    # the order path indefinitely.
                    # A priced alert can decide fast from its own data.  A
                    # bare "analyse BTCUSDT" has no entry price, so the chart
                    # capture is the primary evidence and gets a longer —
                    # still bounded — window to load.
                    has_price = bool(alert.get("price") or alert.get("entry"))
                    # A cold TradingView start can spend ~30 s restoring the
                    # workspace before the chart title appears.  Wait for the
                    # bridge's bounded load instead of falling back to a
                    # chartless decision and rejecting a valid explicit order.
                    tv_result = tv_future.result(timeout=6.0 if has_price else 45.0)
                    if isinstance(tv_result, tuple):
                        tv_status, captured = tv_result
                        if chart_image is None:
                            chart_image = captured
                    else:
                        tv_status = tv_result
                    result.data["tradingview"] = tv_status
                except FutureTimeout:
                    tv_status = {"opened": False, "state": "still_opening"}
                    result.data["tradingview"] = tv_status
                    self._log(
                        TRADINGVIEW, "Chart still opening; Muse decides from alert data",
                        level="WARN", nxt=META,
                    )
                except Exception as exc:
                    tv_status = {"opened": False, "error": f"{type(exc).__name__}: {exc}"}
                    result.data["tradingview"] = tv_status
                    self._log(TRADINGVIEW, f"Chart unavailable: {exc}", level="WARN", nxt=META)

            # If the user did not name a symbol, use the chart that is already
            # visible instead of forcing a default that Muse will reject as a
            # mismatch.  An explicit symbol is never silently replaced.
            chart_symbol = symbol_from_title(tv_status.get("window_title") or "")
            if chart_symbol and not symbol_explicit:
                if canonical_symbol(chart_symbol) != canonical_symbol(symbol_hint):
                    self._log(
                        TRADINGVIEW,
                        f"No symbol requested; using visible chart {chart_symbol} "
                        f"instead of default {symbol_hint}",
                        level="WARN",
                        nxt=META,
                    )
                symbol_hint = chart_symbol
                alert["symbol"] = chart_symbol
            symbol_mismatch = bool(
                symbol_explicit
                and chart_symbol
                and canonical_symbol(chart_symbol) != canonical_symbol(symbol_hint)
            )
            if symbol_mismatch:
                self._log(
                    TRADINGVIEW,
                    f"Requested {symbol_hint} but TradingView title shows "
                    f"{chart_symbol}; refusing to trade a different symbol",
                    level="WARN",
                    nxt=META,
                )

            # The agent always works through its own cursor.  This moves the
            # overlay over the chart, clicks with the ghost click (physical
            # mouse untouched) and stores a full-screen capture before Muse
            # reads the chart.
            live_chart = bool(tv_future is not None or tv_status.get("opened"))
            result.data["cursor_analysis"] = self._agent_cursor_chart(
                symbol_hint,
                stage="paper_analysis",
                click=True,
                allow_gui=live_chart,
            )

            images = [chart_image] if chart_image else None
            execute_flag = alert.get("execute")
            execute_requested = execute_flag is True or str(execute_flag).strip().lower() in {
                "1", "true", "yes", "si", "sí",
            }
            explicit_execution = is_explicit_entry_request(
                request.raw,
                note=str(alert.get("note") or ""),
                execute=execute_requested,
            )
            force_entry = bool(explicit_execution and not symbol_mismatch)
            threshold = (
                self.settings.explicit_trade_min_confidence
                if explicit_execution
                else self.settings.min_trade_confidence
            )

            if symbol_mismatch and explicit_execution:
                summary = self._t(
                    (
                        f"No se abrió orden paper: TradingView muestra "
                        f"{chart_symbol}, no {symbol_hint}. No se opera un símbolo "
                        "distinto al pedido."
                    ),
                    (
                        f"No paper order was opened: TradingView shows "
                        f"{chart_symbol}, not {symbol_hint}. The agent does not "
                        "trade a different symbol."
                    ),
                )
                result.data["symbol_mismatch"] = {
                    "requested": symbol_hint,
                    "chart": chart_symbol,
                }
                result.data["screen_decision"] = self._capture_screen(
                    "paper_symbol_mismatch"
                )
                self._notify(summary)
                return result.finish(TaskState.REJECTED, summary)

            base_prompt = (
                f"TradingView alert / order: {alert}\n\n"
                f"Recalled strategies from FAISS:\n{strategy_block}\n\n"
                f"Paper account: {self.engine.snapshot()}\n"
                f"Risk limits: max {self.settings.max_risk_per_trade_pct}% risk/trade, "
                f"max {self.settings.max_position_pct}% position. Decide now."
            )
            # Explicit orders may not end in HOLD/REJECT.  Muse is asked to
            # choose BUY or SELL, and if it still hesitates (or returns a
            # below-floor confidence) the same chart evidence is sent back
            # with a stricter correction prompt.  The deterministic risk gate
            # below still validates every returned order.
            attempts = (
                max(1, int(self.settings.explicit_trade_decision_attempts))
                if force_entry
                else 1
            )
            decision_started = time.monotonic()
            decision: dict[str, Any] = {}
            decision_attempts: list[dict[str, Any]] = []
            for attempt in range(1, attempts + 1):
                prompt = base_prompt
                if force_entry:
                    prompt += EXPLICIT_EXECUTION_NOTE
                    if attempt > 1:
                        prompt += (
                            "\nPrevious invalid answer: "
                            f"{json.dumps(decision, ensure_ascii=False)[:900]}\n"
                            f"{EXPLICIT_RETRY_NOTE}"
                        )
                decision = self._reason_json(
                    system=(
                        EXPLICIT_DECISION_SYSTEM
                        if force_entry
                        else DECISION_SYSTEM
                    ),
                    user=prompt,
                    schema_hint=(
                        EXPLICIT_DECISION_SCHEMA
                        if force_entry
                        else DECISION_SCHEMA
                    ),
                    images=images,
                    max_tokens=8192,
                    reasoning_effort="high",
                )
                action = str(decision.get("action") or "HOLD").upper()
                confidence = float(decision.get("confidence") or 0)
                decision_attempts.append(
                    {
                        "attempt": attempt,
                        "action": action,
                        "confidence": confidence,
                    }
                )
                result.data["decision"] = decision
                if not force_entry:
                    break
                if action in {"BUY", "SELL"} and confidence >= threshold:
                    break
                if attempt < attempts:
                    reason = (
                        "HOLD/REJECT"
                        if action in {"HOLD", "REJECT"}
                        else f"confidence {confidence:.2f} below {threshold:.2f}"
                    )
                    self._log(
                        META,
                        f"Explicit order attempt {attempt}/{attempts} returned "
                        f"{action} ({reason}); retrying with a stricter prompt",
                        level="WARN",
                        nxt=TRADING,
                    )
                    time.sleep(0.4)
            timings["muse_decision"] = round(time.monotonic() - decision_started, 2)
            result.data["explicit_execution"] = explicit_execution
            result.data["force_entry"] = force_entry
            result.data["confidence_threshold"] = threshold
            result.data["decision_attempts"] = decision_attempts
            self._log(
                META,
                f"Decision {action} confidence={confidence:.2f} "
                f"threshold={threshold:.2f} "
                f"({'explicit' if explicit_execution else 'autonomous'})",
                nxt=TRADING,
            )

            if action in {"HOLD", "REJECT"}:
                if force_entry:
                    summary = self._t(
                        (
                            "No se abrió orden paper: Muse no pudo validar una "
                            f"entrada tras {attempts} intentos. "
                            f"{decision.get('rationale', '')}"
                        ),
                        (
                            "No paper order was opened: Muse could not validate "
                            f"an entry after {attempts} attempts. "
                            f"{decision.get('rationale', '')}"
                        ),
                    )
                    result.data["screen_decision"] = self._capture_screen(
                        "paper_no_entry"
                    )
                    self._notify(summary)
                    return result.finish(TaskState.REJECTED, summary)
                summary = f"No paper order: Muse decided {action}. {decision.get('rationale', '')}"
                result.data["screen_decision"] = self._capture_screen(
                    f"paper_{action.lower()}"
                )
                self._notify(summary)
                return result.finish(TaskState.COMPLETED, summary)
            if confidence < threshold:
                mode = "explicit-order" if explicit_execution else "autonomous"
                summary = (
                    f"No paper order: confidence {confidence:.2f} below "
                    f"{mode} threshold {threshold:.2f}."
                )
                result.data["screen_decision"] = self._capture_screen(
                    "paper_low_confidence"
                )
                self._notify(summary)
                return result.finish(TaskState.REJECTED, summary)

            if tv_future is not None and not tv_status.get("opened") and tv_future.done():
                # Collect a finished chart status without adding a second
                # blocking wait after Muse has already decided.
                try:
                    tv_result = tv_future.result(timeout=0)
                    tv_status = tv_result[0] if isinstance(tv_result, tuple) else tv_result
                    result.data["tradingview"] = tv_status
                except Exception as exc:
                    tv_status = {"opened": False, "error": f"{type(exc).__name__}: {exc}"}
                    result.data["tradingview"] = tv_status
            self.engine.expire_stale_reservations(
                max_age_s=float(self.settings.tradingview_gui_timeout_s) + 30.0
            )
            existing = self.engine.find_open_order(
                str(decision.get("symbol") or symbol_hint),
                action,
                max_age_s=float(self.settings.paper_duplicate_window_s),
            )
            if existing is not None:
                summary = (
                    f"No new paper order: {existing.order_id} is already OPEN "
                    f"{existing.side} {existing.symbol} @ {existing.entry}. "
                    "Duplicate exposure blocked."
                )
                result.data["existing_order"] = existing.to_dict()
                result.data["screen_decision"] = self._capture_screen(
                    "paper_duplicate"
                )
                self._notify(summary)
                return result.finish(TaskState.COMPLETED, summary)

            try:
                order = self.engine.reserve(decision)
            except DuplicatePaperOrderError as exc:
                existing = exc.order
                summary = (
                    f"No new paper order: {existing.order_id} is already OPEN "
                    f"{existing.side} {existing.symbol} @ {existing.entry}. "
                    "Duplicate exposure blocked."
                )
                result.data["existing_order"] = existing.to_dict()
                result.data["screen_decision"] = self._capture_screen(
                    "paper_duplicate"
                )
                self._notify(summary)
                return result.finish(TaskState.COMPLETED, summary)
            except ValueError as exc:
                summary = f"No paper order: {exc}"
                result.data["screen_decision"] = self._capture_screen(
                    "paper_invalid"
                )
                self._notify(summary)
                return result.finish(TaskState.REJECTED, summary)
            result.data["order"] = order.to_dict()
            result.data["order_reserved"] = True

            # The GUI executor is the execution path: Muse sees the native
            # TradingView window, fills the ticket with the agent cursor and
            # keyboard, and only then is the reserved paper order promoted to
            # OPEN.  Explicit orders may not silently fall back to a ledger.
            gui_required = bool(explicit_execution or live_chart)
            gui_result = None
            gui_data: dict[str, Any] = {"available": False, "reason": "not requested"}
            if gui_required:
                gui_result, gui_data = self._run_gui_order(
                    decision, quantity=order.quantity, live_chart=live_chart
                )
                result.data["gui_execution"] = gui_data
            if gui_result is not None and getattr(gui_result, "ok", False):
                self.engine.confirm_ui(
                    order,
                    reference=getattr(gui_result, "reference", ""),
                    price=getattr(gui_result, "fill_price", 0.0) or order.entry,
                    verified=True,
                )
                result.data["order"] = order.to_dict()
                result.data["gui_verified"] = True
            elif gui_required:
                reason = (
                    getattr(gui_result, "reason", "")
                    if gui_result is not None
                    else str(
                        gui_data.get("reason")
                        or gui_data.get("error")
                        or "TradingView GUI unavailable"
                    )
                )
                submitted = bool(getattr(gui_result, "submitted", False))
                self.engine.fail_ui(order, reason, submitted=submitted)
                result.data["order"] = order.to_dict()
                if submitted:
                    summary = self._t(
                        (
                            "La orden paper pudo enviarse en TradingView, pero no se "
                            f"pudo confirmar visualmente: {reason}. Revisa la pestaña "
                            "Positions/Orders. No se marcó como abierta en el registro."
                        ),
                        (
                            "The paper order may have been sent in TradingView, but "
                            f"it could not be visually confirmed: {reason}. Check "
                            "the Positions/Orders tab. It was not marked as open in "
                            "the ledger."
                        ),
                    )
                    result.data["screen_decision"] = self._capture_screen(
                        "paper_ui_unconfirmed"
                    )
                    self._notify(summary)
                    return result.finish(TaskState.FAILED, summary)
                summary = self._t(
                    (
                        "No se abrió orden paper en TradingView: "
                        f"{reason}. No se registró ninguna orden abierta."
                    ),
                    (
                        "No paper order was opened in TradingView: "
                        f"{reason}. No open order was recorded."
                    ),
                )
                result.data["screen_decision"] = self._capture_screen(
                    "paper_ui_failed"
                )
                self._notify(summary)
                return result.finish(TaskState.REJECTED, summary)
            else:
                # Headless/simulation context (no native chart): keep the
                # ledger honest and mark it as not UI-verified.
                self.engine.confirm_ui(
                    order,
                    reference="LEDGER-ONLY",
                    price=order.entry,
                    verified=False,
                )
                result.data["order"] = order.to_dict()
                result.data["gui_verified"] = False

            # Leave the agent pointer parked over the confirmed chart and
            # store the final full-screen evidence of the paper entry.
            result.data["cursor_confirmed"] = self._agent_cursor_chart(
                order.symbol,
                stage="paper_confirmed",
                click=False,
                allow_gui=live_chart,
            )
            if result.data.get("demo_chart"):
                tv_line = "Chart: controlled historical demo analyzed by Muse"
            elif request.chart_image is not None:
                tv_line = "Chart: supplied chart image analyzed by Muse"
            elif tv_status.get("opened"):
                tv_line = f"TradingView: {tv_status.get('symbol', order.symbol)} chart opened"
            elif chart_image is not None:
                tv_line = "Chart: captured chart image analyzed by Muse"
            else:
                tv_line = "TradingView: chart not confirmed; order decided from alert/FAISS data"
            if result.data.get("gui_verified"):
                ui_line = (
                    "TradingView UI: Paper Trading verified; ticket submitted "
                    "and position confirmed"
                )
            elif explicit_execution:
                ui_line = "TradingView UI: not verified"
            else:
                ui_line = "TradingView UI: ledger-only simulation (no native ticket)"
            threshold_label = "explicit-order" if explicit_execution else "autonomous"
            confirmation = (
                f"PAPER ORDER CONFIRMED {order.order_id}\n"
                f"{order.side} {order.quantity} {order.symbol} @ {order.entry}\n"
                f"Stop Loss: {order.stop_loss} | Take Profit: {order.take_profit}\n"
                f"Muse confidence: {confidence:.2f} ({threshold_label} threshold {threshold:.2f})\n"
                f"{tv_line}\n"
                f"{ui_line}\n"
                f"Mode: PAPER ONLY (no real funds)\n"
                f"Rationale: {order.rationale}"
            )
            self.memory.remember(
                "episode", f"Paper {order.side} {order.symbol} @ {order.entry}: {order.rationale}",
                task="paper_trading", outcome="order_opened", order_id=order.order_id,
            )
            self._notify(confirmation)
            self._log(BRAIN, confirmation.splitlines()[0], nxt=SIMPLEX)
            return result.finish(TaskState.COMPLETED, confirmation)
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            self._log(BRAIN, result.error, level="ERROR")
            try:
                result.data["screen_error"] = self._capture_screen("paper_error")
            except Exception:
                pass
            self._notify(f"Paper trading task failed: {result.error}")
            return result.finish(TaskState.FAILED, f"Trading task failed: {result.error}")
        finally:
            timings["total_before_finish"] = round(time.monotonic() - started, 2)
            if tv_pool is not None:
                tv_pool.shutdown(wait=False, cancel_futures=True)

    def _t(self, es: str, en: str) -> str:
        """Return the summary in the user's instruction language."""
        return en if getattr(self, "_language", "es") == "en" else es

    def _notify(self, text: str) -> None:
        if self.notifier:
            try:
                self.notifier(text)
            except Exception as exc:
                self._log(SIMPLEX, f"Notification failed: {exc}", level="WARN")
