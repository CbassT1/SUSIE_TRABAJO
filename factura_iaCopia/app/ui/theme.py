# app/ui/theme.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def palette_dark() -> dict:
    return {
        "BG": "#0b1220",
        "SURFACE": "#0f1a2b",
        "SURFACE2": "#111f36",
        "BORDER": "#22314d",
        "TEXT": "#e5e7eb",
        "MUTED": "#9aa4b2",
        "ACCENT": "#7c3aed",
        "ACCENT2": "#5b21b6",
        "ROW_ALT": "#0d1829",
        "LIST_SELECT": "#5b21b6",
        "WARN": "#f59e0b",
        "DANGER": "#ef4444",
        "SUCCESS": "#22c55e",
    }


def palette_light() -> dict:
    return {
        "BG": "#f3f4f6",
        "SURFACE": "#ffffff",
        "SURFACE2": "#eef2ff",
        "BORDER": "#cbd5e1",
        "TEXT": "#111827",
        "MUTED": "#475569",
        "ACCENT": "#4f46e5",
        "ACCENT2": "#4338ca",
        "ROW_ALT": "#f8fafc",
        "LIST_SELECT": "#c7d2fe",
        "WARN": "#b45309",
        "DANGER": "#b91c1c",
        "SUCCESS": "#15803d",
    }


def get_pal(widget_or_root: tk.Misc) -> dict:
    """
    SIEMPRE toma la paleta desde el toplevel (App).
    Así evitas que ttk use una paleta y tk otra.
    """
    try:
        root = widget_or_root.winfo_toplevel()
    except Exception:
        root = widget_or_root

    pal = getattr(root, "_ui_palette", None)
    if isinstance(pal, dict) and pal:
        return pal

    return palette_light()


def restyle_listbox(widget_or_root: tk.Misc, lb: tk.Listbox) -> None:
    pal = get_pal(widget_or_root)
    lb.configure(
        bg=pal["SURFACE"],
        fg=pal["TEXT"],
        selectbackground=pal["LIST_SELECT"],
        selectforeground=pal["TEXT"],
        highlightbackground=pal["BORDER"],
    )


def apply_theme(root: tk.Tk, pal: dict) -> None:
    """
    Aplica estilos ttk y fija la paleta para que get_pal() funcione.
    """
    root._ui_palette = pal  # <- fuente de verdad

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    BG = pal["BG"]
    SURFACE = pal["SURFACE"]
    SURFACE2 = pal["SURFACE2"]
    BORDER = pal["BORDER"]
    TEXT = pal["TEXT"]
    MUTED = pal["MUTED"]
    ACCENT = pal["ACCENT"]
    ACCENT2 = pal["ACCENT2"]
    WARN = pal["WARN"]
    DANGER = pal["DANGER"]
    SUCCESS = pal["SUCCESS"]

    root.configure(bg=BG)

    # ---------- Base ----------
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)

    style.configure("TLabelframe", background=BG, foreground=TEXT, bordercolor=BORDER)
    style.configure("TLabelframe.Label", background=BG, foreground=TEXT)

    # ---------- Entry ----------
    style.configure(
        "TEntry",
        fieldbackground=SURFACE,
        background=SURFACE,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=(10, 7),
    )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", SURFACE2)],
        foreground=[("disabled", MUTED)],
        bordercolor=[("focus", ACCENT), ("active", ACCENT)],
        lightcolor=[("focus", ACCENT), ("active", ACCENT)],
        darkcolor=[("focus", ACCENT), ("active", ACCENT)],
    )

    # ---------- Combobox ----------
    style.configure(
        "TCombobox",
        fieldbackground=SURFACE,
        background=SURFACE,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=(10, 7),
        arrowsize=14,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", SURFACE), ("disabled", SURFACE2)],
        foreground=[("disabled", MUTED)],
        bordercolor=[("focus", ACCENT), ("active", ACCENT)],
    )

    # ---------- Notebook ----------
    style.configure("TNotebook", background=BG, bordercolor=BORDER)
    style.configure("TNotebook.Tab", padding=(12, 8), background=SURFACE2, foreground=TEXT)
    style.map(
        "TNotebook.Tab",
        background=[("selected", SURFACE), ("active", SURFACE)],
        foreground=[("selected", TEXT), ("active", TEXT)],
    )

    # ---------- Checks / Radios ----------
    style.configure("TCheckbutton", background=BG, foreground=TEXT, padding=(6, 3))
    style.map(
        "TCheckbutton",
        background=[("active", BG)],
        foreground=[("disabled", MUTED)],
        indicatorbackground=[("active", SURFACE2), ("pressed", SURFACE2)],
        indicatorcolor=[("selected", ACCENT), ("active", ACCENT)],
    )

    style.configure("TRadiobutton", background=BG, foreground=TEXT, padding=(6, 3))
    style.map(
        "TRadiobutton",
        background=[("active", BG)],
        foreground=[("disabled", MUTED)],
        indicatorbackground=[("active", SURFACE2), ("pressed", SURFACE2)],
        indicatorcolor=[("selected", ACCENT), ("active", ACCENT)],
    )

    style.configure("TSeparator", background=BORDER)

    # ---------- Buttons ----------
    style.configure(
        "TButton",
        padding=(10, 7),
        background=SURFACE,
        foreground=TEXT,
        bordercolor=BORDER,
        relief="solid",
    )
    style.map(
        "TButton",
        background=[("active", SURFACE2), ("pressed", SURFACE2)],
        bordercolor=[("active", ACCENT), ("pressed", ACCENT)],
        foreground=[("disabled", MUTED)],
    )

    style.configure(
        "Primary.TButton",
        padding=(10, 7),
        background=ACCENT,
        foreground="#ffffff",
        bordercolor=ACCENT,
        relief="solid",
    )
    style.map(
        "Primary.TButton",
        background=[("active", ACCENT2), ("pressed", ACCENT2)],
        bordercolor=[("active", ACCENT2), ("pressed", ACCENT2)],
        foreground=[("disabled", MUTED)],
    )

    # Botones grandes del menú principal
    style.configure(
        "MenuBig.TButton",
        font=("Segoe UI", 16, "bold"),
        padding=(26, 18),
        background=SURFACE,
        foreground=TEXT,
        bordercolor=BORDER,
        relief="solid",
        focusthickness=1,
        focuscolor=BORDER,
    )
    style.map(
        "MenuBig.TButton",
        background=[("active", SURFACE2), ("pressed", SURFACE2)],
        bordercolor=[("active", ACCENT), ("pressed", ACCENT)],
        focuscolor=[("focus", ACCENT), ("!focus", BORDER)],
    )

    style.configure(
        "Danger.TButton",
        padding=(10, 7),
        background=DANGER,
        foreground="#ffffff",
        bordercolor=DANGER,
        relief="solid",
    )

    # ---------- Treeview ----------
    style.configure(
        "Treeview",
        background=SURFACE,
        foreground=TEXT,
        fieldbackground=SURFACE,
        bordercolor=BORDER,
        relief="solid",
        rowheight=26,
    )
    style.map("Treeview", background=[("selected", ACCENT2)], foreground=[("selected", "#ffffff")])

    # Heading normal
    style.configure(
        "Treeview.Heading",
        background=SURFACE2,
        foreground=TEXT,
        relief="flat",
        padding=(10, 8),
    )
    # FIX: evitar hover blanco en encabezados
    style.map(
        "Treeview.Heading",
        background=[("active", SURFACE2), ("pressed", SURFACE2)],
        foreground=[("active", TEXT), ("pressed", TEXT)],
        relief=[("pressed", "flat"), ("active", "flat")],
    )

    # ---------- Dialog / Popup styles (para buscador de claves/unidades) ----------
    style.configure("Dialog.TFrame", background=BG)
    style.configure("DialogCard.TFrame", background=SURFACE)
    style.configure("Dialog.TLabel", background=BG, foreground=TEXT)
    style.configure("DialogMuted.TLabel", background=BG, foreground=MUTED)

    style.configure(
        "Dialog.TEntry",
        fieldbackground=SURFACE,
        foreground=TEXT,
    )

    style.configure(
        "Dialog.Treeview",
        background=SURFACE,
        foreground=TEXT,
        fieldbackground=SURFACE,
        bordercolor=BORDER,
        relief="solid",
        rowheight=26,
    )
    style.map("Dialog.Treeview", background=[("selected", ACCENT2)], foreground=[("selected", "#ffffff")])

    style.configure(
        "Dialog.Treeview.Heading",
        background=SURFACE2,
        foreground=TEXT,
        relief="flat",
        padding=(10, 8),
    )
    style.map(
        "Dialog.Treeview.Heading",
        background=[("active", SURFACE2), ("pressed", SURFACE2)],
        foreground=[("active", TEXT), ("pressed", TEXT)],
        relief=[("pressed", "flat"), ("active", "flat")],
    )

    # ---------- Progressbar ----------
    style.configure(
        "TProgressbar",
        troughcolor=SURFACE2,
        background=ACCENT,
        bordercolor=BORDER,
        lightcolor=ACCENT,
        darkcolor=ACCENT2,
    )

    # ---------- Status labels ----------
    style.configure("Warn.TLabel", background=BG, foreground=WARN)
    style.configure("Danger.TLabel", background=BG, foreground=DANGER)
    style.configure("Success.TLabel", background=BG, foreground=SUCCESS)
