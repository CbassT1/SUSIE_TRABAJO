# app/ui/frames/visor_facturas/panel_left.py

from __future__ import annotations

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Callable, Dict, List, Optional, Tuple


class PanelLeft(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        controller,
        pal_getter: Callable[[], dict],
        on_select: Callable[[Optional[tk.Event]], None],
    ):
        super().__init__(parent)

        self.controller = controller
        self._pal_getter = pal_getter
        self._on_select_cb = on_select

        # Último dict recibido: {archivo_key: [Factura, ...]}
        self._by_file: Dict[str, list] = {}

        # Mapa "texto mostrado en listbox" -> ruta real (si se conoce)
        self._file_display_to_path: Dict[str, str] = {}

        # Clipboard interno del menú contextual
        # mode: copy/cut, items: [(disp, path, key)]
        self._det_menu_clip = {"mode": None, "items": []}

        # Lista de llaves reales (sin icono) en el mismo orden que el listbox
        self.file_keys_sorted: List[str] = []

        self.lst_archivos: tk.Listbox = None  # type: ignore[assignment]
        self._det_menu: tk.Menu = None        # type: ignore[assignment]

        self._build()

    # ========= PUBLIC API =========
    def set_files(self, by_file: dict):
        self._by_file = by_file or {}
        self._populate_archivos()

    def autoselect_first(self) -> bool:
        if self.lst_archivos.size() == 0:
            return False
        self.lst_archivos.selection_clear(0, tk.END)
        self.lst_archivos.selection_set(0)
        self.lst_archivos.activate(0)
        # dispara callback del frame
        self._on_select_cb(None)
        return True

    def select_file_key(self, key: str, *, trigger: bool = True):
        keys = getattr(self, "file_keys_sorted", []) or []
        if key not in keys:
            return
        idx = keys.index(key)

        self.lst_archivos.selection_clear(0, tk.END)
        self.lst_archivos.selection_set(idx)
        self.lst_archivos.activate(idx)
        self.lst_archivos.see(idx)

        if trigger and callable(getattr(self, "_on_select_cb", None)):
            self._on_select_cb(None)

    def clear(self):
        try:
            self.lst_archivos.delete(0, tk.END)
        except Exception:
            pass
        self._file_display_to_path.clear()
        self.file_keys_sorted.clear()
        self._by_file = {}

    # ========= BUILD =========
    def _build(self):
        ttk.Label(self, text="Archivos detectados", font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=10, pady=(10, 6)
        )

        pal = self._pal_getter()

        self.lst_archivos = tk.Listbox(
            self,
            activestyle="none",
            bg=pal.get("SURFACE", "#111111"),
            fg=pal.get("TEXT", "#ffffff"),
            selectbackground=pal.get("LIST_SELECT", "#333333"),
            selectforeground=pal.get("TEXT", "#ffffff"),
            highlightthickness=1,
            highlightbackground=pal.get("BORDER", "#444444"),
            relief="flat",
            bd=0,
            font=("Segoe UI", 11),
        )
        self.lst_archivos.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.lst_archivos.bind("<<ListboxSelect>>", self._on_select_cb)

        self._build_detected_files_menu()
        self.lst_archivos.bind("<Button-3>", self._on_detected_files_right_click)
        self.lst_archivos.bind("<Double-1>", lambda _e: self._det_open_selected_file())

    # ========= DATA =========
    def _basename_to_realpath(self) -> Dict[str, str]:
        paths = getattr(self.controller, "_last_input_paths", None) or []
        idx: Dict[str, str] = {}
        for p in paths:
            try:
                bp = os.path.basename(str(p))
                idx.setdefault(bp, str(p))  # si hay duplicados, se queda el primero
            except Exception:
                pass
        return idx

    def _populate_archivos(self):
        try:
            self.lst_archivos.delete(0, tk.END)
        except Exception:
            return

        self.file_keys_sorted = []
        self._file_display_to_path = {}

        base_idx = self._basename_to_realpath()

        for archivo in sorted(self._by_file.keys()):
            facts = self._by_file.get(archivo, []) or []
            has_error = any(getattr(f, "hoja_origen", "") == "ERROR" for f in facts)
            has_warn = any(getattr(getattr(f, "datos_factura", None), "info_extra", "") for f in facts)

            icon = "❌" if has_error else ("⚠️" if has_warn else "✅")
            disp = f"{icon} {archivo}"

            self.file_keys_sorted.append(archivo)
            self.lst_archivos.insert(tk.END, disp)

            realp = base_idx.get(archivo)
            if realp:
                self._file_display_to_path[disp] = realp

    # ========= MENU =========
    def _build_detected_files_menu(self):
        self._det_menu = tk.Menu(self, tearoff=False)
        self._det_menu.add_command(label="Abrir archivo", command=self._det_open_selected_file)
        self._det_menu.add_command(label="Ver ruta", command=self._det_show_path)
        self._det_menu.add_separator()
        self._det_menu.add_command(label="Copiar nombre", command=self._det_copy_name)
        self._det_menu.add_command(label="Copiar ruta", command=self._det_copy_path)
        self._det_menu.add_separator()
        self._det_menu.add_command(label="Cortar", command=self._det_cut)
        self._det_menu.add_command(label="Copiar", command=self._det_copy)
        self._det_menu.add_command(label="Pegar", command=self._det_paste)
        self._det_menu.add_separator()
        self._det_menu.add_command(label="Duplicar (en visor)", command=self._det_duplicate)
        self._det_menu.add_command(label="Renombrar (en visor)…", command=self._det_rename_display)
        self._det_menu.add_separator()
        self._det_menu.add_command(label="Eliminar del visor", command=self._det_remove_from_view)

    def _on_detected_files_right_click(self, event):
        idx = self.lst_archivos.nearest(event.y)
        if idx >= 0:
            self.lst_archivos.selection_clear(0, tk.END)
            self.lst_archivos.selection_set(idx)
            self.lst_archivos.activate(idx)

        has_sel = bool(self.lst_archivos.curselection())
        can_paste = bool(self._det_menu_clip.get("items"))

        def st(label, enabled):
            try:
                self._det_menu.entryconfigure(label, state=("normal" if enabled else "disabled"))
            except Exception:
                pass

        for lbl in (
            "Abrir archivo", "Ver ruta", "Copiar nombre", "Copiar ruta",
            "Cortar", "Copiar", "Duplicar (en visor)", "Renombrar (en visor)…", "Eliminar del visor"
        ):
            st(lbl, has_sel)

        st("Pegar", can_paste)

        try:
            self._det_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self._det_menu.grab_release()
            except Exception:
                pass

    # ========= HELPERS =========
    def _det_get_selected_display(self) -> Optional[str]:
        sel = self.lst_archivos.curselection()
        if not sel:
            return None
        return self.lst_archivos.get(int(sel[0]))

    def _det_get_selected_idx(self) -> Optional[int]:
        sel = self.lst_archivos.curselection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def _key_at_index(self, idx: int) -> Optional[str]:
        try:
            if idx < 0 or idx >= len(self.file_keys_sorted):
                return None
            return self.file_keys_sorted[idx]
        except Exception:
            return None

    def _det_get_selected_path(self) -> Optional[str]:
        disp = self._det_get_selected_display()
        if not disp:
            return None
        return self._file_display_to_path.get(disp)

    def _open_file_native(self, path: str):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("No se pudo abrir", f"No se pudo abrir el archivo.\n\n{e}")

    # ========= ACTIONS =========
    def _det_open_selected_file(self):
        p = self._det_get_selected_path()
        if not p:
            messagebox.showwarning(
                "Sin ruta",
                "No tengo la ruta completa de este archivo. Re-selecciónalo desde 'Hacer facturas'.",
            )
            return
        self._open_file_native(p)

    def _det_show_path(self):
        p = self._det_get_selected_path()
        if not p:
            messagebox.showwarning("Sin ruta", "No tengo la ruta completa de este archivo.")
            return
        messagebox.showinfo("Ruta", str(p))

    def _det_copy_name(self):
        disp = self._det_get_selected_display()
        if not disp:
            return
        self.clipboard_clear()
        self.clipboard_append(str(disp))

    def _det_copy_path(self):
        p = self._det_get_selected_path()
        if not p:
            messagebox.showwarning("Sin ruta", "No tengo la ruta completa de este archivo.")
            return
        self.clipboard_clear()
        self.clipboard_append(str(p))

    def _det_copy(self):
        disp = self._det_get_selected_display()
        if not disp:
            return
        p = self._file_display_to_path.get(disp, "")
        idx = self._det_get_selected_idx()
        key = self._key_at_index(idx) if idx is not None else None
        self._det_menu_clip = {"mode": "copy", "items": [(disp, p, key)]}

    def _det_cut(self):
        disp = self._det_get_selected_display()
        if not disp:
            return
        p = self._file_display_to_path.get(disp, "")
        idx = self._det_get_selected_idx()
        key = self._key_at_index(idx) if idx is not None else None
        self._det_menu_clip = {"mode": "cut", "items": [(disp, p, key)]}

        if idx is None:
            return

        self.lst_archivos.delete(idx)
        self._file_display_to_path.pop(disp, None)

        # IMPORTANT: mantener keys sincronizadas con el Listbox
        try:
            if 0 <= idx < len(self.file_keys_sorted):
                self.file_keys_sorted.pop(idx)
        except Exception:
            pass

    def _det_paste(self):
        items = list(self._det_menu_clip.get("items") or [])
        if not items:
            return

        mode = self._det_menu_clip.get("mode")
        existing = set(self.lst_archivos.get(0, tk.END))

        for disp, p, key in items:
            new_disp = disp

            # En copy y cut: garantizar nombre único para no colisionar
            n = 2
            while new_disp in existing:
                new_disp = f"{disp} ({n})"
                n += 1

            self.lst_archivos.insert(tk.END, new_disp)
            existing.add(new_disp)

            # IMPORTANT: mantener keys sincronizadas con el Listbox
            if key:
                self.file_keys_sorted.append(key)

            if p:
                self._file_display_to_path[new_disp] = p

        if mode == "cut":
            self._det_menu_clip = {"mode": None, "items": []}

    def _det_duplicate(self):
        disp = self._det_get_selected_display()
        if not disp:
            return
        p = self._file_display_to_path.get(disp, "")
        idx = self._det_get_selected_idx()
        key = self._key_at_index(idx) if idx is not None else None

        existing = set(self.lst_archivos.get(0, tk.END))
        n = 2
        new_disp = f"{disp} ({n})"
        while new_disp in existing:
            n += 1
            new_disp = f"{disp} ({n})"

        self.lst_archivos.insert(tk.END, new_disp)

        # IMPORTANT: mantener keys sincronizadas con el Listbox
        if key:
            self.file_keys_sorted.append(key)

        if p:
            self._file_display_to_path[new_disp] = p

    def _det_rename_display(self):
        disp = self._det_get_selected_display()
        if not disp:
            return

        new_disp = simpledialog.askstring(
            "Renombrar",
            "Nuevo nombre (solo visor):",
            initialvalue=disp,
            parent=self,
        )
        if not new_disp:
            return
        new_disp = new_disp.strip()
        if not new_disp:
            return

        existing = set(self.lst_archivos.get(0, tk.END))
        if new_disp in existing:
            messagebox.showerror("Nombre en uso", "Ya existe un elemento con ese nombre.")
            return

        idx = self._det_get_selected_idx()
        if idx is None:
            return

        p = self._file_display_to_path.pop(disp, "")

        # Nota: el key NO cambia; solo cambia el display
        self.lst_archivos.delete(idx)
        self.lst_archivos.insert(idx, new_disp)
        self.lst_archivos.selection_set(idx)
        self.lst_archivos.activate(idx)

        if p:
            self._file_display_to_path[new_disp] = p

    def _det_remove_from_view(self):
        disp = self._det_get_selected_display()
        if not disp:
            return

        idx = self._det_get_selected_idx()
        if idx is None:
            return

        self.lst_archivos.delete(idx)
        self._file_display_to_path.pop(disp, None)

        # IMPORTANT: mantener keys sincronizadas con el Listbox
        try:
            if 0 <= idx < len(self.file_keys_sorted):
                self.file_keys_sorted.pop(idx)
        except Exception:
            pass
