# parser/normalizers.py
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Optional

# Normaliza SOLO montos tipo "$ 8 3,620.69" -> "$83,620.69" sin destruir columnas
_MONEY_TOKEN = re.compile(r"\$?\s*\d[\d\s,]*\.\d{2}")

def normalize_money_tokens(s: str) -> str:
    def repl(m: re.Match) -> str:
        t = m.group(0)
        has_dollar = "$" in t
        t = t.replace("$", "")
        t = re.sub(r"\s+", "", t)
        return ("$" if has_dollar else "") + t
    return _MONEY_TOKEN.sub(repl, s or "")

def clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def to_decimal(s: str) -> Optional[Decimal]:
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    s = s.replace(",", "").replace("$", "")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None

def normalize_clave_unidad(clave_unidad: str, unidad_col: Optional[str] = None) -> str:
    cu = (clave_unidad or "").strip().upper()
    unidad = (unidad_col or "").strip().upper() if unidad_col else ""
    if cu == "VJE":
        if unidad and re.fullmatch(r"[A-Z0-9]{2,6}", unidad):
            return unidad
        return "E54"
    return cu
