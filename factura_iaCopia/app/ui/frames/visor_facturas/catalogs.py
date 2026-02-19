# app/ui/frames/visor_facturas/catalogs.py
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional


@dataclass
class Catalogs:
    """
    Carga y expone:
      - Catálogo de ClaveProdServ -> Descripción
      - Catálogo de ClaveUnidad -> Nombre/Descripción

    Diseñado para:
      - funcionar en dev (código fuente)
      - funcionar en PyInstaller (sys.frozen / _MEIPASS)
    """
    prodserv_name: Dict[str, str] = field(default_factory=dict)
    unidad_name: Dict[str, str] = field(default_factory=dict)

    # ---------- Public API ----------
    def load(self) -> None:
        """Carga ambos catálogos si existen los archivos .xlsx."""
        try:
            import pandas as pd  # type: ignore
        except Exception:
            # Sin pandas => no cargamos catálogos (degradación elegante)
            self.prodserv_name = {}
            self.unidad_name = {}
            return

        claves_path = self._find_file("claves_sat.xlsx")
        unidades_path = self._find_file("unidades_medida.xlsx")

        # --- claves_sat.xlsx (ClaveProdServ) ---
        try:
            mp: Dict[str, str] = {}
            if claves_path and claves_path.exists():
                df = pd.read_excel(claves_path)
                df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)

                col_clave = None
                col_desc = None

                for c in df.columns:
                    up = self._norm(c)
                    if col_clave is None and ("CLAVE" in up) and (("PROD" in up) or ("SERV" in up)):
                        col_clave = c
                    if col_desc is None and ("DESCRIP" in up or "DESCRIPCION" in up or "NOMBRE" in up):
                        col_desc = c

                if col_clave is None:
                    for c in df.columns:
                        if "CLAVE" in self._norm(c):
                            col_clave = c
                            break

                if col_desc is None:
                    for c in df.columns:
                        up = self._norm(c)
                        if "DESCRIP" in up or "DESCRIPCION" in up or "NOMBRE" in up:
                            col_desc = c
                            break

                if col_clave is None and len(df.columns) >= 1:
                    col_clave = df.columns[0]
                if col_desc is None and len(df.columns) >= 2:
                    col_desc = df.columns[1]

                if col_clave is not None and col_desc is not None:
                    for _, r in df.iterrows():
                        k = r.get(col_clave)
                        d = r.get(col_desc)
                        if k is None or d is None:
                            continue
                        k = str(k).strip()
                        d = str(d).strip()
                        if k and d:
                            mp[k] = d

            self.prodserv_name = mp
        except Exception:
            self.prodserv_name = {}

        # --- unidades_medida.xlsx (ClaveUnidad) ---
        try:
            mp2: Dict[str, str] = {}
            if unidades_path and unidades_path.exists():
                df = pd.read_excel(unidades_path)
                df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)

                col_clave = None
                text_cols = []

                # 1) Preferido: “CLAVE ... UNIDAD”
                for c in df.columns:
                    up = self._norm(c)
                    if col_clave is None and ("CLAVE" in up and "UNIDAD" in up):
                        col_clave = c

                # 2) Si no existe, aceptar “UNIDAD” (sin CLAVE)
                if col_clave is None:
                    for c in df.columns:
                        up = self._norm(c).strip()
                        if up == "UNIDAD" or "UNIDAD" in up:
                            col_clave = c
                            break

                # 3) Fallback: cualquier “CLAVE”
                if col_clave is None:
                    for c in df.columns:
                        if "CLAVE" in self._norm(c):
                            col_clave = c
                            break

                # 4) Último recurso: primera columna
                if col_clave is None and len(df.columns) >= 1:
                    col_clave = df.columns[0]

                for c in df.columns:
                    up = self._norm(c)
                    if any(x in up for x in ["NOMBRE", "DESCRIP", "DESCRIPCION", "SIMBOLO", "SÍMBOLO"]):
                        text_cols.append(c)

                if col_clave is not None:
                    for _, r in df.iterrows():
                        k = r.get(col_clave)
                        if k is None:
                            continue
                        k = self._clean_key(str(k).strip())
                        if not k:
                            continue

                        name = ""
                        for c in text_cols:
                            v = r.get(c)
                            if isinstance(v, str) and v.strip():
                                name = v.strip()
                                break
                        if not name:
                            for c in df.columns:
                                v = r.get(c)
                                if isinstance(v, str) and v.strip():
                                    name = v.strip()
                                    break

                        if name:
                            mp2[k] = name

            self.unidad_name = mp2
        except Exception:
            self.unidad_name = {}

    def prod_name(self, clave: str) -> str:
        if not clave:
            return ""
        return self.prodserv_name.get(str(clave).strip(), "")

    def unid_name(self, clave: str) -> str:
        if not clave:
            return ""
        k = re.sub(r"[^A-Z0-9]", "", str(clave).strip().upper())
        return self.unidad_name.get(k, "")

    def num_to_full_str(self, v) -> str:
        """
        “Sin redondear por UI”: imprime el número completo disponible.
        Si viene float, usa Decimal(str(float)) para evitar notación científica y conservar decimales “visibles”.
        """
        if v is None:
            return ""
        if isinstance(v, str):
            return v.strip()
        try:
            d = Decimal(str(v))
            dn = d.normalize()
            if "E" in format(dn) or "e" in format(dn):
                return format(d, "f").rstrip("0").rstrip(".")
            return format(dn, "f").rstrip("0").rstrip(".")
        except Exception:
            try:
                return str(v)
            except Exception:
                return ""

    # ---------- Internals ----------
    @staticmethod
    def _norm(s: str) -> str:
        t = str(s).upper()
        for a, b in [("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U")]:
            t = t.replace(a, b)
        return t

    @staticmethod
    def _clean_key(s: str) -> str:
        # Por si viene “E-48”, “E 48”, etc.
        return re.sub(r"[^A-Z0-9]", "", (s or "").upper())

    @staticmethod
    def _candidate_dirs() -> list[Path]:
        """
        Rutas candidatas en orden: proyecto, parser, app, cwd, entrypoint y PyInstaller.
        """
        here = Path(__file__).resolve()
        # .../app/ui/frames/visor_facturas/catalogs.py
        app_dir = here.parents[3]        # app/
        proj_dir = app_dir.parent        # proyecto/

        dirs: list[Path] = []

        # PyInstaller / ejecutable
        try:
            if getattr(sys, "frozen", False):
                meipass = getattr(sys, "_MEIPASS", None)
                if meipass:
                    dirs.append(Path(meipass))
                dirs.append(Path(sys.executable).resolve().parent)
        except Exception:
            pass

        dirs.extend(
            [
                proj_dir,
                proj_dir / "parser",
                app_dir,
                Path.cwd(),
                Path(sys.argv[0]).resolve().parent if sys.argv and sys.argv[0] else proj_dir,
            ]
        )

        out: list[Path] = []
        for d in dirs:
            if d and d not in out:
                out.append(d)
        return out

    @classmethod
    def _find_file(cls, filename: str) -> Optional[Path]:
        for d in cls._candidate_dirs():
            p = d / filename
            if p.exists():
                return p
        return None
