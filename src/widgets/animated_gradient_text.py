"""Premium animated gradient headline used by the empty chat state.

Pillow renders the text mask at 3x for smooth edges. NumPy builds the cyclic
violet/blue gradient frames, and Pillow composites the mask and a subtle glow
over the surface colour. A time-based Tk loop drives the fade-in and the slow
gradient drift at about 30 fps. Everything stays local to the desktop app.
"""

from __future__ import annotations

import math
import os
import time
import tkinter as tk
from typing import Optional, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk


class AnimatedGradientText(tk.Canvas):
    """A clean, animated gradient headline.

    Parameters
    ----------
    master:
        Parent Tk widget.
    text:
        Text to render.
    font_size:
        Display font size in pixels.
    bg:
        Surface colour behind the text.  The canvas is composited against this
        colour so the glow and anti-aliased edges blend cleanly.
    colors:
        Cyclic gradient palette.  The first and last colours should match to
        avoid a visible seam when the gradient loops.
    """

    FONT_CANDIDATES = (
        r"C:\Windows\Fonts\seguisb.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    )

    def __init__(
        self,
        master,
        text: str = "At your service",
        font_size: int = 52,
        bg: str = "#FFFFFF",
        colors: Optional[Sequence[str]] = None,
        glow_color: str = "#8B5CF6",
        **kwargs,
    ):
        self._text = str(text)
        self._font_size = max(16, int(font_size))
        self._bg = bg
        self._glow_color = self._hex_rgb(glow_color)
        self._palette = self._build_palette(colors)
        self._render_scale = 3
        self._fade_duration = 0.9
        self._started_at: Optional[float] = None
        self._after_id: Optional[str] = None
        self._photo: Optional[ImageTk.PhotoImage] = None
        self._item: Optional[int] = None
        self._text_mask = None
        self._glow_mask = None
        self._mask_size = (1, 1)
        self._display_size = (1, 1)

        self._build_masks()

        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("bd", 0)
        super().__init__(
            master,
            width=self._display_size[0],
            height=self._display_size[1],
            bg=bg,
            **kwargs,
        )
        self._item = self.create_image(
            self._display_size[0] // 2,
            self._display_size[1] // 2,
            anchor="center",
        )
        self._render_frame(0.0, 0.0)
        self.start()

    @staticmethod
    def _hex_rgb(value: str):
        value = value.lstrip("#")
        if len(value) == 3:
            value = "".join(ch * 2 for ch in value)
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))

    def _build_palette(self, colors: Optional[Sequence[str]]):
        source = list(colors or (
            "#7C3AED",  # violet
            "#8B5CF6",  # light violet
            "#6366F1",  # indigo
            "#2563EB",  # blue
            "#3B82F6",  # bright blue
            "#7C3AED",  # loop back to violet
        ))
        if len(source) < 2:
            source = ["#7C3AED", "#2563EB", "#7C3AED"]
        if source[0] != source[-1]:
            source.append(source[0])
        return np.asarray(
            [self._hex_rgb(color) for color in source],
            dtype=np.float32,
        ) / 255.0

    @classmethod
    def _find_font(cls):
        for path in cls.FONT_CANDIDATES:
            if os.path.exists(path):
                return path
        return None

    def _build_masks(self):
        scale = self._render_scale
        font_path = self._find_font()
        if font_path:
            font = ImageFont.truetype(font_path, self._font_size * scale)
        else:
            font = ImageFont.load_default()

        probe = Image.new("L", (8, 8), 0)
        bbox = ImageDraw.Draw(probe).textbbox(
            (0, 0), self._text, font=font
        )
        text_w = max(1, bbox[2] - bbox[0])
        text_h = max(1, bbox[3] - bbox[1])
        pad_x = 28 * scale
        pad_y = 20 * scale
        width = text_w + pad_x * 2
        height = text_h + pad_y * 2

        mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(mask).text(
            (pad_x - bbox[0], pad_y - bbox[1]),
            self._text,
            font=font,
            fill=255,
        )
        glow = mask.filter(
            ImageFilter.GaussianBlur(max(2, int(5.5 * scale)))
        )
        display_w = max(320, int(round(width / scale)))
        display_h = max(64, int(round(height / scale)))
        # Downsample the masks once.  The animation then composites at display
        # resolution instead of paying for a Lanczos resize on every frame.
        self._text_mask = mask.resize(
            (display_w, display_h), Image.Resampling.LANCZOS
        )
        self._glow_mask = glow.resize(
            (display_w, display_h), Image.Resampling.LANCZOS
        )
        self._mask_size = (display_w, display_h)
        self._display_size = (display_w, display_h)

    def _gradient(self, width: int, height: int, phase: float):
        xs = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
        ys = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
        # Diagonal drift keeps the colour flow organic instead of a flat wipe.
        t = (xs * 0.82 + ys * 0.10 + phase) % 1.0
        positions = np.linspace(
            0.0, 1.0, self._palette.shape[0], dtype=np.float32
        )
        channels = [
            np.interp(
                t,
                positions,
                self._palette[:, channel],
            ).astype(np.float32)
            for channel in range(3)
        ]
        image = np.stack(channels, axis=-1)
        # A very soft moving sheen, not a flashing highlight.
        sheen = 0.95 + 0.05 * (
            0.5 + 0.5 * np.sin((xs * 2.1 - phase * 2.0) * math.tau)
        )
        image *= sheen[:, :, None]
        return Image.fromarray(
            (np.clip(image, 0.0, 1.0) * 255.0).astype(np.uint8),
            "RGB",
        )

    def _render_frame(self, fade: float, elapsed: float):
        if self._text_mask is None or self._glow_mask is None:
            return
        width, height = self._mask_size
        phase = (elapsed * 0.095) % 1.0
        gradient = self._gradient(width, height, phase)

        surface = Image.new("RGB", (width, height), self._bg)
        if fade > 0.0:
            glow_alpha = self._glow_mask.point(
                lambda value: int(value * 0.18 * fade)
            )
            glow = Image.new("RGB", (width, height), self._glow_color)
            surface = Image.composite(glow, surface, glow_alpha)

        text_alpha = self._text_mask.point(
            lambda value: int(value * max(0.0, min(1.0, fade)))
        )
        image = Image.composite(gradient, surface, text_alpha)
        self._photo = ImageTk.PhotoImage(image)
        if self._item is not None:
            self.itemconfigure(self._item, image=self._photo)

    def start(self):
        """Begin (or resume) the fade-in and gradient loop."""
        if self._after_id is not None:
            return
        self._started_at = None
        self._schedule(0)

    def stop(self):
        """Pause the loop without destroying the widget."""
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._started_at = None

    def _schedule(self, delay_ms: int = 34):
        if self._after_id is not None:
            return
        try:
            self._after_id = self.after(delay_ms, self._animate)
        except Exception:
            self._after_id = None

    def _animate(self):
        self._after_id = None
        if not self.winfo_exists():
            return
        if not self.winfo_ismapped():
            self._schedule(220)
            return

        now = time.monotonic()
        if self._started_at is None:
            self._started_at = now
        elapsed = now - self._started_at
        fade_t = min(1.0, elapsed / self._fade_duration)
        # Ease-out cubic: quick but soft entrance, no abrupt stop.
        fade = 1.0 - (1.0 - fade_t) ** 3
        self._render_frame(fade, elapsed)
        self._schedule(34)

    def destroy(self):
        self.stop()
        super().destroy()
