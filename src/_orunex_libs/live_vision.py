"""Screen-only live vision loop for Orunex.

The loop captures the screen at a low rate, measures change locally, and emits
only meaningful frame changes.  It deliberately keeps the LLM out of the
capture thread: a brain/analyzer can be attached later through
``LiveVisionSession.set_analyzer`` without changing the button or the capture
path.

Meta AI adapter
---------------
``MetaVisionProvider`` sends one screen frame to the Meta Model API's
OpenAI-compatible chat endpoint.  Credentials and optional overrides are read
from:

  * ``META_API_KEY``, ``MODEL_API_KEY`` or ``META_AI_API_KEY``
  * ``META_API_BASE``, ``META_AI_ENDPOINT`` or ``META_API_ENDPOINT``
  * ``META_MODEL`` or ``META_AI_VISION_MODEL``

The same keys may also be read from ``orunex_config.json``.  The API key is
never stored in this module or in the public repository.
"""

from __future__ import annotations

import base64
import io
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from PIL import Image, ImageChops, ImageStat

try:
    import mss
except Exception:  # pragma: no cover - optional runtime dependency
    mss = None


@dataclass
class LiveVisionFrame:
    """A single screen frame kept in memory for the vision brain."""

    image: Any
    captured_at: float
    monitor: int = 1
    change_score: float = 0.0

    def png_bytes(self) -> bytes:
        buffer = io.BytesIO()
        self.image.save(buffer, format="PNG")
        return buffer.getvalue()

    def data_url(self) -> str:
        encoded = base64.b64encode(self.png_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"


class LiveVisionNotConfigured(RuntimeError):
    """Raised when a vision brain is requested without a usable adapter."""


def _config_value(key: str) -> str:
    try:
        from _orunex_libs import config_manager

        value = config_manager.get_val(key)
        return value if isinstance(value, str) else ""
    except Exception:
        return ""


def _chat_endpoint(value: str) -> str:
    endpoint = (value or "").strip()
    if not endpoint:
        return "https://api.meta.ai/v1/chat/completions"
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    return endpoint + "/chat/completions"


class MetaVisionProvider:
    """Meta Model API adapter for screen frames.

    The endpoint is OpenAI-compatible and accepts a PNG frame as a data URL.
    The key is read from the environment or the existing local config file; it
    is never written into this module or the repository.
    """

    transport_ready = True
    default_endpoint = "https://api.meta.ai/v1/chat/completions"
    default_model = "muse-spark-1.3"

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = (
            api_key
            or os.environ.get("META_API_KEY")
            or os.environ.get("MODEL_API_KEY")
            or os.environ.get("META_AI_API_KEY")
            or _config_value("meta_api_key")
            or ""
        ).strip()
        self.endpoint = _chat_endpoint(
            endpoint
            or os.environ.get("META_AI_ENDPOINT")
            or os.environ.get("META_API_ENDPOINT")
            or os.environ.get("META_API_BASE")
            or _config_value("meta_api_endpoint")
            or self.default_endpoint
        )
        self.model = (
            model
            or os.environ.get("META_AI_VISION_MODEL")
            or os.environ.get("META_MODEL")
            or _config_value("meta_vision_model")
            or self.default_model
        ).strip()
        self.timeout = 120.0
        try:
            self.timeout = float(os.environ.get("META_API_TIMEOUT", "120"))
        except (TypeError, ValueError):
            pass
        self.last_error = ""

    @property
    def configured(self) -> bool:
        """True when the credential and transport settings are present."""
        return bool(self.api_key and self.endpoint and self.model)

    @property
    def can_analyze(self) -> bool:
        return bool(self.transport_ready and self.configured)

    def analyze(
        self,
        frame: LiveVisionFrame,
        prompt: str = (
            "Describe what is happening on this screen. Focus on the active "
            "application, visible errors, and anything the user may need help with."
        ),
    ) -> Any:
        """Send one screen frame to Meta Model API and return its text."""
        if not self.configured:
            raise LiveVisionNotConfigured(
                "Meta AI vision is not configured. Set META_API_KEY."
            )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": frame.data_url()},
                        },
                    ],
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.2,
            "reasoning_effort": os.environ.get(
                "META_VISION_REASONING_EFFORT", "low"
            ),
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            import requests

            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            if response.status_code != 200:
                message = ""
                try:
                    body = response.json()
                    error = body.get("error") if isinstance(body, dict) else None
                    if isinstance(error, dict):
                        message = str(
                            error.get("message") or error.get("type") or ""
                        )
                except Exception:
                    pass
                if not message:
                    message = response.text.strip()[:300]
                raise RuntimeError(
                    f"Meta vision HTTP {response.status_code}: {message or 'request failed'}"
                )

            data = response.json()
            choices = data.get("choices") or []
            message = (choices[0].get("message") or {}) if choices else {}
            content = message.get("content")
            if isinstance(content, list):
                content = "\n".join(
                    str(block.get("text", "")).strip()
                    for block in content
                    if isinstance(block, dict) and block.get("text")
                ).strip()
            if not isinstance(content, str) or not content.strip():
                finish = (choices[0].get("finish_reason") or "") if choices else ""
                raise RuntimeError(
                    "Meta vision returned no final content"
                    + (f" (finish_reason={finish})." if finish else ".")
                )
            return content.strip()
        except LiveVisionNotConfigured:
            raise
        except Exception as exc:
            self.last_error = str(exc)
            raise RuntimeError(f"Meta vision analysis failed: {exc}") from exc


class LiveVisionSession:
    """Capture and change-detection loop for screen-only live vision.

    The session is UI-agnostic.  Callbacks may run on its worker thread, so a
    Tk caller should marshal them with ``after(0, ...)``.
    """

    def __init__(
        self,
        on_event: Optional[Callable[[LiveVisionFrame], None]] = None,
        on_status: Optional[Callable[[str, str], None]] = None,
        analyzer: Optional[Callable[[LiveVisionFrame], Any]] = None,
        on_analysis: Optional[Callable[[Any], None]] = None,
        interval: float = 1.5,
        monitor: int = 1,
        change_threshold: float = 4.5,
        change_cooldown: float = 2.0,
        skip_own_window: bool = True,
    ):
        self.on_event = on_event
        self.on_status = on_status
        self.analyzer = analyzer
        self.on_analysis = on_analysis
        self.interval = max(0.5, float(interval))
        self.monitor = max(1, int(monitor))
        self.change_threshold = max(0.1, float(change_threshold))
        self.change_cooldown = max(0.0, float(change_cooldown))
        self.skip_own_window = bool(skip_own_window)

        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event: Optional[threading.Event] = None
        self._lock = threading.Lock()
        self._last_small = None
        self._last_frame: Optional[LiveVisionFrame] = None
        self._last_event_at = 0.0
        self._last_error = ""

    @property
    def active(self) -> bool:
        return self._active

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def last_frame(self) -> Optional[LiveVisionFrame]:
        with self._lock:
            return self._last_frame

    def set_analyzer(
        self,
        analyzer: Optional[Callable[[LiveVisionFrame], Any]],
        on_analysis: Optional[Callable[[Any], None]] = None,
    ):
        """Attach the future brain without touching the capture loop."""
        self.analyzer = analyzer
        if on_analysis is not None:
            self.on_analysis = on_analysis

    def start(self):
        if self._active:
            return
        self._active = True
        stop_event = threading.Event()
        self._stop_event = stop_event
        self._thread = threading.Thread(
            target=self._run,
            args=(stop_event,),
            name="orunex-live-vision",
            daemon=True,
        )
        self._thread.start()

    def stop(self, wait: bool = False):
        was_active = self._active
        self._active = False
        if self._stop_event is not None:
            self._stop_event.set()
        thread = self._thread
        if wait and thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        if was_active:
            self._emit_status("Live vision off.", "info")

    def _run(self, stop_event: threading.Event):
        if mss is None:
            self._last_error = "mss is not installed"
            self._active = False
            self._emit_status(
                "Live vision unavailable: the mss package is not installed.",
                "error",
            )
            return

        while not stop_event.is_set():
            try:
                if self.skip_own_window and self._foreground_is_self():
                    stop_event.wait(0.5)
                    continue

                frame = self._capture_frame()
                small = frame.image.convert("L").resize((96, 54))
                with self._lock:
                    previous = self._last_small
                score = 0.0
                if previous is not None and previous.size == small.size:
                    score = float(
                        ImageStat.Stat(
                            ImageChops.difference(previous, small)
                        ).mean[0]
                    )

                frame.change_score = score
                with self._lock:
                    self._last_small = small
                    self._last_frame = frame

                now = time.monotonic()
                changed = score >= self.change_threshold
                cooled = (now - self._last_event_at) >= self.change_cooldown
                if changed and cooled:
                    self._last_event_at = now
                    self._emit_event(frame)
                    self._analyze(frame)
            except Exception as exc:
                self._last_error = str(exc)
                self._emit_status(f"Live vision error: {exc}", "error")
                stop_event.wait(1.5)
                continue

            stop_event.wait(self.interval)

    def _capture_frame(self) -> LiveVisionFrame:
        with mss.mss() as sct:
            monitors = sct.monitors
            if len(monitors) <= 1:
                raise RuntimeError("No screen monitor was detected.")
            index = min(max(1, self.monitor), len(monitors) - 1)
            shot = sct.grab(monitors[index])
            image = Image.frombytes(
                "RGB", shot.size, shot.bgra, "raw", "BGRX"
            )
        return LiveVisionFrame(
            image=image,
            captured_at=time.time(),
            monitor=index,
        )

    def _analyze(self, frame: LiveVisionFrame):
        analyzer = self.analyzer
        if analyzer is None:
            return
        try:
            result = analyzer(frame)
            if result is not None and self.on_analysis is not None:
                self.on_analysis(result)
        except LiveVisionNotConfigured as exc:
            self._last_error = str(exc)
        except Exception as exc:
            self._last_error = str(exc)
            self._emit_status(f"Live vision analysis error: {exc}", "error")

    def _emit_event(self, frame: LiveVisionFrame):
        callback = self.on_event
        if callback is None:
            return
        try:
            callback(frame)
        except Exception as exc:
            self._last_error = str(exc)

    def _emit_status(self, message: str, level: str = "info"):
        callback = self.on_status
        if callback is None:
            return
        try:
            callback(message, level)
        except Exception:
            pass

    @staticmethod
    def _foreground_is_self() -> bool:
        """Avoid observing Orunex itself while its own window is focused."""
        if os.name != "nt":
            return False
        try:
            import ctypes

            user32 = ctypes.windll.user32
            foreground = user32.GetForegroundWindow()
            if not foreground:
                return False
            owner = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(foreground, ctypes.byref(owner))
            return owner.value == os.getpid()
        except Exception:
            return False
