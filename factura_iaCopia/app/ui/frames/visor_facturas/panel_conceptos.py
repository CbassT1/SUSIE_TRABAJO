from __future__ import annotations

# --- stdlib ---
import re
from decimal import Decimal, InvalidOperation
from typing import Callable, Dict, List, Optional, Tuple

# --- tkinter / ttk ---
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

# --- theme / ui helpers ---
from app.ui.theme import get_pal

# --- widgets ---
from app.ui.widgets.scrollbars import ModernScrollbar

# --- modelos ---
from app.models import Factura, Concepto

# --- Catalogs ---
from app.ui.frames.visor_facturas.catalogs import Catalogs


class PanelConceptos(ttk.Frame):
    """
    Panel autocontenido para la tabla de conceptos:
    - búsqueda
    - treeview con scrollbars modernas
    - detalle inferior (concepto completo + precio)
    - total al final
    - edición por doble click
    - menú contextual: copiar/cortar/pegar/duplicar/eliminar/buscar clave
    """

    def __init__(
        self,
        master: ttk.Frame,
        *,
        controller,
        catalogs: Catalogs,
        get_factura: Callable[[], Optional[Factura]],
        mark_saved: Callable[[str], None],
        default_col_widths: Optional[Dict[str, int]] = None,
    ):
        super().__init__(master)

        self.controller = controller
        self.catalogs = catalogs
        self._get_factura = get_factura
        self._mark_saved = mark_saved

        self._default_col_widths = default_col_widths or {
            "cantidad": 80,
            "clv_unid": 110,
            "unid_nombre": 260,
            "clv_prod": 150,
            "prod_nombre": 360,
            "concepto": 760,
            "p_unit": 260,
        }

        self.var_search = tk.StringVar(value="")

        self._conceptos_cache: List[Concepto] = []
        self._tree_item_to_concepto: Dict[str, Concepto] = {}

        # context menu
        self._tree_ctx_menu = None
        self._ctx_iid = None
        self._ctx_col = None
        self._concept_clipboard: List[Concepto] = []

        self._build()

    # ---------------- UI ----------------
    def _build(self):
        head = ttk.Frame(self)
        head.pack(fill="x", pady=(0, 8))

        ttk.Label(head, text="Buscar", style="Muted.TLabel").pack(side="left")
        self.ent_search = ttk.Entry(head, textvariable=self.var_search, width=36)
        self.ent_search.pack(side="left", padx=(10, 10))
        self.ent_search.bind("<KeyRelease>", lambda _e: self._apply_filter())

        ttk.Button(head, text="Reset columnas", command=self._reset_columns).pack(side="right")

        self.frm_conceptos = ttk.Frame(self)
        self.frm_conceptos.pack(fill="both", expand=True)

        self.frm_conceptos.columnconfigure(0, weight=1)
        self.frm_conceptos.rowconfigure(0, weight=1)

        cols = ("cantidad", "clv_unid", "unid_nombre", "clv_prod", "prod_nombre", "concepto", "p_unit")
        self.tree = ttk.Treeview(
            self.frm_conceptos,
            columns=cols,
            show="headings",
            selectmode="browse",
            style="Concepts.Treeview",
        )

        self.tree.heading("cantidad", text="Cant.")
        self.tree.heading("clv_unid", text="Clave unid.")
        self.tree.heading("unid_nombre", text="Unidad (nombre)")
        self.tree.heading("clv_prod", text="Clave prod/serv")
        self.tree.heading("prod_nombre", text="Prod/serv (nombre)")
        self.tree.heading("concepto", text="Concepto")
        self.tree.heading("p_unit", text="Precio unitario")

        self.tree["displaycolumns"] = cols

        self.tree.column("cantidad", width=80, anchor="w", stretch=False)
        self.tree.column("clv_unid", width=110, anchor="center", stretch=False)
        self.tree.column("unid_nombre", width=240, anchor="w", stretch=False)
        self.tree.column("clv_prod", width=150, anchor="center", stretch=False)
        self.tree.column("prod_nombre", width=320, anchor="w", stretch=False)
        self.tree.column("concepto", width=520, minwidth=260, anchor="w", stretch=True)
        self.tree.column("p_unit", width=220, minwidth=180, anchor="e", stretch=False)

        # Persisted widths si existen en settings
        try:
            if getattr(self.controller, "_settings", None):
                self.apply_tree_col_widths(self.controller._settings.tree_col_widths)
        except Exception:
            pass

        pal_getter = lambda: get_pal(self.controller)

        self.vsb_conceptos = ModernScrollbar(
            self.frm_conceptos,
            orient="vertical",
            command=self.tree.yview,
            pal_getter=pal_getter,
            thickness=12,
            pad=6,
            bg_key="BG",
            track_key="SURFACE2",
            thumb_key="BORDER",
            active_key="ACCENT2",
            min_thumb=28,
        )
        self.hsb_conceptos = ModernScrollbar(
            self.frm_conceptos,
            orient="horizontal",
            command=self.tree.xview,
            pal_getter=pal_getter,
            thickness=12,
            pad=6,
            bg_key="BG",
            track_key="SURFACE2",
            thumb_key="BORDER",
            active_key="ACCENT2",
            min_thumb=28,
        )

        self.tree.configure(yscrollcommand=self.vsb_conceptos.set, xscrollcommand=self.hsb_conceptos.set)

        self.tree.grid(row=0, column=0, sticky="nsew", padx=2, pady=(2, 0))
        self.vsb_conceptos.grid(row=0, column=1, sticky="ns", pady=(2, 0))
        self.hsb_conceptos.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 6))

        # --- detalle inferior ---
        detail = ttk.Frame(self.frm_conceptos)
        detail.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(2, 6))
        detail.columnconfigure(1, weight=1)

        ttk.Label(detail, text="Concepto (completo):", style="Muted.TLabel").grid(row=0, column=0, sticky="nw", padx=(0, 8))
        self.lbl_concepto_full = ttk.Label(detail, text="—", wraplength=980, justify="left")
        self.lbl_concepto_full.grid(row=0, column=1, sticky="ew")

        ttk.Label(detail, text="Precio unitario:", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 0), padx=(0, 8))
        self.lbl_precio_full = ttk.Label(detail, text="—", font=("Segoe UI", 11, "bold"))
        self.lbl_precio_full.grid(row=1, column=1, sticky="w", pady=(6, 0))

        footer = ttk.Frame(self.frm_conceptos)
        footer.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 6))
        self.lbl_total = ttk.Label(footer, text="TOTAL: —", font=("Segoe UI", 14, "bold"))
        self.lbl_total.pack(side="right")

        # binds
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        try:
            self._apply_tree_base_style()
            self._apply_tree_tags_theme()
        except Exception:
            pass

        self._apply_tree_tags_theme()

    # -------------- Public API --------------
    def clear(self):
        self._conceptos_cache = []
        self.var_search.set("")
        self._tree_item_to_concepto.clear()
        try:
            for it in self.tree.get_children():
                self.tree.delete(it)
        except Exception:
            pass
        self._set_detail("—", "—")
        try:
            self.lbl_total.config(text="TOTAL: —")
        except Exception:
            pass

    def set_factura(self, fact: Optional[Factura]):
        if not fact:
            self.clear()
            return
        conceptos = list(getattr(fact, "conceptos", []) or [])
        self._conceptos_cache = conceptos
        self._render_conceptos(conceptos)
        self._recalc_factura_total_from_conceptos()

    def focus_search(self):
        try:
            self.ent_search.focus_set()
            self.ent_search.select_range(0, tk.END)
        except Exception:
            pass

    def on_theme_changed(self):
        # tags del tree + scrollbars
        try:
            self._apply_tree_tags_theme()
        except Exception:
            pass
        try:
            if hasattr(self, "vsb_conceptos") and isinstance(self.vsb_conceptos, ModernScrollbar):
                self.vsb_conceptos.refresh_theme()
            if hasattr(self, "hsb_conceptos") and isinstance(self.hsb_conceptos, ModernScrollbar):
                self.hsb_conceptos.refresh_theme()
        except Exception:
            pass

    # -------------- Column widths helpers --------------
    def apply_tree_col_widths(self, widths: Dict[str, int]):
        if not widths:
            return
        for k, w in widths.items():
            try:
                if k in self.tree["columns"]:
                    self.tree.column(k, width=int(w))
            except Exception:
                pass

    def _reset_columns(self):
        for k, w in self._default_col_widths.items():
            try:
                self.tree.column(k, width=w)
            except Exception:
                pass
        try:
            self.controller.set_status("Columnas restablecidas.", auto_clear_ms=1500)
        except Exception:
            pass

    # -------------- Rendering / filter --------------
    def _render_conceptos(self, conceptos: List[Concepto]):
        try:
            for it in self.tree.get_children():
                self.tree.delete(it)
        except Exception:
            pass
        self._tree_item_to_concepto.clear()

        for idx, c in enumerate(conceptos):
            tag = "even" if idx % 2 == 0 else "odd"
            iid = f"c{idx}"

            cantidad = getattr(c, "cantidad", "")
            clv_unid = getattr(c, "clave_unidad", "") or ""
            clv_prod = getattr(c, "clave_prod_serv", "") or ""
            concepto = getattr(c, "concepto", "") or ""

            p_unit = getattr(c, "precio_unitario", None)
            p_unit_s = self.catalogs.num_to_full_str(p_unit)

            values = (
                cantidad,
                clv_unid,
                self.catalogs.unid_name(clv_unid),
                clv_prod,
                self.catalogs.prod_name(clv_prod),
                concepto,
                p_unit_s,
            )

            try:
                self.tree.insert("", "end", iid=iid, values=values, tags=(tag,))
                self._tree_item_to_concepto[iid] = c
            except Exception:
                pass

        self._autofit_columns(("unid_nombre", "prod_nombre", "p_unit"), max_px=520, min_px=140)

    def _apply_filter(self):
        q = (self.var_search.get() or "").strip().lower()
        if not q:
            self._render_conceptos(self._conceptos_cache)
            return

        def _to_str(x) -> str:
            try:
                return str(x or "")
            except Exception:
                return ""

        filtered = []
        for c in self._conceptos_cache:
            hay = " ".join(
                [
                    _to_str(getattr(c, "concepto", "")),
                    _to_str(getattr(c, "clave_prod_serv", "")),
                    _to_str(getattr(c, "clave_unidad", "")),
                    _to_str(getattr(c, "precio_unitario", "")),
                ]
            ).lower()
            if q in hay:
                filtered.append(c)

        self._render_conceptos(filtered)
        try:
            self.controller.set_status(f"Filtro: {len(filtered)} concepto(s) coinciden.", auto_clear_ms=1500)
        except Exception:
            pass

    # -------------- Theme tags --------------
    def _apply_tree_tags_theme(self):
        pal = get_pal(self.controller)
        try:
            self.tree.tag_configure("odd", background=pal["ROW_ALT"])
            self.tree.tag_configure("even", background=pal["SURFACE"])
        except Exception:
            pass

    # -------------- Autofit --------------
    def _autofit_columns(self, col_ids: Tuple[str, ...], *, max_px: int = 520, min_px: int = 90, padding: int = 26):
        if not getattr(self, "tree", None):
            return
        try:
            f = tkfont.nametofont("TkDefaultFont")
            measure = f.measure
        except Exception:
            measure = lambda s: len(str(s)) * 8

        for col in col_ids:
            try:
                max_w = measure(self.tree.heading(col, option="text")) + padding
                for iid in self.tree.get_children(""):
                    vals = self.tree.item(iid, "values") or ()
                    idx = self.tree["columns"].index(col)
                    if idx < len(vals):
                        w = measure(str(vals[idx])) + padding
                        if w > max_w:
                            max_w = w
                max_w = max(min_px, min(int(max_w), max_px))
                self.tree.column(col, width=max_w)
            except Exception:
                pass

    # -------------- Selection detail --------------
    def _on_tree_select(self, _event=None):
        try:
            sel = self.tree.selection()
            if not sel:
                self._set_detail("—", "—")
                return

            row_id = sel[0]
            values = self.tree.item(row_id, "values") or ()
            cols = self.tree["columns"]

            def _get(col_name: str) -> str:
                try:
                    idx = list(cols).index(col_name)
                    if idx < len(values):
                        return "" if values[idx] is None else str(values[idx])
                except Exception:
                    pass
                return ""

            concepto = _get("concepto").strip() or "—"
            precio = _get("p_unit").strip() or "—"
            self._set_detail(concepto, precio)
        except Exception:
            self._set_detail("—", "—")

    def _set_detail(self, concepto: str, precio: str):
        try:
            w = int(self.frm_conceptos.winfo_width())
            wrap = max(520, w - 160)
            self.lbl_concepto_full.configure(wraplength=wrap)
        except Exception:
            pass
        try:
            self.lbl_concepto_full.configure(text=concepto)
            self.lbl_precio_full.configure(text=precio)
        except Exception:
            pass

    # -------------- Edit cell --------------
    def _on_tree_double_click(self, event):
        try:
            region = self.tree.identify("region", event.x, event.y)
            if region != "cell":
                return

            col = self.tree.identify_column(event.x)  # "#1", "#2", ...
            row_id = self.tree.identify_row(event.y)
            if not row_id:
                return

            try:
                idx = int(col[1:]) - 1
            except Exception:
                return

            disp = self.tree["displaycolumns"]
            if not disp or disp == ("#all",):
                disp = self.tree["columns"]
            if idx < 0 or idx >= len(disp):
                return

            col_id = disp[idx]
            if col_id in ("unid_nombre", "prod_nombre"):
                return

            self._prompt_edit_cell(str(row_id), str(col_id))
        except Exception:
            return

    def _sanitize_key_alnum(self, s: str, maxlen: int = 18) -> str:
        s = (s or "").upper().strip()
        s = re.sub(r"[^A-Z0-9]", "", s)
        return s[:maxlen]

    def _parse_decimal(self, s: str) -> Optional[Decimal]:
        s = (s or "").strip()
        if not s:
            return None
        s = s.replace(",", "")
        try:
            return Decimal(s)
        except InvalidOperation:
            return None

    def _prompt_edit_cell(self, row_id: str, col_id: str):
        concepto_obj = self._tree_item_to_concepto.get(str(row_id))
        if concepto_obj is None:
            return

        map_col = {
            "cantidad": ("Cantidad", "cantidad", "qty"),
            "clv_unid": ("Clave unidad (SAT)", "clave_unidad", "key_unid"),
            "clv_prod": ("Clave prod/serv", "clave_prod_serv", "key_prod"),
            "concepto": ("Concepto", "concepto", "text"),
            "p_unit": ("Precio unitario", "precio_unitario", "money"),
        }
        if col_id not in map_col:
            return

        label, attr, mode = map_col[col_id]
        current = getattr(concepto_obj, attr, "")

        if mode in ("money", "qty"):
            current_str = self.catalogs.num_to_full_str(current)
        else:
            current_str = "" if current is None else str(current)

        dlg = tk.Toplevel(self)
        dlg.title(f"Editar: {label}")
        dlg.transient(self.controller)
        dlg.grab_set()
        dlg.resizable(False, False)

        pal = get_pal(self.controller)
        dlg.configure(bg=pal["BG"])

        wrap = ttk.Frame(dlg)
        wrap.pack(padx=18, pady=16)

        ttk.Label(wrap, text=label, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))

        if mode == "text":
            txt = tk.Text(wrap, width=70, height=6, wrap="word")
            txt.insert("1.0", current_str)
            txt.pack(fill="both", expand=True)
            txt.focus_set()

            def get_value():
                return txt.get("1.0", "end").strip()
        else:
            ent = ttk.Entry(wrap, width=42)
            ent.insert(0, current_str)
            ent.pack(fill="x")
            ent.focus_set()
            ent.selection_range(0, "end")

            def get_value():
                return ent.get().strip()

        btns = ttk.Frame(wrap)
        btns.pack(fill="x", pady=(12, 0))

        def on_cancel():
            dlg.destroy()

        def on_ok():
            val = get_value()

            if mode == "qty":
                dec = self._parse_decimal(val)
                if dec is None:
                    self.controller.set_status("Cantidad inválida.", auto_clear_ms=1500)
                    return
                setattr(concepto_obj, attr, float(dec))

            elif mode == "money":
                dec = self._parse_decimal(val)
                if dec is None:
                    self.controller.set_status("Precio inválido.", auto_clear_ms=1500)
                    return
                setattr(concepto_obj, attr, float(dec))

            elif mode == "key_unid":
                setattr(concepto_obj, attr, self._sanitize_key_alnum(val, maxlen=6))

            elif mode == "key_prod":
                setattr(concepto_obj, attr, self._sanitize_key_alnum(val, maxlen=18))

            else:
                setattr(concepto_obj, attr, val)

            self._refresh_tree_row_from_model(row_id, concepto_obj)
            self._recalc_factura_total_from_conceptos()
            try:
                self._mark_saved("Concepto actualizado")
            except Exception:
                pass

            dlg.destroy()

        ttk.Button(btns, text="Cancelar", command=on_cancel).pack(side="right")
        ttk.Button(btns, text="Guardar", command=on_ok).pack(side="right", padx=(0, 10))

        dlg.bind("<Escape>", lambda _e: on_cancel())
        dlg.bind("<Return>", lambda _e: on_ok())

    def _refresh_tree_row_from_model(self, row_id: str, c: Concepto):
        cantidad = getattr(c, "cantidad", "")
        clv_unid = getattr(c, "clave_unidad", "") or ""
        clv_prod = getattr(c, "clave_prod_serv", "") or ""
        concepto = getattr(c, "concepto", "") or ""

        p_unit = getattr(c, "precio_unitario", None)
        p_unit_s = self.catalogs.num_to_full_str(p_unit)

        vals = (
            cantidad,
            clv_unid,
            self.catalogs.unid_name(clv_unid),
            clv_prod,
            self.catalogs.prod_name(clv_prod),
            concepto,
            p_unit_s,
        )
        try:
            self.tree.item(row_id, values=vals)
        except Exception:
            pass

    # -------------- Total --------------
    def _recalc_factura_total_from_conceptos(self):
        f = self._get_factura()
        if not f:
            return

        total = 0.0
        for c in (getattr(f, "conceptos", None) or []):
            imp = getattr(c, "importe", None)
            try:
                if imp is not None and imp != "":
                    total += float(imp)
                    continue
            except Exception:
                pass
            try:
                qty = float(getattr(c, "cantidad", 0) or 0)
                pu = float(getattr(c, "precio_unitario", 0) or 0)
                total += qty * pu
            except Exception:
                pass

        try:
            f.total = float(total)
        except Exception:
            pass

        try:
            self.lbl_total.config(text=f"TOTAL: {float(total):,.2f}")
        except Exception:
            pass

    # -------------- Context menu (copy/cut/paste/dup/del/search) --------------
    def _build_tree_context_menu(self):
        if self._tree_ctx_menu is not None:
            return

        self._tree_ctx_menu = tk.Menu(self, tearoff=False)
        self._tree_ctx_menu.add_command(label="Copiar", command=self._ctx_copy_rows)
        self._tree_ctx_menu.add_command(label="Cortar", command=self._ctx_cut_rows)
        self._tree_ctx_menu.add_command(label="Pegar (después)", command=self._ctx_paste_after)
        self._tree_ctx_menu.add_command(label="Pegar (al final)", command=self._ctx_paste_end)
        self._tree_ctx_menu.add_separator()
        self._tree_ctx_menu.add_command(label="Duplicar fila(s)", command=self._ctx_duplicate_rows)
        self._tree_ctx_menu.add_command(label="Eliminar fila(s)", command=self._ctx_delete_rows)
        self._tree_ctx_menu.add_separator()
        self._tree_ctx_menu.add_command(label="Buscar clave…", command=self._ctx_search_key)

    def _on_tree_right_click(self, event):
        self._build_tree_context_menu()

        iid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        col_id = None
        try:
            if col and col.startswith("#"):
                idx = int(col[1:]) - 1
                cols = list(self.tree["columns"])
                if 0 <= idx < len(cols):
                    col_id = cols[idx]
        except Exception:
            col_id = None

        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            self.tree.focus(iid)

        self._ctx_iid = iid or None
        self._ctx_col = col_id or None

        has_sel = bool(self.tree.selection())
        can_paste = bool(self._concept_clipboard)
        is_key_col = col_id in ("clv_unid", "clv_prod")

        def _set_state(label: str, enabled: bool):
            try:
                self._tree_ctx_menu.entryconfigure(label, state=("normal" if enabled else "disabled"))
            except Exception:
                pass

        _set_state("Copiar", has_sel)
        _set_state("Cortar", has_sel)
        _set_state("Duplicar fila(s)", has_sel)
        _set_state("Eliminar fila(s)", has_sel)
        _set_state("Pegar (después)", can_paste and has_sel)
        _set_state("Pegar (al final)", can_paste)
        _set_state("Buscar clave…", is_key_col and has_sel)

        try:
            self._tree_ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self._tree_ctx_menu.grab_release()
            except Exception:
                pass

    def _clone_concepto(self, c: Concepto) -> Concepto:
        try:
            return Concepto(
                cantidad=getattr(c, "cantidad", 1.0),
                clave_unidad=getattr(c, "clave_unidad", "") or "",
                clave_prod_serv=getattr(c, "clave_prod_serv", "") or "",
                concepto=getattr(c, "concepto", "") or "",
                precio_unitario=getattr(c, "precio_unitario", 0.0) or 0.0,
                importe=getattr(c, "importe", None),
            )
        except Exception:
            cc = Concepto()
            for k in ("cantidad", "clave_unidad", "clave_prod_serv", "concepto", "precio_unitario", "importe"):
                try:
                    setattr(cc, k, getattr(c, k))
                except Exception:
                    pass
            return cc

    def _selected_tree_iids(self) -> List[str]:
        try:
            sel = list(self.tree.selection() or [])
        except Exception:
            sel = []
        return [str(x) for x in sel]

    def _selected_conceptos(self) -> List[Tuple[str, Concepto]]:
        out = []
        for iid in self._selected_tree_iids():
            c = self._tree_item_to_concepto.get(iid)
            if c is not None:
                out.append((iid, c))
        return out

    def _refresh_conceptos_view(self, msg: str = "Conceptos actualizados"):
        f = self._get_factura()
        if not f:
            return
        self._conceptos_cache = list(getattr(f, "conceptos", []) or [])
        try:
            self._apply_filter()
        except Exception:
            self._render_conceptos(self._conceptos_cache)
        self._recalc_factura_total_from_conceptos()
        try:
            self._mark_saved(msg)
        except Exception:
            pass

    def _ctx_copy_rows(self):
        sel = self._selected_conceptos()
        if not sel:
            return
        self._concept_clipboard = [self._clone_concepto(c) for _, c in sel]
        try:
            self.controller.set_status(f"Copiado: {len(self._concept_clipboard)} fila(s)", auto_clear_ms=1500)
        except Exception:
            pass

    def _ctx_cut_rows(self):
        self._ctx_copy_rows()
        self._ctx_delete_rows()

    def _ctx_delete_rows(self):
        f = self._get_factura()
        if not f:
            return
        sel = self._selected_conceptos()
        if not sel:
            return
        conceptos = list(getattr(f, "conceptos", []) or [])
        to_remove = set(id(c) for _, c in sel)
        conceptos = [c for c in conceptos if id(c) not in to_remove]
        f.conceptos = conceptos
        self._refresh_conceptos_view("Fila(s) eliminada(s)")

    def _ctx_duplicate_rows(self):
        f = self._get_factura()
        if not f:
            return
        sel = self._selected_conceptos()
        if not sel:
            return

        conceptos = list(getattr(f, "conceptos", []) or [])
        id_to_idx = {id(c): i for i, c in enumerate(conceptos)}
        idxs = sorted(id_to_idx.get(id(c), -1) for _, c in sel)
        idxs = [i for i in idxs if i >= 0]
        if not idxs:
            return
        insert_at = max(idxs) + 1

        clones = [self._clone_concepto(c) for _, c in sel]
        f.conceptos = conceptos[:insert_at] + clones + conceptos[insert_at:]
        self._refresh_conceptos_view("Fila(s) duplicada(s)")

    def _ctx_paste_after(self):
        f = self._get_factura()
        if not f or not self._concept_clipboard:
            return
        sel = self._selected_conceptos()
        if not sel:
            return

        iid = self.tree.focus() or sel[0][0]
        anchor = self._tree_item_to_concepto.get(str(iid))
        conceptos = list(getattr(f, "conceptos", []) or [])
        id_to_idx = {id(c): i for i, c in enumerate(conceptos)}
        insert_at = id_to_idx.get(id(anchor), len(conceptos)) + 1 if anchor is not None else len(conceptos)

        clones = [self._clone_concepto(c) for c in self._concept_clipboard]
        f.conceptos = conceptos[:insert_at] + clones + conceptos[insert_at:]
        self._refresh_conceptos_view("Pegado")

    def _ctx_paste_end(self):
        f = self._get_factura()
        if not f or not self._concept_clipboard:
            return
        conceptos = list(getattr(f, "conceptos", []) or [])
        clones = [self._clone_concepto(c) for c in self._concept_clipboard]
        f.conceptos = conceptos + clones
        self._refresh_conceptos_view("Pegado")

    def _ctx_search_key(self):
        sel = self._selected_conceptos()
        if not sel:
            return
        iid = self.tree.focus() or sel[0][0]
        c = self._tree_item_to_concepto.get(str(iid))
        if c is None:
            return

        col = getattr(self, "_ctx_col", None)
        if col == "clv_unid":
            self._open_key_search_dialog(target="unidad", concepto_obj=c, row_id=str(iid))
        elif col == "clv_prod":
            self._open_key_search_dialog(target="prodserv", concepto_obj=c, row_id=str(iid))

    def _open_key_search_dialog(self, *, target: str, concepto_obj: Concepto, row_id: str):
        target = (target or "").lower()
        if target not in ("unidad", "prodserv"):
            return

        dlg = tk.Toplevel(self)
        dlg.title("Buscar clave")
        dlg.geometry("720x520")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        pal = get_pal(self.controller)
        dlg.configure(bg=pal["BG"])

        wrap = ttk.Frame(dlg, style="Dialog.TFrame")
        wrap.pack(fill="both", expand=True, padx=12, pady=12)

        src_name = "unidades_medida.xlsx" if target == "unidad" else "claves_sat.xlsx"
        ttk.Label(
            wrap,
            text=f"Fuente: {src_name}",
            style="Dialog.TLabel",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        cur = getattr(concepto_obj, "clave_unidad" if target == "unidad" else "clave_prod_serv", "") or ""
        ttk.Label(wrap, text=f"Clave actual: {cur}", style="DialogMuted.TLabel").pack(anchor="w", pady=(0, 8))

        q_var = tk.StringVar(value="")
        ent = ttk.Entry(wrap, textvariable=q_var, style="Dialog.TEntry")
        ent.pack(fill="x")
        ent.focus_set()

        tv = ttk.Treeview(
            wrap,
            columns=("clave", "nombre"),
            show="headings",
            height=16,
            style="Dialog.Treeview",
        )
        tv.heading("clave", text="Clave")
        tv.heading("nombre", text="Nombre")
        tv.column("clave", width=140, anchor="w", stretch=False)
        tv.column("nombre", width=520, anchor="w", stretch=True)
        tv.pack(fill="both", expand=True, pady=10)

        data = self.catalogs.unidad_name if target == "unidad" else self.catalogs.prodserv_name

        def fill(query: str):
            for it in tv.get_children():
                tv.delete(it)
            q = re.sub(r"[^A-Z0-9]", "", (query or "").upper())
            n = 0
            for k, name in data.items():
                kk = re.sub(r"[^A-Z0-9]", "", str(k).upper())
                nn = str(name or "").upper()
                if not q or (q in kk) or (q in nn):
                    tv.insert("", "end", values=(k, name))
                    n += 1
                    if n >= 300:
                        break

        fill("")
        q_var.trace_add("write", lambda *_: fill(q_var.get()))

        def apply_selected():
            sel2 = tv.selection()
            if not sel2:
                return
            vals = tv.item(sel2[0], "values")
            if not vals:
                return
            new_key = str(vals[0]).strip()

            if target == "unidad":
                concepto_obj.clave_unidad = new_key
            else:
                concepto_obj.clave_prod_serv = new_key

            self._refresh_tree_row_from_model(row_id, concepto_obj)
            try:
                self._mark_saved("Clave actualizada")
            except Exception:
                pass
            dlg.destroy()

        btns = ttk.Frame(wrap, style="Dialog.TFrame")
        btns.pack(fill="x", pady=(0, 2))
        ttk.Button(btns, text="Cancelar", command=dlg.destroy).pack(side="right")
        ttk.Button(btns, text="Sustituir clave", command=apply_selected).pack(side="right", padx=(0, 10))

        tv.bind("<Double-1>", lambda _e: apply_selected())
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        dlg.bind("<Return>", lambda _e: apply_selected())
