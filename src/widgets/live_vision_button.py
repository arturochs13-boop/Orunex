"""Concentric-circle toggle used by Orunex Live Vision.

The control is intentionally a tiny canvas instead of a text button: an outer
ring with a filled inner circle.  When active it uses a smooth, time-based
30 fps animation with two rotating blue arcs and a breathing halo.

Clicking is handled by a single ``<Button-1>`` binding plus a short debounce,
so one physical click can never toggle the session twice.
"""

from __future__ import annotations

import math
import time
import tkinter as tk
from typing import Callable, Optional


class LiveVisionButton(tk.Canvas):
    """A compact, accessible Live Vision toggle.

    Parameters
    ----------
    master:
        Parent Tk widget.
    command:
        Called when the button is clicked.  The owner is responsible for
        changing the session state and then calling ``set_active``.
    size:
        Canvas size in screen pixels.
    bg:
        Canvas background.  Pass the surface colour of the parent so the
        control blends into the composer.
    """

    # Blue family used by the active animation.  Tk canvases cannot do real
    # alpha blending, so a layered palette gives the halo its soft look.
    BLUE_DEEP = "#0668E1"
    BLUE = "#2F80ED"
    BLUE_LIGHT = "#56A8FF"
    BLUE_PALE = "#A8C7FA"
    BLUE_HOVER = "#7EA9DE"

    def __init__(
        self,
        master,
        command: Optional[Callable[[], None]] = None,
        size: int = 40,
        bg: str = "#FFFFFF",
        active_color: str = "#0668E1",
        idle_color: str = "#AAB4C3",
        halo_color: str = "#DCEBFF",
        **kwargs,
    ):
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("bd", 0)
        kwargs.setdefault("cursor", "hand2")
        kwargs.setdefault("takefocus", 1)
        super().__init__(
            master,
            width=size,
            height=size,
            bg=bg,
            **kwargs,
        )
        self._command = command
        self._size = max(28, int(size))
        self._bg = bg
        self._active_color = active_color
        self._idle_color = idle_color
        self._halo_color = halo_color
        self._active = False
        self._hover = False
        self._started_at = 0.0
        self._after_id: Optional[str] = None
        self._last_invoke = 0.0

        # Persistent canvas items avoid delete/recreate flicker at 30 fps.
        self._halo_outer = self.create_oval(
            0, 0, 0, 0, outline=self._halo_color, width=1, state="hidden"
        )
        self._halo_mid = self.create_oval(
            0, 0, 0, 0, outline=self.BLUE_PALE, width=1, state="hidden"
        )
        self._arc_a = self.create_arc(
            0, 0, 0, 0,
            start=0, extent=80, style=tk.ARC,
            outline=self.BLUE_LIGHT, width=2, state="hidden",
        )
        self._arc_b = self.create_arc(
            0, 0, 0, 0,
            start=0, extent=36, style=tk.ARC,
            outline=self.BLUE_PALE, width=1, state="hidden",
        )
        self._ring = self.create_oval(
            0, 0, 0, 0, outline=self._idle_color, width=2
        )
        self._inner = self.create_oval(
            0, 0, 0, 0, fill=self._idle_color, outline=""
        )
        self._spark_a = self.create_oval(
            0, 0, 0, 0, fill=self.BLUE_LIGHT, outline="", state="hidden"
        )
        self._spark_b = self.create_oval(
            0, 0, 0, 0, fill=self.BLUE_PALE, outline="", state="hidden"
        )
        self._focus_ring = self.create_oval(
            0, 0, 0, 0, outline="#C7D1DF", width=1, state="hidden"
        )

        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        self.bind("<Button-1>", self._on_click, add="+")
        self.bind("<Return>", self._on_key, add="+")
        self.bind("<space>", self._on_key, add="+")
        self.bind("<FocusIn>", lambda _event: self._draw(), add="+")
        self.bind("<FocusOut>", lambda _event: self._draw(), add="+")
        self._draw()

    @property
    def active(self) -> bool:
        return self._active

    def set_active(self, active: bool):
        active = bool(active)
        if self._active == active:
            # Keep the visual and the session state in sync even if a caller
            # repeats the same state.
            self._draw()
            if active:
                self._schedule_animation()
            return
        self._active = active
        self._started_at = time.monotonic() if active else 0.0
        if not active and self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._draw()
        if active:
            self._schedule_animation()

    def toggle(self):
        self.set_active(not self._active)

    def _schedule_animation(self):
        if not self._active or self._after_id is not None:
            return
        try:
            self._after_id = self.after(33, self._animate)
        except Exception:
            self._after_id = None

    def _animate(self):
        self._after_id = None
        if not self.winfo_exists() or not self._active:
            return
        self._draw()
        self._schedule_animation()

    def _draw(self):
        if not self.winfo_exists():
            return
        try:
            width = max(self._size, self.winfo_width())
            height = max(self._size, self.winfo_height())
            focused = self.focus_get() is self
        except Exception:
            width = height = self._size
            focused = False

        cx, cy = width / 2.0, height / 2.0
        base = min(width, height) / float(self._size)

        if self._active:
            self._draw_active(cx, cy, base)
        else:
            self._hide(
                self._halo_outer,
                self._halo_mid,
                self._arc_a,
                self._arc_b,
                self._spark_a,
                self._spark_b,
            )
            # Hover is deliberately only a soft blue outline with a neutral
            # core.  Filling the core here made the OFF state look active,
            # especially while the pointer was still over the button.
            ring_color = self.BLUE_HOVER if self._hover else self._idle_color
            self._set_oval(
                self._ring, cx, cy, 11.2 * base,
                ring_color, max(2, int(2 * base)),
            )
            self._set_oval(
                self._inner, cx, cy, 4.9 * base,
                self._idle_color, 0,
            )

        self._set_focus_ring(cx, cy, base, focused)

    def _draw_active(self, cx, cy, base):
        # Time-based motion stays smooth even when Tk delivers a late frame.
        phase = time.monotonic() - self._started_at
        pulse = 0.5 + 0.5 * math.sin(phase * 2.15)
        breath = 0.5 + 0.5 * math.sin(phase * 1.35 + 0.9)
        spin = (phase * 92.0) % 360.0

        self._set_oval(
            self._halo_outer, cx, cy,
            (16.2 + 1.15 * pulse) * base,
            self._halo_color, 1, visible=True,
        )
        self._set_oval(
            self._halo_mid, cx, cy,
            (13.8 + 0.85 * breath) * base,
            self.BLUE_PALE, 1, visible=True,
        )
        self._set_arc(
            self._arc_a, cx, cy,
            (12.5 + 0.20 * pulse) * base,
            spin, 82, self.BLUE_LIGHT, max(2, int(2 * base)),
        )
        self._set_arc(
            self._arc_b, cx, cy,
            (14.7 + 0.30 * breath) * base,
            (360.0 - spin * 1.35) % 360.0,
            34, self.BLUE_PALE, max(1, int(1.5 * base)),
        )
        self._set_oval(
            self._ring, cx, cy, 11.2 * base,
            self._active_color, max(2, int(2.4 * base)),
        )
        self._set_oval(
            self._inner, cx, cy,
            (4.7 + 0.48 * math.sin(phase * 3.1)) * base,
            self._active_color, 0,
        )

        # Two orbiting sparks make the motion unmistakable even at 40 px.
        orbit = 13.7 * base
        for item, offset, radius, color in (
            (self._spark_a, 0.0, 2.0, self.BLUE),
            (self._spark_b, 180.0, 1.35, self.BLUE_PALE),
        ):
            angle = math.radians(spin + offset)
            self._set_dot(
                item,
                cx + orbit * math.cos(angle),
                cy - orbit * math.sin(angle),
                radius * base,
                color,
            )

    def _set_oval(self, item, cx, cy, radius, color, width, visible=True):
        self.coords(item, cx - radius, cy - radius, cx + radius, cy + radius)
        self.itemconfigure(
            item,
            state="normal" if visible else "hidden",
            outline="" if width <= 0 else color,
            fill=color if width <= 0 else "",
            width=max(1, int(width)) if width > 0 else 0,
        )

    def _set_arc(self, item, cx, cy, radius, start, extent, color, width):
        self.coords(item, cx - radius, cy - radius, cx + radius, cy + radius)
        self.itemconfigure(
            item,
            state="normal",
            start=start,
            extent=extent,
            outline=color,
            width=width,
        )

    def _set_dot(self, item, x, y, radius, color):
        self.coords(item, x - radius, y - radius, x + radius, y + radius)
        self.itemconfigure(item, state="normal", fill=color, outline="")

    def _set_focus_ring(self, cx, cy, base, focused):
        if not focused:
            self.itemconfigure(self._focus_ring, state="hidden")
            return
        radius = 17.6 * base
        self.coords(
            self._focus_ring,
            cx - radius, cy - radius, cx + radius, cy + radius,
        )
        self.itemconfigure(self._focus_ring, state="normal", outline="#C7D1DF")

    def _hide(self, *items):
        for item in items:
            self.itemconfigure(item, state="hidden")

    def _on_enter(self, _event=None):
        self._hover = True
        self._draw()

    def _on_leave(self, _event=None):
        self._hover = False
        self._draw()

    def _on_click(self, _event=None):
        try:
            self.focus_set()
        except Exception:
            pass
        self._invoke()
        return "break"

    def _on_key(self, _event=None):
        self._invoke()
        return "break"

    def _invoke(self):
        # One physical click must produce exactly one toggle.  A small guard
        # also protects against synthetic double events on some Windows setups.
        now = time.monotonic()
        if now - self._last_invoke < 0.30:
            return
        self._last_invoke = now
        if callable(self._command):
            self._command()

    def destroy(self):
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        super().destroy()
