from __future__ import annotations

import math
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd
from openpyxl import load_workbook

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "incoming"

UNIDADES_FILE = BASE_DIR / "unidades_medida.xlsx"
CLAVES_FILE = BASE_DIR / "claves_sat.xlsx"

UNIDADES_DF: Optional[pd.DataFrame] = None
UNIDADES_SET: set[str] = set()
UNIDADES_NAME_MAP: dict[str, str] = {}

CLAVES_SET: set[str] = set()
CLAVES_NAME_MAP: dict[str, str] = {}

PROVEEDOR_CANONICOS = {
    "MITAFSA",
    "BETANSA",
    "ARGONZA",
    "REKLAMSA",
    "ERF",
    "EDETESA",
    "XISISA",
    "GEREDAB",
    "TIKSA",
    "VIESA",
    "DIAFIMSA",
    "ARMOLEB",
    "JOVIC",
    "COLMEXL",
    "MARTO",
    "CHESTER",
}

# ====================== UTILIDADES BÁSICAS ======================

def normalize(text: str) -> str:
    t = str(text).upper()
    for a, b in [("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U")]:
        t = t.replace(a, b)
    return t

def to_float(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value)
    s = s.replace("$", "").replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None

def is_blank_cell(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str) and not v.strip():
        return True
    return False

def format_cantidad(value) -> str:
    num = to_float(value)
    if num is None:
        return ""
    if float(num).is_integer():
        return str(int(num))
    return f"{num:.4f}"

def format_4_dec(value) -> str:
    num = to_float(value)
    if num is None:
        return ""
    return f"{num:.4f}"

def format_2_dec(value) -> str:
    num = to_float(value)
    if num is None:
        return ""
    return f"{num:.2f}"

def get_cell_value(row: pd.Series, col_spec: Any):
    if col_spec is None:
        return None
    try:
        if isinstance(col_spec, int):
            return row.iloc[col_spec]
        v = row.get(col_spec)
        if isinstance(v, pd.Series):
            for x in v.tolist():
                if x is None:
                    continue
                if isinstance(x, float) and math.isnan(x):
                    continue
                if isinstance(x, str) and not x.strip():
                    continue
                return x
            return None
        return v
    except Exception:
        return None

def normalize_proveedor(name: Optional[str]) -> Optional[str]:
    if not name:
        return None

    s = str(name).upper()

    patrones_quitar = [
        r"S\.?\s*A\.?\s*DE\s*C\.?\s*V\.?",
        r"SA\s+DE\s+CV",
        r"S\s*DE\s*RL\s*DE\s*CV",
        r"S\.?\s*DE\s*R\.?L\.?\s*DE\s*C\.?\s*V\.?",
    ]
    for pat in patrones_quitar:
        s = re.sub(pat, "", s)

    s = s.replace(",", "").replace(".", "")
    s = re.sub(r"\s+", "", s)
    s = s.strip("-")

    s_norm = normalize(s)
    if not s_norm:
        return None

    mapping = [
        ("MITAFSA", ["MITAFSA", "MITFSA"]),
        ("BETANSA", ["BETANSA"]),
        ("ARGONZA", ["ARGONZA"]),
        ("REKLAMSA", ["REKLAMSA"]),
        ("ERF", ["ERF"]),
        ("EDETESA", ["EDETESA"]),
        ("XISISA", ["XISISA"]),
        ("GEREDAB", ["GEREDAB"]),
        ("TIKSA", ["TIKSA"]),
        ("VIESA", ["VIESA"]),
        ("DIAFIMSA", ["DIAFIMSA"]),
        ("ARMOLEB", ["ARMOLEB"]),
        ("JOVIC", ["JOVIC"]),
        ("COLMEXL", ["COLMEXL"]),
        ("MARTO", ["MARTO", "GRUPOMARTINEZDELATORRE", "MARTINEZDELATORRE"]),
        ("CHESTER", ["CHESTER"]),
    ]

    for canon, tokens in mapping:
        for tok in tokens:
            if tok in s_norm:
                return canon

    return s_norm or None

def normalize_rfc(rfc: Optional[str]) -> Optional[str]:
    if not rfc:
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", str(rfc))
    s = s.upper()
    return s or None


# ====================== CARGA DE CATÁLOGOS ======================

def load_unidades_catalog(path: Path):
    global UNIDADES_DF, UNIDADES_SET, UNIDADES_NAME_MAP
    if not path.exists():
        return

    df = pd.read_excel(path)
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)

    col_clave = None
    for col in df.columns:
        n = normalize(col)
        if "CLAVE" in n and "UNIDAD" in n:
            col_clave = col
            break
    if col_clave is None:
        for col in df.columns:
            if "CLAVE" in normalize(col):
                col_clave = col
                break
    if col_clave is None:
        return

    UNIDADES_DF = df
    UNIDADES_SET = set(
        str(v).strip().upper()
        for v in df[col_clave]
        if not pd.isna(v) and str(v).strip()
    )

    text_cols = []
    for col in df.columns:
        n = normalize(col)
        if any(k in n for k in ["NOMBRE", "DESCRIP", "SIMBOLO", "SÍMBOLO"]):
            text_cols.append(col)

    UNIDADES_NAME_MAP = {}
    for _, row in df.iterrows():
        clave = row.get(col_clave)
        if pd.isna(clave):
            continue
        clave = str(clave).strip().upper()
        for col in text_cols:
            val = row.get(col)
            if isinstance(val, str) and val.strip():
                key = normalize(val)
                if key and key not in UNIDADES_NAME_MAP:
                    UNIDADES_NAME_MAP[key] = clave

def load_claves_catalog(path: Path):
    global CLAVES_SET, CLAVES_NAME_MAP
    if not path.exists():
        return

    df = pd.read_excel(path)
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)

    col_clave = None
    for col in df.columns:
        n = normalize(col)
        if "CLAVE" in n and ("PROD" in n or "SERV" in n):
            col_clave = col
            break
    if col_clave is None:
        for col in df.columns:
            n = normalize(col)
            if "CLAVE" in n:
                col_clave = col
                break
    if col_clave is None:
        return

    col_desc = None
    for col in df.columns:
        n = normalize(col)
        if "DESCRIP" in n or "DESCRIPCION" in n:
            col_desc = col
            break

    CLAVES_SET = set()
    CLAVES_NAME_MAP = {}

    for _, row in df.iterrows():
        v = row.get(col_clave)
        if pd.isna(v):
            continue
        clave = str(v).strip()
        if not clave:
            continue
        CLAVES_SET.add(clave)
        if col_desc:
            desc = row.get(col_desc)
            if isinstance(desc, str) and desc.strip():
                CLAVES_NAME_MAP[clave] = desc.strip()

def load_catalogs():
    load_unidades_catalog(UNIDADES_FILE)
    load_claves_catalog(CLAVES_FILE)


# ====================== MODELO DE DOMINIO ======================

@dataclass
class ConceptoFactura:
    cantidad: Optional[float] = None
    clave_prod_serv: Optional[str] = None
    nombre_prod_serv: Optional[str] = None
    clave_unidad: Optional[str] = None
    descripcion: str = ""
    precio_unitario: Optional[float] = None
    importe: Optional[float] = None

@dataclass
class Factura:
    proveedor: Optional[str]
    rfc: Optional[str]
    conceptos: List[ConceptoFactura] = field(default_factory=list)
    subtotal: Optional[float] = None
    iva: Optional[float] = None
    total: Optional[float] = None
    uso_cfdi: Optional[str] = None
    metodo_pago: Optional[str] = None
    forma_pago: Optional[str] = None
    formato: Optional[str] = None
    archivo: Optional[Path] = None

    # NUEVO: flags útiles para UI
    es_usd: bool = False  # si la hoja es en dólares (ej: “DLLS”)

@dataclass
class ColumnMapping:
    cantidad_col: Optional[object] = None
    clave_prod_col: Optional[object] = None
    clave_unidad_col: Optional[object] = None
    unidad_text_col: Optional[object] = None
    concepto_col: Optional[object] = None
    precio_unitario_col: Optional[object] = None
    importe_col: Optional[object] = None


# ====================== DETECCIÓN DE ENCABEZADO Y TOTALES ======================

HEADER_KEYWORDS = [
    "CANTIDAD",
    "CANT.",
    "CLAVE UNIDAD",
    "CLAVE UNIDAD SAT",
    "CLAVE DE UNIDAD",
    "CLAVE DE SERVICIO",
    "CLAVE PROD",
    "CLAVE PROD SERV",
    "CLAVE PROD/SERV",
    "CLAVE PRODUCTO",
    "CLAVE PROD SERVICIO",
    "CLAVE SAT",
    "CODIGO",
    "CÓDIGO",
    "DESCRIPCION",
    "DESCRIPCIÓN",
    "DESCRIPCION UNIDAD",
    "DESCRIPCION UNIDAD SAT",
    "DESCRIP PROD",
    "DESCRIPCIÓN DE PROD",
    "CONCEPTO",
    "PRECIO UNITARIO",
    "VALOR UNITARIO",
    "VALOR UITARIO",
    "IMPUESTO",
    "IMPORTE",
]

def _count_header_keywords_in_row(row: pd.Series) -> int:
    matches = 0
    for cell in row:
        if isinstance(cell, str):
            cell_up = normalize(cell)
            if any(key in cell_up for key in HEADER_KEYWORDS):
                matches += 1
    return matches

def _debe_unir_header_doble_manuel(header_row: pd.Series, second_row: pd.Series, filename: str, sheet_name: str) -> bool:
    name_hint = "MANUEL" in normalize(Path(filename).name) or "MANUEL" in normalize(str(sheet_name))
    header_hint = any(isinstance(v, str) and "CLAVE DEL" in normalize(v) for v in header_row)

    if not (name_hint or header_hint):
        return False

    for v in second_row:
        if isinstance(v, str) and normalize(v).strip() in {"PRODUCTO", "SAT", "UNITARIO"}:
            return True
    return False

def construir_header_y_data_start(df: pd.DataFrame, header_idx: int, filename: str, sheet_name: str):
    header_row = df.iloc[header_idx].copy()
    data_start_idx = header_idx + 1

    if header_idx + 1 >= len(df):
        return header_row, data_start_idx

    second_row = df.iloc[header_idx + 1]

    unir = False
    if _count_header_keywords_in_row(second_row) >= 2:
        unir = True
    elif _debe_unir_header_doble_manuel(header_row, second_row, filename, sheet_name):
        unir = True

    if unir:
        for col_idx in range(len(header_row)):
            top_val = header_row.iloc[col_idx]
            bottom_val = second_row.iloc[col_idx]

            if is_blank_cell(top_val) and isinstance(bottom_val, str) and bottom_val.strip():
                header_row.iloc[col_idx] = bottom_val
            elif isinstance(top_val, str) and isinstance(bottom_val, str) and bottom_val.strip():
                header_row.iloc[col_idx] = f"{top_val} {bottom_val}".strip()

        data_start_idx = header_idx + 2

    return header_row, data_start_idx

def extraer_parametros_pago_manuel_flexible(df: pd.DataFrame):
    res = {"uso_cfdi": None, "metodo_pago": None, "forma_pago": None}

    fixed = [
        (14, 3, "metodo_pago"),
        (15, 3, "forma_pago"),
        (16, 3, "uso_cfdi"),
    ]
    for r, c, key in fixed:
        if df.shape[0] > r and df.shape[1] > c:
            v = df.iat[r, c]
            if isinstance(v, str) and v.strip():
                txt = v.strip()
                if ":" in txt:
                    after = txt.split(":", 1)[1].strip()
                    res[key] = after or txt
                else:
                    res[key] = txt

    patrones = {
        "uso_cfdi": ["USO CFDI", "USO DE CFDI", "USO DEL CFDI"],
        "metodo_pago": ["METODO DE PAGO", "MÉTODO DE PAGO", "METODO PAGO"],
        "forma_pago": ["FORMA DE PAGO"],
    }

    for _, row in df.iloc[:120].iterrows():
        for j, val in enumerate(row):
            if not isinstance(val, str) or not val.strip():
                continue
            t = val.strip()
            up = normalize(t)

            for key, labels in patrones.items():
                if res[key] is not None:
                    continue
                if any(lbl in up for lbl in labels):
                    if ":" in t:
                        after = t.split(":", 1)[1].strip()
                        if after:
                            res[key] = after
                            continue
                    for k in range(j + 1, len(row)):
                        v = row.iloc[k]
                        if isinstance(v, str) and v.strip():
                            res[key] = v.strip()
                            break

    return res

def encontrar_fila_encabezado(df: pd.DataFrame) -> Optional[int]:
    for idx, row in df.iterrows():
        matches = 0
        for cell in row:
            if isinstance(cell, str):
                cell_up = normalize(cell)
                if any(key in cell_up for key in HEADER_KEYWORDS):
                    matches += 1
        if matches >= 2:
            return idx
    return None

def extraer_totales(df: pd.DataFrame):
    totales = {"subtotal": None, "iva": None, "total": None}

    for _, row in df.iterrows():
        nums = [to_float(v) for v in row]
        nums = [n for n in nums if n is not None]
        if not nums:
            continue
        num = nums[-1]

        for cell in row:
            if not isinstance(cell, str):
                continue
            t = normalize(cell)

            if "SUBTOTAL" in t or "SUB TOTAL" in t or "SUB.TOTAL" in t or "SUB-TOTAL" in t:
                if totales["subtotal"] is None:
                    totales["subtotal"] = num

            if "IVA" in t and "RET" not in t:
                if totales["iva"] is None:
                    totales["iva"] = num

            if any(k in t for k in ["TOTAL DEPOSITADO", "TOTAL FACTURA", "TOTAL A PAGAR"]):
                totales["total"] = num
            elif "TOTAL" in t and "SUBTOTAL" not in t and "SUB TOTAL" not in t and "SUB-TOTAL" not in t:
                if totales["total"] is None:
                    totales["total"] = num

    sub = totales["subtotal"]
    iva = totales["iva"]
    tot = totales["total"]

    if tot is None and sub is not None and iva is not None:
        totales["total"] = sub + iva
    elif tot is not None and sub is not None and iva is not None:
        if abs(tot - sub) < 0.01 and iva > 0:
            totales["total"] = sub + iva

    return totales


# ====================== META: PROVEEDOR Y RFC ======================

BANNED_PROV = {
    "USO DE CFDI",
    "FISICA",
    "MORAL",
    "OBLIGATORIO",
    "ERROR",
    "DIA",
    "ESTADO",
    "REGIMEN",
    "REGIMEN FISCAL",
    "CIUDAD",
    "PAIS",
    "PAÍS",
    "CODIGO POSTAL",
    "CODIGO POSTAL.",
    "CP",
}

def extraer_meta(df: pd.DataFrame):
    meta = {"PROVEEDOR": None, "RAZON SOCIAL:": None, "RFC:": None}
    candidatos_proveedor: List[str] = []

    for _, row in df.iloc[:60].iterrows():
        for j, val in enumerate(row):
            if not isinstance(val, str):
                continue
            text = val.strip()
            t = normalize(text)

            if t.startswith("PROVEEDOR"):
                for k in range(j + 1, len(row)):
                    v = row.iloc[k]
                    if not isinstance(v, str):
                        continue
                    cand = v.strip()
                    if not cand:
                        continue
                    cand_norm = normalize(cand)
                    if cand_norm in BANNED_PROV or len(cand) < 4:
                        continue
                    candidatos_proveedor.append(cand)
                    break

            if "EMPRESA A FACTURAR" in t:
                for k in range(j + 1, len(row)):
                    v = row.iloc[k]
                    if not isinstance(v, str):
                        continue
                    cand = v.strip()
                    if not cand:
                        continue
                    cand_norm = normalize(cand)
                    if cand_norm in BANNED_PROV or len(cand) < 4:
                        continue
                    candidatos_proveedor.append(cand)
                    break

            if "RFC" in t and not meta["RFC:"]:
                for k in range(j + 1, len(row)):
                    v = row.iloc[k]
                    if isinstance(v, str) and v.strip():
                        meta["RFC:"] = v.strip()
                        break

        first_raw = str(row.iloc[0]).strip()
        first = normalize(first_raw)
        if first == "RAZON SOCIAL:":
            razon = str(row.iloc[1]).strip()
            if razon:
                meta["RAZON SOCIAL:"] = razon
        elif first == "RFC:" and not meta["RFC:"]:
            meta["RFC:"] = str(row.iloc[1]).strip()

    if candidatos_proveedor:
        meta["PROVEEDOR"] = max(candidatos_proveedor, key=len)

    meta["PROVEEDOR"] = normalize_proveedor(meta["PROVEEDOR"])
    meta["RFC:"] = normalize_rfc(meta["RFC:"])
    return meta


# ====================== USO CFDI / MÉTODO / FORMA PAGO ======================

def extraer_parametros_pago(df: pd.DataFrame):
    res = {"uso_cfdi": None, "metodo_pago": None, "forma_pago": None}

    patrones = {
        "uso_cfdi": ["USO CFDI", "USO DE CFDI"],
        "metodo_pago": ["METODO DE PAGO", "MÉTODO DE PAGO", "METODO PAGO"],
        "forma_pago": ["FORMA DE PAGO"],
    }

    for _, row in df.iloc[:80].iterrows():
        for j, val in enumerate(row):
            if not isinstance(val, str):
                continue
            t = normalize(val)

            for key, labels in patrones.items():
                if any(lbl in t for lbl in labels) and res[key] is None:
                    for k in range(j + 1, len(row)):
                        v = row.iloc[k]
                        if isinstance(v, str) and v.strip():
                            res[key] = v.strip()
                            break

    return res

def extraer_parametros_pago_manuel(df: pd.DataFrame):
    res = {"uso_cfdi": None, "metodo_pago": None, "forma_pago": None}
    if df.shape[0] >= 17 and df.shape[1] >= 4:
        metodo = df.iat[14, 3]
        forma = df.iat[15, 3]
        uso = df.iat[16, 3]
        if isinstance(metodo, str) and metodo.strip():
            res["metodo_pago"] = metodo.strip()
        if isinstance(forma, str) and forma.strip():
            res["forma_pago"] = forma.strip()
        if isinstance(uso, str) and uso.strip():
            res["uso_cfdi"] = uso.strip()
    return res

def normalizar_metodo_pago(metodo: Optional[str]) -> Optional[str]:
    if not metodo:
        return None

    t = normalize(metodo)
    t_compact = re.sub(r"[^A-Z0-9]", "", t)

    grupo_pue = False
    if "PUE" in t_compact:
        grupo_pue = True
    if "EXHIBICION" in t_compact and "PARCIAL" not in t_compact and "DIFERIDO" not in t_compact:
        grupo_pue = True
    if (
            "PAGOENUNASOLA" in t_compact
            or "PAGOENUNSOLA" in t_compact
            or "PAGOENUNASOLAEXHIBICION" in t_compact
            or "PAGOENUNSOLAEXHIBICION" in t_compact
            or "UNASOLAEXHIBICION" in t_compact
            or "UNSOLAEXHIBICION" in t_compact
    ):
        grupo_pue = True

    grupo_ppd = any(
        token in t_compact
        for token in [
            "PPD",
            "PAGOPARCIAL",
            "PAGOENPARCIALIDADES",
            "PARCIALIDADES",
            "PAGODIFERIDO",
            "PAGOPARCIALDIFERIDO",
        ]
    )

    if (grupo_pue and grupo_ppd) or (not grupo_pue and not grupo_ppd):
        return None
    if grupo_pue:
        return "PUE"
    if grupo_ppd:
        return "PPD"
    return None

def normalizar_forma_pago(forma: Optional[str]) -> Optional[str]:
    if not forma:
        return None

    t = normalize(forma)

    if "POR DEFINIR" in t or "PORDEFINIR" in t:
        return "POR DEFINIR"
    if "CHEQUE" in t:
        return "CHEQUE NOMINATIVO"
    if "TRANSFERENCIA" in t or "TRANSFER " in t or t.endswith("TRANSFER"):
        return "TRANSFERENCIA ELECTRONICA DE FONDOS"

    return None

USO_CFDI_TOKENS = {
    "G01": ["ADQUISICION", "ADQUISICIONDEMERCANCIAS"],
    "G02": ["DEVOLUCIONES", "DESCUENTOS", "BONIFICACIONES"],
    "G03": ["GASTOS", "GASTOSENGENERAL"],
    "I01": ["CONSTRUCCIONES"],
    "I02": ["MOBILIARIO", "EQUIPODEOFICINA"],
    "I03": ["EQUIPODETRANSPORTE"],
    "I04": ["EQUIPODECOMPUTO", "COMPUTO"],
    "I05": ["DADOS", "TROQUELES", "MOLDES", "MATRICES", "HERRAMENTAL"],
    "I06": ["COMUNICACIONESTELEFONICAS"],
    "I07": ["COMUNICACIONESSATELITALES"],
    "I08": ["OTRAMAQUINARIA", "OTRAMAQUINARIAEQUIPO"],
    "D01": ["HONORARIOSMEDICOS", "HOSPITALARIOS", "DENTALES"],
    "D02": ["GASTOSMEDICOSPORINCAPACIDAD", "INCAPACIDAD"],
    "D03": ["GASTOSFUNERALES"],
    "D04": ["DONATIVOS"],
    "D05": ["INTERESESREALESPAGADOSPORCREDITOSH"],
    "D06": ["APORTACIONESVOLUNTARIASALSAR", "SAR"],
    "D07": ["PRIMASDESEGUROSDEGASTOSMEDICOS"],
    "D08": ["GASTOSDETRANSPORTACIONESCOLAR"],
    "D09": ["DEPOSITOSENCUESTASPARAELA", "PENSIONES"],
    "D10": ["PAGOSPORTSERVICIOSEDUCATIVOS", "COLEGIATURAS"],
    "S01": ["SINEFECTOSFISCALES"],
}

def normalizar_uso_cfdi(uso: Optional[str]) -> Optional[str]:
    if not uso:
        return None

    t = normalize(uso)
    t_compact = re.sub(r"[^A-Z0-9]", "", t)

    for code, tokens in USO_CFDI_TOKENS.items():
        if code in t_compact:
            return code
        for tok in tokens:
            if tok in t_compact:
                return code

    return None


# ====================== DETECCIÓN DE COLUMNAS Y FORMATO ======================

def detectar_columnas(tabla: pd.DataFrame) -> ColumnMapping:
    cols_norm = {normalize(str(c)): c for c in tabla.columns}

    cantidad_col = None
    for key_norm, orig in cols_norm.items():
        if key_norm.startswith("CANT"):
            cantidad_col = orig
            break

    clave_unidad_col = None
    for key_norm, orig in cols_norm.items():
        if "CLAVE UNIDAD" in key_norm or "CLAVE DE UNIDAD" in key_norm or "# CLAVE UNIDAD" in key_norm:
            clave_unidad_col = orig
            break

    unidad_text_col = None
    for key_norm, orig in cols_norm.items():
        if key_norm == "UNIDAD":
            unidad_text_col = orig
            break

    clave_prod_col = None
    for key_norm, orig in cols_norm.items():
        tiene_clave = "CLAVE" in key_norm
        tiene_prod_serv = any(w in key_norm for w in ["PRODUCTO", "PROD/SERV", "PROD SERV", "SERVICIO SAT", "SERVICIO"])
        if (
                "CLAVE PRODUCTO" in key_norm
                or "CLAVE PROD" in key_norm
                or "CLAVE DE SERVICIO" in key_norm
                or "CLAVE PROD SERV" in key_norm
                or "CLAVE PROD/SERV" in key_norm
                or "CLAVE PROD SERVICIO" in key_norm
                or key_norm.startswith("CODIGO")
                or key_norm.startswith("CÓDIGO")
                or "CLAVE CONCEPTO" in key_norm
                or "CLAVE DE PRODUCTO" in key_norm
                or (tiene_clave and tiene_prod_serv)
        ):
            clave_prod_col = orig
            break

    if clave_prod_col is None:
        for key_norm, orig in cols_norm.items():
            if key_norm == "SAT":
                clave_prod_col = orig
                break

    if clave_unidad_col is None:
        for key_norm, orig in cols_norm.items():
            if "CLAVE SAT" in key_norm:
                if any("DESCRIPCION UNIDAD" in k for k in cols_norm.keys()):
                    clave_unidad_col = orig
                elif clave_prod_col is None:
                    clave_prod_col = orig
                else:
                    clave_unidad_col = orig
                break

    concepto_col = None
    if "CONCEPTO" in cols_norm:
        concepto_col = cols_norm["CONCEPTO"]
    else:
        for key_norm, orig in cols_norm.items():
            if "DESCRIPCION DE PROD" in key_norm or "DESCRIPCION PROD" in key_norm:
                concepto_col = orig
                break
        if concepto_col is None:
            for key_norm, orig in cols_norm.items():
                if "DESCRIPCION" in key_norm:
                    concepto_col = orig
                    break

    precio_unitario_col = None
    for key_norm, orig in cols_norm.items():
        if (
                (key_norm.startswith("PRECIO") and ("UNIT" in key_norm or key_norm == "PRECIO"))
                or "VALOR UNITARIO" in key_norm
                or "VALOR UITARIO" in key_norm
                or ("VR" in key_norm and "UNITARIO" in key_norm)
        ):
            precio_unitario_col = orig
            break

    importe_col = None
    for key_norm, orig in cols_norm.items():
        if "IMPORTE" in key_norm:
            importe_col = orig
            break

    return ColumnMapping(
        cantidad_col=cantidad_col,
        clave_prod_col=clave_prod_col,
        clave_unidad_col=clave_unidad_col,
        unidad_text_col=unidad_text_col,
        concepto_col=concepto_col,
        precio_unitario_col=precio_unitario_col,
        importe_col=importe_col,
    )

def detectar_formato(cols_norm_keys: set[str], filename: str) -> str:
    if "CLAVE UNIDAD SAT" in cols_norm_keys and "CLAVE PRODUCTO O SERVICIO SAT" in cols_norm_keys:
        return "FORMATO_1"

    if "CLAVE DE UNIDAD DEL SAT" in cols_norm_keys and "CLAVE DE PRODUCTO O SERVICIO SAT" in cols_norm_keys:
        return "FORMATO_2"

    if "CLAVE PROD SERV" in cols_norm_keys:
        return "FORMATO_HAFEN"

    if "# CLAVE UNIDAD" in cols_norm_keys and "# CLAVE CONCEPTO" in cols_norm_keys:
        return "FORMATO_LAMBRETON_2"

    if "PRECIO UNITARIO" in cols_norm_keys and "TOTAL" in cols_norm_keys:
        return "FORMATO_LAMBRETON_1"

    if "CLAVE SAT" in cols_norm_keys and "DESCRIPCION UNIDAD SAT" in cols_norm_keys and "CLAVE PRODUCTO" in cols_norm_keys:
        return "FORMATO_MONY"

    if "CLAVE UNIDAD SAT" in cols_norm_keys and "CLAVE DE SERVICIO SAT" in cols_norm_keys:
        return "FORMATO_MONY_2"

    if "CLAVE UNIDAD SAT" in cols_norm_keys and "CLAVE DEL PRODUCTO" in cols_norm_keys:
        return "FORMATO_MANUEL"

    if any(("VR" in k and "UNITARIO" in k) for k in cols_norm_keys) and any(("VR" in k and "TOTAL" in k) for k in cols_norm_keys):
        return "FORMATO_ULORE"

    if "CONCEPTO" in cols_norm_keys and any(k.startswith("PRECIO") for k in cols_norm_keys) and not any("CLAVE" in k for k in cols_norm_keys):
        return "FORMATO_GM"

    name_up = normalize(Path(filename).name)
    if "HAFEN" in name_up:
        return "FORMATO_HAFEN"
    if "LAMBRETON_1" in name_up or "LAMBRETON1" in name_up:
        return "FORMATO_LAMBRETON_1"
    if "LAMBRETON" in name_up:
        return "FORMATO_LAMBRETON"
    if "MONY" in name_up:
        return "FORMATO_MONY"
    if "FORMATO_1" in name_up:
        return "FORMATO_1"
    if "FORMATO_2" in name_up:
        return "FORMATO_2"
    if "MANUEL" in name_up:
        return "FORMATO_MANUEL"
    if "ULORE" in name_up:
        return "FORMATO_ULORE"
    if "GM" in name_up:
        return "FORMATO_GM"

    return "DESCONOCIDO"


# ====================== INFERENCIA / VALIDACIÓN DESDE CATÁLOGOS ======================

def detectar_unidad_servicio_especial(descripcion: Optional[str], nombre_sat: Optional[str]) -> Optional[str]:
    textos = []
    for t in (descripcion, nombre_sat):
        if isinstance(t, str) and t.strip():
            textos.append(normalize(t))

    if not textos:
        return None

    joined = " ".join(textos)
    compact = re.sub(r"\s+", "", joined)

    if any(w in joined for w in ["ACARREO", "VIAJE", "TRASLADO"]):
        if not UNIDADES_SET or "E54" in UNIDADES_SET:
            return "E54"

    if "HORASTRABAJADAS" in compact or "HORAS" in joined:
        if not UNIDADES_SET or "LH" in UNIDADES_SET:
            return "LH"

    return None

def reglas_unidad_por_texto(descripcion: Optional[str], nombre_sat: Optional[str], unidad_txt: Optional[str]) -> Optional[str]:
    textos = []
    for t in (descripcion, nombre_sat, unidad_txt):
        if isinstance(t, str) and t.strip():
            textos.append(normalize(t))

    if not textos:
        return None

    joined = " ".join(textos)
    compact = re.sub(r"\s+", "", joined)

    service_tokens = ["SERVICIO", "SERVICIOS", "HONORARIO", "MANTENIMIENTO", "MANO DE OBRA", "MANODEOBRA", "TALLER"]
    es_servicio = False
    for tok in service_tokens:
        tok_compact = tok.replace(" ", "")
        if tok in joined or tok_compact in compact:
            es_servicio = True
            break

    if "KIT" in joined:
        if not UNIDADES_SET or "KT" in UNIDADES_SET:
            return "KT"

    if "LOTE" in joined:
        if not UNIDADES_SET or "XLT" in UNIDADES_SET:
            return "XLT"

    if any(w in joined for w in ["ACARREO", "VIAJE", "TRASLADO"]):
        if not UNIDADES_SET or "E54" in UNIDADES_SET:
            return "E54"

    if "HORASTRABAJADAS" in compact or "HORAS" in joined:
        if not UNIDADES_SET or "LH" in UNIDADES_SET:
            return "LH"

    if "ENVIO" in joined:
        if not UNIDADES_SET or "E48" in UNIDADES_SET:
            return "E48"

    if "CAJA" in joined:
        if not UNIDADES_SET or "XBX" in UNIDADES_SET:
            return "XBX"

    if "M2" in joined or "METROSCUADRADOS" in compact or "METROCUADRADO" in compact:
        if es_servicio and (not UNIDADES_SET or "E48" in UNIDADES_SET):
            return "E48"
        if not UNIDADES_SET or "MTK" in UNIDADES_SET:
            return "MTK"

    if "M3" in joined or "METROSCUBICOS" in compact or "METROCUBICO" in compact:
        if es_servicio and (not UNIDADES_SET or "E48" in UNIDADES_SET):
            return "E48"
        if not UNIDADES_SET or "MTQ" in UNIDADES_SET:
            return "MTQ"

    if "KILO" in joined or "KILOS" in joined or re.search(r"\bKG\b", joined) or "KGM" in joined or "KGS" in joined:
        if es_servicio and (not UNIDADES_SET or "E48" in UNIDADES_SET):
            return "E48"
        if not UNIDADES_SET or "KGM" in UNIDADES_SET:
            return "KGM"

    if "TONELADA" in joined or re.search(r"\bTON\b", joined):
        if es_servicio and (not UNIDADES_SET or "E48" in UNIDADES_SET):
            return "E48"
        if not UNIDADES_SET or "TNE" in UNIDADES_SET:
            return "TNE"

    if "ROLLO" in joined:
        if not UNIDADES_SET or "XRO" in UNIDADES_SET:
            return "XRO"

    if "JUEGO" in joined:
        if not UNIDADES_SET or "SET" in UNIDADES_SET:
            return "SET"

    return None

def inferir_clave_unidad(clave_raw, unidad_txt, descripcion, nombre_sat) -> Optional[str]:
    especial = detectar_unidad_servicio_especial(descripcion, nombre_sat)
    if especial:
        return especial

    regla = reglas_unidad_por_texto(descripcion, nombre_sat, unidad_txt)
    if regla:
        return regla

    def es_servicio(texto: Optional[str]) -> bool:
        if not isinstance(texto, str):
            return False
        t = normalize(texto)
        return any(
            w in t
            for w in ["SERVICIO", "SERVICIOS", "HONORARIO", "MANTENIMIENTO", "MANO DE OBRA"]
        )

    if not is_blank_cell(clave_raw):
        cand = str(clave_raw).strip().upper()
        if cand in ("KG", "KGS"):
            cand = "KGM"
        if es_servicio(descripcion) or es_servicio(nombre_sat):
            if not UNIDADES_SET or "E48" in UNIDADES_SET:
                return "E48"
        return cand

    if isinstance(unidad_txt, str) and unidad_txt.strip():
        ut = unidad_txt.strip().upper()
        if ut in ("KG", "KGS"):
            return "KGM"
        key = normalize(unidad_txt)
        if UNIDADES_NAME_MAP and key in UNIDADES_NAME_MAP:
            return UNIDADES_NAME_MAP[key]

    if es_servicio(descripcion) or es_servicio(nombre_sat):
        if not UNIDADES_SET or "E48" in UNIDADES_SET:
            return "E48"

    if isinstance(descripcion, str) and descripcion.strip():
        desc_up = normalize(descripcion)
        if "KIT" in desc_up and (not UNIDADES_SET or "KT" in UNIDADES_SET):
            return "KT"

    return None

def validar_clave_prodserv(clave_raw, descripcion) -> Optional[str]:
    if clave_raw in (None, "", float("nan")):
        return None
    clave = str(clave_raw).strip()
    if not clave:
        return None
    return clave

def detectar_concepto_col_lambreton_1(tabla: pd.DataFrame, mapping: ColumnMapping):
    exclude_cols = set()

    def _col_to_indexes(col_name):
        if col_name is None:
            return []
        if isinstance(col_name, int):
            return [col_name]
        return [i for i, c in enumerate(tabla.columns) if c == col_name]

    exclude_cols.update(_col_to_indexes(mapping.cantidad_col))
    exclude_cols.update(_col_to_indexes(mapping.clave_prod_col))
    exclude_cols.update(_col_to_indexes(mapping.clave_unidad_col))
    exclude_cols.update(_col_to_indexes(mapping.unidad_text_col))
    exclude_cols.update(_col_to_indexes(mapping.precio_unitario_col))
    exclude_cols.update(_col_to_indexes(mapping.importe_col))

    best_i = None
    best_count = -1

    for i in range(len(tabla.columns)):
        if i in exclude_cols:
            continue
        s = tabla.iloc[:, i]
        cnt = 0
        for v in s.head(120):
            if isinstance(v, str) and v.strip():
                cnt += 1
        if cnt > best_count:
            best_count = cnt
            best_i = i

    return best_i


# ====================== REGLAS ESPECIALES (NUEVAS) ======================

def _sheet_is_usd_by_name(sheet_name: str) -> bool:
    return "DLLS" in normalize(sheet_name)

def _contains_token_in_top_block(df: pd.DataFrame, token: str, rows: int = 4, cols: int = 6) -> bool:
    """
    Busca token en un bloque superior (por si no está exactamente en A1).
    """
    tok = normalize(token)
    r = min(rows, df.shape[0])
    c = min(cols, df.shape[1])
    try:
        block = df.iloc[:r, :c]
        for v in block.values.flatten():
            if isinstance(v, str) and v.strip():
                if tok in normalize(v):
                    return True
    except Exception:
        return False
    return False


# ====================== PARSER PRINCIPAL ======================

class ExcelFacturaParser:
    def parse_file(self, ruta: Path) -> List[Factura]:
        wb = load_workbook(ruta, data_only=True, read_only=False)
        visible_sheet_names = [ws.title for ws in wb.worksheets if ws.sheet_state == "visible"]
        if not visible_sheet_names:
            visible_sheet_names = [wb.worksheets[0].title]

        facturas: List[Factura] = []

        for sheet_name in visible_sheet_names:
            df = pd.read_excel(ruta, sheet_name=sheet_name, header=None)

            meta = extraer_meta(df)

            # Detectar formato Kugel por encabezados en las primeras filas
            es_kugel = False
            try:
                top_vals = df.iloc[:40, :].values.flatten()
                for _v in top_vals:
                    if isinstance(_v, str) and "KUGEL" in _v.upper():
                        es_kugel = True
                        break
            except Exception:
                es_kugel = False

            header_idx = encontrar_fila_encabezado(df)
            if header_idx is None:
                continue

            header_row, data_start_idx = construir_header_y_data_start(
                df, header_idx, ruta.name, sheet_name
            )

            tabla = df.iloc[data_start_idx:].copy()
            tabla.columns = header_row
            tabla = tabla.dropna(how="all")

            cols_norm = {normalize(str(c)) for c in tabla.columns}
            formato_hoja = detectar_formato(cols_norm, f"{ruta.name}:{sheet_name}")
            mapping = detectar_columnas(tabla)

            if formato_hoja == "FORMATO_LAMBRETON_1":
                mapping.concepto_col = detectar_concepto_col_lambreton_1(
                    tabla, mapping
                )

            totales_hoja = extraer_totales(df)
            pagos_hoja = extraer_parametros_pago(df)

            if formato_hoja == "FORMATO_MANUEL":
                pagos_m = extraer_parametros_pago_manuel_flexible(df)
                for k, v in pagos_m.items():
                    if v:
                        pagos_hoja[k] = v

            if formato_hoja == "FORMATO_GM":
                top = df.iloc[:4, :]

                if not meta.get("PROVEEDOR"):
                    for val in top.values.flatten():
                        if not isinstance(val, str) or not val.strip():
                            continue
                        cand = normalize_proveedor(val)
                        if cand and cand in PROVEEDOR_CANONICOS:
                            meta["PROVEEDOR"] = cand
                            break

                if not meta.get("RFC:"):
                    for val in top.values.flatten():
                        if not isinstance(val, str):
                            continue
                        if "RFC" in normalize(val):
                            m = re.search(
                                r"([A-Za-z]{3,4}\d{6}[A-Za-z0-9]{3})", val
                            )
                            if m:
                                meta["RFC:"] = m.group(1)
                                break

                uso_gm = None
                metodo_gm = None
                for val in top.values.flatten():
                    if not isinstance(val, str) or not val.strip():
                        continue
                    if uso_gm is None:
                        u = normalizar_uso_cfdi(val)
                        if u:
                            uso_gm = u
                    if metodo_gm is None:
                        mp = normalizar_metodo_pago(val)
                        if mp:
                            metodo_gm = mp

                if uso_gm and not pagos_hoja.get("uso_cfdi"):
                    pagos_hoja["uso_cfdi"] = uso_gm
                if metodo_gm and not pagos_hoja.get("metodo_pago"):
                    pagos_hoja["metodo_pago"] = metodo_gm

            if formato_hoja == "FORMATO_MONY_2":
                top_mony2 = df.iloc[:3, :]
                if not meta.get("PROVEEDOR"):
                    for val in top_mony2.values.flatten():
                        if not isinstance(val, str) or not val.strip():
                            continue
                        cand = normalize_proveedor(val)
                        if cand and cand in PROVEEDOR_CANONICOS:
                            meta["PROVEEDOR"] = cand
                            break

            if not pagos_hoja.get("metodo_pago"):
                for _, row in df.iloc[:80].iterrows():
                    for val in row:
                        if not isinstance(val, str) or not val.strip():
                            continue
                        mp = normalizar_metodo_pago(val)
                        if mp:
                            pagos_hoja["metodo_pago"] = val.strip()
                            break
                    if pagos_hoja.get("metodo_pago"):
                        break

            proveedor = meta.get("PROVEEDOR")
            rfc = meta.get("RFC:")
            subtotal = totales_hoja.get("subtotal")
            iva = totales_hoja.get("iva")
            total = totales_hoja.get("total")

            uso_cfdi = pagos_hoja.get("uso_cfdi")
            metodo_pago = pagos_hoja.get("metodo_pago")
            forma_pago = pagos_hoja.get("forma_pago")

            # ===== NUEVAS REGLAS: MANUEL (CETSA) + DLLS =====
            es_usd = _sheet_is_usd_by_name(sheet_name)

            if formato_hoja == "FORMATO_MANUEL":
                # si arriba aparece CETSA => RFC fijo
                if _contains_token_in_top_block(df, "CETSA", rows=6, cols=10):
                    rfc = "CET960306KS7"

            # ===== NUEVAS REGLAS: HAFEN => proveedor default EDETESA =====
            if formato_hoja == "FORMATO_HAFEN":
                if not proveedor:
                    proveedor = "EDETESA"

            all_conceptos: List[ConceptoFactura] = []
            indices = list(tabla.index)
            used_as_text = set()

            for idx in indices:
                if idx in used_as_text:
                    continue

                row = tabla.loc[idx]

                if mapping.cantidad_col is not None:
                    cant = to_float(row.get(mapping.cantidad_col))
                    if cant is None:
                        continue
                else:
                    cant = 1.0

                clave_prod_raw = (
                    row.get(mapping.clave_prod_col)
                    if mapping.clave_prod_col is not None
                    else None
                )
                clave_unidad_raw = (
                    row.get(mapping.clave_unidad_col)
                    if mapping.clave_unidad_col is not None
                    else None
                )
                unidad_txt = (
                    row.get(mapping.unidad_text_col)
                    if mapping.unidad_text_col is not None
                    else None
                )

                concepto_val = (
                    row.get(mapping.concepto_col)
                    if mapping.concepto_col is not None
                    else None
                )
                if concepto_val is None or (
                    isinstance(concepto_val, float) and math.isnan(concepto_val)
                ):
                    concepto_str = ""
                else:
                    concepto_str = str(concepto_val).strip()

                if not concepto_str:
                    textos_row = []
                    for val in row:
                        if isinstance(val, str) and val.strip():
                            textos_row.append(val.strip())
                    if textos_row:
                        textos_row.sort(key=len, reverse=True)
                        concepto_str = textos_row[0]

                if not concepto_str:
                    for offset in (1, 2, -1, -2):
                        nidx = idx + offset
                        if nidx not in tabla.index:
                            continue
                        nrow = tabla.loc[nidx]
                        n_cant = (
                            to_float(nrow.get(mapping.cantidad_col))
                            if mapping.cantidad_col is not None
                            else None
                        )
                        if n_cant is not None:
                            continue

                        n_val = (
                            nrow.get(mapping.concepto_col)
                            if mapping.concepto_col is not None
                            else None
                        )
                        if isinstance(n_val, str) and n_val.strip():
                            concepto_str = n_val.strip()
                            used_as_text.add(nidx)
                            break

                        textos = [
                            str(v).strip()
                            for v in nrow
                            if isinstance(v, str) and v.strip()
                        ]
                        if textos:
                            textos.sort(key=len, reverse=True)
                            concepto_str = textos[0]
                            used_as_text.add(nidx)
                            break

                if (
                    formato_hoja == "FORMATO_LAMBRETON_1"
                    and mapping.concepto_col is not None
                    and concepto_str
                ):
                    nidx = idx + 1
                    while nidx in tabla.index:
                        nrow = tabla.loc[nidx]
                        n_cant = (
                            to_float(nrow.get(mapping.cantidad_col))
                            if mapping.cantidad_col is not None
                            else None
                        )
                        if n_cant is not None:
                            break

                        extra = nrow.get(mapping.concepto_col)
                        if not isinstance(extra, str) or not extra.strip():
                            break

                        concepto_str += " " + extra.strip()
                        used_as_text.add(nidx)
                        nidx += 1

                if formato_hoja == "FORMATO_MANUEL":
                    if re.search(
                        r"flete", concepto_str, flags=re.IGNORECASE
                    ):
                        concepto_str = re.sub(
                            r"flete",
                            "ENVÍO",
                            concepto_str,
                            flags=re.IGNORECASE,
                        )

                precio = (
                    to_float(row.get(mapping.precio_unitario_col))
                    if mapping.precio_unitario_col is not None
                    else None
                )
                importe = (
                    to_float(row.get(mapping.importe_col))
                    if mapping.importe_col is not None
                    else None
                )

                if (
                    (precio is None or (isinstance(precio, float) and math.isnan(precio)))
                    and importe is not None
                    and cant not in (None, 0)
                ):
                    precio = importe / cant

                clave_prod_final = validar_clave_prodserv(
                    clave_prod_raw, concepto_str
                )
                nombre_prod = (
                    CLAVES_NAME_MAP.get(clave_prod_final)
                    if clave_prod_final
                    else None
                )
                clave_unidad_final: Optional[str] = None

                if formato_hoja == "FORMATO_ULORE":
                    clave_prod_final = "80141605"
                    nombre_prod = CLAVES_NAME_MAP.get(clave_prod_final)
                    clave_unidad_final = "H87"

                elif formato_hoja in ("FORMATO_1", "FORMATO_2"):
                    especial = detectar_unidad_servicio_especial(
                        concepto_str, nombre_prod
                    )
                    if especial:
                        clave_unidad_final = especial
                    else:
                        regla_texto = reglas_unidad_por_texto(
                            concepto_str, nombre_prod, unidad_txt
                        )
                        if regla_texto:
                            clave_unidad_final = regla_texto
                        else:

                            def es_servicio(txt: Optional[str]) -> bool:
                                if not isinstance(txt, str):
                                    return False
                                tt = normalize(txt)
                                return any(
                                    w in tt
                                    for w in [
                                        "SERVICIO",
                                        "SERVICIOS",
                                        "HONORARIO",
                                        "MANTENIMIENTO",
                                        "MANO DE OBRA",
                                        "MANODEOBRA",
                                        "TALLER",
                                    ]
                                )

                            if (
                                es_servicio(concepto_str)
                                or es_servicio(nombre_prod)
                                or es_servicio(unidad_txt)
                            ):
                                clave_unidad_final = "E48"
                            else:
                                clave_unidad_final = "H87"
                else:
                    clave_unidad_final = inferir_clave_unidad(
                        clave_unidad_raw,
                        unidad_txt,
                        concepto_str,
                        nombre_prod,
                    )

                if not (concepto_str or clave_prod_final or clave_unidad_final):
                    continue

                all_conceptos.append(
                    ConceptoFactura(
                        cantidad=cant,
                        clave_prod_serv=clave_prod_final,
                        nombre_prod_serv=nombre_prod,
                        clave_unidad=clave_unidad_final,
                        descripcion=concepto_str,
                        precio_unitario=precio,
                        importe=importe,
                    )
                )

            # Normalización base de parámetros de pago
            uso_cfdi_norm = normalizar_uso_cfdi(uso_cfdi)
            metodo_pago_norm = normalizar_metodo_pago(metodo_pago)
            forma_pago_norm = normalizar_forma_pago(forma_pago)

            # ================== Reglas generales por defecto ==================

            # 1) Uso CFDI: si no se pudo determinar nada, usar G03
            if not uso_cfdi_norm:
                uso_cfdi_norm = "G03"

            # 2) Método PPD: la forma de pago SIEMPRE será "POR DEFINIR"
            if metodo_pago_norm == "PPD":
                forma_pago_norm = "POR DEFINIR"
            # 3) Si no hay forma de pago clara y no es PPD, usar Transferencia
            elif not forma_pago_norm:
                forma_pago_norm = "TRANSFERENCIA ELECTRONICA DE FONDOS"

            # ================== Ajustes especiales formato Kugel ==================

            if es_kugel:
                # RFC fijo para Kugel
                rfc = "KBR1206015VA"

                # Todas las filas sin clave de unidad explícita se marcan como H87
                for _c in all_conceptos:
                    if not (_c.clave_unidad or "").strip():
                        _c.clave_unidad = "H87"

                # Marca el formato para depuración / control si no hay uno ya
                if not formato_hoja:
                    formato_hoja = "FORMATO_KUGEL"

            # ================== Construcción de la factura ==================

            factura = Factura(
                proveedor=proveedor,
                rfc=rfc,
                conceptos=all_conceptos,
                subtotal=subtotal,
                iva=iva,
                total=total,
                uso_cfdi=uso_cfdi_norm,
                metodo_pago=metodo_pago_norm,
                forma_pago=forma_pago_norm,
                formato=formato_hoja or "DESCONOCIDO",
                archivo=Path(f"{ruta.name}::{sheet_name}"),
                es_usd=bool(es_usd),
            )
            facturas.append(factura)

        return facturas


# ====================== IMPRESIÓN EN TERMINAL ======================

def _nan_or(val: Optional[str]) -> str:
    return val if val not in (None, "") else "NaN"

def imprimir_factura(f: Factura):
    print(f"\n=== ARCHIVO: {f.archivo.name if f.archivo else ''} ===")
    print("FORMATO :", f.formato)
    print("PROVEEDOR:", f.proveedor)
    print("RFC      :", f.rfc)
    print("USO CFDI :", _nan_or(f.uso_cfdi))
    print("MÉTODO   :", _nan_or(f.metodo_pago))
    print("FORMA    :", _nan_or(f.forma_pago))
    print("ES_USD   :", "SI" if getattr(f, "es_usd", False) else "NO")

    print("\nCONCEPTOS:")
    print(
        f"{'CANTIDAD':>8} | {'CLV UNID':>10} | {'CLV PROD/SERV':>15} | "
        f"{'NOMBRE CLAVE':<40} | CONCEPTO | {'P.UNIT':>10} | {'IMPORTE':>10}"
    )
    print("-" * 170)

    for c in f.conceptos:
        print(
            f"{format_cantidad(c.cantidad):>8} | "
            f"{(c.clave_unidad or ''):>10} | "
            f"{(c.clave_prod_serv or ''):>15} | "
            f"{(c.nombre_prod_serv or '')[:40]:<40} | "
            f"{c.descripcion} | "
            f"{format_4_dec(c.precio_unitario):>10} | "
            f"{format_4_dec(c.importe):>10}"
        )

    print("\nSUBTOTAL:", format_2_dec(f.subtotal))
    print("IVA     :", format_2_dec(f.iva))
    print("TOTAL   :", format_2_dec(f.total))


# ====================== MAIN ======================

def main(self=None):
    load_catalogs()
    parser = ExcelFacturaParser()

    archivos = [p for p in DATA_DIR.glob("*.xlsx") if not p.name.startswith("~$")]

    if not archivos:
        print("No hay archivos Excel válidos en la carpeta incoming.")
        return

    for archivo in archivos:
        facturas = parser.parse_file(archivo)
        from collections import defaultdict

        self.facturas_por_archivo = defaultdict(list)

        for f in facturas:
            origen = f.archivo.name if f.archivo else ""
            archivo_base = origen.split("::", 1)[0].strip()
            self.facturas_por_archivo[archivo_base].append(f)

        self.archivos_ordenados = sorted(self.facturas_por_archivo.keys())

if __name__ == "__main__":
    main()
