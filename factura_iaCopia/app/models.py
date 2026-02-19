from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Cliente:
    rfc: Optional[str] = None
    proveedor: Optional[str] = None


@dataclass
class DatosFactura:
    uso_cfdi: Optional[str] = None
    metodo_pago: Optional[str] = None
    forma_pago: Optional[str] = None
    sucursal: Optional[str] = None
    # NUEVO: bandera para decidir si esta factura se debe emitir/enviar
    emitir_y_enviar: bool = False
    es_usd: bool = False
    tipo_cambio: str = ""
    info_extra: str = ""


@dataclass
class Concepto:
    cantidad: float
    clave_unidad: str
    clave_prod_serv: str
    concepto: str
    precio_unitario: float
    importe: Optional[float] = None


@dataclass
class Factura:
    id: str
    cliente: Cliente
    datos_factura: DatosFactura
    conceptos: List[Concepto] = field(default_factory=list)
    total: float = 0.0
    archivo_origen: str = ""
    hoja_origen: str = ""
