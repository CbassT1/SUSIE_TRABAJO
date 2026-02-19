from __future__ import annotations

from tkinter import ttk, messagebox
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ui.app import App


class MenuPrincipalFrame(ttk.Frame):
    def __init__(self, master: ttk.Frame, controller: "App"):
        super().__init__(master)
        self.controller = controller

        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(16, 10))

        ttk.Label(header, text="S.U.S.I.E.", font=("Segoe UI", 18, "bold")).pack(side="left")
        self.btn_theme = ttk.Button(
            header,
            text=self.controller.theme_button_label(),
            command=self._toggle_theme,
        )
        self.btn_theme.pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=16, pady=10)

        center = ttk.Frame(body)
        center.pack(expand=True)

        ttk.Label(center, text="Menú principal", font=("Segoe UI", 14, "bold")).pack(pady=(0, 24))

        btn_w = 32

        ttk.Button(
            center,
            text="Hacer facturas",
            style="MenuBig.TButton",
            command=lambda: controller.show("hacer"),
            width=btn_w,
        ).pack(pady=(0, 18))

        ttk.Button(
            center,
            text="Generar reporte (local)",
            style="MenuBig.TButton",
            command=self._reporte_local,
            width=btn_w,
        ).pack(pady=(0, 18))

        ttk.Button(
            center,
            text="Ajustar archivos",
            style="MenuBig.TButton",
            command=lambda: controller.show("ajustes"),
            width=btn_w,
        ).pack()

    def _reporte_local(self):
        self.controller.set_status("Reporte local: pendiente de implementar.", auto_clear_ms=2500)
        messagebox.showinfo("Reporte local", "Placeholder: aquí irá el reporte local.")

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        try:
            self.btn_theme.configure(text=self.controller.theme_button_label())
        except Exception:
            pass
