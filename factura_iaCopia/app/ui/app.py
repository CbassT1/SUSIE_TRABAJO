# app/ui/app.py
from __future__ import annotations

import sys
from typing import Callable, Dict, List, Optional

import tkinter as tk
from tkinter import ttk

from app.models import Factura
from app.settings import AppSettings

from app.ui.theme import apply_theme, palette_dark, palette_light

# Frames (cada uno en su archivo)
from app.ui.frames.menu import MenuPrincipalFrame
from app.ui.frames.hacer_facturas import HacerFacturasFrame
from app.ui.frames.ajustar_archivos import AjustarArchivosFrame
from app.ui.frames.visor_facturas import VisorFacturasFrame

# Drag & Drop real (requiere que el root sea TkinterDnD.Tk)
try:
    from tkinterdnd2 import TkinterDnD  # type: ignore
    _BaseTk = TkinterDnD.Tk  # type: ignore[attr-defined]
except Exception:
    _BaseTk = tk.Tk


# ==========================
# Look & Feel (bootstrap)
# ==========================

def _enable_windows_dpi_awareness():
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


def _auto_tk_scaling(root: tk.Tk, scale_boost: float = 1.15):
    try:
        dpi = root.winfo_fpixels("1i")
        scaling = max(1.0, float(dpi) / 72.0) * float(scale_boost)
        root.tk.call("tk", "scaling", scaling)
    except Exception:
        pass


def _set_default_fonts(root: tk.Tk, base_size: int = 12):
    try:
        import tkinter.font as tkfont
        for name in (
            "TkDefaultFont", "TkTextFont", "TkMenuFont",
            "TkHeadingFont", "TkCaptionFont", "TkTooltipFont"
        ):
            f = tkfont.nametofont(name)
            f.configure(size=base_size)
    except Exception:
        pass


# ==========================
# App
# ==========================

class App(_BaseTk):
    def __init__(self, *, parse_excel_files: Callable[..., List[Factura]]):
        super().__init__()

        _enable_windows_dpi_awareness()
        _auto_tk_scaling(self, scale_boost=1.15)
        _set_default_fonts(self, base_size=12)

        self.title("S.U.S.I.E.")
        self.geometry("1400x820")
        self.minsize(1200, 720)

        # Settings persistentes
        self._settings = AppSettings.load()
        self._is_dark = bool(getattr(self._settings, "is_dark", True))

        apply_theme(self, palette_dark() if self._is_dark else palette_light())

        # Dependencia inyectada desde main.py
        self._parse_excel_files = parse_excel_files

        # Preferencias runtime (se guardan al cerrar)
        self.confirm_delete_files = bool(getattr(self._settings, "confirm_delete_files", True))
        self.use_pdf_ocr = bool(getattr(self._settings, "use_pdf_ocr", False))

        # Se usa por el visor para mapear basename->path real (última selección del usuario)
        self._last_input_paths: List[str] = []

        # Layout base
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Listo")
        status = ttk.Frame(self, style="Status.TFrame")
        status.pack(fill="x", side="bottom", padx=10, pady=(0, 8))
        self.lbl_status = ttk.Label(status, textvariable=self.status_var, style="Status.TLabel")
        self.lbl_status.pack(anchor="w")

        self.frames: Dict[str, ttk.Frame] = {}
        self._build_frames()
        self.show("menu")

        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- Routing / Frames ----------
    def _build_frames(self):
        self.frames["menu"] = MenuPrincipalFrame(self.container, controller=self)
        self.frames["hacer"] = HacerFacturasFrame(self.container, controller=self)
        self.frames["ajustes"] = AjustarArchivosFrame(self.container, controller=self)
        self.frames["visor"] = VisorFacturasFrame(self.container, controller=self, facturas=[])

        for f in self.frames.values():
            f.grid(row=0, column=0, sticky="nsew")
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)

    def show(self, key: str):
        self.frames[key].tkraise()

    # ---------- Status ----------
    def set_status(self, text: str, *, auto_clear_ms: Optional[int] = None):
        self.status_var.set(text)
        if auto_clear_ms:
            self.after(auto_clear_ms, lambda: self.status_var.set("Listo"))

    # ---------- Theme ----------
    def toggle_theme(self):
        self._is_dark = not self._is_dark
        pal = palette_dark() if self._is_dark else palette_light()
        apply_theme(self, pal)

        # Notificar a frames (solo si implementan on_theme_changed)
        for f in self.frames.values():
            if hasattr(f, "on_theme_changed"):
                try:
                    f.on_theme_changed()  # type: ignore[attr-defined]
                except Exception:
                    pass

    def theme_button_label(self) -> str:
        return "Modo claro" if self._is_dark else "Modo oscuro"

    # ---------- Parse ----------
    def parse_excel_files(self, paths: List[str]) -> List[Factura]:
        """
        Compat:
        - parse_excel_files(paths)
        - parse_excel_files(paths, use_pdf_ocr=bool)
        """
        try:
            return self._parse_excel_files(paths, use_pdf_ocr=bool(getattr(self, "use_pdf_ocr", False)))
        except TypeError:
            return self._parse_excel_files(paths)

    def open_visor(self, facturas: List[Factura]):
        visor: VisorFacturasFrame = self.frames["visor"]  # type: ignore[assignment]
        visor.set_facturas(facturas)
        self.show("visor")
        self.set_status(f"Se cargaron {len(facturas)} factura(s).", auto_clear_ms=2500)

    # ---------- Close / Save ----------
    def _on_close(self):
        try:
            self._settings.is_dark = bool(self._is_dark)
            self._settings.confirm_delete_files = bool(self.confirm_delete_files)
            self._settings.use_pdf_ocr = bool(getattr(self, "use_pdf_ocr", False))

            # Persistir anchos de columnas (si el visor los expone)
            visor = self.frames.get("visor")
            if visor is not None and hasattr(visor, "get_tree_col_widths"):
                self._settings.tree_col_widths = visor.get_tree_col_widths()

            self._settings.save()
        except Exception:
            pass
        self.destroy()

    # ---------- Shortcuts ----------
    def _bind_shortcuts(self):
        # Theme
        self.bind_all("<Control-l>", lambda _e: self.toggle_theme())
        self.bind_all("<Control-L>", lambda _e: self.toggle_theme())

        # Ctrl+O: delegar al frame "hacer" si está visible
        def _ctrl_o(_e=None):
            fr = self.frames.get("hacer")
            if fr and fr.winfo_ismapped() and hasattr(fr, "_select_files"):
                try:
                    fr._select_files()  # type: ignore[attr-defined]
                except Exception:
                    pass

        self.bind_all("<Control-o>", _ctrl_o)
        self.bind_all("<Control-O>", _ctrl_o)

        # Ctrl+F: delegar al visor si está visible
        def _ctrl_f(_e=None):
            fr = self.frames.get("visor")
            if fr and fr.winfo_ismapped() and hasattr(fr, "focus_search"):
                try:
                    fr.focus_search()  # type: ignore[attr-defined]
                except Exception:
                    pass

        self.bind_all("<Control-f>", _ctrl_f)
        self.bind_all("<Control-F>", _ctrl_f)
