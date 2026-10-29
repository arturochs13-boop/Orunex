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

    def execute(self, decision: dict[str, Any]) -> PaperOrder:
        """Open a simulated position after hard risk validation."""
        with self._lock:
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
            quantity = self.position_size(entry, stop)
            if quantity <= 0:
                raise ValueError("Computed position size is zero; trade rejected.")
            order = PaperOrder(
                order_id="PAPER-" + uuid.uuid4().hex[:10].upper(),
                symbol=symbol,
                side=side, quantity=quantity, entry=entry,
                stop_loss=stop, take_profit=take,
                rationale=str(decision.get("rationale") or "")[:500],
            )
            self.orders[order.order_id] = order
            self._save_locked()
        self._log(
            f"{order.order_id} {side} {quantity} {order.symbol} @ {entry} "
            f"(SL {stop} / TP {take})",
            nxt=SIMPLEX,
        )
        return order

    def find_open_order(
        self,
        symbol: str,
        side: str,
        *,
        max_age_s: float | None = None,
    ) -> PaperOrder | None:
        """Return a recent OPEN order for the same canonical symbol/side."""
        wanted_symbol = canonical_symbol(symbol)
        wanted_side = str(side or "").upper()
        now = time.time()
        with self._lock:
            for order in self.orders.values():
                if max_age_s is not None and now - order.opened_at > max_age_s:
                    continue
                if (
                    order.status == "OPEN"
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
                from _orunex_libs import virtual_input as vin  # type: ignore

                agent = vin.get_input()
                if not agent.available:
                    evidence["error"] = "virtual input unavailable"
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
            symbol_hint = str(alert.get("symbol") or alert.get("ticker") or "BTCUSDT")
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
                    tv_result = tv_future.result(timeout=6.0 if has_price else 30.0)
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
            explicit_execution = (
                execute_requested
                or "execute the best paper entry" in str(alert.get("note") or "").lower()
                or "ejecuta" in request.raw.lower()
            )
            execution_note = (
                "\nEXPLICIT USER EXECUTION ORDER: the user asked for an entry "
                "from this analysis. Choose BUY or SELL from the chart, use "
                "the live chart price as entry and visible support/resistance "
                "for stop_loss/take_profit. HOLD only if the chart symbol is "
                "unreadable or no coherent stop exists.\n"
                if explicit_execution
                else ""
            )
            decision_started = time.monotonic()
            decision = self._reason_json(
                system=DECISION_SYSTEM,
                user=(
                    f"TradingView alert / order: {alert}\n\n"
                    f"Recalled strategies from FAISS:\n{strategy_block}\n\n"
                    f"Paper account: {self.engine.snapshot()}\n"
                    f"Risk limits: max {self.settings.max_risk_per_trade_pct}% risk/trade, "
                    f"max {self.settings.max_position_pct}% position. Decide now."
                    f"{execution_note}"
                ),
                schema_hint=DECISION_SCHEMA,
                images=images,
                max_tokens=8192,
                reasoning_effort="high",
            )
            timings["muse_decision"] = round(time.monotonic() - decision_started, 2)
            result.data["decision"] = decision
            action = str(decision.get("action") or "HOLD").upper()
            confidence = float(decision.get("confidence") or 0)
            threshold = (
                self.settings.explicit_trade_min_confidence
                if explicit_execution
                else self.settings.min_trade_confidence
            )
            result.data["explicit_execution"] = explicit_execution
            result.data["confidence_threshold"] = threshold
            self._log(
                META,
                f"Decision {action} confidence={confidence:.2f} "
                f"threshold={threshold:.2f} "
                f"({'explicit' if explicit_execution else 'autonomous'})",
                nxt=TRADING,
            )

            if action in {"HOLD", "REJECT"}:
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
                order = self.engine.execute(decision)
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
            result.data["order"] = order.to_dict()
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
            threshold_label = "explicit-order" if explicit_execution else "autonomous"
            confirmation = (
                f"PAPER ORDER CONFIRMED {order.order_id}\n"
                f"{order.side} {order.quantity} {order.symbol} @ {order.entry}\n"
                f"Stop Loss: {order.stop_loss} | Take Profit: {order.take_profit}\n"
                f"Muse confidence: {confidence:.2f} ({threshold_label} threshold {threshold:.2f})\n"
                f"{tv_line}\n"
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

    def _notify(self, text: str) -> None:
        if self.notifier:
            try:
                self.notifier(text)
            except Exception as exc:
                self._log(SIMPLEX, f"Notification failed: {exc}", level="WARN")
