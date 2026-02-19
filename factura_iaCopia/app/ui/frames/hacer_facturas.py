from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, List

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from app.ui.utils import (
    center_toplevel_on_parent,
    open_file_native,
    parse_dnd_file_list,
)
from app.ui.theme import get_pal, restyle_listbox

if TYPE_CHECKING:
    from app.ui.app import App

# Si esto vive en otro lado, impórtalo desde ahí.
# Si ya lo tienes global en gui.py, muévelo a un módulo config.
try:
    from tkinterdnd2 import DND_FILES  # type: ignore
    _HAS_DND = True
except Exception:
    DND_FILES = None
    _HAS_DND = False


class HacerFacturasFrame(ttk.Frame):
    def __init__(self, master: ttk.Frame, controller: "App"):
        super().__init__(master)
        self.controller = controller
        self._paths: List[str] = []

        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(16, 10))

        ttk.Button(header, text="← Volver", command=lambda: controller.show("menu")).pack(side="left")
        ttk.Label(header, text="Hacer facturas", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(12, 0))
        ttk.Button(header, text=self.controller.theme_button_label(), command=self._toggle_theme).pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=16, pady=10)

        drop = ttk.LabelFrame(body, text="Arrastra y suelta (opcional)")
        drop.pack(fill="x", pady=(0, 10))

        pal = get_pal(self.controller)
        dnd_text = "Arrastra aquí tus archivos" if _HAS_DND else "Drag&Drop no disponible"
        self.drop_area = tk.Label(
            drop,
            text=dnd_text,
            bg=pal["SURFACE2"],
            fg=pal["TEXT"],
            bd=1,
            relief="solid",
            padx=14,
            pady=12,
            font=("Segoe UI", 11),
            anchor="w",
        )
        self.drop_area.pack(fill="x", padx=12, pady=12)

        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=(0, 12))

        ttk.Button(actions, text="Seleccionar archivos (Ctrl+O)", command=self._select_files).pack(side="left")
        ttk.Button(actions, text="Limpiar lista", command=self._clear_files).pack(side="left", padx=(10, 0))

        list_frame = ttk.LabelFrame(body, text="Archivos listos")
        list_frame.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            list_frame,
            activestyle="none",
            bg=pal["SURFACE"],
            fg=pal["TEXT"],
            selectbackground=pal["LIST_SELECT"],
            selectforeground=pal["TEXT"],
            highlightthickness=1,
            highlightbackground=pal["BORDER"],
            relief="flat",
            bd=0,
            font=("Segoe UI", 11),
        )
        self.listbox.configure(selectmode=tk.EXTENDED, exportselection=False)
        self.listbox.pack(fill="both", expand=True, padx=12, pady=12)

        self._files_clipboard = {"mode": None, "paths": []}  # mode: "copy" | "cut"
        self._build_ready_files_menu()

        self.listbox.bind("<Button-3>", self._on_ready_files_right_click)
        self.listbox.bind("<Double-Button-1>", lambda _e: self._ready_open_selected())
        self.listbox.bind("<Button-1>", lambda _e: (self.listbox.focus_set(), None))
        self.listbox.bind("<Delete>", lambda _e: self._ready_remove_selected())

        self.listbox.bind("<Control-c>", lambda _e: (self._ready_copy(), "break"))
        self.listbox.bind("<Control-C>", lambda _e: (self._ready_copy(), "break"))
        self.listbox.bind("<Control-x>", lambda _e: (self._ready_cut(), "break"))
        self.listbox.bind("<Control-X>", lambda _e: (self._ready_cut(), "break"))
        self.listbox.bind("<Control-v>", lambda _e: (self._ready_paste(), "break"))
        self.listbox.bind("<Control-V>", lambda _e: (self._ready_paste(), "break"))

        footer = ttk.Frame(body)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Button(footer, text="Continuar", style="Primary.TButton", command=self._continue).pack(side="right")

        self._bind_dnd()

    def _bind_dnd(self):
        if not _HAS_DND:
            return
        for w in (self.drop_area, self.listbox):
            try:
                w.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
                w.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]
            except Exception:
                pass

    def _on_drop(self, event):
        paths = parse_dnd_file_list(str(event.data))
        self._add_files(paths)

    def _select_files(self):
        last_dir = None
        try:
            if getattr(self.controller, "_settings", None) and getattr(self.controller._settings, "last_dir", ""):
                last_dir = self.controller._settings.last_dir
        except Exception:
            pass

        paths = filedialog.askopenfilenames(
            title="Selecciona archivos",
            initialdir=last_dir,
            filetypes=[
                ("Excel o PDF", "*.xlsx *.pdf"),
                ("Excel", "*.xlsx"),
                ("PDF", "*.pdf"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if paths:
            try:
                first = str(paths[0])
                parent = first.replace("\\", "/").rsplit("/", 1)[0]
                if getattr(self.controller, "_settings", None):
                    self.controller._settings.last_dir = parent
            except Exception:
                pass
            self._add_files(list(paths))

    def _add_files(self, paths: List[str]):
        added = 0
        for p in paths:
            p = str(p)
            ext = p.lower()
            if not (ext.endswith(".xlsx") or ext.endswith(".pdf")):
                continue
            if p not in self._paths:
                self._paths.append(p)
                added += 1

        if added:
            self._refresh_list()
            self.controller.set_status(
                f"Se agregaron {added} archivo(s). Total: {len(self._paths)}.",
                auto_clear_ms=2500,
            )

    def _clear_files(self):
        self._paths = []
        self._refresh_list()
        self.controller.set_status("Lista limpiada.", auto_clear_ms=1500)

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for p in self._paths:
            self.listbox.insert(tk.END, Path(p).name)

    def _ready_remove_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        try:
            removed = self._paths.pop(idx)
        except Exception:
            return
        self._refresh_list()
        try:
            self.controller.set_status(f"Quitado: {Path(removed).name}", auto_clear_ms=1500)
        except Exception:
            pass

    def _continue(self):
        if not self._paths:
            messagebox.showwarning("Sin archivos", "Agrega al menos un archivo .xlsx para continuar.", parent=self)
            return

        dlg = tk.Toplevel(self)
        dlg.title("Procesando")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        dlg.resizable(False, False)

        pal = get_pal(self.controller)
        dlg.configure(bg=pal["BG"])

        wrap = ttk.Frame(dlg)
        wrap.pack(padx=18, pady=16)
        ttk.Label(wrap, text="Procesando archivos...", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(wrap, text=f"Archivos: {len(self._paths)}", style="Muted.TLabel").pack(anchor="w", pady=(4, 10))

        pb = ttk.Progressbar(wrap, mode="indeterminate", length=360)
        pb.pack(fill="x")
        pb.start(12)

        dlg.update_idletasks()
        center_toplevel_on_parent(self.controller, dlg, 440, 150)

        self.controller.set_status(f"Procesando {len(self._paths)} archivo(s)...")

        def _close_dialog():
            try:
                pb.stop()
            except Exception:
                pass
            try:
                dlg.grab_release()
            except Exception:
                pass
            try:
                dlg.destroy()
            except Exception:
                pass

        self.controller._last_input_paths = list(self._paths)

        def _worker():
            try:
                facturas = self.controller.parse_excel_files(self._paths)
                err = None
            except Exception as e:
                facturas = []
                err = e

            def _done():
                _close_dialog()
                if err is not None:
                    self.controller.set_status("Error al procesar archivos.")
                    messagebox.showerror(
                        "Error al parsear",
                        f"No se pudieron leer los archivos.\n\nDetalle:\n{err}",
                        parent=self,
                    )
                    return
                if not facturas:
                    self.controller.set_status("Sin facturas detectadas.", auto_clear_ms=2500)
                    messagebox.showwarning(
                        "Sin facturas",
                        "No se detectaron facturas/hojas visibles en los archivos.",
                        parent=self,
                    )
                    return
                self.controller.open_visor(facturas)

            self.controller.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        # Botón de tema
        header = self.winfo_children()[0]
        for w in header.winfo_children():
            if isinstance(w, ttk.Button) and w.cget("text") in ("Modo claro", "Modo oscuro"):
                w.configure(text=self.controller.theme_button_label())

        restyle_listbox(self.controller, self.listbox)
        pal = get_pal(self.controller)
        self.drop_area.configure(bg=pal["SURFACE2"], fg=pal["TEXT"], highlightbackground=pal["BORDER"])

    # -------- menú contextual --------
    def _build_ready_files_menu(self):
        self._ready_menu = tk.Menu(self, tearoff=False)
        self._ready_menu.add_command(label="Abrir archivo", command=self._ready_open_selected)
        self._ready_menu.add_command(label="Ver ruta", command=self._ready_show_path)
        self._ready_menu.add_separator()
        self._ready_menu.add_command(label="Copiar nombre", command=self._ready_copy_name)
        self._ready_menu.add_command(label="Copiar ruta", command=self._ready_copy_path)
        self._ready_menu.add_separator()
        self._ready_menu.add_command(label="Cortar", command=self._ready_cut)
        self._ready_menu.add_command(label="Copiar", command=self._ready_copy)
        self._ready_menu.add_command(label="Pegar", command=self._ready_paste)
        self._ready_menu.add_separator()
        self._ready_menu.add_command(label="Duplicar", command=self._ready_duplicate)
        self._ready_menu.add_command(label="Renombrar archivo…", command=self._ready_rename_on_disk)
        self._ready_menu.add_separator()
        self._ready_menu.add_command(label="Eliminar de la lista", command=self._ready_remove_selected)

    def _on_ready_files_right_click(self, event):
        idx = self.listbox.nearest(event.y)
        if idx >= 0:
            current = set(self.listbox.curselection())
            if idx not in current:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(idx)
                self.listbox.activate(idx)

        has_sel = bool(self.listbox.curselection())
        can_paste = bool(self._files_clipboard.get("paths"))

        def st(label, enabled):
            try:
                self._ready_menu.entryconfigure(label, state=("normal" if enabled else "disabled"))
            except Exception:
                pass

        for lbl in (
            "Abrir archivo",
            "Ver ruta",
            "Copiar nombre",
            "Copiar ruta",
            "Cortar",
            "Copiar",
            "Duplicar",
            "Renombrar archivo…",
            "Eliminar de la lista",
        ):
            st(lbl, has_sel)
        st("Pegar", can_paste)

        try:
            self._ready_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self._ready_menu.grab_release()
            except Exception:
                pass

    def _ready_get_selected_paths(self):
        sel = self.listbox.curselection()
        if not sel:
            return []
        return [self._paths[int(i)] for i in sel if 0 <= int(i) < len(self._paths)]

    def _ready_open_selected(self):
        paths = self._ready_get_selected_paths()
        if not paths:
            return
        open_file_native(paths[0], parent=self)

    def _ready_show_path(self):
        paths = self._ready_get_selected_paths()
        if not paths:
            return
        messagebox.showinfo("Ruta", str(paths[0]), parent=self)

    def _ready_copy_name(self):
        paths = self._ready_get_selected_paths()
        if not paths:
            return
        name = Path(paths[0]).name
        self.clipboard_clear()
        self.clipboard_append(name)

    def _ready_copy_path(self):
        paths = self._ready_get_selected_paths()
        if not paths:
            return
        self.clipboard_clear()
        self.clipboard_append(str(paths[0]))

    def _ready_copy(self):
        paths = self._ready_get_selected_paths()
        if not paths:
            return
        self._files_clipboard = {"mode": "copy", "paths": list(paths)}

    def _ready_cut(self):
        paths = self._ready_get_selected_paths()
        if not paths:
            return

        self._files_clipboard = {"mode": "cut", "paths": list(paths)}
        cut_set = set(paths)
        self._paths = [p for p in self._paths if p not in cut_set]
        self._refresh_list()

        try:
            self.controller.set_status(f"Cortado: {len(paths)} archivo(s).", auto_clear_ms=1500)
        except Exception:
            pass

    def _ready_paste(self):
        mode = self._files_clipboard.get("mode")
        clip_paths = list(self._files_clipboard.get("paths") or [])
        if not clip_paths:
            return

        sel = self.listbox.curselection()
        insert_at = (max(sel) + 1) if sel else len(self._paths)
        insert_at = min(insert_at, len(self._paths))

        if mode == "cut":
            for p in clip_paths:
                self._paths.insert(insert_at, p)
                insert_at += 1
            self._files_clipboard = {"mode": None, "paths": []}
        else:
            for p in clip_paths:
                self._paths.insert(insert_at, p)
                insert_at += 1

        self._refresh_list()

    def _ready_duplicate(self):
        paths = self._ready_get_selected_paths()
        if not paths:
            return
        for p in paths:
            self._paths.append(p)
        self._refresh_list()

    def _ready_rename_on_disk(self):
        paths = self._ready_get_selected_paths()
        if not paths:
            return
        old_path = Path(paths[0])
        if not old_path.exists():
            messagebox.showerror("No encontrado", f"No existe:\n{old_path}", parent=self)
            return

        new_name = simpledialog.askstring(
            "Renombrar",
            "Nuevo nombre (con extensión):",
            initialvalue=old_path.name,
            parent=self,
        )
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name:
            return

        new_path = old_path.with_name(new_name)
        if new_path.exists():
            messagebox.showerror("Ya existe", f"Ya existe:\n{new_path.name}", parent=self)
            return

        try:
            old_path.rename(new_path)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo renombrar:\n{e}", parent=self)
            return

        for i, p in enumerate(self._paths):
            if Path(p) == old_path:
                self._paths[i] = str(new_path)

        self._refresh_list()
