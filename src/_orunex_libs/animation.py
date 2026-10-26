import tkinter as tk

def fade_in(widget, alpha=0, step=0.05):
    if alpha < 1.0:
        widget.attributes("-alpha", alpha)
        widget.after(50, lambda: fade_in(widget, alpha + step))
    else:
        widget.attributes("-alpha", 1.0)

def fade_out(widget, alpha=1.0, step=0.05):
    if alpha > 0.0:
        widget.attributes("-alpha", alpha)
        widget.after(50, lambda: fade_out(widget, alpha - step))
    else:
        widget.destroy()
