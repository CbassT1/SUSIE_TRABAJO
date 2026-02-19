from __future__ import annotations

from typing import List, Tuple

# Factura "del parser" (la que viene de excel_parser.py)
from parser.legacy_excel_parser import Factura as ParserFactura


# Modelos "de la app" (UI / dominio)
from app.models import Factura, Cliente, DatosFactura, Concepto


def _split_origen(archivo_obj) -> Tuple[str, str]:
    """
    El parser guarda archivo como Path con nombre tipo: 'ARCHIVO.xlsx::HOJA'
    Aquí lo separamos en (archivo_origen, hoja_origen).
    """
    if archivo_obj is None:
        return "", ""
    name = getattr(archivo_obj, "name", str(archivo_obj))
    if "::" in name:
        a, h = name.split("::", 1)
        return a.strip(), h.strip()
    return str(name).strip(), ""


def _safe_str(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _safe_float(v, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def factura_parser_to_ui(f: ParserFactura, idx: int = 0) -> Factura:
    archivo_origen, hoja_origen = _split_origen(f.archivo)

    # ID estable por archivo+hoja+posicion
    fid = f"{archivo_origen}::{hoja_origen}::{idx}"

    conceptos: List[Concepto] = []
    for c in (f.conceptos or []):
        conceptos.append(
            Concepto(
                cantidad=_safe_float(getattr(c, "cantidad", 0.0), 0.0),
                clave_unidad=_safe_str(getattr(c, "clave_unidad", "")),
                clave_prod_serv=_safe_str(getattr(c, "clave_prod_serv", "")),
                concepto=_safe_str(getattr(c, "descripcion", "")),
                precio_unitario=_safe_float(getattr(c, "precio_unitario", 0.0), 0.0),
            )
        )

    datos = DatosFactura(
        uso_cfdi=_safe_str(getattr(f, "uso_cfdi", "")),
        metodo_pago=_safe_str(getattr(f, "metodo_pago", "")),
        forma_pago=_safe_str(getattr(f, "forma_pago", "")),
    )

    # NUEVO: pasar flag USD si tu modelo lo soporta
    if hasattr(datos, "es_usd"):
        try:
            setattr(datos, "es_usd", bool(getattr(f, "es_usd", False)))
        except Exception:
            pass

    return Factura(
        id=fid,
        cliente=Cliente(
            rfc=_safe_str(getattr(f, "rfc", "")),
            proveedor=_safe_str(getattr(f, "proveedor", "")),
        ),
        datos_factura=datos,
        conceptos=conceptos,
        total=_safe_float(getattr(f, "total", 0.0), 0.0),
        archivo_origen=archivo_origen,
        hoja_origen=hoja_origen,
    )


def facturas_parser_to_ui(lista_facturas: List[ParserFactura]) -> List[Factura]:
    out: List[Factura] = []
    for i, f in enumerate(lista_facturas or []):
        out.append(factura_parser_to_ui(f, idx=i))
    return out
