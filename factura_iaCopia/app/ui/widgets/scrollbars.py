# app/ui/widgets/scrollbars.py
from __future__ import annotations

import tkinter as tk


class ModernScrollbar(tk.Canvas):
    """
    Scrollbar moderna dibujada (Canvas).
    - Soporta orient="horizontal"/"vertical"
    - API compatible con ttk.Scrollbar: command=widget.xview/yview y widget.configure(xscrollcommand=sb.set)
    - Respeta min_thumb sin romper el rango real (mapeo correcto).
    """

    def __init__(
        self,
        master,
        orient="horizontal",
        command=None,
        pal_getter=None,
        thickness=12,
        pad=6,
        bg_key="BG",
        track_key="BG",
        thumb_key="SURFACE2",
        active_key="ACCENT2",
        min_thumb=28,
        **kwargs
    ):
        self.orient = orient
        self.command = command or (lambda *a: None)
        self.pal_getter = pal_getter or (lambda: {})
        self.thickness = int(thickness)
        self.pad = int(pad)
        self.bg_key = bg_key
        self.track_key = track_key
        self.thumb_key = thumb_key
        self.active_key = active_key
        self.min_thumb = int(min_thumb)

        # estado del “viewport” (0..1)
        self._fraction0 = 0.0
        self._fraction1 = 1.0

        self._dragging = False
        self._drag_offset = 0  # offset en px dentro del thumb

        # Canvas sizing
        base_cfg = dict(highlightthickness=0, bd=0, relief="flat")
        base_cfg.update(kwargs)
        if self.orient == "vertical":
            super().__init__(master, width=self.thickness, **base_cfg)
        else:
            super().__init__(master, height=self.thickness, **base_cfg)

        self.refresh_theme()

        # bindings
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", lambda _e: self._stop_drag())

    def refresh_theme(self):
        pal = self.pal_getter() or {}
        self.pal = pal
        bg = pal.get(self.bg_key, "#000000")
        self.configure(bg=bg)
        self._redraw()

    # ---- ttk-like API ----
    def set(self, first, last):
        try:
            f0 = float(first)
            f1 = float(last)
        except Exception:
            f0, f1 = 0.0, 1.0

        # clamp defensivo
        f0 = max(0.0, min(1.0, f0))
        f1 = max(0.0, min(1.0, f1))
        if f1 < f0:
            f0, f1 = f1, f0

        self._fraction0 = f0
        self._fraction1 = f1
        self._redraw()

    # ---- geometry helpers ----
    def _usable_len(self):
        if self.orient == "vertical":
            return max(1, self.winfo_height() - 2 * self.pad)
        return max(1, self.winfo_width() - 2 * self.pad)

    def _span(self):
        return max(0.0, min(1.0, (self._fraction1 - self._fraction0)))

    def _thumb_len_px(self, usable):
        # tamaño visual (puede ser > span*usable por min_thumb)
        return max(self.min_thumb, int(round(self._span() * usable)))

    def _denom(self):
        # rango real para moveto (0..1-span)
        return max(0.0, 1.0 - self._span())

    def _ratio_from_fraction(self):
        # thumb_ratio = fraction0 / (1-span) (si hay scroll), 0 si no
        denom = self._denom()
        if denom <= 1e-9:
            return 0.0
        r = self._fraction0 / denom
        return max(0.0, min(1.0, r))

    def _fraction_from_ratio(self, ratio):
        # fraction0 = ratio * (1-span)
        ratio = max(0.0, min(1.0, ratio))
        return ratio * self._denom()

    def _thumb_bbox(self):
        """
        Devuelve bbox del thumb en coords de canvas:
        horizontal: (x0, y0, x1, y1)
        vertical:   (x0, y0, x1, y1)
        """
        usable = self._usable_len()
        tlen = self._thumb_len_px(usable)
        track_len = max(1, usable - tlen)

        ratio = self._ratio_from_fraction()
        pos = int(round(ratio * track_len))

        if self.orient == "vertical":
            y0 = self.pad + pos
            y1 = y0 + tlen
            x0 = 1
            x1 = max(2, self.winfo_width() - 1)
            return x0, y0, x1, y1
        else:
            x0 = self.pad + pos
            x1 = x0 + tlen
            y0 = 1
            y1 = max(2, self.winfo_height() - 1)
            return x0, y0, x1, y1

    # ---- drawing ----
    def _draw_pill(self, x0, y0, x1, y1, fill, tag):
        self.delete(tag)
        w = max(1, x1 - x0)
        h = max(1, y1 - y0)
        r = min(h // 2, w // 2)
        # caps
        self.create_oval(x0, y0, x0 + 2 * r, y1, fill=fill, outline=fill, tags=(tag,))
        self.create_oval(x1 - 2 * r, y0, x1, y1, fill=fill, outline=fill, tags=(tag,))
        # middle
        self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline=fill, tags=(tag,))

    def _redraw(self):
        self.delete("all")

        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 2 or h <= 2:
            return

        pal = self.pal_getter() or {}
        bg = pal.get(self.bg_key, "#000000")
        track = pal.get(self.track_key, bg)
        thumb = pal.get(self.thumb_key, "#666666")
        thumb_active = pal.get(self.active_key, thumb)

        # Track (rail finito)
        if self.orient == "vertical":
            cx = w // 2
            rail = max(2, w // 5)
            self.create_rectangle(cx - rail // 2, 0, cx + rail // 2, h, fill=track, outline=track)
        else:
            cy = h // 2
            rail = max(2, h // 5)
            self.create_rectangle(0, cy - rail // 2, w, cy + rail // 2, fill=track, outline=track)

        # Thumb pill
        x0, y0, x1, y1 = self._thumb_bbox()
        fill = thumb_active if self._dragging else thumb
        self._draw_pill(x0, y0, x1, y1, fill=fill, tag="thumb")

    # ---- events ----
    def _on_click(self, e):
        x0, y0, x1, y1 = self._thumb_bbox()
        inside = (x0 <= e.x <= x1) and (y0 <= e.y <= y1)
        if inside:
            self._dragging = True
            if self.orient == "vertical":
                self._drag_offset = e.y - y0
            else:
                self._drag_offset = e.x - x0
            self._redraw()
            return

        # click en el track -> jump
        self._jump_to(e.x, e.y)

    def _jump_to(self, x, y):
        usable = self._usable_len()
        tlen = self._thumb_len_px(usable)
        track_len = max(1, usable - tlen)

        if self.orient == "vertical":
            pos = (y - self.pad) - (tlen / 2)
        else:
            pos = (x - self.pad) - (tlen / 2)

        ratio = pos / track_len
        f0 = self._fraction_from_ratio(ratio)
        self.command("moveto", f0)

    def _on_drag(self, e):
        if not self._dragging:
            return

        usable = self._usable_len()
        tlen = self._thumb_len_px(usable)
        track_len = max(1, usable - tlen)

        if self.orient == "vertical":
            pos = (e.y - self._drag_offset) - self.pad
        else:
            pos = (e.x - self._drag_offset) - self.pad

        ratio = pos / track_len
        f0 = self._fraction_from_ratio(ratio)
        self.command("moveto", f0)

    def _stop_drag(self):
        self._dragging = False
        self._redraw()


class ModernHScrollbar(ModernScrollbar):
    def __init__(self, master, *, command, pal_getter, **kwargs):
        super().__init__(
            master,
            orient="horizontal",
            command=command,
            pal_getter=pal_getter,
            **kwargs,
        )
