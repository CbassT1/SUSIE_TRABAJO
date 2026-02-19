# tests/test_pdf_parser.py
from __future__ import annotations

from parser.pdf_parser import parse_pdf_invoice


def test_provisionales_has_5_pages():
    facts = parse_pdf_invoice("251209 PROVISIONALES.pdf", use_ocr=False)
    assert len(facts) == 5


def test_vje_maps_to_e54():
    facts = parse_pdf_invoice("251209 PROVISIONALES.pdf", use_ocr=False)
    # Busca cualquier concepto con clave_unidad E54 (por mapeo VJE)
    assert any((c.clave_unidad or "").upper() == "E54" for f in facts for c in (f.conceptos or []))
