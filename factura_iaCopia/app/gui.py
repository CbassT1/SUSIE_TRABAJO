# app/gui.py
from __future__ import annotations

import sys
import tkinter as tk

# Drag & Drop real (requiere que el root sea TkinterDnD.Tk)
try:
    from tkinterdnd2 import TkinterDnD  # type: ignore
    _HAS_DND = True
    _BaseTk = TkinterDnD.Tk  # type: ignore[attr-defined]
except Exception:
    TkinterDnD = None  # type: ignore
    _HAS_DND = False
    _BaseTk = tk.Tk

# ==========================
# Look & Feel
# ==========================

def _enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes  # pylint: disable=import-error
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _auto_tk_scaling(root: tk.Tk, scale_boost: float = 1.15) -> None:
    try:
        dpi = root.winfo_fpixels("1i")
        scaling = max(1.0, float(dpi) / 72.0) * float(scale_boost)
        root.tk.call("tk", "scaling", scaling)
    except Exception:
        pass


def _set_default_fonts(root: tk.Tk, base_size: int = 12) -> None:
    try:
        import tkinter.font as tkfont
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont", "TkTooltipFont"):
            f = tkfont.nametofont(name)
            f.configure(size=base_size)
    except Exception:
        pass


def _center_toplevel_on_parent(parent: tk.Tk, win: tk.Toplevel, w: int, h: int) -> None:
    parent.update_idletasks()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    x = px + (pw - w) // 2
    y = py + (ph - h) // 2
    win.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
