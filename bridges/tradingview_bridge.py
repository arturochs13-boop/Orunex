"""TradingView Desktop bridge — chart context for paper-trading tasks.

The bridge only opens/focuses the installed TradingView application and can
capture its chart window for Muse Spark.  It deliberately does NOT click a
broker order button and has no live-trading capability: executable orders are
created by the paper-trading engine in :mod:`tasks.trading_task` after Muse
decides and the deterministic risk gate accepts them.
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from core.config import Settings, get_settings
from core.events import TRADINGVIEW, EventBus

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_CRYPTO_QUOTES = ("USDT", "USDC", "USD", "BTC", "ETH", "EUR")
_SYMBOL_TITLE_RE = re.compile(r"\b([A-Z]{2,12}(?:USDT|USDC|USD|BTC|ETH))\b")


def _symbol_in_title(title: str) -> str:
    """Return the crypto symbol shown in a TradingView window title."""
    match = _SYMBOL_TITLE_RE.search(str(title or "").upper())
    return match.group(1) if match else ""


def normalize_symbol(symbol: str) -> tuple[str, str]:
    """Return ``(display_symbol, tradingview_symbol)`` for an alert symbol."""
    raw = str(symbol or "BTCUSDT").strip().upper().replace(" ", "")
    raw = raw.replace("/", "")
    if raw.endswith(".P"):
        raw = raw[:-2]
    if ":" in raw:
        exchange, ticker = raw.split(":", 1)
        return ticker, f"{exchange}:{ticker}"
    if any(raw.endswith(quote) and len(raw) > len(quote) for quote in _CRYPTO_QUOTES):
        return raw, f"BINANCE:{raw}"
    return raw, raw


def interval_for_timeframe(timeframe: object) -> str:
    raw = str(timeframe or "1h").strip()
    if raw.upper() == "1M":
        return "M"  # monthly; plain "1m" below means one minute
    value = raw.lower().replace(" ", "")
    mapping = {
        "1": "1", "1m": "1", "3": "3", "3m": "3", "5": "5", "5m": "5",
        "15": "15", "15m": "15", "30": "30", "30m": "30", "45": "45",
        "60": "60", "1h": "60", "60m": "60", "2h": "120", "120": "120",
        "4h": "240", "240": "240", "1d": "D", "d": "D", "daily": "D",
        "1w": "W", "w": "W", "weekly": "W", "monthly": "M",
    }
    return mapping.get(value, "60")


@dataclass
class TradingViewStatus:
    installed: bool = False
    running: bool = False
    app_id: str = ""
    exe: str = ""
    window_title: str = ""
    last_symbol: str = ""
    last_error: str = ""
    last_opened_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self))


@dataclass
class _Window:
    hwnd: int
    title: str
    pid: int
    exe: str


class TradingViewBridge:
    """Launch/focus TradingView Desktop and open a symbol chart."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        bus: Optional[EventBus] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bus = bus
        self._lock = threading.RLock()
        self._app_id = ""
        self._exe = ""
        self._last_symbol = ""
        self._last_error = ""
        self._last_opened_at = 0.0
        self._status_cache: Optional[TradingViewStatus] = None
        self._status_at = 0.0
        self._op_lock = threading.RLock()
        self._app_id_checked_at = 0.0
        self._exe_checked_at = 0.0

    # ------------------------------------------------------------------- util
    def _log(self, message: str, *, level: str = "INFO", next_stage: str = "") -> None:
        if self.bus:
            self.bus.log(TRADINGVIEW, message, level=level, next_stage=next_stage)

    # -------------------------------------------------------------- discovery
    def find_app_id(self) -> str:
        with self._lock:
            if self._app_id:
                return self._app_id
            # Negative discovery is cached too: status polling must not keep
            # spawning PowerShell on machines without TradingView.
            if time.monotonic() - self._app_id_checked_at < 60.0:
                return ""
            self._app_id_checked_at = time.monotonic()
            configured = (self.settings.tradingview_app_id or "").strip()
            if configured:
                self._app_id = configured
                return configured
            if os.name != "nt":
                return ""
            local = os.environ.get("LOCALAPPDATA", "")
            packages = Path(local) / "Packages" if local else None
            if packages and packages.exists():
                matches = sorted(packages.glob("TradingView.Desktop_*"))
                if matches:
                    self._app_id = f"{matches[0].name}!TradingView.Desktop"
                    return self._app_id
            # Fallback: ask Windows for the Start-app registration.
            try:
                result = subprocess.run(
                    [
                        "powershell", "-NoProfile", "-Command",
                        "(Get-StartApps | Where-Object { $_.Name -eq 'TradingView' } "
                        "| Select-Object -First 1 -ExpandProperty AppID)",
                    ],
                    capture_output=True, text=True, timeout=12,
                    creationflags=_NO_WINDOW,
                )
                value = (result.stdout or "").strip().splitlines()
                if value and value[0].strip():
                    self._app_id = value[0].strip()
            except (OSError, subprocess.SubprocessError):
                pass
            return self._app_id

    def find_exe(self) -> str:
        with self._lock:
            if self._exe:
                return self._exe
            if time.monotonic() - self._exe_checked_at < 60.0:
                return ""
            self._exe_checked_at = time.monotonic()
            configured = (self.settings.tradingview_exe or "").strip()
            if configured and Path(configured).exists():
                self._exe = configured
                return configured
            if os.name == "nt":
                try:
                    result = subprocess.run(
                        [
                            "powershell", "-NoProfile", "-Command",
                            "$p = Get-AppxPackage -Name TradingView.Desktop "
                            "| Select-Object -First 1; if ($p) { Join-Path "
                            "$p.InstallLocation 'TradingView.exe' }",
                        ],
                        capture_output=True, text=True, timeout=12,
                        creationflags=_NO_WINDOW,
                    )
                    value = (result.stdout or "").strip()
                    if value and Path(value).exists():
                        self._exe = value
                except (OSError, subprocess.SubprocessError):
                    pass
            return self._exe

    @property
    def installed(self) -> bool:
        return bool(self.find_app_id() or self.find_exe())

    # ---------------------------------------------------------------- windows
    def _windows(self) -> list[_Window]:
        if os.name != "nt":
            return []
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        found: list[_Window] = []
        enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            exe = self._process_exe(int(pid.value))
            if exe.lower() == "tradingview.exe":
                found.append(_Window(int(hwnd), title, int(pid.value), exe))
            return True

        user32.EnumWindows(enum_proc_type(callback), 0)
        # Main chart windows carry a symbol title; prefer those over helpers.
        found.sort(key=lambda w: (":" in w.title or "/" in w.title, len(w.title)), reverse=True)
        return found

    @staticmethod
    def _process_exe(pid: int) -> str:
        if os.name != "nt" or pid <= 0:
            return ""
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        process_query_limited_information = 0x1000
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return ""
        try:
            size = ctypes.c_ulong(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return Path(buffer.value).name
        finally:
            kernel32.CloseHandle(handle)
        return ""

    def is_running(self) -> bool:
        if self._windows():
            return True
        if os.name != "nt":
            return False
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq TradingView.exe", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=8, creationflags=_NO_WINDOW,
            )
            return "TradingView.exe" in (result.stdout or "")
        except (OSError, subprocess.SubprocessError):
            return False

    def window_title(self) -> str:
        windows = self._windows()
        return windows[0].title if windows else ""

    def focus(self) -> bool:
        windows = self._windows()
        if not windows or os.name != "nt":
            return False
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = windows[0].hwnd
        try:
            if int(user32.GetForegroundWindow()) == hwnd:
                return True
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.15)
            return int(user32.GetForegroundWindow()) == hwnd
        except Exception:
            return False

    # ---------------------------------------------------------------- opening
    def launch(self, *, timeout: Optional[float] = None) -> bool:
        with self._op_lock:
            return self._launch_unlocked(timeout=timeout)

    def _launch_unlocked(self, *, timeout: Optional[float] = None) -> bool:
        timeout = float(timeout or self.settings.tradingview_launch_timeout_s)
        if self.is_running():
            self.focus()
            return True
        exe = self.find_exe()
        app_id = self.find_app_id()
        try:
            if exe:
                subprocess.Popen([exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif app_id and os.name == "nt":
                subprocess.Popen(
                    ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                self._last_error = "TradingView Desktop not found."
                self._log(self._last_error, level="ERROR")
                return False
        except OSError as exc:
            self._last_error = f"Could not launch TradingView: {exc}"
            self._log(self._last_error, level="ERROR")
            return False
        self._log("TradingView Desktop launching…", next_stage="Meta API")
        deadline = time.monotonic() + max(1.0, timeout)
        while time.monotonic() < deadline:
            if self.is_running():
                self.focus()
                self._log("TradingView Desktop ready", next_stage="Meta API")
                return True
            time.sleep(0.35)
        self._last_error = "TradingView did not open before the timeout."
        self._log(self._last_error, level="WARN")
        return self.is_running()

    def chart_url(self, symbol: str, timeframe: str = "1h") -> str:
        _display, tv_symbol = normalize_symbol(symbol)
        base = self.settings.tradingview_chart_base_url.rstrip("/") + "/"
        query = urllib.parse.urlencode(
            {"symbol": tv_symbol, "interval": interval_for_timeframe(timeframe)}
        )
        return f"{base}?{query}"

    def open_chart(
        self,
        symbol: str,
        timeframe: str = "1h",
        *,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Open ``symbol`` in TradingView Desktop; return a status dictionary."""
        with self._op_lock:
            return self._open_chart_unlocked(symbol, timeframe, timeout=timeout)

    def _open_chart_unlocked(
        self,
        symbol: str,
        timeframe: str = "1h",
        *,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        display, tv_symbol = normalize_symbol(symbol)
        if not self._launch_unlocked(timeout=timeout):
            return {**self.status().to_dict(), "symbol": tv_symbol,
                    "opened": False, "elapsed_s": round(time.monotonic() - started, 2)}
        # Electron restores its workspace asynchronously.  Sending the chart
        # URL while the window still says "TradingView" made the link get
        # ignored, leaving the home screen ("New tab") for Muse to analyse.
        ready_deadline = time.monotonic() + 6.0
        while time.monotonic() < ready_deadline:
            title = self.window_title().strip()
            if title and (
                title.lower() == "new tab" or _symbol_in_title(title)
            ):
                break
            time.sleep(0.35)

        # Reuse the chart that is already visible when it matches the
        # requested symbol.  Sending the URL unconditionally makes Electron
        # open a duplicate tab; a fresh tab restores the "Account Manager"
        # panel instead of the user's Paper Trading panel, which would make
        # the paper-only GUI guard abort.
        visible_now = _symbol_in_title(self.window_title())
        if visible_now and visible_now.upper() == display.upper():
            self.focus()
            with self._lock:
                self._last_symbol = tv_symbol
                self._last_opened_at = time.time()
                self._last_error = ""
            self._log(
                f"Chart already open: {tv_symbol} ({timeframe}); reusing the "
                "visible TradingView tab",
                next_stage="Meta API",
            )
            self._status_at = 0.0
            status = {
                **self.status().to_dict(),
                "symbol": tv_symbol,
                "url": self.chart_url(symbol, timeframe),
                "opened": True,
                "title_confirmed": True,
                "visible_symbol": visible_now,
                "reused": True,
                "elapsed_s": round(time.monotonic() - started, 2),
            }
            status["window_title"] = (
                self.window_title() or status.get("window_title", "")
            )
            return status

        url = self.chart_url(symbol, timeframe)
        try:
            exe = self.find_exe()
            if os.name == "nt" and exe:
                # Hand the URL straight to the native executable.  Electron's
                # single-instance lock forwards it to the running app, so the
                # link can never fall through to the default browser (Chrome).
                subprocess.Popen(
                    [exe, url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif os.name == "nt":
                # Never hand a chart URL to the default browser.  If the
                # executable cannot be discovered, report it and let the
                # caller decide; Chrome is not an acceptable fallback.
                self._last_error = (
                    "TradingView.exe not found; refusing to open the chart in "
                    "the default browser. Set TRADINGVIEW_EXE in .env."
                )
                self._log(self._last_error, level="ERROR")
                return {**self.status().to_dict(), "symbol": tv_symbol,
                        "opened": False,
                        "elapsed_s": round(time.monotonic() - started, 2)}
            else:
                subprocess.Popen(["xdg-open", url])
        except OSError as exc:
            self._last_error = f"Could not open TradingView chart: {exc}"
            self._log(self._last_error, level="WARN")
            return {**self.status().to_dict(), "symbol": tv_symbol,
                    "opened": False, "elapsed_s": round(time.monotonic() - started, 2)}
        # Wait for *any* chart title, not only the requested symbol:
        # TradingView may restore a different chart, and the task adopts the
        # visible symbol when the user did not name one.  The old 6 s window
        # returned while the window still said "New tab", so the screenshot
        # contained the TradingView home screen and Muse rejected the order.
        deadline = time.monotonic() + 15.0
        opened = False
        visible_title = ""
        visible_symbol = ""
        while time.monotonic() < deadline:
            visible_title = self.window_title()
            visible_symbol = _symbol_in_title(visible_title)
            if visible_symbol:
                opened = True
                break
            time.sleep(0.4)
        requested_in_title = bool(
            visible_title
            and (
                display.upper() in visible_title.upper()
                or tv_symbol.split(":")[-1].upper() in visible_title.upper()
            )
        )
        self.focus()
        with self._lock:
            self._last_symbol = tv_symbol
            self._last_opened_at = time.time()
            if not opened:
                self._last_error = "Chart link sent; symbol title not confirmed yet."
            elif not requested_in_title:
                self._last_error = (
                    f"Requested {tv_symbol}; visible chart is {visible_symbol}."
                )
        self._log(
            f"Chart open requested: {tv_symbol} ({timeframe})"
            + ("" if opened else " — still loading")
            + (
                f"; visible chart {visible_symbol}"
                if opened and not requested_in_title
                else ""
            ),
            next_stage="Meta API",
        )
        self._status_at = 0.0
        running = self.is_running()
        status = {
            **self.status().to_dict(), "symbol": tv_symbol, "url": url,
            # The link was delivered to a running TradingView window.  The
            # window title is only a weak confirmation in multi-tab layouts
            # (it can show another tab's symbol), so the chart capture +
            # Muse's reading of the chart header is the real verification.
            "opened": bool(opened or running),
            "title_confirmed": requested_in_title,
            "visible_symbol": visible_symbol,
            "elapsed_s": round(time.monotonic() - started, 2),
        }
        # The task uses this title to adopt the visible chart when the user
        # did not name a symbol.  Do not let the status cache hide it.
        status["window_title"] = visible_title or status.get("window_title", "")
        return status

    def _capture_print_window(self, hwnd: int):
        """Capture a window's own pixels even if another app covers it."""
        import win32gui
        import win32ui
        from PIL import Image

        hwnd_dc = 0
        mfc_dc = None
        save_dc = None
        bitmap = None
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width, height = right - left, bottom - top
            if width < 200 or height < 200:
                return None
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)
            # PW_RENDERFULLCONTENT (2) works for Electron/Chromium windows.
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            user32.PrintWindow.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint
            ]
            user32.PrintWindow.restype = ctypes.c_bool
            if not user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2):
                return None
            bits = bitmap.GetBitmapBits(True)
            return Image.frombuffer(
                "RGB", (width, height), bits, "raw", "BGRX", 0, 1
            ).copy()
        finally:
            if bitmap is not None:
                try:
                    win32gui.DeleteObject(bitmap.GetHandle())
                except Exception:
                    pass
            if save_dc is not None:
                try:
                    save_dc.DeleteDC()
                except Exception:
                    pass
            if mfc_dc is not None:
                try:
                    mfc_dc.DeleteDC()
                except Exception:
                    pass
            if hwnd_dc:
                try:
                    win32gui.ReleaseDC(hwnd, hwnd_dc)
                except Exception:
                    pass

    def capture_chart(self, symbol: str = "") -> Optional[bytes]:
        """Capture the TradingView window as PNG bytes (best effort)."""
        with self._op_lock:
            return self._capture_chart_unlocked(symbol)

    def _capture_chart_unlocked(self, symbol: str = "") -> Optional[bytes]:
        self.focus()
        time.sleep(0.25)
        windows = self._windows()
        if not windows or os.name != "nt":
            return None
        if symbol:
            display, tv_symbol = normalize_symbol(symbol)
            title = windows[0].title.upper()
            if display not in title and tv_symbol.split(":")[-1] not in title:
                # Multi-tab layouts title the window after a different tab.
                # Capture anyway: Muse reads the symbol from the chart
                # header itself and must HOLD if it does not match.
                self._last_error = (
                    f"Chart title {windows[0].title!r} may not match {tv_symbol}; "
                    "capturing for visual verification."
                )
                self._log(self._last_error, level="WARN")
        try:
            from PIL import Image, ImageGrab

            image = None
            try:
                image = self._capture_print_window(windows[0].hwnd)
            except Exception:
                image = None
            if image is None:
                user32 = ctypes.windll.user32  # type: ignore[attr-defined]
                rect = ctypes.create_string_buffer(16)
                if not user32.GetWindowRect(windows[0].hwnd, rect):
                    return None
                left, top, right, bottom = ctypes.cast(
                    rect, ctypes.POINTER(ctypes.c_long * 4)
                ).contents
                if right - left < 200 or bottom - top < 200:
                    return None
                # Raise the chart only for the fallback desktop grab.
                user32.SetWindowPos(windows[0].hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
                try:
                    time.sleep(0.2)
                    image = ImageGrab.grab(bbox=(left, top, right, bottom))
                finally:
                    user32.SetWindowPos(
                        windows[0].hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002
                    )
            # Muse should read market evidence, not the watchlist or the
            # TradingView paper-trading panel (which may show a different
            # account).  Crop to the chart pane before scaling.  The pane
            # spans roughly the left 56% and the top 63% of the window; the
            # previous 55% cut off the current price line and the newest
            # candles, which made Muse's directional confidence artificially
            # low.
            width, height = image.size
            if width >= 800 and height >= 500:
                image = image.crop(
                    (
                        int(width * 0.04),
                        int(height * 0.10),
                        int(width * 0.56),
                        int(height * 0.63),
                    )
                )
            if image.width > 1600:
                height = max(1, int(image.height * 1600 / image.width))
                image = image.resize((1600, height), Image.LANCZOS)
            output = BytesIO()
            image.save(output, format="PNG", optimize=True)
            data = output.getvalue()
            self._log(f"TradingView chart captured ({len(data) // 1024} KB)", next_stage="Meta API")
            return data
        except Exception as exc:
            self._last_error = f"Chart capture unavailable: {exc}"
            return None

    @staticmethod
    def _image_looks_ready(data: Optional[bytes]) -> bool:
        """Heuristic: a painted chart has contrast; a loading spinner does not."""
        if not data:
            return False
        try:
            from PIL import Image, ImageStat

            image = Image.open(BytesIO(data)).convert("L")
            image.thumbnail((320, 320))
            stat = ImageStat.Stat(image)
            mean, stddev = float(stat.mean[0]), float(stat.stddev[0])
            # Loading screens are near-white with almost no contrast.  A
            # painted chart (dark or light) has candles/text everywhere.
            return mean < 235.0 or stddev > 28.0
        except Exception:
            return True

    def open_and_capture(
        self,
        symbol: str,
        timeframe: str = "1h",
        *,
        capture: bool = True,
        settle_s: float = 3.0,
    ) -> tuple[dict[str, Any], Optional[bytes]]:
        """Open and capture one chart atomically (no symbol interleaving)."""
        with self._op_lock:
            status = self._open_chart_unlocked(symbol, timeframe)
            image: Optional[bytes] = None
            if capture and status.get("opened"):
                # A same-symbol timeframe change reuses the window title, so
                # the title check cannot tell the old tab from the new one.
                # Give the new tab a fixed paint window before the first grab.
                if settle_s > 0:
                    time.sleep(float(settle_s))
                # Candles/indicators paint after the window title does; a
                # half-loaded frame made Muse report zero confidence.  Require
                # both a symbol title and a painted image so the home screen
                # ("New tab") is never sent to Muse as if it were a chart.
                deadline = time.monotonic() + 10.0
                while True:
                    title = self.window_title()
                    image = self._capture_chart_unlocked(symbol)
                    if _symbol_in_title(title) and self._image_looks_ready(image):
                        break
                    if time.monotonic() >= deadline:
                        self._log(
                            "Chart still painting; capture may be incomplete",
                            level="WARN", next_stage="Meta API",
                        )
                        break
                    time.sleep(1.0)
            return status, image

    def warmup(self) -> dict[str, Any]:
        ready = self.launch()
        return {**self.status().to_dict(), "ready": ready}

    def status(self, *, force: bool = False) -> TradingViewStatus:
        now = time.monotonic()
        if (
            not force and self._status_cache is not None
            and now - self._status_at < 10.0
        ):
            return TradingViewStatus(**self._status_cache.to_dict())
        windows = self._windows()
        configured_exe = (self.settings.tradingview_exe or "").strip()
        status = TradingViewStatus(
            installed=self.installed,
            running=bool(windows) or self.is_running(),
            app_id=self.find_app_id(),
            # Do not run PowerShell discovery on the status hot path; the
            # executable is resolved lazily only when a launch is needed.
            exe=self._exe or (configured_exe if configured_exe and Path(configured_exe).exists() else ""),
            window_title=windows[0].title if windows else "",
            last_symbol=self._last_symbol,
            last_error=self._last_error,
            last_opened_at=self._last_opened_at,
        )
        self._status_cache = status
        self._status_at = now
        return status
