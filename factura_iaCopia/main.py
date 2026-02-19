# main.py
from __future__ import annotations

from typing import List, Optional
import traceback

from parser.excel_parser import parse_excel_files
from parser.pdf_parser import parse_pdf_files

from app.models import Factura, Cliente, DatosFactura
from app.ui.app import App
import os, sys


def _error_factura(filename_only: str, detail: str) -> Factura:
    return Factura(
        id=f"{filename_only}::ERROR",
        cliente=Cliente(proveedor=None, rfc=None),
        datos_factura=DatosFactura(info_extra=f"ERROR: {detail}"),
        conceptos=[],
        total=0.0,
        archivo_origen=filename_only,
        hoja_origen="ERROR",
    )


def parse_files_mixed(paths: List[str], *, use_pdf_ocr: bool = False) -> List[Factura]:
    """
    Parser mixto con manejo de errores POR ARCHIVO:
    - Si un archivo falla, no tira toda la corrida; regresa una "Factura ERROR" para que la UI lo muestre.
    """
    facturas: List[Factura] = []

    for p in (paths or []):
        p_str = str(p)
        filename_only = p_str.split("\\")[-1].split("/")[-1]

        try:
            if p_str.lower().endswith(".xlsx"):
                facturas.extend(parse_excel_files([p_str]))
            elif p_str.lower().endswith(".pdf"):
                facturas.extend(parse_pdf_files([p_str], use_ocr=use_pdf_ocr))
        except Exception as e:
            detail = "".join(traceback.format_exception_only(type(e), e)).strip()
            facturas.append(_error_factura(filename_only, detail))

    return facturas


if __name__ == "__main__":
    # El App llama "parse_excel_files" por compatibilidad, pero aquí puede ser mixto.
    app = App(parse_excel_files=parse_files_mixed)
    app.mainloop()

