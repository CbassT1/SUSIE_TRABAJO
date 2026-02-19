# app/ui/dialogs.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from app.ui.theme import get_pal


def _center_toplevel_on_parent(parent: tk.Misc, win: tk.Toplevel, w: int, h: int):
    # Centrado simple y estable (evita depender de utils por ahora)
    try:
        win.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        # fallback: solo set size
        try:
            win.geometry(f"{w}x{h}")
        except Exception:
            pass


class ConfirmDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, title: str, message: str, checkbox_text: str, *, use_ocr_default: bool = False):
        super().__init__(parent)

        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.result_yes = False
        self.var_skip = tk.BooleanVar(value=False)

        # OCR checkbox (si quieres usarlo)
        self.var_use_ocr = tk.BooleanVar(value=bool(use_ocr_default))

        pal = get_pal(parent)
        self.configure(bg=pal["BG"])

        wrap = ttk.Frame(self)
        wrap.pack(padx=18, pady=16)

        ttk.Label(wrap, text=message, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Checkbutton(
            wrap,
            text=checkbox_text,
            variable=self.var_skip,
            style="Card.TCheckbutton",
        ).pack(anchor="w", pady=(10, 0))

        btns = ttk.Frame(wrap)
        btns.pack(fill="x", pady=(14, 0))

        ttk.Checkbutton(
            btns,
            text="Usar OCR en PDF (si es escaneado)",
            variable=self.var_use_ocr,
        ).pack(side="right", padx=(6, 0))

        ttk.Button(btns, text="Cancelar", command=self._no).pack(side="right")
        ttk.Button(btns, text="Eliminar", style="Primary.TButton", command=self._yes).pack(side="right", padx=(0, 10))

        self.update_idletasks()
        _center_toplevel_on_parent(parent, self, 520, 190)

        self.bind("<Escape>", lambda _e: self._no())
        self.bind("<Return>", lambda _e: self._yes())

    def _yes(self):
        self.result_yes = True
        self.destroy()

    def _no(self):
        self.result_yes = False
        self.destroy()
