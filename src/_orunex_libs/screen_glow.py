"""High-quality animated screen-edge glow for Windows.

The old implementation painted four opaque Tk strips.  That produced hard
corners and a flat, low-resolution border.  This module uses a layered Win32
window with per-pixel alpha instead:

* one continuous rounded-rectangle glow (no cut corners),
* a soft inward aura plus a luminous core,
* a smooth, cyclic blue-only gradient flowing around the border,
* fully click-through, topmost and absent from Alt+Tab.

The overlay is rendered on a background thread so the Tk event loop never
blocks.  It gracefully no-ops on platforms without the Win32 APIs.
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


# Win32 constants
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


def _smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


class ScreenGlowOverlay:
    """Owns a single layered window and its animation thread."""

    def __init__(self, width: int, height: int, fps: int = 24):
        self.width = max(320, int(width))
        self.height = max(240, int(height))
        self.fps = max(15, min(45, int(fps)))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._prepared = False
        self._bands = []
        self._lut = None
        self._frame = None
        self._frame_buffer = None
        self._frame_direct = False
        self._last_error = ""
        self._window_ready = threading.Event()
        self._hwnd = 0

    # ------------------------------------------------------------------ public
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
                # A previous fade-out is still finishing; give it a moment so
                # a new task does not start with two layered windows.
                self._thread.join(timeout=0.45)
                if self._thread.is_alive():
                    return
            self._stop_event.clear()
            self._window_ready.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="OrunexScreenGlow",
                daemon=True,
            )
            self._thread.start()

    def stop(self, wait: bool = True) -> None:
        self._stop_event.set()
        # The animation thread owns the window.  It hides the layered window
        # itself on the next frame, avoiding a cross-thread ShowWindow call
        # that can block while audio synthesis is busy.
        thread = self._thread
        if wait and thread and thread.is_alive():
            thread.join(timeout=0.9)
        if not thread or not thread.is_alive():
            self._thread = None

    def _hide_window_now(self) -> None:
        hwnd = getattr(self, "_hwnd", 0)
        if not hwnd:
            return
        try:
            if "user32" in globals():
                user32.ShowWindow(hwnd, 0)  # SW_HIDE
                # Layered windows have occasionally ignored the first hide on
                # this desktop; SWP_HIDEWINDOW is a second, independent path.
                user32.SetWindowPos(
                    hwnd,
                    0,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOSIZE
                    | SWP_NOMOVE
                    | SWP_NOZORDER
                    | SWP_NOACTIVATE
                    | SWP_HIDEWINDOW,
                )
        except Exception as exc:
            print(f"[SCREEN GLOW] hide failed: {exc}")

    def last_error(self) -> str:
        return self._last_error

    # ------------------------------------------------------------------ thread
    def _run(self) -> None:
        hwnd = 0
        mem_dc = 0
        screen_dc = 0
        bitmap = 0
        old_bitmap = 0
        bits = ctypes.c_void_p()
        start = time.perf_counter()
        try:
            hwnd, screen_dc, mem_dc, bitmap, old_bitmap, bits = self._create_window()
            self._hwnd = hwnd
            self._window_ready.set()
            if self._stop_event.is_set():
                self._hide_window_now()
            interval = 1.0 / self.fps
            next_frame = time.perf_counter()
            while not self._stop_event.is_set():
                now = time.perf_counter()
                elapsed = now - start
                # Gentle fade-in so the border does not flash on screen.
                fade_in = _smoothstep(elapsed / 0.42)
                self._render_frame(bits, fade_in, elapsed)
                self._update_window(hwnd, screen_dc, mem_dc)
                self._pump_messages()
                next_frame += interval
                delay = next_frame - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_frame = time.perf_counter()
            # Live-off is a hard stop: hide the contour immediately from the
            # thread that owns the window, then release the layered surface in
            # the finally block.  A fade-out here made the border linger over
            # the desktop after Live had already been switched off.
            self._hide_window_now()
        except Exception as exc:  # keep failures out of the UI loop
            self._last_error = str(exc)
            try:
                print(f"[SCREEN GLOW] {exc}")
            except Exception:
                pass
        finally:
            self._window_ready.set()
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
            self._frame = None
            self._frame_buffer = None
            self._frame_direct = False

    # ------------------------------------------------------------------ window
    def _create_window(self):
        global user32, gdi32, kernel32
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        kernel32 = ctypes.windll.kernel32

        # Explicit signatures matter on 64-bit Windows: without them ctypes
        # truncates window/DC handles to 32 bits.
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetLastError.restype = wintypes.DWORD
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        user32.GetDC.restype = wintypes.HDC
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.ReleaseDC.restype = ctypes.c_int
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        user32.UpdateLayeredWindow.restype = wintypes.BOOL
        user32.UpdateLayeredWindow.argtypes = [
            wintypes.HWND,
            wintypes.HDC,
            ctypes.POINTER(wintypes.POINT),
            ctypes.POINTER(wintypes.SIZE),
            wintypes.HDC,
            ctypes.POINTER(wintypes.POINT),
            wintypes.DWORD,
            ctypes.POINTER(_BLENDFUNCTION),
            wintypes.DWORD,
        ]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetWindowPos.restype = wintypes.BOOL
        user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        gdi32.CreateCompatibleDC.restype = wintypes.HDC
        gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        gdi32.CreateDIBSection.restype = wintypes.HBITMAP
        gdi32.CreateDIBSection.argtypes = [
            wintypes.HDC,
            ctypes.POINTER(_BITMAPINFO),
            wintypes.UINT,
            ctypes.POINTER(ctypes.c_void_p),
            wintypes.HANDLE,
            wintypes.DWORD,
        ]
        gdi32.SelectObject.restype = wintypes.HGDIOBJ
        gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        gdi32.DeleteObject.restype = wintypes.BOOL
        gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        gdi32.DeleteDC.restype = wintypes.BOOL
        gdi32.DeleteDC.argtypes = [wintypes.HDC]

        hinstance = kernel32.GetModuleHandleW(None)
        ex_style = (
            WS_EX_LAYERED
            | WS_EX_TRANSPARENT
            | WS_EX_TOPMOST
            | WS_EX_TOOLWINDOW
            | WS_EX_NOACTIVATE
        )
        # Use a built-in window class.  A Python ctypes WNDPROC is a fatal
        # liability here: any exception raised from a Win32 callback terminates
        # the whole process (0xc000041d) instead of surfacing as a Python
        # traceback.  A STATIC window gives us the same layered popup surface
        # while Windows owns the window procedure.
        hwnd = user32.CreateWindowExW(
            ex_style,
            "STATIC",
            "",
            WS_POPUP,
            0,
            0,
            self.width,
            self.height,
            None,
            None,
            hinstance,
            None,
        )
        if not hwnd:
            raise ctypes.WinError()

        user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            self.width,
            self.height,
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
        bmi.bmiHeader.biHeight = -self.height  # top-down rows
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(
            mem_dc,
            ctypes.byref(bmi),
            DIB_RGB_COLORS,
            ctypes.byref(bits),
            None,
            0,
        )
        if not bitmap:
            raise ctypes.WinError()
        old_bitmap = gdi32.SelectObject(mem_dc, bitmap)
        self._prepare_static_fields()
        self._bind_frame(bits)
        return hwnd, screen_dc, mem_dc, bitmap, old_bitmap, bits

    def _pump_messages(self):
        msg = wintypes.MSG()
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0x0001):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    # ------------------------------------------------------------------ frames
    def _prepare_static_fields(self):
        """Build the four border bands and the premultiplied colour table once.

        Only the outer band of the screen can contain glow pixels.  Rendering
        that band at native resolution avoids a full-screen resize every frame
        while keeping the rounded core line perfectly sharp.
        """
        width, height = self.width, self.height
        # This is a screen-contour glow, not an inset rectangle.  It hugs the
        # physical display edge and spends almost all of its visual budget on
        # a thin inner aura, so it never becomes a box sitting over content.
        inset = max(2, int(round(min(width, height) * 0.0025)))
        radius = max(24.0, min(width, height) * 0.018)

        # A compact band is enough for the contour and its soft falloff.
        margin = int(round(min(width, height) * 0.078))
        margin = max(64, min(110, margin))
        margin = min(margin, max(32, min(width, height) // 3))

        bands = []
        ranges = (
            (0, margin, 0, width),
            (height - margin, height, 0, width),
            (margin, height - margin, 0, margin),
            (margin, height - margin, width - margin, width),
        )
        for y0, y1, x0, x1 in ranges:
            if y1 <= y0 or x1 <= x0:
                continue
            xs = np.arange(x0, x1, dtype=np.float32)[None, :]
            ys = np.arange(y0, y1, dtype=np.float32)[:, None]
            half_w = width / 2.0
            half_h = height / 2.0
            qx = np.abs(xs - half_w) - (half_w - inset - radius)
            qy = np.abs(ys - half_h) - (half_h - inset - radius)
            outside = np.sqrt(
                np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2
            )
            d = np.minimum(np.maximum(qx, qy), 0.0) + outside - radius

            inward = np.maximum(-d, 0.0)
            outward = np.maximum(d, 0.0)
            inside = d <= 0.0
            core = np.exp(-((np.abs(d) / 2.4) ** 2))
            inner = np.where(
                inside, np.exp(-((inward / 24.0) ** 2)), 0.0
            )
            outer = np.where(
                inside, 0.0, np.exp(-((outward / 8.0) ** 2))
            )
            far = np.where(
                inside, np.exp(-((inward / 52.0) ** 2)), 0.0
            )
            profile = 0.90 * core + 0.20 * inner + 0.06 * outer + 0.025 * far
            profile = np.clip(profile, 0.0, 1.0).astype(np.float32)

            edge_dist = np.minimum(
                np.minimum(xs, width - 1 - xs),
                np.minimum(ys, height - 1 - ys),
            )

            # Keep the luminous contour at the physical screen edge.  The
            # one-pixel ramp only avoids a hard clipping line; it must not
            # create the transparent gap that made the old overlay look like
            # a small box floating inside the display.
            edge_fade = np.clip(edge_dist / 1.5, 0.0, 1.0)

            # Fade the faint tail to zero at the inner boundary of this band,
            # so adjacent bands meet without a visible horizontal/vertical cut.
            band_fade = np.clip((margin - edge_dist) / 30.0, 0.0, 1.0)
            band_fade = band_fade * band_fade * (3.0 - 2.0 * band_fade)

            profile *= edge_fade * band_fade

            u = xs / max(1.0, width - 1)
            v = ys / max(1.0, height - 1)
            phase_a = (
                2.0 * math.pi * (0.86 * u + 0.52 * v)
            ).astype(np.float32)
            phase_b = (
                2.0 * math.pi * (-0.46 * u + 1.04 * v)
            ).astype(np.float32)
            phase_c = (
                2.0 * math.pi * (0.72 * u - 0.63 * v)
            ).astype(np.float32)
            bands.append(
                {
                    "slice": (slice(y0, y1), slice(x0, x1)),
                    "profile": profile,
                    "sin_a": np.sin(phase_a),
                    "cos_a": np.cos(phase_a),
                    "sin_b": np.sin(phase_b),
                    "cos_b": np.cos(phase_b),
                    "sin_c": np.sin(phase_c),
                    "cos_c": np.cos(phase_c),
                }
            )

        # A cyclic blue palette avoids a colour seam when the wave wraps.
        steps = 512
        t = np.linspace(0.0, 1.0, steps, endpoint=False, dtype=np.float32)
        hue = 0.596 + 0.044 * np.sin(2.0 * math.pi * t)
        sat = 0.82 + 0.055 * np.cos(2.0 * math.pi * t + 0.65)
        val = 0.89 + 0.075 * np.cos(2.0 * math.pi * t + 1.75)
        palette = np.zeros((steps, 3), dtype=np.float32)
        for index in range(steps):
            palette[index] = _hsv_to_rgb(
                float(hue[index]), float(sat[index]), float(val[index])
            )
        palette = (palette * 255.0).clip(0, 255)

        # Combined (palette index, alpha) -> premultiplied BGRA.  This keeps
        # the per-frame cost to two lookups instead of several float blends.
        lut = np.zeros((steps, 256, 4), dtype=np.uint8)
        levels = (np.arange(256, dtype=np.float32) / 255.0)[None, :]
        lut[..., 0] = (palette[:, 2][:, None] * levels).astype(np.uint8)
        lut[..., 1] = (palette[:, 1][:, None] * levels).astype(np.uint8)
        lut[..., 2] = (palette[:, 0][:, None] * levels).astype(np.uint8)
        lut[..., 3] = np.arange(256, dtype=np.uint8)[None, :]

        self._bands = bands
        self._lut = lut.reshape(-1, 4)
        if self._frame is None:
            self._frame = np.zeros((height, width, 4), dtype=np.uint8)
        self._prepared = True

    def _bind_frame(self, bits):
        """Write band pixels straight into the layered window's DIB."""
        nbytes = self.width * self.height * 4
        self._frame_buffer = (ctypes.c_ubyte * nbytes).from_address(bits.value)
        self._frame = np.frombuffer(self._frame_buffer, dtype=np.uint8).reshape(
            self.height, self.width, 4
        )
        self._frame_direct = True

    def _render_frame(self, bits, fade: float, elapsed: float):
        if not self._prepared:
            self._prepare_static_fields()
        time_s = float(elapsed)
        w1 = 2.0 * math.pi * 0.235 * time_s
        w2 = 2.0 * math.pi * 0.155 * time_s
        w3 = 2.0 * math.pi * 0.285 * time_s
        c1, s1 = math.cos(w1), math.sin(w1)
        c2, s2 = math.cos(w2), math.sin(w2)
        c3, s3 = math.cos(w3), math.sin(w3)
        breathing = 0.95 + 0.05 * math.sin(2.0 * math.pi * 0.18 * time_s)
        strength = fade * breathing
        step = 511
        frame = self._frame
        lut = self._lut

        for band in self._bands:
            wave = 0.62 * (
                band["sin_a"] * c1 - band["cos_a"] * s1
            ) + 0.38 * (
                band["sin_b"] * c2 + band["cos_b"] * s2
            )
            shimmer = 0.92 + 0.08 * (
                band["sin_c"] * c3 - band["cos_c"] * s3
            )
            index = ((wave + 1.0) * 0.5 * step).astype(np.int32)
            np.clip(index, 0, step, out=index)
            alpha = band["profile"] * shimmer
            alpha *= strength
            np.clip(alpha, 0.0, 1.0, out=alpha)
            alpha8 = (alpha * 255.0).astype(np.uint8)
            lookup = index.astype(np.uint32) * 256 + alpha8
            frame[band["slice"]] = lut[lookup]

        if not self._frame_direct:
            ctypes.memmove(bits, frame.ctypes.data, frame.nbytes)

    def _update_window(self, hwnd, screen_dc, mem_dc):
        size = wintypes.SIZE(self.width, self.height)
        src = wintypes.POINT(0, 0)
        dst = wintypes.POINT(0, 0)
        blend = _BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        ok = user32.UpdateLayeredWindow(
            hwnd,
            screen_dc,
            ctypes.byref(dst),
            ctypes.byref(size),
            mem_dc,
            ctypes.byref(src),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )
        if not ok and not self._last_error:
            self._last_error = f"UpdateLayeredWindow failed: {ctypes.GetLastError()}"


def _hsv_to_rgb(hue: float, saturation: float, value: float):
    """Small dependency-free HSV helper (avoids importing colorsys per frame)."""
    hue = hue % 1.0
    sector = hue * 6.0
    index = int(sector)
    fraction = sector - index
    p = value * (1.0 - saturation)
    q = value * (1.0 - saturation * fraction)
    t = value * (1.0 - saturation * (1.0 - fraction))
    index %= 6
    if index == 0:
        return (value, t, p)
    if index == 1:
        return (q, value, p)
    if index == 2:
        return (p, value, t)
    if index == 3:
        return (p, q, value)
    if index == 4:
        return (t, p, value)
    return (value, p, q)
