# app/settings.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional


def _settings_path(app_name: str = "SUSIE") -> Path:
    # Windows: %APPDATA%/SUSIE/settings.json
    appdata = os.environ.get("APPDATA") or str(Path.home())
    p = Path(appdata) / app_name / "settings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class AppSettings:
    is_dark: bool = True
    last_dir: str = ""
    confirm_delete_files: bool = True
    use_pdf_ocr: bool = False
    tree_col_widths: Dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.tree_col_widths is None:
            self.tree_col_widths = {}

    @classmethod
    def load(cls) -> "AppSettings":
        path = _settings_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            s = cls()
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            if s.tree_col_widths is None:
                s.tree_col_widths = {}
            return s
        except Exception:
            return cls()

    def save(self) -> None:
        path = _settings_path()
        payload = asdict(self)
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            # best-effort; do not crash app
            pass
