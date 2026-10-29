"""Fluid white-spark overlay for agent clicks.

The OS executor can click from a worker thread.  Tk widgets must be created on
the UI thread, so :func:`configure` stores the main window and
:func:`spark_at` schedules the short-lived overlay with ``after(0, ...)``.

The overlay uses a transparent-colour key on Windows and draws a white spark
burst with a subtle dark shadow, which keeps it readable over both light and
dark applications.  It never takes focus and destroys itself after ~0.55 s.
"""

from __future__ import annotations

import math
import random
import sys
import threading
import time
import tkinter as tk
from typing import List, Optional

TRANSPARENT_COLOR = "#010203"
_MAX_ACTIVE = 8
_LIFETIME = 0.62
_FRAME_MS = 16

_root: Optional[tk.Misc] = None
_active: List[tk.Toplevel] = []
_lock = threading.Lock()


def configure(root: Optional[tk.Misc]) -> None:
    """Register the Tk root used to create overlays."""
    global _root
    _root = root


def shutdown() -> None:
    """Destroy every live overlay (called when the app closes)."""
    with _lock:
        windows = list(_active)
        _active.clear()
    for window in windows:
        try:
            window.destroy()
        except Exception:
            pass


def spark_at(x: int, y: int, root: Optional[tk.Misc] = None) -> None:
    """Schedule a white spark burst at screen coordinates ``x, y``."""
    target = root or _root
    if target is None:
        return
    try:
        target.after(0, lambda: _spawn(target, int(x), int(y)))
    except Exception:
        # The app may be shutting down, or the caller may not have a Tk loop.
        pass


def _spawn(root: tk.Misc, x: int, y: int) -> None:
    try:
        if not root.winfo_exists():
            return
    except Exception:
        return

    with _lock:
        while len(_active) >= _MAX_ACTIVE:
            old = _active.pop(0)
            try:
                old.destroy()
            except Exception:
                pass

    size = 210
    try:
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
    except Exception:
        screen_w, screen_h = 1920, 1080
    left = max(0, min(x - size // 2, max(0, screen_w - size)))
    top = max(0, min(y - size // 2, max(0, screen_h - size)))

    try:
        window = tk.Toplevel(root)
    except Exception:
        return
    try:
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        try:
            window.attributes("-transparentcolor", TRANSPARENT_COLOR)
        except Exception:
            # Non-Windows Tk builds do not support the colour key.  Keep a
            # small dark canvas instead of failing the animation.
            pass
        try:
            window.wm_attributes("-toolwindow", True)
        except Exception:
            pass
        window.geometry(f"{size}x{size}+{left}+{top}")
        canvas = tk.Canvas(
            window,
            width=size,
            height=size,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(fill="both", expand=True)
    except Exception:
        try:
            window.destroy()
        except Exception:
            pass
        return

    with _lock:
        _active.append(window)

    cx = x - left
    cy = y - top
    rng = random.Random((x * 73856093) ^ (y * 19349663))
    particles = []
    count = 20
    for index in range(count):
        angle = (2.0 * math.pi * index / count) + rng.uniform(-0.16, 0.16)
        speed = rng.uniform(38.0, 80.0)
        length = rng.uniform(13.0, 28.0)
        delay = rng.uniform(0.0, 0.06)
        width = rng.choice((2.0, 2.5, 3.0))
        shadow = canvas.create_line(
            cx, cy, cx, cy, fill="#1F2937", width=width + 1.5,
            capstyle=tk.ROUND,
        )
        core = canvas.create_line(
            cx, cy, cx, cy, fill="#FFFFFF", width=width, capstyle=tk.ROUND,
        )
        particles.append(
            {
                "angle": angle,
                "speed": speed,
                "length": length,
                "delay": delay,
                "shadow": shadow,
                "core": core,
            }
        )

    glow = canvas.create_oval(
        cx - 10, cy - 10, cx + 10, cy + 10,
        outline="#CBD5E1", width=8.0, stipple="gray25",
    )
    ring_shadow = canvas.create_oval(
        cx - 4, cy - 4, cx + 4, cy + 4,
        outline="#1F2937", width=3.0,
    )
    ring = canvas.create_oval(
        cx - 3, cy - 3, cx + 3, cy + 3,
        outline="#FFFFFF", width=2.4,
    )
    dot = canvas.create_oval(
        cx - 2, cy - 2, cx + 2, cy + 2,
        fill="#FFFFFF", outline="",
    )

    start = time.monotonic()

    def finish() -> None:
        with _lock:
            try:
                _active.remove(window)
            except ValueError:
                pass
        try:
            window.destroy()
        except Exception:
            pass

    def frame() -> None:
        elapsed = time.monotonic() - start
        t = min(1.0, elapsed / _LIFETIME)
        if t >= 1.0:
            finish()
            return

        for particle in particles:
            local_t = max(0.0, min(1.0, (elapsed - particle["delay"]) / 0.44))
            if local_t <= 0.0:
                canvas.itemconfigure(particle["shadow"], state="hidden")
                canvas.itemconfigure(particle["core"], state="hidden")
                continue
            ease = 1.0 - (1.0 - local_t) ** 3
            distance = 3.0 + particle["speed"] * ease
            angle = particle["angle"]
            head_x = cx + math.cos(angle) * distance
            head_y = cy + math.sin(angle) * distance
            tail = particle["length"] * (1.0 - local_t * 0.75)
            tail_x = head_x - math.cos(angle) * tail
            tail_y = head_y - math.sin(angle) * tail
            fade = int(255 - 88 * local_t)
            color = f"#{fade:02x}{fade:02x}{min(255, fade + 8):02x}"
            canvas.coords(particle["shadow"], tail_x + 1, tail_y + 1, head_x + 1, head_y + 1)
            canvas.coords(particle["core"], tail_x, tail_y, head_x, head_y)
            canvas.itemconfigure(
                particle["shadow"],
                state="normal",
                fill="#334155" if local_t < 0.82 else TRANSPARENT_COLOR,
                width=max(1.0, 2.5 * (1.0 - local_t * 0.5)),
            )
            canvas.itemconfigure(
                particle["core"],
                state="normal",
                fill=color,
                width=max(1.0, 2.0 * (1.0 - local_t * 0.55)),
                stipple="" if local_t < 0.72 else "gray50",
            )

        ease = 1.0 - (1.0 - t) ** 2
        radius = 3.0 + 32.0 * ease
        glow_radius = 8.0 + 38.0 * ease
        ring_color = f"#{int(255 - 100 * t):02x}{int(255 - 90 * t):02x}{int(255 - 70 * t):02x}"
        canvas.coords(
            glow,
            cx - glow_radius,
            cy - glow_radius,
            cx + glow_radius,
            cy + glow_radius,
        )
        canvas.coords(ring_shadow, cx - radius - 1, cy - radius - 1, cx + radius + 1, cy + radius + 1)
        canvas.coords(ring, cx - radius, cy - radius, cx + radius, cy + radius)
        canvas.coords(dot, cx - 3.0, cy - 3.0, cx + 3.0, cy + 3.0)
        canvas.itemconfigure(
            glow,
            outline="#94A3B8" if t < 0.85 else TRANSPARENT_COLOR,
            width=max(1.0, 9.0 * (1.0 - t)),
            stipple="gray25" if t < 0.7 else "gray12",
        )
        canvas.itemconfigure(
            ring_shadow,
            outline="#334155" if t < 0.8 else TRANSPARENT_COLOR,
            width=max(1.0, 3.5 * (1.0 - t)),
        )
        canvas.itemconfigure(
            ring,
            outline=ring_color,
            width=max(1.0, 2.2 * (1.0 - t)),
            stipple="" if t < 0.72 else "gray50",
        )
        canvas.itemconfigure(
            dot,
            fill=ring_color if t < 0.75 else TRANSPARENT_COLOR,
        )

        try:
            window.after(_FRAME_MS, frame)
        except Exception:
            finish()

    try:
        window.after(_FRAME_MS, frame)
    except Exception:
        finish()
