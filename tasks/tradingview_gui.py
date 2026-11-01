"""Recursive vision/action loop for the native TradingView paper ticket.

The trading task already asks Muse for the market decision.  This module is
the missing *execution* half: it captures the native TradingView window,
asks Muse what it sees and which single UI action to take next, performs that
action with Orunex's own cursor/keyboard, then captures again.  The loop is
deliberately bounded and every action is validated before it reaches Windows.

Safety invariants
-----------------
* PAPER TRADING ONLY.  ``submit`` is refused unless the screenshot shows the
  "Paper Trading" panel (Muse's reading **and** a deterministic template
  match) and a second, independent Muse verification confirms the ticket
  values.
* The model never gets arbitrary Python/shell execution.  It can only ask
  for ``click``, ``type``, ``press``, ``hotkey``, ``scroll``, ``wait``,
  ``think``, ``abort``, ``submit`` or ``done``.
* Clicks are expressed in normalized coordinates relative to the captured
  TradingView window, so they cannot land outside the app.
* No broker API is imported or called here.

The module is injectable for tests: ``input_factory``, ``window_finder``,
``capture_func`` and ``paper_checker`` can all be replaced with fakes.
"""

from __future__ import annotations

import json
import math
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from core.config import Settings, get_settings
from core.events import EventBus, META, TRADING, TRADINGVIEW

# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------
ALLOWED_ACTIONS = {
    "click",
    "type",
    "press",
    "hotkey",
    "scroll",
    "wait",
    "think",
    "abort",
    "submit",
    "done",
    "set_field",
}

ACTION_SCHEMA = (
    '{"observation": str, "ui_state": "chart|ticket|position|confirmation|unknown", '
    '"paper_trading_visible": bool, "paper_text": str, "symbol": str, '
    '"selected_side": "buy|sell|unknown", "order_type": "market|limit|stop|unknown", '
    '"price_value": str, "units_value": str, "size_value": str, '
    '"size_mode": "USD margin|Units|percent|other|unknown", '
    '"take_profit_enabled": bool, '
    '"take_profit_value": str, "stop_loss_enabled": bool, "stop_loss_value": str, '
    '"submit_text": str, "ad_visible": bool, "ready_to_submit": bool, '
    '"confidence": 0.0, "thought": str, '
    '"action": "click|type|press|hotkey|scroll|wait|think|abort|submit|done|set_field", '
    '"x": 0.0, "y": 0.0, "text": str, "key": str, "keys": [str], '
    '"amount": 0, "seconds": 0.0, "reason": str}'
)

SUBMIT_VERIFY_SCHEMA = (
    '{"paper_trading_visible": bool, "paper_text": str, "symbol": str, '
    '"side": "BUY|SELL|UNKNOWN", "order_type": "MARKET|LIMIT|STOP|UNKNOWN", '
    '"price_value": str, "units": str, "take_profit_enabled": bool, '
    '"take_profit": str, "stop_loss_enabled": bool, "stop_loss": str, '
    '"submit_text": str, "safe_to_submit": bool, "reason": str, "confidence": 0.0}'
)

CONFIRM_SCHEMA = (
    '{"paper_trading_visible": bool, "submitted": bool, "position_visible": bool, '
    '"symbol": str, "side": "BUY|SELL|UNKNOWN", "units": str, '
    '"evidence": str, "confidence": 0.0}'
)

GUI_SYSTEM = (
    "You are Muse, the visual operator of Orunex. You control the NATIVE "
    "TradingView desktop application through a virtual cursor and keyboard. "
    "This is PAPER TRADING ONLY: never open a browser, never use a real "
    "broker, never change the trading account, never promise profit. You see "
    "one screenshot per step and return exactly one safe UI action as JSON. "
    "If you cannot identify an element with confidence, return action "
    "\"think\" or scroll inside the ticket instead of guessing. If the panel "
    "is not Paper Trading, return \"abort\"."
)

VERIFY_SYSTEM = (
    "You are Muse, a strict paper-trading safety verifier. Read the supplied "
    "TradingView screenshot. Never approve an order unless the Paper Trading "
    "panel is visibly active and every ticket value matches the intended "
    "paper order. Be literal: do not infer hidden values. Return only JSON."
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def canonical_symbol(value: object) -> str:
    raw = str(value or "").strip().upper().replace(" ", "").replace("/", "")
    if ":" in raw:
        raw = raw.split(":", 1)[1]
    if raw.endswith(".P"):
        raw = raw[:-2]
    return raw


def fmt_number(value: float, *, places: int = 8) -> str:
    text = f"{float(value):.{places}f}".rstrip("0").rstrip(".")
    return text or "0"


def as_float(value: object) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None
    text = str(value).strip().replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "si", "sí"}


def close_enough(actual: Optional[float], expected: float, *, rel: float = 0.01) -> bool:
    if actual is None:
        return False
    return abs(actual - expected) <= max(0.01, abs(expected) * rel)


def _norm_coord(value: object, size: int) -> Optional[float]:
    """Accept normalized, percentage or pixel coordinates.

    Muse is asked for 0..1, but vision models occasionally answer in pixels or
    percent.  Converting those forms is safer than rejecting a good click.
    """
    number = as_float(value)
    if number is None:
        return None
    if 0.0 <= number <= 1.0:
        return number
    if 2.0 <= number <= 100.0:
        return number / 100.0
    if 100.0 < number <= max(1.0, size * 1.2):
        return number / max(1.0, size)
    return None


def _safe_text(value: object, *, limit: int = 64) -> Optional[str]:
    text = str(value or "")
    if not text or len(text) > limit:
        return None
    if any(ch in text for ch in "\r\n\t"):
        return None
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        return None
    return text


_KEY_ALIASES = {
    "return": "enter",
    "escape": "esc",
    "del": "delete",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "control": "ctrl",
    "windows": "win",
}
_ALLOWED_KEYS = {
    "enter", "tab", "esc", "space", "backspace", "delete", "insert",
    "home", "end", "pageup", "pagedown", "up", "down", "left", "right",
    "ctrl", "alt", "shift", "win", "capslock", "numlock",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10",
    "f11", "f12",
    *(chr(code) for code in range(ord("a"), ord("z") + 1)),
    *(str(number) for number in range(10)),
}


def _safe_key(value: object) -> Optional[str]:
    key = _KEY_ALIASES.get(str(value or "").strip().lower(), str(value or "").strip().lower())
    return key if key in _ALLOWED_KEYS else None


def _safe_keys(value: object) -> Optional[list[str]]:
    if isinstance(value, str):
        value = [part for part in re.split(r"[+\s]+", value) if part]
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 4:
        return None
    keys = [_safe_key(part) for part in value]
    if any(key is None for key in keys):
        return None
    lowered = [str(key) for key in keys]
    # Never let a model close/quit the app or open a new window/tab.
    if "alt" in lowered and "f4" in lowered:
        return None
    if "ctrl" in lowered and any(key in lowered for key in ("w", "q", "n", "t", "u")):
        return None
    if "shift" in lowered and "ctrl" in lowered and "q" in lowered:
        return None
    return lowered


def _strip_json(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except Exception:
        pass
    start, depth = -1, 0
    for index, char in enumerate(text):
        if char == "{":
            if start < 0:
                start = index
            depth += 1
        elif char == "}" and start >= 0:
            depth -= 1
            if depth == 0:
                try:
                    value = json.loads(text[start : index + 1])
                    if isinstance(value, dict):
                        return value
                except Exception:
                    break
    raise ValueError("Muse did not return a JSON object")


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
@dataclass
class GuiAgentResult:
    ok: bool
    status: str
    reason: str = ""
    submitted: bool = False
    confirmed: bool = False
    paper_verified: bool = False
    ready: bool = False
    reference: str = ""
    fill_price: float = 0.0
    steps: list[dict[str, Any]] = field(default_factory=list)
    screens: list[str] = field(default_factory=list)
    ui: dict[str, Any] = field(default_factory=dict)
    elapsed_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "reason": self.reason,
            "submitted": self.submitted,
            "confirmed": self.confirmed,
            "paper_verified": self.paper_verified,
            "ready": self.ready,
            "reference": self.reference,
            "fill_price": self.fill_price,
            "steps": self.steps,
            "screens": self.screens,
            "ui": self.ui,
            "elapsed_s": self.elapsed_s,
        }


# ---------------------------------------------------------------------------
# Deterministic Paper Trading panel check
# ---------------------------------------------------------------------------
class PaperPanelVerifier:
    """Template match for the visible "Paper Trading" label.

    Muse also reports the panel, but a model can hallucinate.  This check is
    deterministic: it looks for the exact rendered label in the lower-left
    area of the captured window.  The template is stored in
    ``data/templates/tv_paper_trading.png``.
    """

    def __init__(self, template_path: Optional[Path] = None) -> None:
        self.template_path = template_path or (
            Path(__file__).resolve().parent.parent / "data" / "templates" / "tv_paper_trading.png"
        )
        self._template = None
        self._template_key = None

    def _load(self):
        if self._template is not None:
            return self._template
        try:
            from PIL import Image
            import numpy as np

            image = Image.open(self.template_path).convert("L")
            self._template = np.asarray(image, dtype=np.float32)
            self._template_key = str(self.template_path)
            return self._template
        except Exception:
            self._template = None
            return None

    def check(self, image: Any) -> dict[str, Any]:
        """Return ``{"ok": bool, "score": float, "box": ...}``.

        The check is intentionally conservative.  A missing template or a
        score below 0.65 blocks ``submit``.  The lower threshold tolerates a
        small tooltip covering the first letters of the label while still
        requiring the distinctive "Paper Trading" glyph pattern.
        """
        try:
            import numpy as np
            from PIL import Image

            template = self._load()
            if template is None or image is None:
                return {"ok": False, "score": 0.0, "reason": "template unavailable"}
            width, height = image.size
            # Search the lower-left area where the paper panel header lives.
            x0 = int(width * 0.01)
            x1 = int(width * 0.34)
            y0 = int(height * 0.58)
            y1 = int(height * 0.82)
            if x1 - x0 < 40 or y1 - y0 < 20:
                return {"ok": False, "score": 0.0, "reason": "capture too small"}
            region = image.crop((x0, y0, x1, y1)).convert("L")
            # Work at half resolution: the label is ~150 px wide, so it stays
            # legible while the sliding window remains cheap.
            region = region.resize(
                (max(1, region.width // 2), max(1, region.height // 2)),
                Image.Resampling.BILINEAR,
            )
            templ = Image.fromarray(template.astype("uint8")).resize(
                (max(1, template.shape[1] // 2), max(1, template.shape[0] // 2)),
                Image.Resampling.BILINEAR,
            )
            t = np.asarray(templ, dtype=np.float32)
            r = np.asarray(region, dtype=np.float32)
            th, tw = t.shape
            if r.shape[0] < th or r.shape[1] < tw:
                return {"ok": False, "score": 0.0, "reason": "template larger than search area"}
            t_mean = float(t.mean())
            t_zero = t - t_mean
            t_norm = float(np.sqrt((t_zero ** 2).sum()))
            if t_norm <= 1e-6:
                return {"ok": False, "score": 0.0, "reason": "empty template"}
            windows = np.lib.stride_tricks.sliding_window_view(r, (th, tw))
            w_mean = windows.mean(axis=(2, 3), keepdims=True)
            w_zero = windows - w_mean
            w_norm = np.sqrt((w_zero ** 2).sum(axis=(2, 3)))
            denom = w_norm * t_norm
            scores = np.divide(
                (w_zero * t_zero).sum(axis=(2, 3)),
                denom,
                out=np.zeros_like(denom, dtype=np.float32),
                where=denom > 1e-6,
            )
            flat = int(np.argmax(scores))
            best = float(scores.flat[flat])
            yy, xx = np.unravel_index(flat, scores.shape)
            return {
                "ok": best >= 0.65,
                "score": round(best, 4),
                "box": [
                    x0 + int(xx) * 2,
                    y0 + int(yy) * 2,
                    x0 + (int(xx) + tw) * 2,
                    y0 + (int(yy) + th) * 2,
                ],
            }
        except Exception as exc:
            return {"ok": False, "score": 0.0, "reason": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# GUI loop
# ---------------------------------------------------------------------------
class TradingViewGuiAgent:
    """Bounded capture -> Muse -> action loop for the native paper ticket."""

    def __init__(
        self,
        *,
        meta: Any,
        settings: Optional[Settings] = None,
        bus: Optional[EventBus] = None,
        screen_dir: Optional[Path] = None,
        input_factory: Optional[Callable[[], Any]] = None,
        window_finder: Optional[Callable[[], Any]] = None,
        capture_func: Optional[Callable[[], Any]] = None,
        paper_checker: Optional[Callable[[Any], dict[str, Any]]] = None,
        max_steps: Optional[int] = None,
        timeout_s: Optional[float] = None,
    ) -> None:
        self.meta = meta
        self.settings = settings or get_settings()
        self.bus = bus
        self.screen_dir = screen_dir or (
            self.settings.paper_state_path.parent / "screens"
        )
        self._input_factory = input_factory
        self._window_finder = window_finder
        self._capture_func = capture_func
        self._paper_checker = paper_checker
        self.max_steps = max(
            1, int(max_steps or getattr(self.settings, "tradingview_gui_max_steps", 18))
        )
        self.timeout_s = max(
            10.0,
            float(timeout_s or getattr(self.settings, "tradingview_gui_timeout_s", 300.0)),
        )
        self._input: Any = None
        self._paper_verifier = PaperPanelVerifier()

    # ---------------------------------------------------------------- logging
    def _log(self, message: str, *, level: str = "INFO", nxt: str = "") -> None:
        if self.bus:
            try:
                self.bus.log(TRADINGVIEW, message, level=level, next_stage=nxt)
            except Exception:
                pass

    # --------------------------------------------------------------- capture
    def _get_input(self):
        if self._input is None:
            if self._input_factory is not None:
                self._input = self._input_factory()
            else:
                try:
                    from _orunex_libs import virtual_input as vin  # type: ignore
                except ImportError:
                    src_dir = Path(__file__).resolve().parent.parent / "src"
                    if str(src_dir) not in sys.path:
                        sys.path.insert(0, str(src_dir))
                    from _orunex_libs import virtual_input as vin  # type: ignore
                self._input = vin.get_input()
        return self._input

    def _get_window(self):
        if self._window_finder is not None:
            return self._window_finder()
        try:
            from _orunex_libs import virtual_input as vin  # type: ignore
        except ImportError:
            src_dir = Path(__file__).resolve().parent.parent / "src"
            if str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))
            from _orunex_libs import virtual_input as vin  # type: ignore
        return vin.find_tradingview_window()

    def _default_capture(self):
        """Capture only the TradingView client area, never the whole desktop."""
        from PIL import ImageGrab

        agent = self._get_input()
        window = self._get_window()
        if window is None:
            return None
        try:
            agent.attach_window(window)
        except Exception:
            pass
        try:
            agent.maximize()
        except Exception:
            pass
        try:
            agent.focus()
        except Exception:
            pass
        time.sleep(0.35)
        try:
            from _orunex_libs import virtual_input as vin  # type: ignore
        except ImportError:
            src_dir = Path(__file__).resolve().parent.parent / "src"
            if str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))
            from _orunex_libs import virtual_input as vin  # type: ignore
        try:
            vin._ensure_dpi_aware()  # type: ignore[attr-defined]
        except Exception:
            pass
        left, top, width, height = vin.get_client_rect(window.hwnd)
        if width < 320 or height < 240:
            return None
        image = ImageGrab.grab(
            bbox=(left, top, left + width, top + height), all_screens=True
        )
        return image, (left, top, width, height), window

    def _capture(self, step: int):
        try:
            if self._capture_func is not None:
                result = self._capture_func()
            else:
                result = self._default_capture()
        except Exception as exc:
            self._log(f"GUI capture failed: {type(exc).__name__}: {exc}", level="WARN")
            return None
        if not result:
            return None
        if len(result) == 2:
            image, rect = result
            window = None
        else:
            image, rect, window = result
        if image is None:
            return None
        try:
            self.screen_dir.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            path = self.screen_dir / f"{stamp}_{int(time.time() * 1000) % 1000:03d}_gui_{step:02d}.png"
            image.save(path, format="PNG")
        except Exception:
            path = None
        return {"image": image, "rect": rect, "window": window, "path": path}

    # --------------------------------------------------------------- Muse I/O
    def _reason_json(self, **kwargs: Any) -> dict[str, Any]:
        try:
            return self.meta.reason_json(**kwargs)
        except TypeError:
            for key in ("max_tokens", "reasoning_effort", "model"):
                kwargs.pop(key, None)
            return self.meta.reason_json(**kwargs)

    def _ask_action(
        self,
        *,
        order: dict[str, Any],
        step: int,
        submitted: bool,
        history: list[dict[str, Any]],
        capture: dict[str, Any],
        paper_check: dict[str, Any],
    ) -> dict[str, Any]:
        width, height = capture["image"].size
        history_lines = []
        for item in history[-6:]:
            history_lines.append(
                f"- step {item.get('step')}: {item.get('action')} "
                f"{item.get('target', '')} -> {item.get('result', '')[:220]}"
            )
        history_text = "\n".join(history_lines) or "(no actions yet)"
        # Detect a stuck click loop (Muse clicked the same field eight times in
        # a row without ever typing) and call it out in the next prompt.
        recent_clicks: list[tuple[float, float]] = []
        for item in reversed(history):
            if item.get("action") not in {"click", "submit"}:
                break
            requested = item.get("requested") or {}
            try:
                recent_clicks.append(
                    (float(requested.get("x")), float(requested.get("y")))
                )
            except (TypeError, ValueError):
                break
        repeat_warning = ""
        if len(recent_clicks) >= 2:
            first_x, first_y = recent_clicks[0]
            if all(
                abs(x - first_x) <= 0.02 and abs(y - first_y) <= 0.02
                for x, y in recent_clicks[1:]
            ):
                repeat_warning = (
                    "\nWARNING: the last "
                    f"{len(recent_clicks)} actions were clicks on the same spot. "
                    "Do NOT click it again. If it is a number field, use "
                    "\"set_field\" with the exact value; if it is a toggle, "
                    "click it once and move to the next checklist item."
                )
        correction = ""
        # Only nudge the size when the ticket is genuinely off.  The ticket
        # rounds to 3 decimals, so 0.0249 for 0.025044 is already correct; an
        # unconditional "correction" made the agent loop back to the margin
        # field and burn its whole step budget.
        for item in reversed(history):
            mode = str(item.get("size_mode") or "").lower()
            units_seen = as_float(item.get("units_value"))
            size_seen = as_float(item.get("size_value"))
            if "margin" not in mode or not units_seen or not size_seen:
                continue
            tolerance = order["quantity"] * 0.005
            if abs(units_seen - order["quantity"]) <= tolerance:
                break
            corrected = size_seen * order["quantity"] / units_seen
            correction = (
                "\nCORRECTION from the last ticket state: "
                f"{item.get('size_value')} USD margin produced "
                f"{item.get('units_value')} units. To hit "
                f"{order['quantity_text']} units, set the LEFT size field to "
                f"{fmt_number(corrected, places=2)} USD margin."
            )
            break
        phase = (
            "The submit button has already been clicked. DO NOT click it again. "
            "Verify the paper position/order in the bottom panel and return "
            "\"done\" only when it is visibly there."
            if submitted
            else "Fill the ticket and submit exactly one paper order."
        )
        prompt = f"""
GOAL: place exactly this PAPER order in the visible TradingView ticket:
- symbol: {order['symbol']}
- side: {order['side']}
- order type: MARKET
- quantity: {order['quantity_text']} units
- USD margin equivalent at 10x: {order['margin_text']} USD
- take profit: {order['take_profit_text']} (enabled)
- stop loss: {order['stop_loss_text']} (enabled)
- reference entry from the chart decision: {order['entry_text']}
Do not change these values. Do not place any other order. Never use real funds.

SIZE FIELD: The label above the left size input tells you its mode, usually
"USD margin". That LEFT number field (for example the one showing 115.16) is
the editable one. The right-hand "units" dropdown only changes the DISPLAY
unit: clicking it does NOT set the order size. If the label says "USD margin",
edit the LEFT field with action "set_field" and text {order['margin_text']}. If
the label says "Units", use "set_field" with text {order['quantity_text']}
instead. After Tab, the
right-hand text should show about {order['quantity_text']} units (the ticket
rounds to 3 decimals, so 0.868 is normal). If the ticket already shows units
within 1% of {order['quantity_text']}, the size is DONE: do NOT edit the size
field again, move on to Exits. In every reply report size_value as the LEFT
field text (for example "115.16") and size_mode as the label (for example
"USD margin" or "Units").{correction}

PHASE: {phase}
Current step: {step}/{self.max_steps}. submitted={submitted}.
Deterministic "Paper Trading" label match: {paper_check.get('ok')} (score {paper_check.get('score')}).
Screenshot: native TradingView window, {width}x{height} px. Coordinates are
normalized 0..1 from the top-left of THIS image. Always click the CENTER of
the element. If you answer in pixels or percent the loop will convert it, but
0..1 is preferred.

Recent action history:
{history_text}{repeat_warning}

Checklist (perform the next unmet step, one action per turn):
1. If a popup/ad covers the paper panel or the ticket, close it with its X.
2. Confirm the chart symbol is {order['symbol']}. If it is different, click
   the symbol box at the top-left, press Ctrl+A, type {order['symbol']},
   press Enter, wait, then re-check.
3. If the order ticket is not visible, click the Trade button at the top-right.
4. Select the Order tab (not DOM).
5. Select the {order['side']} side.
6. Select Market.
7. Set the order size with the LEFT size field, as described in SIZE FIELD.
   Use action "set_field" (it clicks, Ctrl+A, types and presses Tab in one
   step). Do NOT click the right-hand "units" dropdown. If the submit button
   says "Start creating order", click the {order['side']} side pill and Market
   again before editing the size.
8. Open Exits. Enable Take profit and set {order['take_profit_text']} with
   action "set_field". Enable Stop loss and set {order['stop_loss_text']} with
   action "set_field". The Stop loss row sits BELOW Take profit: scroll DOWN
   inside the ticket with amount -5 (negative scrolls down, positive scrolls
   up). Never scroll over the chart. If the Stop loss toggle is off, click its
   switch first.
9. Verify the submit button text contains "{order['side']}", "{order['symbol']}"
   and "MARKET", and that the quantity shown is within 1% of
   {order['quantity_text']} (rounding to 3 decimals is expected). The panel
   must say Paper Trading. Only then return action "submit" with the center of
   that button.
10. After submit, do NOT submit again. Check Positions or Orders in the Paper
    Trading panel. Return "done" only when the intended position/order is
    visibly present.

Rules:
- One action per reply. Use "think" if you are unsure; use "abort" if the
  symbol is wrong, the panel is not Paper Trading, or you cannot proceed.
- EDIT A NUMBER FIELD ONLY WITH "set_field": give its center x/y and the exact
  text. It performs click + Ctrl+A + type + Tab atomically. Never click the
  same field twice in a row: if a field is already focused, set_field edits it.
- For press use "tab", "enter", "esc", "backspace", etc. For hotkey use keys
  like ["ctrl","a"].
- If a field already shows the exact value, do not retype it.
- Never guess a destructive click. Never click Upgrade, account settings,
  deposit, or any real-money control.
- The only submit button you may press is the paper ticket button whose text
  matches the intended order.
""".strip()
        response = self._reason_json(
            system=GUI_SYSTEM,
            user=prompt,
            schema_hint=ACTION_SCHEMA,
            images=[capture["path"]] if capture.get("path") else None,
            max_tokens=1800,
            reasoning_effort="medium",
        )
        return _strip_json(response)

    def _verify_submit(
        self, *, order: dict[str, Any], capture: dict[str, Any]
    ) -> tuple[bool, str, dict[str, Any]]:
        prompt = f"""
Look at this TradingView screenshot immediately before a paper order is sent.
The intended order is:
- symbol: {order['symbol']}
- side: {order['side']}
- order type: MARKET
- units: {order['quantity_text']}
- take profit: {order['take_profit_text']} (must be enabled)
- stop loss: {order['stop_loss_text']} (must be enabled)

Read the actual ticket literally. Approve ONLY if the visible panel says
"Paper Trading", the side and symbol match, the order type is Market, the
units match, both exits are enabled with the intended values, and the submit
button text clearly refers to this order. The ticket rounds the quantity to
3 decimals, so any value within 1% of the intended units (for example 0.868
for 0.867243) is a match; do not require all six decimals. If anything is
missing or differs, set safe_to_submit=false and explain exactly what is
wrong.

A tooltip or the agent pointer may partially cover the "Paper Trading" label
or the submit button. If you can still identify the paper panel from the
visible part of the label ("...er Trading") plus its Positions/Orders/Balance
history tabs, set paper_trading_visible=true and note the obstruction. Do not
approve a live/real account or a panel you cannot identify at all.
""".strip()
        raw = self._reason_json(
            system=VERIFY_SYSTEM,
            user=prompt,
            schema_hint=SUBMIT_VERIFY_SCHEMA,
            images=[capture["path"]] if capture.get("path") else None,
            max_tokens=1200,
            reasoning_effort="high",
        )
        data = _strip_json(raw)
        mismatches: list[str] = []
        if not as_bool(data.get("paper_trading_visible")):
            mismatches.append("Paper Trading no visible")
        if canonical_symbol(data.get("symbol")) != canonical_symbol(order["symbol"]):
            mismatches.append(
                f"symbol {data.get('symbol')!r} != {order['symbol']!r}"
            )
        if str(data.get("side") or "").upper() != order["side"]:
            mismatches.append(f"side {data.get('side')!r} != {order['side']!r}")
        if str(data.get("order_type") or "").upper() != "MARKET":
            mismatches.append(f"order type {data.get('order_type')!r} != MARKET")
        if not close_enough(as_float(data.get("units")), order["quantity"], rel=0.01):
            mismatches.append(
                f"units {data.get('units')!r} != {order['quantity_text']!r}"
            )
        if not as_bool(data.get("take_profit_enabled")):
            mismatches.append("take profit not enabled")
        if not close_enough(
            as_float(data.get("take_profit")), order["take_profit"], rel=0.002
        ):
            mismatches.append(
                f"take profit {data.get('take_profit')!r} != {order['take_profit_text']!r}"
            )
        if not as_bool(data.get("stop_loss_enabled")):
            mismatches.append("stop loss not enabled")
        if not close_enough(
            as_float(data.get("stop_loss")), order["stop_loss"], rel=0.002
        ):
            mismatches.append(
                f"stop loss {data.get('stop_loss')!r} != {order['stop_loss_text']!r}"
            )
        submit_text = str(data.get("submit_text") or "").upper()
        submit_compact = submit_text.replace(" ", "")
        side_visible = order["side"] in submit_text or (
            len(order["side"]) >= 2
            and order["side"][:2] in submit_text
            and canonical_symbol(order["symbol"]) in submit_compact
        )
        if not side_visible:
            mismatches.append(f"submit text lacks {order['side']}")
        if canonical_symbol(order["symbol"]) not in submit_compact:
            mismatches.append(f"submit text lacks {order['symbol']}")
        if not as_bool(data.get("safe_to_submit")):
            mismatches.append("verifier did not approve")
        if as_float(data.get("confidence")) is not None and float(
            data.get("confidence")
        ) < 0.60:
            mismatches.append(f"verifier confidence {data.get('confidence')} < 0.60")
        if mismatches:
            return False, "; ".join(mismatches), data
        return True, "", data

    def _verify_confirmation(
        self, *, order: dict[str, Any], capture: dict[str, Any]
    ) -> tuple[bool, str, dict[str, Any]]:
        prompt = f"""
Look at this TradingView screenshot AFTER a paper market order was sent.
The intended paper position is:
- symbol: {order['symbol']}
- side: {order['side']}
- units: {order['quantity_text']}

Check the bottom Paper Trading panel (Positions, Orders or Order history).
Return submitted=true and position_visible=true only if you can literally see
that position/order, with the matching symbol and side. The displayed units
may be rounded to 3 decimals; accept a value within 2% of the intended units.
If a popup covers the panel, say so. Do not infer from the order ticket alone:
the ticket may still show the form.
""".strip()
        raw = self._reason_json(
            system=VERIFY_SYSTEM,
            user=prompt,
            schema_hint=CONFIRM_SCHEMA,
            images=[capture["path"]] if capture.get("path") else None,
            max_tokens=900,
            reasoning_effort="high",
        )
        data = _strip_json(raw)
        mismatches: list[str] = []
        if not as_bool(data.get("paper_trading_visible")):
            mismatches.append("Paper Trading no visible")
        if not (as_bool(data.get("submitted")) or as_bool(data.get("position_visible"))):
            mismatches.append("no submitted order/position visible")
        if canonical_symbol(data.get("symbol")) != canonical_symbol(order["symbol"]):
            mismatches.append(
                f"symbol {data.get('symbol')!r} != {order['symbol']!r}"
            )
        if str(data.get("side") or "").upper() != order["side"]:
            mismatches.append(f"side {data.get('side')!r} != {order['side']!r}")
        units = as_float(data.get("units"))
        if units is not None and not close_enough(
            units, order["quantity"], rel=0.02
        ):
            mismatches.append(f"units {units} != {order['quantity_text']}")
        if mismatches:
            return False, "; ".join(mismatches), data
        return True, "", data

    # ------------------------------------------------------------- action I/O
    def _screen_point(
        self, x_norm: float, y_norm: float, rect: tuple[int, int, int, int]
    ) -> tuple[int, int]:
        left, top, width, height = rect
        x = left + int(round(x_norm * max(1, width - 1)))
        y = top + int(round(y_norm * max(1, height - 1)))
        return x, y

    def _recapture_neutral(self, step: int, capture: dict[str, Any]):
        """Move the agent pointer away from the ticket controls and recapture."""
        try:
            agent = self._get_input()
            neutral = self._screen_point(0.46, 0.90, capture["rect"])
            agent.move_to(*neutral, duration=0.15)
            time.sleep(0.35)
            return self._capture(step)
        except Exception:
            return capture

    def _execute_action(
        self,
        *,
        action: dict[str, Any],
        capture: dict[str, Any],
        order: dict[str, Any],
    ) -> dict[str, Any]:
        agent = self._get_input()
        rect = capture["rect"]
        width, height = capture["image"].size
        kind = action["action"]
        if kind in {"click", "submit"}:
            x_norm = _norm_coord(action.get("x"), width)
            y_norm = _norm_coord(action.get("y"), height)
            if x_norm is None or y_norm is None:
                return {"ok": False, "error": "invalid coordinates"}
            x, y = self._screen_point(x_norm, y_norm, rect)
            result = agent.click(x, y, ensure_focus=True, duration=0.22)
            return {
                "ok": bool(result.get("ok")),
                "x": x,
                "y": y,
                "normalized": [round(x_norm, 4), round(y_norm, 4)],
                "result": result,
            }
        if kind == "set_field":
            # One atomic edit: click, select-all, type, Tab.  Muse used to
            # click the same numeric field forever instead of typing, so the
            # whole edit is a single validated action here.
            text = _safe_text(action.get("text"))
            x_norm = _norm_coord(action.get("x"), width)
            y_norm = _norm_coord(action.get("y"), height)
            if text is None:
                return {"ok": False, "error": "unsafe or empty text"}
            if x_norm is None or y_norm is None:
                return {"ok": False, "error": "invalid coordinates"}
            x, y = self._screen_point(x_norm, y_norm, rect)
            clicked = agent.click(x, y, ensure_focus=True, duration=0.18)
            if not clicked.get("ok"):
                return {"ok": False, "error": "click failed", "x": x, "y": y}
            time.sleep(0.25)
            agent.hotkey("ctrl", "a", ensure_focus=True)
            time.sleep(0.12)
            typed = agent.type_text(text, ensure_focus=True, interval=0.04)
            time.sleep(0.15)
            agent.press("tab", ensure_focus=True)
            time.sleep(0.35)
            return {
                "ok": bool(typed),
                "x": x,
                "y": y,
                "text": text,
                "normalized": [round(x_norm, 4), round(y_norm, 4)],
            }
        if kind == "type":
            text = _safe_text(action.get("text"))
            if text is None:
                return {"ok": False, "error": "unsafe or empty text"}
            ok = agent.type_text(text, ensure_focus=True, interval=0.04)
            return {"ok": bool(ok), "text": text}
        if kind == "press":
            key = _safe_key(action.get("key"))
            if key is None:
                return {"ok": False, "error": "unsupported key"}
            ok = agent.press(key, ensure_focus=True)
            return {"ok": bool(ok), "key": key}
        if kind == "hotkey":
            keys = _safe_keys(action.get("keys"))
            if keys is None:
                return {"ok": False, "error": "unsupported hotkey"}
            ok = agent.hotkey(*keys, ensure_focus=True)
            return {"ok": bool(ok), "keys": keys}
        if kind == "scroll":
            x_norm = _norm_coord(action.get("x"), width)
            y_norm = _norm_coord(action.get("y"), height)
            amount_raw = action.get("amount")
            amount = int(amount_raw) if amount_raw not in (None, "") else -5
            if amount == 0:
                amount = -5
            amount = max(-20, min(20, amount))
            if x_norm is None or y_norm is None:
                return {"ok": False, "error": "invalid scroll"}
            x, y = self._screen_point(x_norm, y_norm, rect)
            agent.move_to(x, y, duration=0.15)
            ok = agent.scroll(amount, ensure_focus=True)
            return {"ok": bool(ok), "x": x, "y": y, "amount": amount}
        if kind == "wait":
            seconds = max(0.0, min(5.0, float(action.get("seconds") or 0.8)))
            time.sleep(seconds)
            return {"ok": True, "seconds": seconds}
        if kind == "think":
            return {"ok": True, "thought": str(action.get("thought") or action.get("reason") or "")[:300]}
        return {"ok": False, "error": f"unhandled action {kind}"}

    # -------------------------------------------------------------- main loop
    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        entry: float,
        stop_loss: float,
        take_profit: float,
        rationale: str = "",
        allow_submit: bool = True,
    ) -> GuiAgentResult:
        started = time.monotonic()
        steps: list[dict[str, Any]] = []
        screens: list[str] = []
        # The native paper ticket sizes by USD margin at 10x by default.  Give
        # Muse both representations so it never has to do the arithmetic: the
        # left field takes the margin, the right label shows the units.
        leverage = 10.0
        order = {
            "symbol": canonical_symbol(symbol),
            "side": str(side or "").upper(),
            "quantity": float(quantity),
            "quantity_text": fmt_number(quantity, places=6),
            "margin_text": fmt_number(float(quantity) * float(entry) / leverage, places=2),
            "entry": float(entry),
            "entry_text": fmt_number(entry, places=8),
            "stop_loss": float(stop_loss),
            "stop_loss_text": fmt_number(stop_loss, places=8),
            "take_profit": float(take_profit),
            "take_profit_text": fmt_number(take_profit, places=8),
            "rationale": str(rationale or "")[:400],
        }
        if order["side"] not in {"BUY", "SELL"} or order["quantity"] <= 0:
            return GuiAgentResult(
                ok=False, status="invalid_order",
                reason="side must be BUY/SELL and quantity must be positive",
            )
        submitted = False
        confirmed = False
        paper_verified = False
        blocked_submits = 0
        parse_errors = 0
        last_ui: dict[str, Any] = {}
        last_reason = ""
        try:
            for step in range(1, self.max_steps + 1):
                if time.monotonic() - started > self.timeout_s:
                    last_reason = f"GUI loop timed out after {self.timeout_s:.0f}s"
                    break
                capture = self._capture(step)
                if capture is None:
                    last_reason = "TradingView window/capture unavailable"
                    break
                if capture.get("path"):
                    screens.append(str(capture["path"]))
                paper_check = (
                    self._paper_checker(capture["image"])
                    if self._paper_checker is not None
                    else self._paper_verifier.check(capture["image"])
                )
                if paper_check.get("ok"):
                    paper_verified = True
                try:
                    observation = self._ask_action(
                        order=order,
                        step=step,
                        submitted=submitted,
                        history=steps,
                        capture=capture,
                        paper_check=paper_check,
                    )
                    parse_errors = 0
                except Exception as exc:
                    parse_errors += 1
                    last_reason = f"Muse GUI response invalid: {type(exc).__name__}: {exc}"
                    self._log(last_reason, level="WARN", nxt=META)
                    if parse_errors >= 3:
                        break
                    time.sleep(0.5)
                    continue
                raw_action = str(observation.get("action") or "").strip().lower()
                action: dict[str, Any] = {"action": raw_action}
                for key in (
                    "x", "y", "text", "key", "keys", "amount", "seconds",
                    "reason", "thought",
                ):
                    if key in observation:
                        action[key] = observation[key]
                step_record: dict[str, Any] = {
                    "step": step,
                    "action": raw_action,
                    "observation": str(observation.get("observation") or "")[:500],
                    "ui_state": str(observation.get("ui_state") or ""),
                    "paper_trading_visible": as_bool(
                        observation.get("paper_trading_visible")
                    ),
                    "symbol": observation.get("symbol"),
                    "selected_side": observation.get("selected_side"),
                    "order_type": observation.get("order_type"),
                    "units_value": observation.get("units_value"),
                    "size_value": observation.get("size_value"),
                    "size_mode": observation.get("size_mode"),
                    "take_profit_enabled": as_bool(
                        observation.get("take_profit_enabled")
                    ),
                    "take_profit_value": observation.get("take_profit_value"),
                    "stop_loss_enabled": as_bool(
                        observation.get("stop_loss_enabled")
                    ),
                    "stop_loss_value": observation.get("stop_loss_value"),
                    "submit_text": observation.get("submit_text"),
                    "confidence": as_float(observation.get("confidence")),
                    "paper_template": paper_check,
                    "screen": str(capture.get("path") or ""),
                    "requested": {
                        key: action.get(key)
                        for key in ("x", "y", "text", "key", "keys", "amount", "seconds")
                        if action.get(key) is not None
                    },
                }
                last_ui = observation

                if raw_action not in ALLOWED_ACTIONS:
                    step_record["result"] = f"blocked: unknown action {raw_action!r}"
                    steps.append(step_record)
                    self._log(step_record["result"], level="WARN", nxt=TRADING)
                    continue
                if raw_action == "abort":
                    last_reason = str(
                        observation.get("reason")
                        or observation.get("observation")
                        or "Muse aborted the GUI task"
                    )[:500]
                    step_record["result"] = f"aborted: {last_reason}"
                    steps.append(step_record)
                    break
                if raw_action == "submit" and (submitted or not allow_submit):
                    step_record["result"] = (
                        "blocked: submit already used"
                        if submitted
                        else "blocked: dry-run (submit disabled)"
                    )
                    steps.append(step_record)
                    if not allow_submit:
                        return GuiAgentResult(
                            ok=False, status="dry_run_ready", ready=True,
                            reason="ticket filled; submit disabled for dry-run",
                            submitted=False, confirmed=False,
                            paper_verified=paper_verified,
                            steps=steps, screens=screens, ui=last_ui,
                            elapsed_s=round(time.monotonic() - started, 2),
                        )
                    continue
                if raw_action == "done" and not submitted:
                    # Accept a pre-existing matching position, otherwise the
                    # agent must actually submit the order.
                    ok, reason, confirm = self._verify_confirmation(
                        order=order, capture=capture
                    )
                    if ok:
                        confirmed = True
                        paper_verified = True
                        last_ui = {**last_ui, "confirmation": confirm}
                        step_record["result"] = "done: matching position already visible"
                        steps.append(step_record)
                        break
                    step_record["result"] = f"blocked done: {reason}"
                    steps.append(step_record)
                    continue
                if raw_action == "submit":
                    if not allow_submit:
                        step_record["result"] = "blocked: dry-run (submit disabled)"
                        steps.append(step_record)
                        return GuiAgentResult(
                            ok=False, status="dry_run_ready", ready=True,
                            reason="ticket filled; submit disabled for dry-run",
                            submitted=False, confirmed=False,
                            paper_verified=paper_verified,
                            steps=steps, screens=screens, ui=last_ui,
                            elapsed_s=round(time.monotonic() - started, 2),
                        )
                    # Park the agent pointer away from the submit button and
                    # the paper label, then take a clean verification frame.
                    fresh = self._recapture_neutral(step, capture)
                    if fresh is not None:
                        capture = fresh
                        if capture.get("path"):
                            screens.append(str(capture["path"]))
                        step_record["screen"] = str(capture.get("path") or "")
                        paper_check = (
                            self._paper_checker(capture["image"])
                            if self._paper_checker is not None
                            else self._paper_verifier.check(capture["image"])
                        )
                        step_record["paper_template"] = paper_check
                        if paper_check.get("ok"):
                            paper_verified = True
                    # Guard 1: Muse's own observation.
                    guard_errors: list[str] = []
                    if not as_bool(observation.get("paper_trading_visible")):
                        guard_errors.append("Muse does not see Paper Trading")
                    if not paper_check.get("ok"):
                        guard_errors.append(
                            f"Paper Trading template not found (score {paper_check.get('score')})"
                        )
                    if not as_bool(observation.get("ready_to_submit")):
                        guard_errors.append("Muse did not mark ready_to_submit")
                    confidence = as_float(observation.get("confidence")) or 0.0
                    if confidence < 0.60:
                        guard_errors.append(f"Muse confidence {confidence:.2f} < 0.60")
                    if str(observation.get("selected_side") or "").upper() != order["side"]:
                        guard_errors.append(
                            f"visible side {observation.get('selected_side')!r} != {order['side']}"
                        )
                    if str(observation.get("order_type") or "").upper() != "MARKET":
                        guard_errors.append(
                            f"visible order type {observation.get('order_type')!r} != MARKET"
                        )
                    if not close_enough(
                        as_float(observation.get("units_value")),
                        order["quantity"], rel=0.01,
                    ):
                        guard_errors.append(
                            f"visible units {observation.get('units_value')!r} "
                            f"!= {order['quantity_text']}"
                        )
                    # Guard 2: independent Muse verification.
                    if not guard_errors:
                        ok, reason, verify_data = self._verify_submit(
                            order=order, capture=capture
                        )
                        last_ui = {**last_ui, "submit_verification": verify_data}
                        if not ok:
                            guard_errors.append(reason)
                    if guard_errors:
                        blocked_submits += 1
                        step_record["result"] = "submit blocked: " + "; ".join(guard_errors)
                        steps.append(step_record)
                        self._log(
                            f"GUI submit blocked ({blocked_submits}): "
                            + "; ".join(guard_errors),
                            level="WARN",
                            nxt=TRADING,
                        )
                        if blocked_submits >= 2:
                            last_reason = "submit blocked twice: " + "; ".join(guard_errors)
                            break
                        time.sleep(0.6)
                        continue
                    # Both guards passed: click the paper submit button.
                    result = self._execute_action(
                        action=action, capture=capture, order=order
                    )
                    submitted = bool(result.get("ok"))
                    step_record["result"] = (
                        "submitted" if submitted else f"submit click failed: {result}"
                    )
                    steps.append(step_record)
                    self._log(
                        "Paper submit clicked"
                        if submitted
                        else "Paper submit click failed",
                        level="INFO" if submitted else "WARN",
                        nxt=TRADING,
                    )
                    time.sleep(1.2)
                    continue
                if raw_action == "done":
                    # Post-submit: independent confirmation of the position.
                    ok, reason, confirm = self._verify_confirmation(
                        order=order, capture=capture
                    )
                    last_ui = {**last_ui, "confirmation": confirm}
                    if ok:
                        confirmed = True
                        paper_verified = True
                        step_record["result"] = "done: paper position confirmed"
                        steps.append(step_record)
                        break
                    step_record["result"] = f"done blocked: {reason}"
                    steps.append(step_record)
                    self._log(f"GUI confirmation blocked: {reason}", level="WARN", nxt=TRADING)
                    continue
                # Normal action: validate and execute.
                if raw_action == "click":
                    if _norm_coord(action.get("x"), capture["image"].size[0]) is None or _norm_coord(
                        action.get("y"), capture["image"].size[1]
                    ) is None:
                        step_record["result"] = "blocked: invalid click coordinates"
                        steps.append(step_record)
                        continue
                if raw_action == "scroll":
                    if _norm_coord(action.get("x"), capture["image"].size[0]) is None or _norm_coord(
                        action.get("y"), capture["image"].size[1]
                    ) is None:
                        step_record["result"] = "blocked: invalid scroll coordinates"
                        steps.append(step_record)
                        continue
                result = self._execute_action(
                    action=action, capture=capture, order=order
                )
                step_record["result"] = (
                    "ok" if result.get("ok") else f"failed: {result.get('error') or result}"
                )
                step_record["execution"] = {
                    key: value for key, value in result.items()
                    if key in {"x", "y", "text", "key", "keys", "amount", "seconds", "normalized"}
                }
                steps.append(step_record)
                self._log(
                    f"GUI step {step}: {raw_action} -> "
                    f"{'ok' if result.get('ok') else 'failed'}",
                    level="INFO" if result.get("ok") else "WARN",
                    nxt=TRADING,
                )
                time.sleep(0.45)
        except Exception as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
            self._log(f"GUI loop error: {last_reason}", level="ERROR", nxt=TRADING)
        elapsed = round(time.monotonic() - started, 2)
        fill_price = as_float(last_ui.get("price_value")) or order["entry"]
        if fill_price <= 0 or not (
            0.90 * order["entry"] <= fill_price <= 1.10 * order["entry"]
        ):
            fill_price = order["entry"]
        if confirmed:
            reference = "TV-PAPER-" + time.strftime("%Y%m%d-%H%M%S")
            return GuiAgentResult(
                ok=True, status="confirmed", submitted=submitted, confirmed=True,
                paper_verified=paper_verified, ready=True, reference=reference,
                fill_price=fill_price, steps=steps, screens=screens,
                ui=last_ui, elapsed_s=elapsed,
            )
        if submitted:
            return GuiAgentResult(
                ok=False, status="unconfirmed", submitted=True, confirmed=False,
                paper_verified=paper_verified, reason=last_reason
                or "order was clicked but no paper position/order could be verified",
                fill_price=fill_price, steps=steps, screens=screens,
                ui=last_ui, elapsed_s=elapsed,
            )
        return GuiAgentResult(
            ok=False, status="failed" if last_reason else "exhausted",
            submitted=False, confirmed=False, paper_verified=paper_verified,
            reason=last_reason or "GUI loop ended without a confirmed paper order",
            steps=steps, screens=screens, ui=last_ui, elapsed_s=elapsed,
        )
