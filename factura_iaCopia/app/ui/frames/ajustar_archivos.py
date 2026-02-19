# app/ui/frames/ajustar_archivos.py
from __future__ import annotations

from tkinter import ttk


class AjustarArchivosFrame(ttk.Frame):
    def __init__(self, master: ttk.Frame, controller):
        super().__init__(master)
        self.controller = controller

        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(16, 10))

        ttk.Button(header, text="← Volver", command=lambda: controller.show("menu")).pack(side="left")
        ttk.Label(header, text="Ajustar archivos", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(12, 0))
        self.btn_theme = ttk.Button(
            header,
            text=self.controller.theme_button_label(),
            command=self._toggle_theme,
        )
        self.btn_theme.pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=16, pady=10)

        ttk.Label(
            body,
            text="Placeholder. Aquí irán utilidades por formatos específicos.",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        try:
            self.btn_theme.configure(text=self.controller.theme_button_label())
        except Exception:
            pass
