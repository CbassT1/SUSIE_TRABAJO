from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import messagebox


def parse_dnd_file_list(raw: str) -> List[str]:
    raw = str(raw)
    paths: List[str] = []
    buf = ""
    in_brace = False

    for ch in raw:
        if ch == "{":
            in_brace = True
            buf = ""
        elif ch == "}":
            in_brace = False
            if buf.strip():
                paths.append(buf.strip())
            buf = ""
        elif ch == " " and not in_brace:
            if buf.strip():
                paths.append(buf.strip())
            buf = ""
        else:
            buf += ch

    if buf.strip():
        paths.append(buf.strip())

    return paths


def open_file_native(path: str, parent: Optional[tk.Widget] = None) -> None:
    path = str(path)
    if not os.path.exists(path):
        messagebox.showerror("No encontrado", f"No existe:\n{path}", parent=parent)
        return

    sysname = platform.system().lower()
    try:
        if "windows" in sysname:
            os.startfile(path)  # type: ignore[attr-defined]
        elif "darwin" in sysname:
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo abrir:\n{path}\n\n{e}", parent=parent)


def center_toplevel_on_parent(controller: Any, dlg: tk.Toplevel, w: int, h: int) -> None:
    """
    Centra dlg respecto a la ventana principal (controller.winfo_toplevel()).
    """
    try:
        root = controller.winfo_toplevel()
        root.update_idletasks()

        rx = root.winfo_rootx()
        ry = root.winfo_rooty()
        rw = root.winfo_width()
        rh = root.winfo_height()

        x = rx + (rw // 2) - (w // 2)
        y = ry + (rh // 2) - (h // 2)

        dlg.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")
    except Exception:
        # fallback centro de pantalla
        try:
            sw = dlg.winfo_screenwidth()
            sh = dlg.winfo_screenheight()
            x = (sw // 2) - (w // 2)
            y = (sh // 2) - (h // 2)
            dlg.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            pass

