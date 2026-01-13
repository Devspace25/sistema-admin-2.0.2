from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DeliveryChargeInference:
    amount_usd_input: float
    amount_bs_input: float
    usd_to_add: float


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def infer_delivery_charge(
    *,
    amount_usd_input: float | None,
    amount_bs_input: float | None,
    delivery_amount_bs: float | None,
    zone_price_usd: float | None,
    bcv_rate: float | None,
) -> DeliveryChargeInference:
    """Inferir el cargo de delivery a sumar a una venta.

    Reglas (orden de prioridad):
    1) Si hay monto USD explícito, se usa.
    2) Si no hay USD pero hay Bs y tasa, se convierte.
    3) Si ambos montos están en 0, se intenta inferir por `zone_price_usd`.
       - Si se infiere USD por zona, se completa Bs usando `delivery_amount_bs` si existe,
         o `zone_price_usd * bcv_rate` si hay tasa.
    4) Como último recurso, si hay `delivery_amount_bs` y tasa, se convierte.

    Devuelve siempre valores >= 0.
    """

    usd = max(_safe_float(amount_usd_input), 0.0)
    bs = max(_safe_float(amount_bs_input), 0.0)
    delivery_bs = max(_safe_float(delivery_amount_bs), 0.0)
    zone_usd = max(_safe_float(zone_price_usd), 0.0)
    rate = _safe_float(bcv_rate)

    inferred_usd = usd
    inferred_bs = bs

    if inferred_usd <= 0.0 and inferred_bs > 0.0 and rate > 0.0:
        inferred_usd = inferred_bs / rate

    if inferred_usd <= 0.0 and inferred_bs <= 0.0 and zone_usd > 0.0:
        inferred_usd = zone_usd
        if delivery_bs > 0.0:
            inferred_bs = delivery_bs
        elif rate > 0.0:
            inferred_bs = zone_usd * rate

    if inferred_usd <= 0.0 and inferred_bs <= 0.0 and delivery_bs > 0.0 and rate > 0.0:
        inferred_bs = delivery_bs
        inferred_usd = delivery_bs / rate

    usd_to_add = max(inferred_usd, 0.0)
    return DeliveryChargeInference(
        amount_usd_input=max(inferred_usd, 0.0),
        amount_bs_input=max(inferred_bs, 0.0),
        usd_to_add=usd_to_add,
    )
