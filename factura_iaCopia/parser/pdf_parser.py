# parser/pdf_parser.py
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional, Tuple

from app.models import Factura, Cliente, DatosFactura, Concepto
from parser.legacy_excel_parser import (
    normalize_proveedor,
    normalize_rfc,
    normalizar_forma_pago,
    normalizar_metodo_pago,
    normalizar_uso_cfdi,
)

# ----------------- Helpers -----------------
def _to_decimal(s: str) -> Optional[Decimal]:
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

def _clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def _extract_pages_pdfplumber(path: str) -> List[List[str]]:
    import pdfplumber  # type: ignore

    pages: List[List[str]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            lines: List[str] = []
            for ln in txt.splitlines():
                ln = ln.rstrip()
                if ln.strip():
                    lines.append(ln)
            pages.append(lines)
    return pages

# Normaliza SOLO montos: "$ 8 3,620.69" -> "$83,620.69"
_MONEY_TOKEN = re.compile(r"\$?\s*\d[\d\s,]*\.\d{2}")
def _normalize_money_tokens(s: str) -> str:
    def repl(m: re.Match) -> str:
        t = m.group(0)
        has_dollar = "$" in t
        t = t.replace("$", "")
        t = re.sub(r"\s+", "", t)
        return ("$" if has_dollar else "") + t
    return _MONEY_TOKEN.sub(repl, s or "")

# ----------------- Regex de renglones -----------------
_ROW_RE_A = re.compile(
    r"""
    ^\s*
    (?P<cant>\d+(?:\.\d+)?)
    \s+
    (?P<clv_unid>[A-Z0-9]{2,6})
    \s+
    (?P<clv_prod>\d{6,12})
    \s+
    (?P<concepto>.+?)
    \s+
    \$?\s*(?P<pu>\d[\d,]*(?:\.\d+)?)
    \s+
    \$?\s*(?P<importe>\d[\d,]*(?:\.\d+)?)
    \s*$
    """,
    re.VERBOSE,
)

# cant  unidad  clave_unidad  clave_prod  concepto  pu  importe
_ROW_RE_B = re.compile(
    r"""
    ^\s*
    (?P<cant>\d+(?:\.\d+)?)
    \s+
    (?P<unidad>[A-ZÁÉÍÓÚÑa-z0-9]{2,6})
    \s+
    (?P<clv_unid>[A-Z0-9]{2,6})
    \s+
    (?P<clv_prod>\d{6,12})
    \s+
    (?P<concepto>.+?)
    \s+
    \$?\s*(?P<pu>\d[\d,]*(?:\.\d+)?)
    \s+
    \$?\s*(?P<importe>\d[\d,]*(?:\.\d+)?)
    \s*$
    """,
    re.VERBOSE,
)

_TOTAL_RE = re.compile(r"^\s*TOTAL:\s*\$?\s*([\d,]+(?:\.\d+)?)\s*$", re.IGNORECASE)
_SUBTOTAL_RE = re.compile(r"^\s*SUBTOTAL:\s*\$?\s*([\d,]+(?:\.\d+)?)\s*$", re.IGNORECASE)
_IVA_RE = re.compile(r"^\s*IVA:\s*\$?\s*([\d,]+(?:\.\d+)?)\s*$", re.IGNORECASE)

def _looks_like_invoice_page(lines: List[str]) -> bool:
    joined = "\n".join(lines[:180]).upper()
    return ("SUBTOTAL" in joined and "IVA" in joined and "TOTAL" in joined) or (
        "CANTIDAD" in joined and "CLAVE" in joined and "P.U." in joined
    )

def _extract_meta(lines: List[str]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    proveedor = rfc = uso_cfdi = metodo_pago = forma_pago = None

    for ln in lines[:220]:
        s0 = _clean_spaces(ln)
        s = _normalize_money_tokens(s0)
        up = s.upper()

        if proveedor is None and "PROVEEDOR" in up:
            cand = s.split(":", 1)[1].strip() if ":" in s else s
            proveedor = normalize_proveedor(cand) or cand

        if rfc is None and "RFC" in up:
            m = re.search(r"([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})", up)
            if m:
                rfc = normalize_rfc(m.group(1))

        if uso_cfdi is None:
            u = normalizar_uso_cfdi(s)
            if u:
                uso_cfdi = u

        if metodo_pago is None:
            mp = normalizar_metodo_pago(s)
            if mp:
                metodo_pago = mp

        if forma_pago is None:
            fp = normalizar_forma_pago(s)
            if fp:
                forma_pago = fp

        if proveedor and rfc and uso_cfdi and metodo_pago and forma_pago:
            break

    return proveedor, rfc, uso_cfdi, metodo_pago, forma_pago

def _fix_clave_unidad(clv_unid: str, unidad_col: Optional[str]) -> str:
    cu = (clv_unid or "").strip().upper()
    unidad = (unidad_col or "").strip().upper() if unidad_col else ""
    if cu == "VJE":
        return unidad if unidad and re.fullmatch(r"[A-Z0-9]{2,6}", unidad) else "E54"
    return cu

def _parse_page(lines: List[str], archivo_origen: str, page_no: int) -> Optional[Factura]:
    if not lines or not _looks_like_invoice_page(lines):
        return None

    proveedor, rfc, uso_cfdi, metodo_pago, forma_pago = _extract_meta(lines)

    conceptos: List[Concepto] = []
    subtotal = iva = total = None

    for ln in lines:
        raw = _clean_spaces(ln)
        s = _normalize_money_tokens(raw)

        m = _ROW_RE_A.match(s)
        if m:
            cant = _to_decimal(m.group("cant")) or Decimal("0")
            clv_unid = _fix_clave_unidad(m.group("clv_unid"), None)
            clv_prod = m.group("clv_prod").strip()
            concepto_txt = _clean_spaces(m.group("concepto"))
            pu = _to_decimal(m.group("pu")) or Decimal("0")
            imp = _to_decimal(m.group("importe")) or Decimal("0")
            conceptos.append(
                Concepto(
                    cantidad=float(cant),
                    clave_unidad=clv_unid,
                    clave_prod_serv=clv_prod,
                    concepto=concepto_txt,
                    precio_unitario=float(pu),
                    importe=float(imp),
                )
            )
            continue

        m = _ROW_RE_B.match(s)
        if m:
            cant = _to_decimal(m.group("cant")) or Decimal("0")
            unidad_col = m.group("unidad")
            clv_unid = _fix_clave_unidad(m.group("clv_unid"), unidad_col)
            clv_prod = m.group("clv_prod").strip()
            concepto_txt = _clean_spaces(m.group("concepto"))
            pu = _to_decimal(m.group("pu")) or Decimal("0")
            imp = _to_decimal(m.group("importe")) or Decimal("0")
            conceptos.append(
                Concepto(
                    cantidad=float(cant),
                    clave_unidad=clv_unid,
                    clave_prod_serv=clv_prod,
                    concepto=concepto_txt,
                    precio_unitario=float(pu),
                    importe=float(imp),
                )
            )
            continue

        ms = _SUBTOTAL_RE.match(s)
        if ms:
            subtotal = _to_decimal(ms.group(1))
            continue

        mi = _IVA_RE.match(s)
        if mi:
            iva = _to_decimal(mi.group(1))
            continue

        mt = _TOTAL_RE.match(s)
        if mt:
            total = _to_decimal(mt.group(1))
            continue

    if total is None:
        if subtotal is not None and iva is not None:
            total = subtotal + iva
        elif conceptos:
            total = sum(Decimal(str(c.importe or 0)) for c in conceptos)
        else:
            total = Decimal("0")

    hoja_origen = f"PDF-{page_no}"
    return Factura(
        id=f"{archivo_origen}::{hoja_origen}",
        cliente=Cliente(proveedor=proveedor, rfc=rfc),
        datos_factura=DatosFactura(
            uso_cfdi=uso_cfdi,
            metodo_pago=metodo_pago,
            forma_pago=forma_pago,
            info_extra="",
        ),
        conceptos=conceptos,
        total=float(total),
        archivo_origen=archivo_origen,
        hoja_origen=hoja_origen,
    )

def parse_pdf_invoice(path: str, *, use_ocr: bool = False) -> List[Factura]:
    # use_ocr queda listo para futuro; hoy solo usamos pdfplumber
    p = Path(path)
    archivo_origen = p.name

    pages = _extract_pages_pdfplumber(str(p))
    out: List[Factura] = []
    for i, page_lines in enumerate(pages, start=1):
        f = _parse_page(page_lines, archivo_origen, i)
        if f is not None:
            out.append(f)
    return out

def parse_pdf_files(paths: List[str], *, use_ocr: bool = False) -> List[Factura]:
    out: List[Factura] = []
    for p in (paths or []):
        if str(p).lower().endswith(".pdf"):
            out.extend(parse_pdf_invoice(p, use_ocr=use_ocr))
    return out
