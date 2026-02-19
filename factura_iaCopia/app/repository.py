from __future__ import annotations

from pathlib import Path
from typing import List

from app.models import Factura
from parser.adapter import facturas_parser_to_ui


class ExcelRepository:
    def __init__(self, incoming_dir: Path, excel_parser):
        self.incoming_dir = incoming_dir
        self.excel_parser = excel_parser

    def cargar_todas(self) -> List[Factura]:
        facturas_ui: List[Factura] = []
        archivos = [p for p in self.incoming_dir.glob("*.xlsx") if not p.name.startswith("~$")]

        for archivo in archivos:
            facturas_parser = self.excel_parser.parse_file(archivo)
            facturas_ui.extend(facturas_parser_to_ui(facturas_parser))

        return facturas_ui
