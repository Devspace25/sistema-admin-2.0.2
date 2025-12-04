from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

# Archivo por defecto dentro de data/
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_PATH = DATA_DIR / "price_params.json"

# Valores por defecto razonables (puedes ajustarlos en price_params.json)
DEFAULTS: Dict[str, Any] = {
    # Materiales por m2
    "mat_acrilico_3_mm": 45.0,
    "mat_acrilico_5_mm": 60.0,
    "mat_acrilico_9_mm": 95.0,
    "mat_acrilico_12_mm": 130.0,
    "mat_pvc_3_mm": 25.0,
    "mat_pvc_5_mm": 35.0,
    "mat_pvc_9_mm": 55.0,
    "mat_pvc_12_mm": 75.0,
    "mat_mdf_3_mm": 18.0,
    "mat_mdf_5_mm": 24.0,
    "mat_mdf_9_mm": 32.0,
    "mat_mdf_12_mm": 45.0,

    # Modelos (recargos por m2)
    "modelo_impresion_m2": 20.0,
    "modelo_relieve_m2": 30.0,
    "modelo_rotulado_m2": 25.0,
    "modelo_dtf_m2": 22.0,

    # Silueta extra por m2
    "corte_silueta_extra_m2": 15.0,

    # Soportes unitarios
    "soporte_base_plastica_peq_unit": 2.0,
    "soporte_base_plastica_grd_unit": 3.5,
    "separador_acero_peq_unit": 1.5,
    "separador_acero_grd_unit": 2.0,
    "separador_acrilico_peq_unit": 1.2,
    "separador_acrilico_grd_unit": 1.7,
    "gancho_pared_unit": 0.8,

    # Combos separadores
    "separador_acero_combo_2": 2.5,
    "separador_acero_combo_4": 4.5,
    "separador_acero_combo_6": 6.0,
    "separador_acrilico_combo_2": 2.0,
    "separador_acrilico_combo_4": 3.5,
    "separador_acrilico_combo_6": 4.8,

    # Luces por m2 (o por metro lineal si redondo)
    "luz_tipo_led_cinta": 18.0,
    "luz_tipo_neon_manguera": 25.0,
    "luz_tipo_ceo_corporeo": 28.0,
    "luz_tipo_neon_blister": 30.0,

    # Reguladores
    "regulador_3A": 6.0,
    "regulador_5A": 8.0,
    "regulador_7A": 10.0,
}

_CACHE: Dict[str, Any] | None = None


def load_price_params(path: Path | None = None) -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    p = path or DEFAULT_PATH
    data: Dict[str, Any] = {}
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    # Merge defaults sin pisar claves definidas
    merged = {**DEFAULTS, **data}
    _CACHE = merged
    return merged


def get_param(key: str, default: float | int | str | None = 0.0) -> Any:
    pp = load_price_params()
    return pp.get(key, default)


def material_key(material_name: str, espesor_mm: int) -> str:
    # Normalizar a slugs esperados en price_params: acrilico/pvc/mdf
    name = material_name.strip().lower()
    if "acril" in name:
        slug = "acrilico"
    elif "pvc" in name:
        slug = "pvc"
    elif "mdf" in name:
        slug = "mdf"
    else:
        slug = name.replace(" ", "_")
    return f"mat_{slug}_{int(espesor_mm)}_mm"
