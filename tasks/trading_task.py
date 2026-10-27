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
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from core.config import Settings, get_settings
from core.events import BRAIN, FAISS, META, SIMPLEX, TRADING, EventBus
from core.faiss_memory import FAISSMemory
from core.meta_api import MetaAPIClient
from tasks.base import TaskResult, TaskState

DECISION_SCHEMA = (
    '{"action": "BUY|SELL|HOLD|REJECT", "symbol": str, "entry": number, '
    '"stop_loss": number, "take_profit": number, "confidence": 0.0, '
    '"rationale": str, "strategy_refs": [str]}'
)
DECISION_SYSTEM = (
    "You are Muse Spark, a disciplined trading analyst operating ONLY in "
    "paper-trading mode. Analyse the supplied market snapshot and recalled "
    "strategies. Prefer HOLD over a weak trade. Any BUY/SELL must include a "
    "coherent stop_loss and take_profit. Never promise profit."
)


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
        quantity = self.position_size(entry, stop)
        if quantity <= 0:
            raise ValueError("Computed position size is zero; trade rejected.")
        order = PaperOrder(
            order_id="PAPER-" + uuid.uuid4().hex[:10].upper(),
            symbol=str(decision.get("symbol") or "UNKNOWN").upper(),
            side=side, quantity=quantity, entry=entry,
            stop_loss=stop, take_profit=take,
            rationale=str(decision.get("rationale") or "")[:500],
        )
        with self._lock:
            self.orders[order.order_id] = order
            self._save_locked()
        self._log(
            f"{order.order_id} {side} {quantity} {order.symbol} @ {entry} "
            f"(SL {stop} / TP {take})",
            nxt=SIMPLEX,
        )
        return order

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

    def _log(self, stage: str, message: str, *, nxt: str = "", level: str = "INFO") -> None:
        if self.bus:
            self.bus.log(stage, message, level=level, next_stage=nxt)

    def run(self, request: TradingRequest) -> TaskResult:
        result = TaskResult(kind="paper_trading")
        try:
            alert = parse_tradingview_alert(request.raw)
            symbol_hint = str(alert.get("symbol") or alert.get("ticker") or "")
            strategies = self.memory.search(
                f"trading strategy {symbol_hint} {request.raw[:300]}",
                top_k=4, kind="strategy",
            )
            strategy_block = "\n".join(
                f"- ({s['score']:.2f}) {s['text'][:500]}" for s in strategies
            ) or "(no stored strategies; apply conservative defaults)"
            self._log(FAISS, f"Recalled {len(strategies)} strateg(ies)", nxt=META)

            images = [request.chart_image] if request.chart_image else None
            decision = self.meta.reason_json(
                system=DECISION_SYSTEM,
                user=(
                    f"TradingView alert / order: {alert}\n\n"
                    f"Recalled strategies from FAISS:\n{strategy_block}\n\n"
                    f"Paper account: {self.engine.snapshot()}\n"
                    f"Risk limits: max {self.settings.max_risk_per_trade_pct}% risk/trade, "
                    f"max {self.settings.max_position_pct}% position. Decide now."
                ),
                schema_hint=DECISION_SCHEMA,
                images=images,
            )
            result.data["decision"] = decision
            action = str(decision.get("action") or "HOLD").upper()
            confidence = float(decision.get("confidence") or 0)
            self._log(META, f"Decision {action} confidence={confidence:.2f}", nxt=TRADING)

            if action in {"HOLD", "REJECT"}:
                summary = f"No paper order: Muse decided {action}. {decision.get('rationale', '')}"
                self._notify(summary)
                return result.finish(TaskState.COMPLETED, summary)
            if confidence < self.settings.min_trade_confidence:
                summary = (
                    f"No paper order: confidence {confidence:.2f} below "
                    f"threshold {self.settings.min_trade_confidence:.2f}."
                )
                self._notify(summary)
                return result.finish(TaskState.REJECTED, summary)

            order = self.engine.execute(decision)
            result.data["order"] = order.to_dict()
            confirmation = (
                f"PAPER ORDER CONFIRMED {order.order_id}\n"
                f"{order.side} {order.quantity} {order.symbol} @ {order.entry}\n"
                f"Stop Loss: {order.stop_loss} | Take Profit: {order.take_profit}\n"
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
            self._notify(f"Paper trading task failed: {result.error}")
            return result.finish(TaskState.FAILED, f"Trading task failed: {result.error}")

    def _notify(self, text: str) -> None:
        if self.notifier:
            try:
                self.notifier(text)
            except Exception as exc:
                self._log(SIMPLEX, f"Notification failed: {exc}", level="WARN")
