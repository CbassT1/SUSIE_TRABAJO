from __future__ import annotations

from pathlib import Path
from typing import List

from app.models import Factura as UIFactura, Cliente, DatosFactura, Concepto
from parser.legacy_excel_parser import ExcelFacturaParser, load_catalogs

_CATALOGS_LOADED = False


def _ensure_catalogs_loaded():
    global _CATALOGS_LOADED
    if not _CATALOGS_LOADED:
        load_catalogs()
        _CATALOGS_LOADED = True


def _split_origen(origen: str):
    """
    Tu legacy guarda archivo como Path(f"{ruta.name}::{sheet_name}")
    Ejemplo: "archivo.xlsx::Hoja 1"
    """
    origen = (origen or "").strip()
    if "::" in origen:
        a, h = origen.split("::", 1)
        return a.strip(), h.strip()
    return origen, ""


def parse_excel_files(paths: List[str]) -> List[UIFactura]:
    """
    Función que la GUI espera: recibe rutas, devuelve List[app.models.Factura].
    """
    _ensure_catalogs_loaded()
    parser = ExcelFacturaParser()

    out: List[UIFactura] = []

    for p in (paths or []):
        ruta = Path(str(p))

        # Ignora temporales de Excel
        if ruta.name.startswith("~$"):
            continue

        legacy_facturas = parser.parse_file(ruta)

        for lf in legacy_facturas:
            origen_str = ""
            try:
                # lf.archivo es Path("archivo.xlsx::Hoja")
                origen_str = lf.archivo.name if lf.archivo else ruta.name
            except Exception:
                origen_str = ruta.name

            archivo_origen, hoja_origen = _split_origen(origen_str)

            cliente = Cliente(
                rfc=(lf.rfc or None),
                proveedor=(lf.proveedor or None),
            )

            datos = DatosFactura(
                uso_cfdi=(lf.uso_cfdi or None),
                metodo_pago=(lf.metodo_pago or None),
                forma_pago=(lf.forma_pago or None),
                es_usd=bool(getattr(lf, "es_usd", False)),
                tipo_cambio="",
                info_extra="",
            )

            conceptos_ui: List[Concepto] = []
            for c in (lf.conceptos or []):
                cantidad = float(c.cantidad or 0.0) if c.cantidad is not None else 0.0
                precio_unit = float(c.precio_unitario or 0.0) if c.precio_unitario is not None else 0.0
                importe = float(c.importe) if c.importe is not None else None

                conceptos_ui.append(
                    Concepto(
                        cantidad=cantidad,
                        clave_unidad=str(c.clave_unidad or ""),
                        clave_prod_serv=str(c.clave_prod_serv or ""),
                        concepto=str(c.descripcion or ""),
                        precio_unitario=precio_unit,
                        importe=importe,
                    )
                )

            total_val = float(lf.total or 0.0) if lf.total is not None else 0.0

            # ID estable para el visor
            factura_id = f"{archivo_origen}::{hoja_origen}" if hoja_origen else archivo_origen

            out.append(
                UIFactura(
                    id=factura_id,
                    cliente=cliente,
                    datos_factura=datos,
                    conceptos=conceptos_ui,
                    total=total_val,
                    archivo_origen=archivo_origen,
                    hoja_origen=hoja_origen,
                )
            )

    return out
