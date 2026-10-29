"""Full-screen viewer for the controlled Orunex demo chart.

The image itself already carries the "controlled historical scenario / paper
demo" labels.  This viewer only presents it cleanly for the hackathon video;
it has no trading controls and never talks to a broker.
"""

from __future__ import annotations

import argparse
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parent
DEFAULT_CHART = ROOT / "charts" / "btcusdt_1h_pullback.png"


def main() -> int:
    parser = argparse.ArgumentParser(description="Show the Orunex demo chart")
    parser.add_argument("--chart", default=str(DEFAULT_CHART))
    parser.add_argument("--seconds", type=float, default=0.0)
    args = parser.parse_args()

    chart_path = Path(args.chart).expanduser().resolve()
    if not chart_path.is_file():
        raise SystemExit(f"Chart not found: {chart_path}")

    root = tk.Tk()
    root.title("Orunex Demo Chart — BTCUSDT 1h")
    root.configure(bg="#05070d")
    root.attributes("-fullscreen", True)
    # Launched from a background recorder, Tk cannot always win the Windows
    # foreground lock; topmost still guarantees the chart is what the video
    # sees.  The recorder closes this process before returning to Orunex.
    root.attributes("-topmost", True)
    root.bind("<Escape>", lambda _event: root.destroy())
    root.bind("<q>", lambda _event: root.destroy())

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    margin = 24
    max_w = max(320, screen_w - margin * 2)
    max_h = max(240, screen_h - margin * 2)

    image = Image.open(chart_path).convert("RGB")
    scale = min(max_w / image.width, max_h / image.height)
    size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    image = image.resize(size, Image.LANCZOS)
    photo = ImageTk.PhotoImage(image)

    label = tk.Label(root, image=photo, bg="#05070d", bd=0)
    label.image = photo  # type: ignore[attr-defined]
    label.place(relx=0.5, rely=0.5, anchor="center")

    if args.seconds and args.seconds > 0:
        root.after(int(args.seconds * 1000), root.destroy)

    root.lift()
    try:
        root.focus_force()
    except Exception:
        pass
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
