from __future__ import annotations

# --- stdlib ---
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Optional
from tkinter import font as tkfont

# --- tkinter / ttk ---
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# --- modelos ---
from app.models import Factura, Concepto
from app.models import Cliente, DatosFactura

# --- app core ---
from typing import TYPE_CHECKING

# --- theme / ui helpers ---
from app.ui.theme import get_pal, restyle_listbox

# --- widgets ---
from app.ui.widgets.scrollbars import ModernScrollbar, ModernHScrollbar

# --- dialogs ---
from app.ui.dialogs import ConfirmDialog

# --- constants ---
from app.ui.constants import PROVEEDORES_OPCIONES, USO_CFDI_OPCIONES, FORMA_PAGO_OPCIONES

# --- Catalogs ---
from app.ui.frames.visor_facturas.catalogs import Catalogs

# --- Panels ---
from .panel_left import PanelLeft
from .panel_sheets import PanelSheets
from .panel_conceptos import PanelConceptos



if TYPE_CHECKING:
    from app.ui.app import App

class VisorFacturasFrame(ttk.Frame):
    def __init__(self, master: ttk.Frame, controller: App, facturas: List[Factura]):
        super().__init__(master)
        self.controller = controller

        self._facturas: List[Factura] = []
        self._by_file: Dict[str, List[Factura]] = defaultdict(list)

        self._factura_sel: Optional[Factura] = None

        self._method_buttons: Dict[str, ttk.Button] = {}

        self._accordion_active: str = "conceptos"

        # Catálogos (nombre por clave)
        self.catalogs = Catalogs()
        self.catalogs.load()

        self._default_col_widths = {
            "cantidad": 80,
            "clv_unid": 110,
            "unid_nombre": 260,
            "clv_prod": 150,
            "prod_nombre": 360,
            "concepto": 760,
            "p_unit": 260,
        }

        self.var_emitir_enviar = tk.BooleanVar(value=False)

        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Button(header, text="☰", command=self._toggle_left_panel, width=3).pack(side="left")
        ttk.Button(header, text="← Volver", command=self._back).pack(side="left", padx=(8, 0))
        ttk.Label(header, text="Visor de facturas", font=("Segoe UI", 14, "bold")).pack(side="left", padx=(12, 0))

        self.btn_theme = ttk.Button(header, text=self.controller.theme_button_label(), command=self._toggle_theme)
        self.btn_theme.pack(side="right")

        self.paned = ttk.Panedwindow(self, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        self.left = ttk.Frame(self.paned)
        self.right = ttk.Frame(self.paned)

        self.paned.add(self.left, weight=3)
        self.paned.add(self.right, weight=7)
        try:
            self.paned.paneconfigure(self.left, minsize=0)
            self.paned.paneconfigure(self.right, minsize=0)
        except Exception:
            pass

        self._left_visible = True
        self._left_last_sash = 420

        self._build_left()
        self._build_right()

        self.controller.after(50, self._collapse_left_on_start)

        self.set_facturas(facturas)

    # ---------- Panel izquierdo: ocultar/mostrar ----------
    def _collapse_left_on_start(self):
        try:
            # arranca colapsado
            self._left_visible = True
            self._toggle_left_panel(force_collapse=True)
        except Exception:
            pass

    def _toggle_left_panel(self, force_collapse: bool = False):
        """
        Oculta / muestra el panel izquierdo (Archivos detectados) moviendo el sash.
        """
        try:
            self.controller.update_idletasks()

            if force_collapse or self._left_visible:
                try:
                    self._left_last_sash = int(self.paned.sashpos(0))
                except Exception:
                    self._left_last_sash = 520  # default más grande

                self.paned.sashpos(0, 1)
                self._left_visible = False
                self.controller.set_status("Panel de archivos oculto.", auto_clear_ms=1200)
            else:
                # Abrir más ancho por defecto (mínimo 520 o 35% del ancho)
                try:
                    total_w = max(1, int(self.paned.winfo_width()))
                except Exception:
                    total_w = 1200

                preferred = max(520, int(total_w * 0.35))
                target = int(self._left_last_sash or preferred)
                target = max(target, preferred)

                self.paned.sashpos(0, target)
                self._left_visible = True
                self.controller.set_status("Panel de archivos visible.", auto_clear_ms=1200)
        except Exception:
            pass

    def _back(self):
        self.controller.show("hacer")

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        # lo que ya tienes
        self.btn_theme.configure(text=self.controller.theme_button_label())
        restyle_listbox(self.controller, self.lst_archivos)

        # hojas ahora lo maneja PanelSheets
        try:
            if hasattr(self, "panel_sheets") and self.panel_sheets:
                self.panel_sheets.on_theme_changed()
        except Exception:
            pass

        self._refresh_method_styles()
        self._refresh_accordion_styles()
        self._apply_text_theme()
        # ===== FIX Treeview modo claro/oscuro =====
        try:
            if getattr(self, "tree", None):
                self._apply_tree_base_style()
                self._apply_tree_tags_theme()
        except Exception:
            pass

        self._apply_tree_tags_theme()

        # Scrollbars modernas de conceptos
        try:
            if hasattr(self, "panel_conceptos") and self.panel_conceptos:
                self.panel_conceptos.on_theme_changed()
        except Exception:
            pass

            if hasattr(self, "hsb_conceptos") and isinstance(self.hsb_conceptos, ModernScrollbar):
                self.hsb_conceptos.refresh_theme()
        except Exception:
            pass

    def set_facturas(self, facturas: List[Factura]):
        self._facturas = list(facturas or [])
        self._by_file = defaultdict(list)
        for f in self._facturas:
            self._by_file[getattr(f, "archivo_origen", None) or "SIN_ARCHIVO"].append(f)

        if hasattr(self, "panel_left") and self.panel_left:
            self.panel_left.set_files(self._by_file)
            if hasattr(self, "panel_sheets") and self.panel_sheets:
                # PanelSheets lee directo de self._by_file con get_by_file, no requiere set_files
                pass

            self.panel_left.autoselect_first()

    # ===== LEFT =====
    def _build_left(self):
        self.panel_left = PanelLeft(
            self.left,
            controller=self.controller,
            pal_getter=lambda: get_pal(self.controller),
            on_select=self._on_archivo_select,
        )
        self.panel_left.pack(fill="both", expand=True)

        # Para no reescribir otras partes que aún usan self.lst_archivos:
        self.lst_archivos = self.panel_left.lst_archivos

    # ===== RIGHT =====
    def _build_right(self):
        top = ttk.Frame(self.right)
        top.pack(fill="x", padx=12, pady=(10, 6))

        self.lbl_header = ttk.Label(top, text="Archivo: —", font=("Segoe UI", 12, "bold"))
        self.lbl_header.pack(anchor="w")

        self.lbl_warn = ttk.Label(top, text="", font=("Segoe UI", 10, "bold"))
        self.lbl_warn.pack(anchor="w", pady=(4, 0))

        # ===== HOJAS (PanelSheets) =====
        row = ttk.Frame(self.right)
        row.pack(fill="x", padx=12, pady=(0, 8))

        self.panel_sheets = PanelSheets(
            row,
            controller=self.controller,
            on_select_sheet=self._set_factura,
            get_by_file=lambda: self._by_file,
            get_facturas_list=lambda: self._facturas,
            refresh_left_panel=lambda: self.panel_left.set_files(self._by_file),
            autoselect_first_file=self.panel_left.autoselect_first,
        )
        self.panel_sheets.pack(side="left", fill="x", expand=True)

        ttk.Separator(self.right, orient="horizontal").pack(fill="x", padx=12, pady=(4, 12))

        # ===== Acordeón =====
        self.acc = ttk.Frame(self.right)
        self.acc.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        hdr_row = ttk.Frame(self.acc)
        hdr_row.pack(fill="x", pady=(0, 10))

        self.btn_acc_datos = ttk.Button(
            hdr_row,
            text="Datos de factura",
            style="AccHdr.TButton",
            command=lambda: self._set_accordion("datos"),
        )
        self.btn_acc_datos.pack(side="left", fill="x", expand=True)

        self.btn_acc_conc = ttk.Button(
            hdr_row,
            text="Conceptos",
            style="AccHdr.TButton",
            command=lambda: self._set_accordion("conceptos"),
        )
        self.btn_acc_conc.pack(side="left", fill="x", expand=True, padx=(10, 0))

        # IMPORTANTE: esto evita el error var_proveedor (aquí se crean las vars)
        self.panel_datos = ttk.Frame(self.acc)
        self.panel_datos.pack(fill="x", pady=(0, 14))
        self._build_data_panel(self.panel_datos)

        self.panel_conceptos = PanelConceptos(
            self.acc,
            controller=self.controller,
            catalogs=self.catalogs,
            get_factura=lambda: self._factura_sel,
            mark_saved=self._mark_saved,
            default_col_widths=self._default_col_widths,
        )
        self.panel_conceptos.pack(fill="both", expand=True)

        self._set_accordion("conceptos", init=True)

    # ===== Acordeón =====
    def _refresh_accordion_styles(self):
        self.btn_acc_datos.configure(style="AccHdrSel.TButton" if self._accordion_active == "datos" else "AccHdr.TButton")
        self.btn_acc_conc.configure(style="AccHdrSel.TButton" if self._accordion_active == "conceptos" else "AccHdr.TButton")

    def _pulse_active_header(self):
        active = self._accordion_active
        btn = self.btn_acc_datos if active == "datos" else self.btn_acc_conc
        normal_style = "AccHdrSel.TButton"
        alt_style = "AccHdr.TButton"
        btn.configure(style=alt_style)
        self.after(60, lambda: btn.configure(style=normal_style))
        self.after(120, lambda: btn.configure(style=alt_style))
        self.after(180, lambda: btn.configure(style=normal_style))

    def _set_accordion(self, which: str, init: bool = False):
        self._accordion_active = which

        if which == "datos":
            self.panel_conceptos.pack_forget()
            self.panel_datos.pack(fill="x", pady=(0, 14))
        else:
            self.panel_datos.pack_forget()
            self.panel_conceptos.pack(fill="both", expand=True)

        self._refresh_accordion_styles()
        if not init:
            self._pulse_active_header()

    # ===== Panel Datos =====
    def _build_data_panel(self, parent: ttk.Frame):
        card = ttk.Frame(parent, style="Card.TFrame")
        card.pack(fill="x", padx=0, pady=0)

        inner = ttk.Frame(card, style="CardInner.TFrame")
        inner.pack(fill="x", padx=14, pady=14)
        pal = get_pal(self.controller)

        self.var_manual_user = tk.StringVar(value="")
        self.var_manual_pass = tk.StringVar(value="")

        self.var_usd = tk.BooleanVar(value=False)
        self.var_fx = tk.StringVar(value="")

        self.var_extra = tk.BooleanVar(value=False)
        self.var_saved = tk.StringVar(value="")

        self.var_rfc_msg = tk.StringVar(value="")
        self.var_fx_msg = tk.StringVar(value="")

        # Proveedor / RFC / Uso / Método / Forma / Sucursal
        ttk.Label(inner, text="Proveedor", style="Muted.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 8)
        )
        self.var_proveedor = tk.StringVar(value="")
        self.cmb_proveedor = ttk.Combobox(
            inner,
            textvariable=self.var_proveedor,
            values=PROVEEDORES_OPCIONES,
            state="readonly",
            width=22,
        )
        self.cmb_proveedor.grid(row=0, column=1, sticky="w", pady=(0, 8))
        self.cmb_proveedor.bind("<<ComboboxSelected>>", self._on_proveedor_change)
        self._hook_combobox(self.cmb_proveedor)

        ttk.Label(inner, text="RFC", style="Muted.TLabel").grid(
            row=0, column=2, sticky="w", padx=(24, 10), pady=(0, 8)
        )
        self.var_rfc = tk.StringVar(value="")
        self.ent_rfc = ttk.Entry(inner, textvariable=self.var_rfc, width=22)
        self.ent_rfc.grid(row=0, column=3, sticky="w", pady=(0, 8))
        self.ent_rfc.bind("<KeyRelease>", self._on_rfc_live)
        self.ent_rfc.bind("<FocusOut>", self._on_rfc_change)

        self.lbl_rfc_msg = ttk.Label(inner, textvariable=self.var_rfc_msg, style="Muted.TLabel")
        self.lbl_rfc_msg.grid(row=0, column=4, sticky="w", padx=(10, 0), pady=(0, 8))

        ttk.Label(inner, text="Uso CFDI", style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=(0, 8)
        )
        self.var_uso = tk.StringVar(value="")
        self.cmb_uso = ttk.Combobox(
            inner,
            textvariable=self.var_uso,
            values=USO_CFDI_OPCIONES,
            state="readonly",
            width=8,
        )
        self.cmb_uso.grid(row=1, column=1, sticky="w", pady=(0, 8))
        self.cmb_uso.bind("<<ComboboxSelected>>", self._on_uso_change)
        self._hook_combobox(self.cmb_uso)

        # NUEVO: sucursal (solo aplicará para ciertos proveedores, pero se define aquí)
        self.var_sucursal = tk.StringVar(value="")
        self.lbl_sucursal = ttk.Label(inner, text="Sucursal", style="Muted.TLabel")
        self.cmb_sucursal = ttk.Combobox(
            inner,
            textvariable=self.var_sucursal,
            values=("Monterrey", "Guadalajara"),
            state="readonly",
            width=12,
        )
        # Compartimos la fila 1, más a la derecha
        self.lbl_sucursal.grid(row=1, column=4, sticky="w", padx=(24, 10), pady=(0, 8))
        self.cmb_sucursal.grid(row=1, column=5, sticky="w", pady=(0, 8))
        self.cmb_sucursal.bind("<<ComboboxSelected>>", self._on_sucursal_change)
        self._hook_combobox(self.cmb_sucursal)

        ttk.Label(inner, text="Método", style="Muted.TLabel").grid(
            row=1, column=2, sticky="w", padx=(24, 10), pady=(0, 8)
        )
        self.var_metodo = tk.StringVar(value="PUE")

        self.method_frame = ttk.Frame(inner, style="CardInner.TFrame")
        self.method_frame.grid(row=1, column=3, sticky="w", pady=(0, 8))

        btn_pue = ttk.Button(
            self.method_frame,
            text="PUE",
            style="Method.TButton",
            command=lambda: self._set_metodo("PUE"),
        )
        btn_ppd = ttk.Button(
            self.method_frame,
            text="PPD",
            style="Method.TButton",
            command=lambda: self._set_metodo("PPD"),
        )
        btn_pue.pack(side="left", padx=(0, 8))
        btn_ppd.pack(side="left")
        self._method_buttons = {"PUE": btn_pue, "PPD": btn_ppd}

        ttk.Label(inner, text="Forma de pago", style="Muted.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=(0, 8)
        )
        self.var_forma = tk.StringVar(value="")
        self.cmb_forma = ttk.Combobox(
            inner,
            textvariable=self.var_forma,
            values=FORMA_PAGO_OPCIONES,
            state="readonly",
            width=44,
        )
        self.cmb_forma.grid(row=2, column=1, columnspan=3, sticky="w", pady=(0, 8))
        self.cmb_forma.bind("<<ComboboxSelected>>", self._on_forma_change)
        self._hook_combobox(self.cmb_forma)

        self.chk_usd = tk.Checkbutton(
            inner,
            text="Factura en dólares (USD)",
            variable=self.var_usd,
            command=self._update_usd_fields,
            font=("Segoe UI", 10, "bold"),
            bg=pal["BG"],
            fg=pal["MUTED"],
            activebackground=pal["BG"],
            activeforeground=pal["TEXT"],
            selectcolor=pal["BG"],  # que el cuadrito no se vuelva blanco
            highlightthickness=1,
            bd=0,
        )
        self.chk_usd.grid(row=3, column=0, sticky="w", pady=(4, 8))

        self.fx_wrap = ttk.Frame(inner, style="CardInner.TFrame")
        self.fx_wrap.grid(row=3, column=1, sticky="w", pady=(4, 8))
        ttk.Label(self.fx_wrap, text="Tipo de cambio", style="Muted.TLabel").pack(
            side="left", padx=(0, 10)
        )
        self.ent_fx = ttk.Entry(self.fx_wrap, textvariable=self.var_fx, width=12)
        self.ent_fx.pack(side="left")
        self.ent_fx.bind("<KeyRelease>", self._on_fx_live)
        self.ent_fx.bind("<FocusOut>", self._on_fx_change)

        self.lbl_fx_msg = ttk.Label(self.fx_wrap, textvariable=self.var_fx_msg, style="Muted.TLabel")
        self.lbl_fx_msg.pack(side="left", padx=(10, 0))

        self.chk_extra = tk.Checkbutton(
            inner,
            text="Agregar información extra",
            variable=self.var_extra,
            command=self._update_extra_fields,
            font=("Segoe UI", 10, "bold"),
            bg=pal["BG"],
            fg=pal["MUTED"],
            activebackground=pal["BG"],
            activeforeground=pal["TEXT"],
            selectcolor=pal["BG"],
            highlightthickness=1,
            bd=0,
        )
        self.chk_extra.grid(row=4, column=0, sticky="w", pady=(0, 8))

        self.chk_emitir_enviar = tk.Checkbutton(
            inner,
            text="Emitir y enviar esta factura",
            variable=self.var_emitir_enviar,
            command=self._on_emitir_enviar_change,
            font=("Segoe UI", 11, "bold"),
            bg=pal["BG"],
            fg=pal["TEXT"],
            activebackground=pal["BG"],
            activeforeground=pal["TEXT"],
            selectcolor=pal["BG"],
            highlightthickness=1,
            bd=0,
        )
        self.chk_emitir_enviar.grid(
            row=4,
            column=3,
            columnspan=3,
            sticky="e",
            padx=(40, 0),
            pady=(0, 8),
        )

        self.extra_wrap = ttk.Frame(inner, style="CardInner.TFrame")
        self.extra_wrap.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(0, 8))

        self.chk_emitir_enviar.grid(row=4, column=1, sticky="w", pady=(0, 8))
        ttk.Label(self.extra_wrap, text="Notas", style="Muted.TLabel").pack(anchor="w")
        self.txt_extra = tk.Text(
            self.extra_wrap,
            height=4,
            wrap="word",
            font=("Segoe UI", 11),
            bd=0,
            highlightthickness=1,
        )
        self.txt_extra.pack(fill="x", expand=True, pady=(6, 0))
        self.txt_extra.bind(
            "<FocusOut>", lambda _e: self._mark_saved("Notas actualizadas")
        )

        self.manual_wrap = ttk.Frame(inner, style="CardInner.TFrame")
        self.manual_wrap.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(6, 0))

        ttk.Label(self.manual_wrap, text="Usuario", style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=(0, 8)
        )
        self.ent_manual_user = ttk.Entry(
            self.manual_wrap, textvariable=self.var_manual_user, width=22
        )
        self.ent_manual_user.grid(row=1, column=1, sticky="w", pady=(0, 8))
        self.ent_manual_user.bind(
            "<FocusOut>", lambda _e: self._mark_saved("Usuario actualizado")
        )

        ttk.Label(self.manual_wrap, text="Contraseña", style="Muted.TLabel").grid(
            row=1, column=2, sticky="w", padx=(24, 10), pady=(0, 8)
        )
        self.ent_manual_pass = ttk.Entry(
            self.manual_wrap, textvariable=self.var_manual_pass, width=22, show="•"
        )
        self.ent_manual_pass.grid(row=1, column=3, sticky="w", pady=(0, 8))
        self.ent_manual_pass.bind(
            "<FocusOut>", lambda _e: self._mark_saved("Contraseña actualizada")
        )

        # Al iniciar, ocultamos/mostramos sucursal según proveedor
        self._update_sucursal_visibility()

        self.lbl_saved = ttk.Label(inner, textvariable=self.var_saved, style="Muted.TLabel")
        self.lbl_saved.grid(row=0, column=5, sticky="e", padx=(18, 0), pady=(0, 8))

        inner.columnconfigure(3, weight=1)
        inner.columnconfigure(4, weight=1)
        inner.columnconfigure(5, weight=1)

        self._refresh_method_styles()
        self._update_provider_manual_fields()
        self._update_usd_fields()
        self._update_extra_fields()
        self._apply_text_theme()
        self._on_rfc_live()
        self._on_fx_live()
        self._refresh_toggle_colors()

    def _mark_saved(self, msg: str = "Guardado"):
        self.var_saved.set("Guardado")
        self.controller.set_status(msg, auto_clear_ms=2000)
        self.after(1200, lambda: self.var_saved.set(""))

    def _apply_text_theme(self):
        pal = get_pal(self.controller)
        try:
            self.txt_extra.configure(
                bg=pal["SURFACE2"],
                fg=pal["TEXT"],
                insertbackground=pal["TEXT"],
                selectbackground=pal["ACCENT2"],
                selectforeground=pal["TEXT"],
                highlightbackground=pal["BORDER"],
                highlightcolor=pal["ACCENT"],
            )
        except Exception:
            pass
        self._refresh_toggle_colors()

    def _sanitize_rfc_alnum(self, s: str) -> str:
        s = (s or "").upper()
        s = re.sub(r"[^A-Z0-9]", "", s)
        return s[:13]

    def _is_rfc_len_ok(self, s: str) -> bool:
        n = len(s)
        return (n == 0) or (n == 12) or (n == 13)

    def _sanitize_fx_numeric(self, s: str) -> str:
        s = (s or "")
        s = s.replace(",", "").strip()
        out = []
        dot_used = False
        for ch in s:
            if ch.isdigit():
                out.append(ch)
            elif ch == "." and not dot_used:
                out.append(ch)
                dot_used = True
        return "".join(out)

    def _fx_format_ok(self, s: str) -> bool:
        if not s:
            return False
        return re.match(r"^\d+(\.\d+)?$", s) is not None

    def _on_rfc_live(self, _evt=None):
        raw = self.var_rfc.get()
        clean = self._sanitize_rfc_alnum(raw)
        if clean != raw:
            self.var_rfc.set(clean)

        ok = self._is_rfc_len_ok(clean)
        try:
            self.ent_rfc.configure(style="TEntry" if ok else "Error.TEntry")
        except Exception:
            pass

        if clean and not ok:
            self.var_rfc_msg.set("RFC debe tener 12 o 13.")
        else:
            self.var_rfc_msg.set("")

    def _on_fx_live(self, _evt=None):
        if not self.var_usd.get():
            self.var_fx_msg.set("")
            try:
                self.ent_fx.configure(style="TEntry")
            except Exception:
                pass
            return

        raw = self.var_fx.get()
        clean = self._sanitize_fx_numeric(raw)
        if clean != raw:
            self.var_fx.set(clean)

        if not clean:
            self.var_fx_msg.set("")
            try:
                self.ent_fx.configure(style="TEntry")
            except Exception:
                pass
            return

        ok = self._fx_format_ok(clean)
        try:
            self.ent_fx.configure(style="TEntry" if ok else "Warn.TEntry")
        except Exception:
            pass

        self.var_fx_msg.set("" if ok else "Solo números y decimales.")

    def _on_fx_change(self, _evt=None):
        if not self.var_usd.get():
            return
        ok = self._fx_format_ok((self.var_fx.get() or "").strip())
        if ok:
            try:
                self.ent_fx.configure(style="TEntry")
            except Exception:
                pass
            self._mark_saved("Tipo de cambio actualizado")
        else:
            try:
                self.ent_fx.configure(style="Warn.TEntry")
            except Exception:
                pass
            self.controller.set_status("Tipo de cambio inválido (solo números y decimales).", auto_clear_ms=3500)

    def _update_provider_manual_fields(self):
        sel = (self.var_proveedor.get() or "").strip().lower()
        show = (sel == "otro")
        if show:
            self.manual_wrap.grid()
        else:
            self.manual_wrap.grid_remove()

    def _update_usd_fields(self):
        if self.var_usd.get():
            self.fx_wrap.grid()
            self._on_fx_live()
            self._mark_saved("Marcado: Factura en dólares")
        else:
            self.fx_wrap.grid_remove()
            self.var_fx.set("")
            self.var_fx_msg.set("")
            try:
                self.ent_fx.configure(style="TEntry")
            except Exception:
                pass
            self._mark_saved("Desmarcado: Factura en dólares")

        self._refresh_toggle_colors()

    def _update_sucursal_visibility(self):
        prov = (self.var_proveedor.get() or "").strip().lower()
        show = prov in ("xisisa", "viesa")

        try:
            if show:
                # Volvemos a mostrar usando la última geometría conocida
                self.lbl_sucursal.grid()
                self.cmb_sucursal.grid()
                # Si no hay sucursal seleccionada, por defecto Monterrey
                if not (self.var_sucursal.get() or "").strip():
                    self.var_sucursal.set("Monterrey")
            else:
                # Ocultamos y limpiamos
                self.lbl_sucursal.grid_remove()
                self.cmb_sucursal.grid_remove()
                self.var_sucursal.set("")
                if self._factura_sel and getattr(self._factura_sel, "datos_factura", None) is not None:
                    self._factura_sel.datos_factura.sucursal = None
        except Exception:
            # Si por alguna razón aún no existen los widgets, no queremos que truene la app
            pass

    def _update_extra_fields(self):
        if self.var_extra.get():
            self.extra_wrap.grid()
            self._mark_saved("Marcado: Información extra")
        else:
            self.extra_wrap.grid_remove()
            try:
                self.txt_extra.delete("1.0", "end")
            except Exception:
                pass
            self._mark_saved("Desmarcado: Información extra")
        self._refresh_toggle_colors()

    def _refresh_toggle_colors(self):
        pal = get_pal(self.controller)

        def _style_chk(chk, var, is_primary=False):
            if chk is None:
                return
            selected = bool(var.get())
            # color del texto
            fg = pal["SUCCESS"] if is_primary and selected else (
                pal["ACCENT"] if selected else pal["MUTED"]
            )
            border = pal["ACCENT"] if selected else pal["BG"]

            chk.configure(
                bg=pal["BG"],
                fg=fg,
                activebackground=pal["BG"],
                activeforeground=fg,
                highlightthickness=1,
                highlightbackground=border,
                highlightcolor=border,
            )

        _style_chk(self.chk_usd, self.var_usd, is_primary=False)
        _style_chk(self.chk_extra, self.var_extra, is_primary=False)
        _style_chk(self.chk_emitir_enviar, self.var_emitir_enviar, is_primary=True)

    def focus_search(self):
        try:
            self._set_accordion("conceptos")
            if hasattr(self, "panel_conceptos") and self.panel_conceptos:
                self.panel_conceptos.focus_search()
        except Exception:
            pass

    # ===== Combobox popdown tint =====
    def _tint_combobox_popdown_for(self, combo: ttk.Combobox):
        pal = get_pal(self.controller)
        bg = pal["SURFACE"]
        fg = pal["TEXT"]
        sel_bg = pal["ACCENT2"]
        sel_fg = pal["TEXT"]
        border = pal["BORDER"]
        try:
            pop = combo.tk.eval(f"ttk::combobox::PopdownWindow {str(combo)}")
            lb_path = f"{pop}.f.l"
            lb = self.controller.nametowidget(lb_path)
            lb.configure(
                bg=bg, fg=fg,
                selectbackground=sel_bg, selectforeground=sel_fg,
                highlightbackground=border, highlightthickness=1,
                relief="flat", bd=0,
            )
        except Exception:
            pass

    def _hook_combobox(self, combo: ttk.Combobox):
        combo.bind("<Button-1>", lambda _e: self.controller.after(20, lambda: self._tint_combobox_popdown_for(combo)), add="+")
        combo.bind("<KeyRelease-Down>", lambda _e: self.controller.after(20, lambda: self._tint_combobox_popdown_for(combo)), add="+")
        combo.bind("<KeyRelease-Return>", lambda _e: self.controller.after(20, lambda: self._tint_combobox_popdown_for(combo)), add="+")

    def _update_sheet_buttons_state(self):
        """
        Habilita o deshabilita los botones de duplicar / eliminar
        según si hay una factura (hoja) seleccionada.
        """
        has = bool(self._factura_sel)
        if hasattr(self, "btn_dup_sheet"):
            if has:
                self.btn_dup_sheet.state(["!disabled"])
            else:
                self.btn_dup_sheet.state(["disabled"])
        if hasattr(self, "btn_del_sheet"):
            if has:
                self.btn_del_sheet.state(["!disabled"])
            else:
                self.btn_del_sheet.state(["disabled"])

    def _refresh_method_styles(self):
        active = (self.var_metodo.get().strip() or "PUE")
        for k, btn in self._method_buttons.items():
            btn.configure(style="MethodSel.TButton" if k == active else "Method.TButton")

    def _set_metodo(self, metodo: str):
        self.var_metodo.set(metodo)
        self._refresh_method_styles()
        self._on_metodo_change()
        self._mark_saved("Método actualizado")

    def _clear_view(self):
        # ===== HOJAS (ahora vive en PanelSheets; ya no toques sheets_frame/_sheet_buttons) =====
        try:
            if hasattr(self, "panel_sheets") and self.panel_sheets:
                self.panel_sheets.clear()
        except Exception:
            pass

        # ===== Datos (panel_datos) =====
        try:
            self.var_proveedor.set("")
            self.var_rfc.set("")
            self.var_uso.set("")
            self.var_metodo.set("PUE")
            self._refresh_method_styles()
            self.var_forma.set("")
        except Exception:
            pass

        try:
            self.var_sucursal.set("")
        except Exception:
            pass

        try:
            self.var_manual_user.set("")
            self.var_manual_pass.set("")
        except Exception:
            pass

        try:
            self.var_emitir_enviar.set(False)
        except Exception:
            pass

        try:
            self.var_usd.set(False)
            self.var_fx.set("")
            self.var_fx_msg.set("")
        except Exception:
            pass

        try:
            self.var_extra.set(False)
            try:
                self.txt_extra.delete("1.0", "end")
            except Exception:
                pass
        except Exception:
            pass

        # refrescar visibilidades/colores (sin marcar "guardado" agresivamente)
        try:
            self._update_provider_manual_fields()
            self._update_sucursal_visibility()
            self._update_usd_fields()
            self._update_extra_fields()
            self._on_rfc_live()
            self._on_fx_live()
        except Exception:
            pass

        # ===== CONCEPTOS (ahora vive en PanelConceptos) =====
        try:
            if hasattr(self, "panel_conceptos") and self.panel_conceptos:
                self.panel_conceptos.clear()
        except Exception:
            pass

        # ===== Estado interno =====
        self._factura_sel = None

        try:
            self.lbl_header.configure(text="Archivo: —")
        except Exception:
            pass

        try:
            self.lbl_warn.configure(text="")
        except Exception:
            pass

        try:
            self._update_sheet_buttons_state()
        except Exception:
            pass

    def _on_archivo_select(self, _evt=None):
        sel = self.lst_archivos.curselection()
        if not sel:
            return

        idx = sel[0]

        keys = self.panel_left.file_keys_sorted
        if idx < 0 or idx >= len(keys):
            return
        archivo_key = keys[idx]

        self.panel_sheets.render_for_file(archivo_key)

        facturas = self._by_file.get(archivo_key, [])
        if facturas:
            self._set_factura(sorted(facturas, key=lambda x: (getattr(x, "hoja_origen", "") or ""))[0])

    def _set_factura(self, fact: Factura):
        if fact is None:
            self._clear_view()
            return

        self._factura_sel = fact

        # --- header ---
        archivo = getattr(fact, "archivo_origen", None) or "SIN_ARCHIVO"
        hoja = getattr(fact, "hoja_origen", None) or ""
        try:
            if hoja:
                self.lbl_header.configure(text=f"Archivo: {archivo}  ·  Hoja: {hoja}")
            else:
                self.lbl_header.configure(text=f"Archivo: {archivo}")
        except Exception:
            pass

        # --- marcar chip activo (PanelSheets) ---
        try:
            if hasattr(self, "panel_sheets") and self.panel_sheets:
                self.panel_sheets.set_active_factura(fact)
        except Exception:
            pass

        # --- asegurar modelos ---
        self._ensure_cliente()
        self._ensure_datos()

        # --- cargar vars del panel de datos desde el modelo ---
        try:
            cli = getattr(fact, "cliente", None)
            dat = getattr(fact, "datos_factura", None)

            # proveedor / rfc
            self.var_proveedor.set((getattr(cli, "proveedor", "") or "").strip())
            self.var_rfc.set((getattr(cli, "rfc", "") or "").strip())

            # uso / metodo / forma
            self.var_uso.set((getattr(dat, "uso_cfdi", "") or "").strip())
            self.var_metodo.set((getattr(dat, "metodo_pago", "PUE") or "PUE").strip() or "PUE")
            self.var_forma.set((getattr(dat, "forma_pago", "") or "").strip())

            # sucursal (si aplica)
            try:
                self.var_sucursal.set((getattr(dat, "sucursal", "") or "").strip())
            except Exception:
                pass

            # emitir y enviar
            try:
                self.var_emitir_enviar.set(bool(getattr(dat, "emitir_y_enviar", False)))
            except Exception:
                self.var_emitir_enviar.set(False)

            # USD / FX
            try:
                is_usd = bool(getattr(dat, "usd", False))
            except Exception:
                is_usd = False
            self.var_usd.set(is_usd)

            try:
                fx_val = getattr(dat, "tipo_cambio", "") or ""
            except Exception:
                fx_val = ""
            self.var_fx.set("" if fx_val is None else str(fx_val).strip())

            # Extra / notas
            try:
                extra_txt = getattr(dat, "info_extra", "") or ""
                extra_on = bool(extra_txt.strip())
            except Exception:
                extra_txt = ""
                extra_on = False

            self.var_extra.set(extra_on)
            try:
                self.txt_extra.delete("1.0", "end")
                if extra_txt:
                    self.txt_extra.insert("1.0", extra_txt)
            except Exception:
                pass

        except Exception:
            # si algo falla aquí, no queremos bloquear el visor
            pass

        # --- refrescar estilos/visibilidad ---
        try:
            self._refresh_method_styles()
            self._update_provider_manual_fields()
            self._update_sucursal_visibility()
            self._update_usd_fields()
            self._update_extra_fields()
            self._on_rfc_live()
            self._on_fx_live()
        except Exception:
            pass

        # --- conceptos + total (PanelConceptos) ---
        try:
            if hasattr(self, "panel_conceptos") and self.panel_conceptos:
                self.panel_conceptos.set_factura(fact)
        except Exception:
            pass

        try:
            self._update_sheet_buttons_state()
        except Exception:
            pass

    # ===== Model updates =====
    def _ensure_cliente(self):
        if not self._factura_sel:
            return
        if getattr(self._factura_sel, "cliente", None) is None:
            self._factura_sel.cliente = Cliente()

    def _ensure_datos(self):
        if not self._factura_sel:
            return
        if getattr(self._factura_sel, "datos_factura", None) is None:
            self._factura_sel.datos_factura = DatosFactura()

    def _on_rfc_change(self, _evt=None):
        if not self._factura_sel:
            return
        rfc = (self.var_rfc.get() or "").strip()
        ok = self._is_rfc_len_ok(rfc)
        try:
            self.ent_rfc.configure(style="TEntry" if ok else "Error.TEntry")
        except Exception:
            pass
        self._ensure_cliente()
        self._factura_sel.cliente.rfc = rfc
        self._mark_saved("RFC actualizado" if ok else "RFC inválido (12/13 caracteres)")
        if not ok and rfc:
            self.controller.set_status("RFC inválido: debe ser 12 o 13 caracteres.", auto_clear_ms=3500)

    def _on_proveedor_change(self, _evt=None):
        self._update_provider_manual_fields()
        # Actualizamos visibilidad de sucursal aunque no haya factura seleccionada
        self._update_sucursal_visibility()

        if not self._factura_sel:
            return
        self._ensure_cliente()
        self._factura_sel.cliente.proveedor = self.var_proveedor.get().strip()
        self._mark_saved("Proveedor actualizado")

    def _on_uso_change(self, _evt=None):
        if not self._factura_sel:
            return
        self._ensure_datos()
        self._factura_sel.datos_factura.uso_cfdi = self.var_uso.get().strip()
        self._mark_saved("Uso CFDI actualizado")

    def _on_metodo_change(self):
        if not self._factura_sel:
            return
        self._ensure_datos()
        self._factura_sel.datos_factura.metodo_pago = self.var_metodo.get().strip()

    def _on_forma_change(self, _evt=None):
        if not self._factura_sel:
            return
        self._ensure_datos()
        self._factura_sel.datos_factura.forma_pago = self.var_forma.get().strip()
        self._mark_saved("Forma de pago actualizada")

    def _on_emitir_enviar_change(self, _evt=None):
        """
        Actualiza el modelo cuando el usuario marca / desmarca 'Emitir y enviar esta factura'.
        """
        if not getattr(self, "_factura_sel", None):
            return
        self._ensure_datos()
        val = bool(self.var_emitir_enviar.get())
        self._factura_sel.datos_factura.emitir_y_enviar = val
        self._mark_saved("Opción 'emitir y enviar' actualizada")
        self._refresh_toggle_colors()

    def _on_sucursal_change(self, _evt=None):
        if not self._factura_sel:
            return
        self._ensure_datos()
        val = (self.var_sucursal.get() or "").strip()
        self._factura_sel.datos_factura.sucursal = val or None
        self._mark_saved("Sucursal actualizada")

    def _apply_tree_base_style(self):
        pal = get_pal(self.controller)

        try:
            st = ttk.Style(self.controller)

            # Usamos un style dedicado para no pelear con otros treeviews
            st.configure(
                "Concepts.Treeview",
                background=pal["SURFACE"],
                foreground=pal["TEXT"],
                fieldbackground=pal["SURFACE"],
                bordercolor=pal["BORDER"],
                lightcolor=pal["BORDER"],
                darkcolor=pal["BORDER"],
                rowheight=26,
            )

            st.configure(
                "Concepts.Treeview.Heading",
                background=pal["SURFACE2"],
                foreground=pal["TEXT"],
                relief="flat",
            )

            # Colores de selección (muy importante en modo claro)
            st.map(
                "Concepts.Treeview",
                background=[("selected", pal["ACCENT2"])],
                foreground=[("selected", pal["TEXT"])],
            )

        except Exception:
            pass

    def _apply_tree_tags_theme(self):
        pal = get_pal(self.controller)

        try:
            # Filas alternadas (fondo)
            self.tree.tag_configure("odd", background=pal["ROW_ALT"], foreground=pal["TEXT"])
            self.tree.tag_configure("even", background=pal["SURFACE"], foreground=pal["TEXT"])
        except Exception:
            pass

    # --- helpers de archivo/hoja ---
    def _file_key_for_fact(self, fact: Factura) -> str:
        return getattr(fact, "archivo_origen", None) or "SIN_ARCHIVO"