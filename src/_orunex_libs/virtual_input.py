"""Orunex virtual cursor and keyboard.

This module gives the agent its own input channel instead of relying on
``pyautogui`` writing into whichever window happens to have focus.

Components
----------
``VirtualCursor``
    A topmost, click-through, no-activate layered window that draws the
    agent's own pointer over the coordinates it is operating on.  The system
    cursor is still moved for the actual click injection, but the visible
    agent pointer never takes focus and stays independent of the user's mouse.

``VirtualKeyboard``
    Unicode text injection through ``SendInput``.  It is layout-independent
    (Spanish accents, symbols and emoji work) and types with a human cadence.

``WindowTarget`` / ``find_window``
    Win32 window discovery, focus stealing (``AttachThreadInput``) and
    deterministic maximize (``ShowWindow(SW_MAXIMIZE)`` + work-area fallback).

``AgentInput``
    Facade used by the OS executor: attach a window, maximize it, move the
    agent cursor, click, type, press keys and scroll.

Safety
------
Only local UI automation is performed.  No broker, network or code
execution is involved.  The overlay is click-through and never takes focus.
Set ``ORUNEX_VIRTUAL_INPUT=0`` to disable the whole layer, or
``ORUNEX_VIRTUAL_CURSOR=0`` to keep the input channel but hide the overlay.
"""

from __future__ import annotations

import ctypes
import math
import os
import random
import sys
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

IS_WINDOWS = os.name == "nt"

# ---------------------------------------------------------------------------
# Win32 bindings
# ---------------------------------------------------------------------------
if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
else:  # pragma: no cover - the project is Windows-first
    user32 = kernel32 = gdi32 = None  # type: ignore[assignment]

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_RESTORE = 9
SW_MAXIMIZE = 3
SW_SHOWNOACTIVATE = 4
SW_SHOWMAXIMIZED = 3

HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_HIDEWINDOW = 0x0080

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
BI_RGB = 0
DIB_RGB_COLORS = 0

PM_REMOVE = 0x0001
SPI_GETWORKAREA = 0x0030
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
VK_MENU = 0x12

_CURSOR_SIZE = 64
_CURSOR_HOTSPOT = (7, 5)


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_UNION),
    ]


class _WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
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


class _RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", ctypes.c_ubyte),
        ("rgbGreen", ctypes.c_ubyte),
        ("rgbRed", ctypes.c_ubyte),
        ("rgbReserved", ctypes.c_ubyte),
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


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


def _configure_win32() -> None:
    if not IS_WINDOWS:
        return
    user32.SendInput.argtypes = [
        wintypes.UINT,
        ctypes.POINTER(_INPUT),
        ctypes.c_int,
    ]
    user32.SendInput.restype = wintypes.UINT
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.BOOL,
    ]
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetActiveWindow.argtypes = [wintypes.HWND]
    user32.SetActiveWindow.restype = wintypes.HWND
    user32.SetFocus.argtypes = [wintypes.HWND]
    user32.SetFocus.restype = wintypes.HWND
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.GetWindowPlacement.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(_WINDOWPLACEMENT),
    ]
    user32.GetWindowPlacement.restype = wintypes.BOOL
    user32.SystemParametersInfoW.argtypes = [
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        wintypes.UINT,
    ]
    user32.SystemParametersInfoW.restype = wintypes.BOOL
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int
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
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.restype = wintypes.BOOL
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
    user32.UpdateLayeredWindow.restype = wintypes.BOOL
    user32.PeekMessageW.argtypes = [
        ctypes.POINTER(_MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
        wintypes.UINT,
    ]
    user32.PeekMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(_MSG)]
    user32.TranslateMessage.restype = wintypes.BOOL
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(_MSG)]
    user32.DispatchMessageW.restype = wintypes.LPARAM
    user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.keybd_event.argtypes = [
        ctypes.c_ubyte,
        ctypes.c_ubyte,
        wintypes.DWORD,
        ULONG_PTR,
    ]
    user32.keybd_event.restype = None
    user32.ShowCursor.argtypes = [wintypes.BOOL]
    user32.ShowCursor.restype = ctypes.c_int

    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC,
        ctypes.POINTER(_BITMAPINFO),
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL


_configure_win32()

_DPI_READY = False


def _ensure_dpi_aware() -> None:
    """Make cursor/window coordinates physical pixels on Windows."""
    global _DPI_READY
    if _DPI_READY or not IS_WINDOWS:
        return
    _DPI_READY = True
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


# Enable physical-pixel coordinates as early as possible.  Enabling it lazily
# (for example the first time a window is focused) makes every coordinate
# captured before that point look shifted on scaled displays, which is
# indistinguishable from the cursor having moved.  If the host app already
# declared DPI awareness the call fails harmlessly.
_ensure_dpi_aware()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def enabled() -> bool:
    """True when the agent-owned input layer is enabled."""
    return _env_bool("ORUNEX_VIRTUAL_INPUT", True)


def _emit(kind: str, message: str, level: str = "info", **data: Any) -> None:
    try:
        from _orunex_libs import activity_log  # type: ignore

        activity_log.emit(kind, message, level, **data)
    except Exception:
        pass


def _send_inputs(inputs: Sequence[_INPUT]) -> bool:
    if not IS_WINDOWS or not inputs:
        return False
    array = (_INPUT * len(inputs))(*inputs)
    sent = int(user32.SendInput(len(inputs), array, ctypes.sizeof(_INPUT)))
    return sent == len(inputs)


def _mouse_input(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> _INPUT:
    return _INPUT(
        type=INPUT_MOUSE,
        u=_INPUT_UNION(
            mi=_MOUSEINPUT(
                dx=int(dx),
                dy=int(dy),
                mouseData=int(data),
                dwFlags=int(flags),
                time=0,
                dwExtraInfo=0,
            )
        ),
    )


def _key_input(vk: int = 0, scan: int = 0, flags: int = 0) -> _INPUT:
    return _INPUT(
        type=INPUT_KEYBOARD,
        u=_INPUT_UNION(
            ki=_KEYBDINPUT(
                wVk=int(vk),
                wScan=int(scan),
                dwFlags=int(flags),
                time=0,
                dwExtraInfo=0,
            )
        ),
    )


def _mouse_click(button: str = "left", *, clicks: int = 1, interval: float = 0.0) -> bool:
    mapping = {
        "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
        "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    }
    down, up = mapping.get(str(button).lower(), mapping["left"])
    ok = True
    for index in range(max(1, int(clicks))):
        ok = _send_inputs([_mouse_input(down)]) and ok
        time.sleep(interval if interval else random.uniform(0.035, 0.085))
        ok = _send_inputs([_mouse_input(up)]) and ok
        if index < clicks - 1:
            time.sleep(random.uniform(0.07, 0.12))
    return ok


def _mouse_wheel(amount: int) -> bool:
    return _send_inputs([_mouse_input(MOUSEEVENTF_WHEEL, data=int(amount) * 120)])


def _get_cursor_pos() -> tuple[int, int]:
    if not IS_WINDOWS:
        return (0, 0)
    point = wintypes.POINT()
    if user32.GetCursorPos(ctypes.byref(point)):
        return (int(point.x), int(point.y))
    return (0, 0)


def _set_cursor_pos(x: int, y: int) -> bool:
    if not IS_WINDOWS:
        return False
    return bool(user32.SetCursorPos(int(x), int(y)))


_ghost_lock = threading.RLock()


class _HiddenSystemCursor:
    """Temporarily hide the system cursor and restore it on exit."""

    def __init__(self) -> None:
        self.point = wintypes.POINT()
        self.visible = False
        self.hidden = 0

    def __enter__(self) -> bool:
        if not IS_WINDOWS:
            return False
        self.visible = bool(user32.GetCursorPos(ctypes.byref(self.point)))
        if self.visible:
            # ShowCursor is a display counter; decrement until the cursor is
            # actually hidden, then restore the exact number of increments.
            while user32.ShowCursor(False) >= 0:
                self.hidden += 1
                if self.hidden >= 8:
                    break
        return self.visible

    def __exit__(self, *exc_info) -> bool:
        if self.visible:
            _set_cursor_pos(int(self.point.x), int(self.point.y))
            for _ in range(self.hidden):
                user32.ShowCursor(True)
        return False


def _ghost_click(x: int, y: int, button: str = "left", clicks: int = 1) -> bool:
    """Click at screen coordinates without leaving the user's cursor moved.

    ``SendInput`` still needs the system cursor at the target, so it is hidden
    for the few milliseconds of the injection and restored to its original
    position afterwards.  The agent's layered pointer is the only cursor the
    user sees.
    """
    if not IS_WINDOWS:
        return False
    if not _env_bool("ORUNEX_GHOST_CLICK", True):
        return _set_cursor_pos(x, y) and _mouse_click(button, clicks=clicks)
    with _ghost_lock:
        with _HiddenSystemCursor() as ready:
            if not ready:
                return False
            if not _set_cursor_pos(int(x), int(y)):
                return False
            time.sleep(0.012)
            ok = _mouse_click(button, clicks=clicks, interval=0.02)
            time.sleep(0.012)
            return ok


def _ghost_scroll(x: int, y: int, amount: int) -> bool:
    """Scroll at screen coordinates while preserving the user's cursor."""
    if not IS_WINDOWS:
        return False
    if not _env_bool("ORUNEX_GHOST_CLICK", True):
        return _set_cursor_pos(x, y) and _mouse_wheel(amount)
    with _ghost_lock:
        with _HiddenSystemCursor() as ready:
            if not ready:
                return False
            if not _set_cursor_pos(int(x), int(y)):
                return False
            time.sleep(0.012)
            ok = _mouse_wheel(amount)
            time.sleep(0.012)
            return ok


# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------
_VK: dict[str, int] = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "menu": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pgup": 0x21,
    "pagedown": 0x22,
    "pgdn": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "ins": 0x2D,
    "delete": 0x2E,
    "del": 0x2E,
    "win": 0x5B,
    "windows": 0x5B,
    "cmd": 0x5B,
    "meta": 0x5B,
    "numlock": 0x90,
    "scrolllock": 0x91,
    "printscreen": 0x2C,
    "prtsc": 0x2C,
    "multiply": 0x6A,
    "add": 0x6B,
    "subtract": 0x6D,
    "decimal": 0x6E,
    "divide": 0x6F,
}
for _letter in "abcdefghijklmnopqrstuvwxyz":
    _VK[_letter] = ord(_letter.upper())
for _digit in "0123456789":
    _VK[_digit] = ord(_digit)
_VK.update(
    {
        ";": 0xBA,
        "=": 0xBB,
        ",": 0xBC,
        "-": 0xBD,
        ".": 0xBE,
        "/": 0xBF,
        "`": 0xC0,
        "[": 0xDB,
        "\\": 0xDC,
        "]": 0xDD,
        "'": 0xDE,
    }
)
for _n in range(1, 25):
    _VK[f"f{_n}"] = 0x6F + _n

_EXTENDED_KEYS = {
    0x21,
    0x22,
    0x23,
    0x24,
    0x25,
    0x26,
    0x27,
    0x28,
    0x2C,
    0x2D,
    0x2E,
    0x5B,
    0x6F,
    0x90,
}

_MODIFIER_KEYS = {"ctrl", "control", "alt", "menu", "shift", "win", "windows", "cmd", "meta"}


def _normalize_key(name: str) -> str:
    return str(name or "").strip().lower().replace(" ", "")


def _split_hotkey(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part for part in (p.strip() for p in text.split("+")) if part]


def _key_vk(name: str) -> int:
    normalized = _normalize_key(name)
    if normalized in _VK:
        return _VK[normalized]
    if len(normalized) == 1:
        return ord(normalized.upper())
    return 0


def _key_down(name: str) -> None:
    vk = _key_vk(name)
    if not vk:
        return
    flags = KEYEVENTF_EXTENDEDKEY if vk in _EXTENDED_KEYS else 0
    _send_inputs([_key_input(vk=vk, flags=flags)])


def _key_up(name: str) -> None:
    vk = _key_vk(name)
    if not vk:
        return
    flags = KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if vk in _EXTENDED_KEYS else 0)
    _send_inputs([_key_input(vk=vk, flags=flags)])


def _type_char(char: str) -> bool:
    """Type one Unicode character through SendInput."""
    if not char:
        return False
    if char == "\n":
        _key_down("enter")
        _key_up("enter")
        return True
    if char == "\t":
        _key_down("tab")
        _key_up("tab")
        return True
    units = char.encode("utf-16-le")
    ok = True
    for index in range(0, len(units), 2):
        code = int.from_bytes(units[index : index + 2], "little")
        ok = _send_inputs([_key_input(scan=code, flags=KEYEVENTF_UNICODE)]) and ok
        ok = _send_inputs(
            [_key_input(scan=code, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
        ) and ok
    return ok


class VirtualKeyboard:
    """Unicode keyboard owned by the agent."""

    def __init__(self, *, human: Optional[bool] = None) -> None:
        self._human = _env_bool("ORUNEX_INPUT_HUMAN", True) if human is None else human
        self._speed = _env_float("ORUNEX_INPUT_SPEED", 1.0)

    @property
    def available(self) -> bool:
        return bool(IS_WINDOWS and enabled() and user32 is not None)

    def type_text(
        self,
        text: str,
        *,
        interval: Optional[float] = None,
        human: Optional[bool] = None,
    ) -> bool:
        if not self.available:
            return False
        value = str(text or "")
        if not value:
            return True
        human_mode = self._human if human is None else bool(human)
        base = 0.026 if human_mode else 0.004
        if interval is not None:
            base = max(0.0, float(interval))
        speed = _env_float("ORUNEX_INPUT_SPEED", self._speed)
        long_pause_at = random.randint(18, 34)
        for index, char in enumerate(value):
            if char == "\r":
                continue
            _type_char(char)
            if not human_mode:
                if base > 0:
                    time.sleep(base * speed)
                continue
            delay = base * random.uniform(0.62, 1.38) * speed
            if char in " .,;:!?¿¡":
                delay *= 1.35
            if index and index % long_pause_at == 0:
                delay += random.uniform(0.06, 0.16)
            time.sleep(delay)
        return True

    def press(self, key: str, *, presses: int = 1, interval: float = 0.03) -> bool:
        if not self.available:
            return False
        keys = _split_hotkey(key)
        if not keys:
            return False
        if len(keys) > 1:
            return self.hotkey(*keys)
        for _ in range(max(1, int(presses))):
            _key_down(keys[0])
            time.sleep(0.018)
            _key_up(keys[0])
            if interval:
                time.sleep(interval)
        return True

    def hotkey(self, *keys: str) -> bool:
        if not self.available:
            return False
        normalized: list[str] = []
        for key in keys:
            normalized.extend(_split_hotkey(key))
        if not normalized:
            return False
        modifiers = [key for key in normalized if _normalize_key(key) in _MODIFIER_KEYS]
        taps = [key for key in normalized if _normalize_key(key) not in _MODIFIER_KEYS]
        if not taps:
            taps = modifiers[-1:]
            modifiers = modifiers[:-1]
        for modifier in modifiers:
            _key_down(modifier)
            time.sleep(0.012)
        for index, tap in enumerate(taps):
            _key_down(tap)
            time.sleep(0.022)
            _key_up(tap)
            if index < len(taps) - 1:
                time.sleep(0.018)
        for modifier in reversed(modifiers):
            _key_up(modifier)
            time.sleep(0.012)
        return True


# ---------------------------------------------------------------------------
# Window discovery / control
# ---------------------------------------------------------------------------
@dataclass
class WindowInfo:
    hwnd: int
    title: str
    pid: int
    exe: str
    class_name: str
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)

    @property
    def area(self) -> int:
        left, top, right, bottom = self.rect
        return max(0, right - left) * max(0, bottom - top)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hwnd": self.hwnd,
            "title": self.title,
            "pid": self.pid,
            "exe": self.exe,
            "class_name": self.class_name,
            "rect": list(self.rect),
        }


def _window_title(hwnd: int) -> str:
    length = int(user32.GetWindowTextLengthW(hwnd))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value.strip()


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value.strip()


def _process_exe(pid: int) -> str:
    if not IS_WINDOWS or pid <= 0:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return os.path.basename(buffer.value)
    finally:
        kernel32.CloseHandle(handle)
    return ""


def _window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    return (0, 0, 0, 0)


def window_info(hwnd: int) -> Optional[WindowInfo]:
    if not IS_WINDOWS or not hwnd or not user32.IsWindow(hwnd):
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return WindowInfo(
        hwnd=int(hwnd),
        title=_window_title(hwnd),
        pid=int(pid.value),
        exe=_process_exe(int(pid.value)),
        class_name=_class_name(hwnd),
        rect=_window_rect(hwnd),
    )


def list_windows(
    *,
    exe: Optional[str | Iterable[str]] = None,
    title: Optional[str | Iterable[str]] = None,
    class_name: Optional[str] = None,
    include_hidden: bool = False,
    include_tool_windows: bool = False,
) -> list[WindowInfo]:
    if not IS_WINDOWS:
        return []
    exe_filter = _as_lower_set(exe)
    title_filter = [item.lower() for item in _as_list(title) if item]
    class_filter = str(class_name or "").strip().lower()
    found: list[WindowInfo] = []
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        try:
            if not include_hidden and not user32.IsWindowVisible(hwnd):
                return True
            title_value = _window_title(hwnd)
            if not title_value:
                return True
            ex_style = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
            if not include_tool_windows and ex_style & WS_EX_TOOLWINDOW:
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            exe_value = _process_exe(int(pid.value))
            if exe_filter and exe_value.lower() not in exe_filter:
                return True
            if title_filter and not any(item in title_value.lower() for item in title_filter):
                return True
            class_value = _class_name(hwnd)
            if class_filter and class_filter not in class_value.lower():
                return True
            found.append(
                WindowInfo(
                    hwnd=int(hwnd),
                    title=title_value,
                    pid=int(pid.value),
                    exe=exe_value,
                    class_name=class_value,
                    rect=_window_rect(hwnd),
                )
            )
        except Exception:
            pass
        return True

    user32.EnumWindows(enum_proc(callback), 0)
    found.sort(key=lambda item: (item.area, len(item.title)), reverse=True)
    return found


def _as_list(value: Optional[str | Iterable[str]]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _as_lower_set(value: Optional[str | Iterable[str]]) -> set[str]:
    return {item.strip().lower() for item in _as_list(value) if item and item.strip()}


def find_window(
    *,
    exe: Optional[str | Iterable[str]] = None,
    title: Optional[str | Iterable[str]] = None,
    class_name: Optional[str] = None,
    include_hidden: bool = False,
    include_tool_windows: bool = False,
) -> Optional[WindowInfo]:
    windows = list_windows(
        exe=exe,
        title=title,
        class_name=class_name,
        include_hidden=include_hidden,
        include_tool_windows=include_tool_windows,
    )
    return windows[0] if windows else None


def find_tradingview_window() -> Optional[WindowInfo]:
    """Find the native TradingView Desktop main window."""
    window = find_window(exe="TradingView.exe")
    if window:
        return window
    return find_window(title=("TradingView",), include_tool_windows=True)


def get_foreground_window() -> int:
    if not IS_WINDOWS:
        return 0
    return int(user32.GetForegroundWindow() or 0)


def focus_window(hwnd: int) -> bool:
    """Bring ``hwnd`` to the foreground using the kernel attach trick."""
    if not IS_WINDOWS or not hwnd or not user32.IsWindow(hwnd):
        return False
    _ensure_dpi_aware()
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        if int(user32.GetForegroundWindow() or 0) == int(hwnd):
            return True
        current_thread = int(kernel32.GetCurrentThreadId())
        foreground = int(user32.GetForegroundWindow() or 0)
        foreground_thread = int(
            user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        )
        target_thread = int(user32.GetWindowThreadProcessId(hwnd, None))
        attached: list[int] = []
        for thread_id in {foreground_thread, target_thread}:
            if thread_id and thread_id != current_thread:
                if user32.AttachThreadInput(current_thread, thread_id, True):
                    attached.append(thread_id)
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)
        finally:
            for thread_id in attached:
                try:
                    user32.AttachThreadInput(current_thread, thread_id, False)
                except Exception:
                    pass
        time.sleep(0.12)
        if int(user32.GetForegroundWindow() or 0) == int(hwnd):
            return True
        # Windows can refuse SetForegroundWindow when the caller is not the
        # active process.  A synthetic ALT tap clears that foreground lock.
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.08)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        time.sleep(0.12)
        return int(user32.GetForegroundWindow() or 0) == int(hwnd)
    except Exception:
        return False


def maximize_window(hwnd: int) -> dict[str, Any]:
    """Maximize a window and verify it, with a work-area fallback."""
    if not IS_WINDOWS or not hwnd or not user32.IsWindow(hwnd):
        return {"ok": False, "method": "unavailable", "rect": (0, 0, 0, 0)}
    _ensure_dpi_aware()
    method = "showwindow"
    try:
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        time.sleep(0.18)
        placement = _WINDOWPLACEMENT()
        placement.length = ctypes.sizeof(_WINDOWPLACEMENT)
        maximized = bool(
            user32.GetWindowPlacement(hwnd, ctypes.byref(placement))
            and int(placement.showCmd) == SW_SHOWMAXIMIZED
        )
        if not maximized:
            work = wintypes.RECT()
            if user32.SystemParametersInfoW(
                SPI_GETWORKAREA, 0, ctypes.byref(work), 0
            ):
                width = int(work.right - work.left)
                height = int(work.bottom - work.top)
                if width > 100 and height > 100:
                    user32.SetWindowPos(
                        hwnd,
                        HWND_TOP,
                        int(work.left),
                        int(work.top),
                        width,
                        height,
                        SWP_SHOWWINDOW,
                    )
                    method = "work_area"
                    time.sleep(0.18)
        rect = _window_rect(hwnd)
        work = wintypes.RECT()
        user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(work), 0)
        work_area = (
            int(work.left),
            int(work.top),
            int(work.right),
            int(work.bottom),
        )
        covers = (
            rect[2] - rect[0] >= (work_area[2] - work_area[0]) - 24
            and rect[3] - rect[1] >= (work_area[3] - work_area[1]) - 24
        )
        return {
            "ok": bool(maximized or covers),
            "method": method if (maximized or covers) else "failed",
            "rect": rect,
            "work_area": work_area,
            "show_cmd": int(placement.showCmd),
        }
    except Exception as exc:
        return {"ok": False, "method": "error", "error": str(exc), "rect": (0, 0, 0, 0)}


def get_client_rect(hwnd: int) -> tuple[int, int, int, int]:
    """Return the client area in screen coordinates as ``(l, t, w, h)``."""
    if not IS_WINDOWS or not hwnd:
        return (0, 0, 0, 0)
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return (0, 0, 0, 0)
    top_left = wintypes.POINT(int(rect.left), int(rect.top))
    bottom_right = wintypes.POINT(int(rect.right), int(rect.bottom))
    if not user32.ClientToScreen(hwnd, ctypes.byref(top_left)):
        return (0, 0, 0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(bottom_right)):
        return (0, 0, 0, 0)
    return (
        int(top_left.x),
        int(top_left.y),
        max(0, int(bottom_right.x - top_left.x)),
        max(0, int(bottom_right.y - top_left.y)),
    )


def client_to_screen(hwnd: int, x: int, y: int) -> tuple[int, int]:
    if not IS_WINDOWS or not hwnd:
        return (int(x), int(y))
    point = wintypes.POINT(int(x), int(y))
    if user32.ClientToScreen(hwnd, ctypes.byref(point)):
        return (int(point.x), int(point.y))
    return (int(x), int(y))


# ---------------------------------------------------------------------------
# Virtual cursor overlay
# ---------------------------------------------------------------------------
def _point_in_polygon(x: float, y: float, points: Sequence[tuple[float, float]]) -> bool:
    inside = False
    count = len(points)
    for index in range(count):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % count]
        if (y1 > y) != (y2 > y):
            denominator = (y2 - y1) or 1e-9
            intersect = (x2 - x1) * (y - y1) / denominator + x1
            if x < intersect:
                inside = not inside
    return inside


def _distance_to_segment(
    x: float,
    y: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length_sq))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def _cursor_bitmap_fallback(size: int = _CURSOR_SIZE) -> bytes:
    """Pure-Python pointer bitmap used when Pillow is unavailable."""
    design = [
        (7.0, 5.0),
        (7.0, 52.0),
        (18.0, 41.0),
        (26.0, 60.0),
        (36.0, 55.0),
        (28.0, 37.0),
        (45.0, 37.0),
    ]
    scale = size / 64.0
    base = [(x * scale, y * scale) for x, y in design]
    shadow = [(x + 2.0 * scale, y + 3.0 * scale) for x, y in base]
    edges = list(zip(base, base[1:] + base[:1]))
    data = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            px, py = x + 0.5, y + 0.5
            inside = _point_in_polygon(px, py, base)
            in_shadow = _point_in_polygon(px, py, shadow)
            offset = (y * size + x) * 4
            if inside:
                edge = min(
                    _distance_to_segment(px, py, start, end)
                    for start, end in edges
                )
                t = max(0.0, min(1.0, (py - 5.0 * scale) / (55.0 * scale)))
                red = int(125 - 88 * t)
                green = int(235 - 136 * t)
                blue = int(255 - 20 * t)
                alpha = 246
                if edge < 1.9 * scale:
                    red, green, blue = 7, 14, 28
                    alpha = 255
                elif x < 14 * scale and y < 34 * scale:
                    red = min(255, red + 36)
                    green = min(255, green + 16)
                    blue = min(255, blue + 6)
                data[offset] = (blue * alpha) // 255
                data[offset + 1] = (green * alpha) // 255
                data[offset + 2] = (red * alpha) // 255
                data[offset + 3] = alpha
            elif in_shadow:
                alpha = 74
                data[offset] = (16 * alpha) // 255
                data[offset + 1] = (8 * alpha) // 255
                data[offset + 2] = (3 * alpha) // 255
                data[offset + 3] = alpha
    return bytes(data)


def _cursor_bitmap(size: int = _CURSOR_SIZE) -> bytes:
    """Build a polished premultiplied BGRA pointer bitmap.

    The cursor is a modern glass arrow: ice-cyan to royal-blue gradient,
    crisp navy outline, inner white highlight, soft cyan halo and a floating
    drop shadow.  Pillow provides anti-aliasing; a pure-Python renderer keeps
    the overlay working if Pillow is unavailable.
    """
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except Exception:
        return _cursor_bitmap_fallback(size)

    scale = 4
    canvas = size * scale
    design = [(7, 5), (7, 52), (18, 41), (26, 60), (36, 55), (28, 37), (45, 37)]
    points = [(x * scale, y * scale) for x, y in design]

    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))

    # Soft border falloff for the atmospheric layers.  Without it the blurred
    # shadow/glow is clipped by the bitmap edge and shows up as a faint square
    # over light windows.  The solid arrow is composited afterwards so it stays
    # fully opaque.
    def feather(layer: "Image.Image") -> "Image.Image":
        inset = 5 * scale
        mask = Image.new("L", (canvas, canvas), 0)
        ImageDraw.Draw(mask).rectangle(
            [inset, inset, canvas - inset, canvas - inset], fill=255
        )
        mask = mask.filter(ImageFilter.GaussianBlur(3.5 * scale))
        red, green, blue, alpha = layer.split()
        alpha = Image.composite(alpha, Image.new("L", (canvas, canvas), 0), mask)
        return Image.merge("RGBA", (red, green, blue, alpha))

    # Floating drop shadow.
    shadow = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon(
        [(x + 3 * scale, y + 4 * scale) for x, y in points],
        fill=(2, 6, 16, 100),
    )
    shadow = feather(shadow.filter(ImageFilter.GaussianBlur(3.5 * scale)))
    image = Image.alpha_composite(image, shadow)

    # Soft cyan halo around the silhouette.
    glow = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    ImageDraw.Draw(glow).line(
        points + [points[0]],
        fill=(56, 189, 248, 135),
        width=4 * scale,
        joint="curve",
    )
    glow = feather(glow.filter(ImageFilter.GaussianBlur(4 * scale)))
    image = Image.alpha_composite(image, glow)

    # Diagonal ice-cyan to royal-blue gradient.
    gradient = Image.new("RGBA", (canvas, canvas))
    pixels = gradient.load()
    for y in range(canvas):
        for x in range(canvas):
            t = min(1.0, max(0.0, (x + y) / (2.0 * canvas)))
            pixels[x, y] = (
                int(125 + (37 - 125) * t),
                int(235 + (99 - 235) * t),
                int(255 + (235 - 255) * t),
                255,
            )
    mask = Image.new("L", (canvas, canvas), 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    fill = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    fill.paste(gradient, (0, 0), mask)
    image = Image.alpha_composite(image, fill)

    # Inner specular highlight on the left edge.
    highlight = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    ImageDraw.Draw(highlight).line(
        [(9 * scale, 12 * scale), (10 * scale, 46 * scale)],
        fill=(255, 255, 255, 135),
        width=2 * scale,
    )
    highlight = highlight.filter(ImageFilter.GaussianBlur(1 * scale))
    highlight.putalpha(
        Image.composite(
            highlight.getchannel("A"),
            Image.new("L", (canvas, canvas), 0),
            mask,
        )
    )
    image = Image.alpha_composite(image, highlight)

    # Crisp navy outline.
    outline = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    ImageDraw.Draw(outline).line(
        points + [points[0]],
        fill=(7, 14, 28, 255),
        width=3 * scale,
        joint="curve",
    )
    image = Image.alpha_composite(image, outline)

    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    image = image.resize((size, size), resample)

    data = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            red, green, blue, alpha = image.getpixel((x, y))
            offset = (y * size + x) * 4
            data[offset] = (blue * alpha) // 255
            data[offset + 1] = (green * alpha) // 255
            data[offset + 2] = (red * alpha) // 255
            data[offset + 3] = alpha
    return bytes(data)


class VirtualCursor:
    """Topmost click-through pointer owned by the agent."""

    def __init__(self, *, enabled: Optional[bool] = None) -> None:
        self.enabled = _env_bool("ORUNEX_VIRTUAL_CURSOR", True) if enabled is None else enabled
        self._size = _CURSOR_SIZE
        self._lock = threading.RLock()
        self._target = (0, 0)
        self._display = (0.0, 0.0)
        self._visible = False
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._hwnd = 0
        self._shown = False
        self._error = ""
        self._screen_dc = 0
        self._mem_dc = 0
        self._bitmap = 0
        self._old_bitmap = 0
        self._bits = ctypes.c_void_p()

    @property
    def available(self) -> bool:
        return bool(IS_WINDOWS and enabled() and self.enabled and user32 is not None)

    @property
    def position(self) -> tuple[int, int]:
        with self._lock:
            return self._target

    @property
    def visible(self) -> bool:
        with self._lock:
            return self._visible

    @property
    def error(self) -> str:
        return self._error

    def start(self) -> bool:
        if not self.available:
            return False
        with self._lock:
            if self._thread and self._thread.is_alive():
                return True
            self._stop.clear()
            self._ready.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="OrunexVirtualCursor",
                daemon=True,
            )
            self._thread.start()
        return self._ready.wait(timeout=1.2) and bool(self._hwnd)

    def set_position(self, x: int, y: int, *, visible: bool = True) -> None:
        if not self.available:
            return
        if not self.start():
            return
        with self._lock:
            self._target = (int(x), int(y))
            self._visible = bool(visible)

    def show(self) -> None:
        if not self.available:
            return
        if not self.start():
            return
        with self._lock:
            self._visible = True

    def hide(self) -> None:
        with self._lock:
            self._visible = False

    def shutdown(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=0.8)
        self._thread = None
        self._hwnd = 0
        self._shown = False

    # ------------------------------------------------------------------ thread
    def _run(self) -> None:
        try:
            self._create_window()
            with self._lock:
                self._display = (float(self._target[0]), float(self._target[1]))
            self._ready.set()
            while not self._stop.is_set():
                with self._lock:
                    target_x, target_y = self._target
                    visible = self._visible
                display_x, display_y = self._display
                delta_x = target_x - display_x
                delta_y = target_y - display_y
                if abs(delta_x) < 0.35 and abs(delta_y) < 0.35:
                    display_x, display_y = float(target_x), float(target_y)
                else:
                    display_x += delta_x * 0.42
                    display_y += delta_y * 0.42
                self._display = (display_x, display_y)
                if self._hwnd:
                    if visible and not self._shown:
                        user32.ShowWindow(self._hwnd, SW_SHOWNOACTIVATE)
                        self._shown = True
                    elif not visible and self._shown:
                        user32.ShowWindow(self._hwnd, SW_HIDE)
                        self._shown = False
                    if visible:
                        user32.SetWindowPos(
                            self._hwnd,
                            HWND_TOPMOST,
                            int(display_x) - _CURSOR_HOTSPOT[0],
                            int(display_y) - _CURSOR_HOTSPOT[1],
                            self._size,
                            self._size,
                            SWP_NOACTIVATE | SWP_SHOWWINDOW,
                        )
                self._pump_messages()
                time.sleep(0.008)
        except Exception as exc:  # pragma: no cover - desktop-dependent
            self._error = str(exc)
        finally:
            self._ready.set()
            self._destroy_window()

    def _pump_messages(self) -> None:
        message = _MSG()
        while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

    def _create_window(self) -> None:
        _ensure_dpi_aware()
        hinstance = kernel32.GetModuleHandleW(None)
        ex_style = (
            WS_EX_LAYERED
            | WS_EX_TRANSPARENT
            | WS_EX_TOPMOST
            | WS_EX_TOOLWINDOW
            | WS_EX_NOACTIVATE
        )
        hwnd = user32.CreateWindowExW(
            ex_style,
            "STATIC",
            "OrunexVirtualCursor",
            WS_POPUP,
            -1000,
            -1000,
            self._size,
            self._size,
            None,
            None,
            hinstance,
            None,
        )
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self._hwnd = int(hwnd)

        self._screen_dc = int(user32.GetDC(None))
        if not self._screen_dc:
            raise ctypes.WinError(ctypes.get_last_error())
        self._mem_dc = int(gdi32.CreateCompatibleDC(self._screen_dc))
        if not self._mem_dc:
            raise ctypes.WinError(ctypes.get_last_error())

        bitmap_info = _BITMAPINFO()
        header = bitmap_info.bmiHeader
        header.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        header.biWidth = self._size
        header.biHeight = -self._size
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(
            self._screen_dc,
            ctypes.byref(bitmap_info),
            DIB_RGB_COLORS,
            ctypes.byref(bits),
            None,
            0,
        )
        if not bitmap:
            raise ctypes.WinError(ctypes.get_last_error())
        self._bitmap = int(bitmap)
        self._bits = bits
        pixels = _cursor_bitmap(self._size)
        ctypes.memmove(bits, pixels, len(pixels))
        self._old_bitmap = int(gdi32.SelectObject(self._mem_dc, self._bitmap))

        size = wintypes.SIZE(self._size, self._size)
        source = wintypes.POINT(0, 0)
        destination = wintypes.POINT(-1000, -1000)
        blend = _BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(
            self._hwnd,
            self._screen_dc,
            ctypes.byref(destination),
            ctypes.byref(size),
            self._mem_dc,
            ctypes.byref(source),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )

    def _destroy_window(self) -> None:
        try:
            if self._mem_dc and self._old_bitmap:
                gdi32.SelectObject(self._mem_dc, self._old_bitmap)
        except Exception:
            pass
        try:
            if self._bitmap:
                gdi32.DeleteObject(self._bitmap)
        except Exception:
            pass
        try:
            if self._mem_dc:
                gdi32.DeleteDC(self._mem_dc)
        except Exception:
            pass
        try:
            if self._screen_dc:
                user32.ReleaseDC(None, self._screen_dc)
        except Exception:
            pass
        try:
            if self._hwnd:
                user32.DestroyWindow(self._hwnd)
        except Exception:
            pass
        self._screen_dc = 0
        self._mem_dc = 0
        self._bitmap = 0
        self._old_bitmap = 0
        self._hwnd = 0
        self._shown = False


_cursor_lock = threading.RLock()
_cursor: Optional[VirtualCursor] = None


def get_cursor() -> VirtualCursor:
    global _cursor
    with _cursor_lock:
        if _cursor is None:
            _cursor = VirtualCursor()
        return _cursor


# ---------------------------------------------------------------------------
# Agent input facade
# ---------------------------------------------------------------------------
def _human_path(
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    duration: Optional[float] = None,
) -> tuple[list[tuple[int, int]], float]:
    x0, y0 = start
    x1, y1 = end
    distance = math.hypot(x1 - x0, y1 - y0)
    if distance < 1.5:
        return [(int(x1), int(y1))], 0.0
    speed = _env_float("ORUNEX_INPUT_SPEED", 1.0)
    if duration is None:
        duration = max(0.16, min(1.35, distance / 1500.0)) * speed
    duration = max(0.08, float(duration))
    steps = max(10, min(90, int(distance / 11.0)))
    normal_x = -(y1 - y0) / distance
    normal_y = (x1 - x0) / distance
    bend = random.uniform(-0.16, 0.16) * distance
    control_1 = (
        x0 + (x1 - x0) * 0.32 + normal_x * bend,
        y0 + (y1 - y0) * 0.32 + normal_y * bend,
    )
    control_2 = (
        x0 + (x1 - x0) * 0.68 + normal_x * bend * 0.55,
        y0 + (y1 - y0) * 0.68 + normal_y * bend * 0.55,
    )
    points: list[tuple[int, int]] = []
    for index in range(1, steps + 1):
        t = index / steps
        eased = t * t * (3.0 - 2.0 * t)
        inverse = 1.0 - eased
        px = (
            inverse**3 * x0
            + 3.0 * inverse**2 * eased * control_1[0]
            + 3.0 * inverse * eased**2 * control_2[0]
            + eased**3 * x1
        )
        py = (
            inverse**3 * y0
            + 3.0 * inverse**2 * eased * control_1[1]
            + 3.0 * inverse * eased**2 * control_2[1]
            + eased**3 * y1
        )
        jitter = (1.0 - eased) * 0.7
        points.append(
            (
                int(round(px + random.uniform(-jitter, jitter))),
                int(round(py + random.uniform(-jitter, jitter))),
            )
        )
    points[-1] = (int(x1), int(y1))
    return points, duration


class AgentInput:
    """Agent-owned pointer and keyboard bound to a target window."""

    def __init__(self, *, cursor: Optional[VirtualCursor] = None) -> None:
        self.cursor = cursor or get_cursor()
        self.keyboard = VirtualKeyboard()
        self.target: Optional[WindowInfo] = None
        self._lock = threading.RLock()

    @property
    def available(self) -> bool:
        return bool(IS_WINDOWS and self.keyboard.available)

    def attach_window(
        self,
        window: Optional[WindowInfo | int] = None,
        *,
        exe: Optional[str | Iterable[str]] = None,
        title: Optional[str | Iterable[str]] = None,
        class_name: Optional[str] = None,
    ) -> bool:
        info: Optional[WindowInfo] = None
        if isinstance(window, WindowInfo):
            info = window
        elif isinstance(window, int) and window:
            info = window_info(window)
        else:
            info = find_window(exe=exe, title=title, class_name=class_name)
        if info is None:
            return False
        with self._lock:
            self.target = info
        return True

    def focus(self) -> bool:
        with self._lock:
            target = self.target
        if target is None:
            return False
        return focus_window(target.hwnd)

    def maximize(self) -> dict[str, Any]:
        with self._lock:
            target = self.target
        if target is None:
            return {"ok": False, "method": "no_target", "rect": (0, 0, 0, 0)}
        result = maximize_window(target.hwnd)
        if result.get("ok"):
            self.target = window_info(target.hwnd) or target
            _emit(
                "display",
                f"Maximized {target.title or target.exe}",
                "success",
                hwnd=target.hwnd,
                method=result.get("method"),
            )
        return result

    def center(self) -> tuple[int, int]:
        with self._lock:
            target = self.target
        if target is None:
            return _get_cursor_pos()
        left, top, width, height = get_client_rect(target.hwnd)
        if width <= 0 or height <= 0:
            left, top, right, bottom = target.rect
            return ((left + right) // 2, (top + bottom) // 2)
        return (left + width // 2, top + height // 2)

    def client_point(self, relative_x: float, relative_y: float) -> tuple[int, int]:
        with self._lock:
            target = self.target
        if target is None:
            return _get_cursor_pos()
        left, top, width, height = get_client_rect(target.hwnd)
        if width <= 0 or height <= 0:
            left, top, right, bottom = target.rect
            width, height = right - left, bottom - top
        return (
            left + int(max(0.0, min(1.0, relative_x)) * width),
            top + int(max(0.0, min(1.0, relative_y)) * height),
        )

    def move_to(
        self,
        x: int,
        y: int,
        *,
        duration: Optional[float] = None,
        visible: bool = True,
    ) -> dict[str, Any]:
        _ensure_dpi_aware()
        # The overlay moves on its own; the physical cursor is never dragged
        # along the path.  The first visible move starts at the target so the
        # pointer does not sweep in from the top-left corner of the screen.
        start = self.cursor.position if self.cursor.visible else (int(x), int(y))
        points, total = _human_path(start, (int(x), int(y)), duration=duration)
        self.cursor.set_position(points[0][0], points[0][1], visible=visible)
        per_step = (total / max(1, len(points))) if total else 0.0
        for point_x, point_y in points:
            self.cursor.set_position(point_x, point_y, visible=visible)
            if per_step:
                time.sleep(per_step * random.uniform(0.82, 1.18))
        return {"ok": True, "x": int(x), "y": int(y), "duration": total}

    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        *,
        button: str = "left",
        clicks: int = 1,
        relative: bool = False,
        ensure_focus: bool = True,
        duration: Optional[float] = None,
    ) -> dict[str, Any]:
        if x is None or y is None:
            target_x, target_y = self.center()
        elif relative:
            target_x, target_y = self.client_point(float(x), float(y))
        else:
            target_x, target_y = int(x), int(y)
        focused = True
        if ensure_focus:
            focused = self.focus()
            time.sleep(0.08)
        move = self.move_to(target_x, target_y, duration=duration)
        ok = _ghost_click(target_x, target_y, button=button, clicks=clicks)
        if not ok:
            # Last resort for environments where hiding the system cursor is
            # not allowed: click visibly, then put the user's cursor back.
            original = _get_cursor_pos()
            _set_cursor_pos(target_x, target_y)
            ok = _mouse_click(button, clicks=clicks)
            _set_cursor_pos(*original)
        try:
            from _orunex_libs import click_fx  # type: ignore

            click_fx.spark_at(target_x, target_y)
        except Exception:
            pass
        _emit(
            "click",
            f"Agent click ({target_x}, {target_y})",
            "info",
            x=target_x,
            y=target_y,
            button=button,
            focused=focused,
            ghost=bool(ok),
        )
        return {
            "ok": bool(ok),
            "x": target_x,
            "y": target_y,
            "focused": focused,
            "duration": move.get("duration", 0.0),
        }

    def type_text(
        self,
        text: str,
        *,
        ensure_focus: bool = True,
        interval: Optional[float] = None,
    ) -> bool:
        focused = True
        if ensure_focus:
            focused = self.focus()
            time.sleep(0.1)
        if not focused and ensure_focus:
            return False
        result = self.keyboard.type_text(text, interval=interval)
        if result:
            preview = " ".join(str(text or "").split())[:60]
            _emit("keyboard", f"Agent typed: {preview}", "info", chars=len(str(text or "")))
        return result

    def press(self, key: str, *, presses: int = 1, ensure_focus: bool = True) -> bool:
        if ensure_focus and not self.focus():
            return False
        return self.keyboard.press(key, presses=presses)

    def hotkey(self, *keys: str, ensure_focus: bool = True) -> bool:
        if ensure_focus and not self.focus():
            return False
        return self.keyboard.hotkey(*keys)

    def scroll(self, amount: int, *, ensure_focus: bool = True) -> bool:
        if ensure_focus and not self.focus():
            return False
        with self._lock:
            target = self.target
        if self.cursor.visible:
            x, y = self.cursor.position
        elif target is not None:
            x, y = self.center()
        else:
            x, y = _get_cursor_pos()
        return _ghost_scroll(x, y, int(amount))

    def status(self) -> dict[str, Any]:
        with self._lock:
            target = self.target
        return {
            "available": self.available,
            "cursor": {
                "enabled": self.cursor.enabled,
                "running": bool(self.cursor._thread and self.cursor._thread.is_alive()),
                "position": list(self.cursor.position),
                "error": self.cursor.error,
            },
            "target": target.to_dict() if target else None,
            "foreground": get_foreground_window(),
        }


_input_lock = threading.RLock()
_agent_input: Optional[AgentInput] = None


def get_input() -> AgentInput:
    global _agent_input
    with _input_lock:
        if _agent_input is None:
            _agent_input = AgentInput()
        return _agent_input


def shutdown() -> None:
    """Stop the overlay and drop the singleton (called on app close)."""
    global _agent_input, _cursor
    with _input_lock:
        _agent_input = None
    with _cursor_lock:
        cursor = _cursor
        _cursor = None
    if cursor is not None:
        cursor.shutdown()
