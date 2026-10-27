"""Simplex bridge listener — encrypted remote commands for the agent.

Reuses the exact WebSocket protocol of the production Orunex bridge:
the Simplex Chat CLI listens on ``ws://127.0.0.1:5227`` and accepts JSON
frames ``{"corrId": "...", "cmd": "@<contact> <text>"}``.  Incoming
``newChatItems`` events are normalised into :class:`RemoteCommand`.

The listener transports text only.  Routing/decision-making belongs to
Muse Spark in :class:`core.agent_brain.AgentBrain`.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.config import Settings, get_settings
from core.events import SIMPLEX, EventBus

try:
    import websocket  # type: ignore
    WS_AVAILABLE = True
except ImportError:
    websocket = None  # type: ignore
    WS_AVAILABLE = False


@dataclass
class RemoteCommand:
    text: str
    contact: str = ""
    received_at: float = field(default_factory=time.time)
    raw: dict[str, Any] = field(default_factory=dict)


class SimplexBridgeListener:
    """Reconnecting Simplex listener running on its own daemon thread."""

    def __init__(
        self,
        on_command: Optional[Callable[[RemoteCommand], None]] = None,
        settings: Optional[Settings] = None,
        bus: Optional[EventBus] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bus = bus
        self.on_command = on_command
        self.ws: Any = None
        self.connected = False
        self.contact = self.settings.simplex_contact
        self.last_error = ""
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._corr = 0
        self._corr_lock = threading.Lock()
        self._connected_at = 0.0
        self._outbox: "queue.SimpleQueue[str]" = queue.SimpleQueue()

    # ------------------------------------------------------------------- util
    def _log(self, message: str, *, level: str = "INFO", next_stage: str = "") -> None:
        if self.bus:
            self.bus.log(SIMPLEX, message, level=level, next_stage=next_stage)

    @property
    def available(self) -> bool:
        return WS_AVAILABLE

    def _next_corr(self) -> str:
        with self._corr_lock:
            self._corr += 1
            return str(self._corr)

    # -------------------------------------------------------------- lifecycle
    def start(self) -> bool:
        if not WS_AVAILABLE:
            self.last_error = "websocket-client not installed (pip install websocket-client)."
            self._log(self.last_error, level="ERROR")
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="SimplexBridgeListener", daemon=True
        )
        self._thread.start()
        self._log(f"Listener starting -> {self.settings.simplex_ws_url}", next_stage="MuseSpark Brain")
        return True

    def stop(self) -> None:
        self._stop.set()
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        self.connected = False
        self._log("Listener stopped")

    def _run_loop(self) -> None:
        backoff = 2.0
        while not self._stop.is_set():
            try:
                self.ws = websocket.WebSocketApp(
                    self.settings.simplex_ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self.ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
            self.connected = False
            if self._stop.is_set():
                break
            self._log(f"Reconnecting in {backoff:.0f}s…", level="WARN")
            self._stop.wait(backoff)
            backoff = min(backoff * 1.5, 30.0)

    # -------------------------------------------------------------- callbacks
    def _on_open(self, _ws: Any) -> None:
        self.connected = True
        self._connected_at = time.time()
        self.last_error = ""
        self._log("Connected to Simplex CLI (E2E channel ready)", next_stage="MuseSpark Brain")
        if self.bus:
            self.bus.status(SIMPLEX, "connected")
        try:
            self._send({"cmd": "/auto_accept on"})
        except Exception:
            pass
        queued: list[str] = []
        while True:
            try:
                queued.append(self._outbox.get_nowait())
            except queue.Empty:
                break
        for text in queued:  # send once; send_message re-queues only on failure
            self.send_message(text)

    def _on_close(self, _ws: Any, _code: Any, _msg: Any) -> None:
        self.connected = False
        if self.bus:
            self.bus.status(SIMPLEX, "disconnected")

    def _on_error(self, _ws: Any, error: Any) -> None:
        self.last_error = str(error)
        self._log(f"WebSocket error: {error}", level="WARN")

    def _on_message(self, _ws: Any, message: str) -> None:
        try:
            data = json.loads(message)
        except Exception:
            return
        resp = data.get("resp") if isinstance(data, dict) else None
        if not isinstance(resp, dict) or resp.get("type") != "newChatItems":
            return
        # Ignore history replayed right after connecting.
        if time.time() - self._connected_at < 5.0:
            return
        items = resp.get("chatItems") or []
        if not isinstance(items, list):
            return
        for item in items:
            try:
                chat_item = item.get("chatItem", {})
                content = chat_item.get("content", {})
                if content.get("type") == "sndMsgContent":
                    continue  # our own messages
                text = str(content.get("msgContent", {}).get("text") or "").strip()
                if not text:
                    continue
                contact = (
                    chat_item.get("chatInfo", {}).get("contact", {}).get("localDisplayName")
                    or self.contact
                    or ""
                )
                if contact:
                    self.contact = str(contact)
                command = RemoteCommand(text=text, contact=str(contact), raw=item)
                self._log(f"Remote command from {contact or 'contact'}: {text[:80]!r}",
                          next_stage="MuseSpark Brain")
                if self.on_command:
                    threading.Thread(
                        target=self._dispatch, args=(command,),
                        name="SimplexDispatch", daemon=True,
                    ).start()
            except Exception as exc:
                self._log(f"Dropped malformed chat item: {exc}", level="WARN")

    def _dispatch(self, command: RemoteCommand) -> None:
        try:
            if self.on_command:
                self.on_command(command)
        except Exception as exc:
            self._log(f"Command handler failed: {type(exc).__name__}: {exc}", level="ERROR")

    # ---------------------------------------------------------------- sending
    def _send(self, payload: dict[str, Any]) -> bool:
        if not self.ws or not self.connected:
            return False
        payload.setdefault("corrId", self._next_corr())
        try:
            self.ws.send(json.dumps(payload) + "\n")
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def send_message(self, text: str, contact: Optional[str] = None) -> bool:
        """Send a text notification back through the encrypted channel."""
        target = (contact or self.contact or self.settings.simplex_contact or "").strip()
        clean = str(text or "").strip()
        if not clean:
            return False
        if not self.connected or not target:
            self._outbox.put(clean)
            self._log("Message queued (no live contact yet)", level="WARN")
            return False
        ok = self._send({"cmd": f"@{target} {clean}"})
        self._log(f"Notification {'sent' if ok else 'FAILED'} -> {target}")
        return ok
