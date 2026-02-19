# app/ui/frames/visor_facturas/panel_sheets.py

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Callable, Dict, List, Optional

from app.models import Factura
from app.ui.theme import get_pal
from app.ui.widgets.scrollbars import ModernScrollbar


class PanelSheets(ttk.Frame):
    def __init__(
        self,
        parent: ttk.Frame,
        *,
        controller,
        on_select_sheet: Callable[[Factura], None],
        get_by_file: Callable[[], Dict[str, List[Factura]]],
        get_facturas_list: Callable[[], List[Factura]],
        refresh_left_panel: Callable[[], None],
        autoselect_first_file: Callable[[], None],
    ):
        super().__init__(parent)

        self.controller = controller
        self._on_select_sheet = on_select_sheet
        self._get_by_file = get_by_file
        self._get_facturas_list = get_facturas_list
        self._refresh_left_panel = refresh_left_panel
        self._autoselect_first_file = autoselect_first_file

        self._sheet_buttons: Dict[int, ttk.Button] = {}
        self._active_sheet_key: Optional[int] = None

        self._sheet_menu: Optional[tk.Menu] = None
        self._sheet_menu_fact: Optional[Factura] = None

        self._sheets_window_id: Optional[int] = None

        self._build()

    # ---------------- Public API ----------------
    def clear(self):
        try:
            for w in self.sheets_frame.winfo_children():
                w.destroy()
        except Exception:
            pass
        self._sheet_buttons.clear()
        self._active_sheet_key = None
        self._sheet_menu_fact = None

        try:
            self.sheets_canvas.xview_moveto(0.0)
            self.sheets_canvas.configure(scrollregion=(0, 0, 0, self.sheets_canvas.winfo_height()))
        except Exception:
            pass

    def on_theme_changed(self):
        pal = get_pal(self.controller)

        # Canvas de chips
        try:
            self.sheets_canvas.configure(bg=pal["BG"])
        except Exception:
            pass

        # Scrollbar moderna
        try:
            if isinstance(self.sheets_scroll, ModernScrollbar):
                self.sheets_scroll.refresh_theme()
        except Exception:
            pass

        # Recalcular scrollregion
        try:
            self.controller.update_idletasks()
            req_w = self.sheets_frame.winfo_reqwidth()
            if self._sheets_window_id is not None:
                self.sheets_canvas.itemconfigure(self._sheets_window_id, width=req_w)
            self.sheets_canvas.configure(scrollregion=(0, 0, req_w, self.sheets_canvas.winfo_height()))
        except Exception:
            pass

        self._refresh_sheet_styles()

    def set_active_factura(self, fact: Optional[Factura]):
        if fact is None:
            self._active_sheet_key = None
            self._refresh_sheet_styles()
            return
        self._active_sheet_key = id(fact)
        self._refresh_sheet_styles()

    def render_for_file(self, archivo_key: str):
        self._render_sheet_chips(archivo_key)

    # ---------------- Build ----------------
    def _build(self):
        row = ttk.Frame(self)
        row.pack(fill="x", expand=True)

        ttk.Label(row, text="Hojas:", font=("Segoe UI", 11, "bold")).pack(side="left")

        pal = get_pal(self.controller)

        sheet_container = ttk.Frame(row)
        sheet_container.pack(side="left", fill="x", expand=True, padx=(10, 0))
        sheet_container.columnconfigure(0, weight=1)

        self.sheets_canvas = tk.Canvas(
            sheet_container,
            height=28,
            highlightthickness=0,
            bd=0,
            bg=pal["SURFACE"],
        )
        self.sheets_canvas.grid(row=0, column=0, sticky="ew")

        self.sheets_scroll = ModernScrollbar(
            sheet_container,
            orient="horizontal",
            command=self.sheets_canvas.xview,
            pal_getter=lambda: get_pal(self.controller),
            thickness=12,
            pad=6,
            bg_key="BG",
            track_key="BG",
            thumb_key="BORDER",
            active_key="ACCENT2",
            min_thumb=28,
        )
        self.sheets_scroll.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        self.sheets_canvas.configure(xscrollcommand=self.sheets_scroll.set)

        self.sheets_frame = ttk.Frame(self.sheets_canvas)
        self._sheets_window_id = self.sheets_canvas.create_window((0, 0), window=self.sheets_frame, anchor="nw")

        def _on_sheets_config(_event=None):
            self.sheets_canvas.configure(scrollregion=self.sheets_canvas.bbox("all"))
            try:
                req_w = self.sheets_frame.winfo_reqwidth()
                if self._sheets_window_id is not None:
                    self.sheets_canvas.itemconfigure(self._sheets_window_id, width=req_w)
            except Exception:
                pass

        def _on_canvas_resize(event):
            try:
                if self._sheets_window_id is not None:
                    self.sheets_canvas.itemconfigure(self._sheets_window_id, height=event.height)
            except Exception:
                pass

        self.sheets_frame.bind("<Configure>", _on_sheets_config)
        self.sheets_canvas.bind("<Configure>", _on_canvas_resize)

        # Wheel horizontal SOLO con SHIFT
        def _wheel_x(event):
            try:
                if not (event.state & 0x0001):  # SHIFT
                    return
                step = int(-1 * (event.delta / 120))
            except Exception:
                step = -1
            self.sheets_canvas.xview_scroll(step, "units")
            return "break"

        self.sheets_canvas.bind("<MouseWheel>", _wheel_x, add="+")
        self.sheets_canvas.bind("<Button-4>", lambda e: (self.sheets_canvas.xview_scroll(-1, "units"), "break")[1], add="+")
        self.sheets_canvas.bind("<Button-5>", lambda e: (self.sheets_canvas.xview_scroll(1, "units"), "break")[1], add="+")

        # Menú contextual
        self._sheet_menu = tk.Menu(self, tearoff=False)
        self._sheet_menu.add_command(label="Renombrar hoja…", command=self._on_ctx_rename_sheet)
        self._sheet_menu.add_separator()
        self._sheet_menu.add_command(label="Duplicar hoja", command=self._on_ctx_duplicate_sheet)
        self._sheet_menu.add_command(label="Eliminar hoja", command=self._on_ctx_delete_sheet)
        self._sheet_menu_fact = None

    # ---------------- Internal helpers ----------------
    def _file_key_for_fact(self, fact: Factura) -> str:
        return getattr(fact, "archivo_origen", None) or "SIN_ARCHIVO"

    def _next_sheet_name_for_file(self, archivo_key: str, base_name: Optional[str] = None) -> str:
        by_file = self._get_by_file()
        facts = by_file.get(archivo_key, []) or []
        existing = {(getattr(f, "hoja_origen", None) or "").strip() for f in facts}

        base = (base_name or "").strip() or f"Hoja {len(facts) + 1}"
        candidate = base
        n = 1
        while candidate in existing:
            suf = "copia" if n == 1 else f"copia {n}"
            candidate = f"{base} ({suf})"
            n += 1
        return candidate

    def _refresh_sheet_styles(self):
        for key, btn in self._sheet_buttons.items():
            btn.configure(style="SheetSel.TButton" if self._active_sheet_key == key else "Sheet.TButton")

    # ---------------- Render chips ----------------
    def _render_sheet_chips(self, archivo_key: str):
        for w in self.sheets_frame.winfo_children():
            w.destroy()

        self._sheet_buttons.clear()

        by_file = self._get_by_file()
        facturas = sorted(
            by_file.get(archivo_key, []) or [],
            key=lambda x: (getattr(x, "hoja_origen", None) or ""),
        )

        def mk_cmd(fact: Factura):
            return lambda f=fact: self._on_select_sheet(f)

        for i, f in enumerate(facturas):
            hoja = getattr(f, "hoja_origen", None) or f"(Hoja {i + 1})"
            key = id(f)
            min_chars = max(10, len(hoja) + 2)

            btn = ttk.Button(
                self.sheets_frame,
                text=hoja,
                style="SheetSel.TButton" if self._active_sheet_key == key else "Sheet.TButton",
                width=min_chars,
                command=mk_cmd(f),
            )
            btn.pack(side="left", padx=(0, 8), pady=2)
            self._sheet_buttons[key] = btn

            btn.bind("<Button-3>", lambda e, fact=f: self._show_sheet_context(e, fact))

        # Forzar layout + scrollregion correcto
        try:
            self.sheets_frame.update_idletasks()
            self.sheets_canvas.update_idletasks()

            h = max((b.winfo_reqheight() for b in self._sheet_buttons.values()), default=0)
            if h:
                new_h = h + 6
                self.sheets_canvas.configure(height=new_h)
                if self._sheets_window_id is not None:
                    self.sheets_canvas.itemconfigure(self._sheets_window_id, height=new_h)

            req_w = self.sheets_frame.winfo_reqwidth()
            if self._sheets_window_id is not None:
                self.sheets_canvas.itemconfigure(self._sheets_window_id, width=req_w)

            self.sheets_canvas.configure(scrollregion=(0, 0, req_w, self.sheets_canvas.winfo_height()))
            self.sheets_canvas.xview_moveto(0.0)
        except Exception:
            pass

    # ---------------- Context menu ----------------
    def _show_sheet_context(self, event: tk.Event, fact: Factura):
        self._sheet_menu_fact = fact
        # seleccionar la hoja donde se hace clic derecho
        try:
            self._on_select_sheet(fact)
        except Exception:
            pass

        if self._sheet_menu is not None:
            try:
                self._sheet_menu.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    self._sheet_menu.grab_release()
                except Exception:
                    pass

    def _on_ctx_rename_sheet(self):
        if not self._sheet_menu_fact:
            return

        fact = self._sheet_menu_fact
        archivo_key = self._file_key_for_fact(fact)

        old_name = (getattr(fact, "hoja_origen", None) or "").strip()

        new_name = simpledialog.askstring(
            "Renombrar hoja",
            "Nuevo nombre para la hoja:",
            initialvalue=old_name or "",
            parent=self,
        )
        if new_name is None:
            return

        new_name = new_name.strip()
        if not new_name:
            messagebox.showerror("Nombre inválido", "El nombre de la hoja no puede estar vacío.")
            return

        by_file = self._get_by_file()
        existing = {(getattr(f, "hoja_origen", None) or "").strip() for f in by_file.get(archivo_key, [])}
        if new_name in existing and new_name != old_name:
            messagebox.showerror("Nombre en uso", "Ya existe una hoja con ese nombre en este archivo.")
            return

        setattr(fact, "hoja_origen", new_name)

        self._render_sheet_chips(archivo_key)
        self.set_active_factura(fact)
        try:
            self.controller.set_status("Hoja renombrada.", auto_clear_ms=2000)
        except Exception:
            pass

    def _on_ctx_duplicate_sheet(self):
        if not self._sheet_menu_fact:
            return
        self._duplicate_sheet(self._sheet_menu_fact)

    def _on_ctx_delete_sheet(self):
        if not self._sheet_menu_fact:
            return
        self._delete_sheet(self._sheet_menu_fact)

    def _duplicate_sheet(self, fact: Factura):
        archivo_key = self._file_key_for_fact(fact)
        by_file = self._get_by_file()
        lst = by_file.get(archivo_key)
        if not lst:
            return

        new_fact = copy.deepcopy(fact)

        base_name = getattr(fact, "hoja_origen", None) or ""
        new_name = self._next_sheet_name_for_file(archivo_key, base_name)
        setattr(new_fact, "hoja_origen", new_name)

        lst.append(new_fact)
        self._get_facturas_list().append(new_fact)

        # refresca panel izquierdo (conteos/alertas)
        try:
            self._refresh_left_panel()
        except Exception:
            pass

        self._render_sheet_chips(archivo_key)
        self._on_select_sheet(new_fact)
        try:
            self.controller.set_status("Hoja duplicada.", auto_clear_ms=2000)
        except Exception:
            pass

    def _delete_sheet(self, fact: Factura):
        archivo_key = self._file_key_for_fact(fact)
        by_file = self._get_by_file()
        lst = by_file.get(archivo_key, []) or []
        if not lst:
            return

        if not messagebox.askyesno(
            "Eliminar hoja",
            "¿Quieres eliminar esta hoja de factura?\n"
            "Esta acción no se puede deshacer dentro del visor.",
        ):
            return

        try:
            lst.remove(fact)
        except ValueError:
            pass

        try:
            self._get_facturas_list().remove(fact)
        except ValueError:
            pass

        if not lst:
            by_file.pop(archivo_key, None)

        try:
            self._refresh_left_panel()
        except Exception:
            pass

        # seleccionar algo válido
        if archivo_key in by_file and by_file[archivo_key]:
            self._render_sheet_chips(archivo_key)
            facturas = sorted(by_file[archivo_key], key=lambda x: (getattr(x, "hoja_origen", "") or ""))
            self._on_select_sheet(facturas[0])
        else:
            # ya no hay hojas en ese archivo; seleccionar otro archivo si existe
            if by_file:
                self._autoselect_first_file()
            else:
                self.clear()

        try:
            self.controller.set_status("Hoja eliminada.", auto_clear_ms=2000)
        except Exception:
            pass
