"""Desktop-wide ``Executing...`` indicator for Orunex.

Plain blue text with no background, rendered into a Win32 layered window
with per-pixel alpha (the same mechanism as the Live screen glow).  It is
topmost, click-through and absent from Alt+Tab, so it stays visible over
any application - TradingView included - while the agent is active, and it
animates on its own thread so the Tk event loop never blocks.
"""

from __future__ import annotations

import ctypes
import math
import os
import threading
import time
from ctypes import wintypes

try:
    import numpy as np
except Exception:  # pragma: no cover - optional desktop dependency
    np = None


WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_HIDEWINDOW = 0x0080
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
BI_RGB = 0
DIB_RGB_COLORS = 0

_TEXT = "Executing..."


class _RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", ctypes.c_ubyte),
        ("rgbGreen", ctypes.c_ubyte),
        ("rgbRed", ctypes.c_ubyte),
        ("rgbReserved", ctypes.c_ubyte),
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", _RGBQUAD * 1),
    ]


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


def _load_font(size: int):
    from PIL import ImageFont

    candidates = (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\seguisb.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
    )
    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                continue
    return ImageFont.load_default()


class ExecutingOverlay:
    """Owns one small layered window showing animated blue text."""

    def __init__(self, fps: int = 30):
        self.fps = max(15, min(45, int(fps)))
        self.width = 280
        self.height = 52
        self.x = 0
        self.y = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._last_error = ""
        self._hwnd = 0
        self._core_mask = None
        self._glow_mask = None

    @property
    def active(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if os.name != "nt" or np is None:
            return
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                if not self._stop_event.is_set():
                    return
                self._thread.join(timeout=0.45)
                if self._thread.is_alive():
                    return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run, name="OrunexExecutingOverlay", daemon=True
            )
            self._thread.start()

    def stop(self, wait: bool = False) -> None:
        self._stop_event.set()
        thread = self._thread
        if wait and thread and thread.is_alive():
            thread.join(timeout=0.9)
        if not thread or not thread.is_alive():
            self._thread = None

    def last_error(self) -> str:
        return self._last_error

    # ------------------------------------------------------------------ thread
    def _run(self) -> None:
        hwnd = mem_dc = screen_dc = bitmap = old_bitmap = 0
        bits = ctypes.c_void_p()
        start = time.perf_counter()
        try:
            self._prepare_masks()
            self._compute_position()
            hwnd, screen_dc, mem_dc, bitmap, old_bitmap, bits = self._create_window()
            self._hwnd = hwnd
            interval = 1.0 / self.fps
            next_frame = time.perf_counter()
            while not self._stop_event.is_set():
                elapsed = time.perf_counter() - start
                self._render_frame(bits, elapsed)
                self._update_window(hwnd, screen_dc, mem_dc)
                self._pump_messages()
                next_frame += interval
                delay = next_frame - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_frame = time.perf_counter()
            self._hide_window_now()
        except Exception as exc:
            self._last_error = str(exc)
            try:
                print(f"[EXECUTING OVERLAY] {exc}")
            except Exception:
                pass
        finally:
            try:
                if mem_dc and old_bitmap:
                    gdi32.SelectObject(mem_dc, old_bitmap)
            except Exception:
                pass
            try:
                if bitmap:
                    gdi32.DeleteObject(bitmap)
            except Exception:
                pass
            try:
                if mem_dc:
                    gdi32.DeleteDC(mem_dc)
            except Exception:
                pass
            try:
                if screen_dc:
                    user32.ReleaseDC(None, screen_dc)
            except Exception:
                pass
            try:
                if hwnd:
                    user32.DestroyWindow(hwnd)
            except Exception:
                pass
            self._hwnd = 0

    def _hide_window_now(self) -> None:
        if not self._hwnd:
            return
        try:
            user32.ShowWindow(self._hwnd, 0)
            user32.SetWindowPos(
                self._hwnd, 0, 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER
                | SWP_NOACTIVATE | SWP_HIDEWINDOW,
            )
        except Exception:
            pass

    # ------------------------------------------------------------------ layout
    def _compute_position(self) -> None:
        try:
            work = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(
                0x0030, 0, ctypes.byref(work), 0
            ):
                left, right, bottom = int(work.left), int(work.right), int(work.bottom)
            else:
                raise OSError("SPI_GETWORKAREA failed")
        except Exception:
            left, right, bottom = 0, 1920, 1040
        self.x = left + max(0, (right - left - self.width) // 2)
        self.y = max(0, bottom - self.height - 12)

    def _prepare_masks(self) -> None:
        from PIL import Image, ImageDraw, ImageFilter

        font = _load_font(30)
        probe = Image.new("L", (self.width, self.height), 0)
        draw = ImageDraw.Draw(probe)
        bbox = draw.textbbox((0, 0), _TEXT, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        # Shrink the window to the text so no empty band sits over content.
        self.width = int(text_w + 28)
        self.height = int(text_h + 22)
        image = Image.new("L", (self.width, self.height), 0)
        draw = ImageDraw.Draw(image)
        draw.text(
            ((self.width - text_w) / 2 - bbox[0], (self.height - text_h) / 2 - bbox[1]),
            _TEXT,
            font=font,
            fill=255,
        )
        self._core_mask = np.asarray(image, dtype=np.float32) / 255.0
        glow = image.filter(ImageFilter.GaussianBlur(radius=4.0))
        self._glow_mask = np.asarray(glow, dtype=np.float32) / 255.0

    # ------------------------------------------------------------------ window
    def _create_window(self):
        global user32, gdi32, kernel32
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        kernel32 = ctypes.windll.kernel32

        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
        ]
        user32.GetDC.restype = wintypes.HDC
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.ReleaseDC.restype = ctypes.c_int
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        user32.UpdateLayeredWindow.restype = wintypes.BOOL
        user32.UpdateLayeredWindow.argtypes = [
            wintypes.HWND, wintypes.HDC,
            ctypes.POINTER(wintypes.POINT), ctypes.POINTER(wintypes.SIZE),
            wintypes.HDC, ctypes.POINTER(wintypes.POINT), wintypes.DWORD,
            ctypes.POINTER(_BLENDFUNCTION), wintypes.DWORD,
        ]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetWindowPos.restype = wintypes.BOOL
        user32.SetWindowPos.argtypes = [
            wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, wintypes.UINT,
        ]
        gdi32.CreateCompatibleDC.restype = wintypes.HDC
        gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        gdi32.CreateDIBSection.restype = wintypes.HBITMAP
        gdi32.CreateDIBSection.argtypes = [
            wintypes.HDC, ctypes.POINTER(_BITMAPINFO), wintypes.UINT,
            ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD,
        ]
        gdi32.SelectObject.restype = wintypes.HGDIOBJ
        gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        gdi32.DeleteObject.restype = wintypes.BOOL
        gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        gdi32.DeleteDC.restype = wintypes.BOOL
        gdi32.DeleteDC.argtypes = [wintypes.HDC]

        ex_style = (
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST
            | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        )
        hwnd = user32.CreateWindowExW(
            ex_style, "STATIC", "", WS_POPUP,
            self.x, self.y, self.width, self.height,
            None, None, kernel32.GetModuleHandleW(None), None,
        )
        if not hwnd:
            raise ctypes.WinError()
        user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        user32.SetWindowPos(
            hwnd, HWND_TOPMOST, self.x, self.y, self.width, self.height,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        screen_dc = user32.GetDC(None)
        if not screen_dc:
            raise ctypes.WinError()
        mem_dc = gdi32.CreateCompatibleDC(screen_dc)
        if not mem_dc:
            raise ctypes.WinError()
        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self.width
        bmi.bmiHeader.biHeight = -self.height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(
            mem_dc, ctypes.byref(bmi), DIB_RGB_COLORS,
            ctypes.byref(bits), None, 0,
        )
        if not bitmap:
            raise ctypes.WinError()
        old_bitmap = gdi32.SelectObject(mem_dc, bitmap)
        return hwnd, screen_dc, mem_dc, bitmap, old_bitmap, bits

    def _pump_messages(self):
        msg = wintypes.MSG()
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0x0001):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    # ------------------------------------------------------------------ frames
    def _render_frame(self, bits, elapsed: float):
        width, height = self.width, self.height
        nbytes = width * height * 4
        buffer = (ctypes.c_ubyte * nbytes).from_address(bits.value)
        frame = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)

        xs = np.arange(width, dtype=np.float32)
        # Bright head travelling left -> right, wrapping with a short pause.
        cycle = (elapsed * 0.55) % 1.35
        head = -40.0 + cycle * (width + 80.0)
        glow = np.exp(-(((xs - head) / 34.0) ** 2)).astype(np.float32)
        brightness = 0.72 + 0.38 * glow  # blue core that flares as it passes
        # Blue tones only: deep azure base flaring to bright sky blue.
        red = (37.0 + 90.0 * glow)[None, :]
        green = (99.0 + 80.0 * glow)[None, :]
        blue = np.full((1, width), 235.0, dtype=np.float32)

        core = self._core_mask
        halo = self._glow_mask * 0.55
        # Composite halo under the core (premultiplied-style alpha blend).
        alpha = halo + core * (1.0 - halo)
        core_weight = core * (1.0 - halo) / np.maximum(alpha, 1e-6)
        halo_weight = 1.0 - core_weight
        out_r = red * core_weight + 147.0 * halo_weight
        out_g = green * core_weight + 197.0 * halo_weight
        out_b = blue * core_weight + 253.0 * halo_weight

        frame[..., 0] = (out_b * alpha).clip(0, 255).astype(np.uint8)
        frame[..., 1] = (out_g * alpha).clip(0, 255).astype(np.uint8)
        frame[..., 2] = (out_r * alpha).clip(0, 255).astype(np.uint8)
        frame[..., 3] = (alpha * 255.0).clip(0, 255).astype(np.uint8)

    def _update_window(self, hwnd, screen_dc, mem_dc):
        size = wintypes.SIZE(self.width, self.height)
        src = wintypes.POINT(0, 0)
        dst = wintypes.POINT(self.x, self.y)
        blend = _BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        ok = user32.UpdateLayeredWindow(
            hwnd, screen_dc, ctypes.byref(dst), ctypes.byref(size),
            mem_dc, ctypes.byref(src), 0, ctypes.byref(blend), ULW_ALPHA,
        )
        if not ok and not self._last_error:
            self._last_error = f"UpdateLayeredWindow failed: {ctypes.GetLastError()}"
