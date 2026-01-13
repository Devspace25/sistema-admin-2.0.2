from __future__ import annotations

from src.admin_app.services.delivery_sale_sync import infer_delivery_charge


def test_infer_uses_explicit_usd() -> None:
    inf = infer_delivery_charge(
        amount_usd_input=5.0,
        amount_bs_input=0.0,
        delivery_amount_bs=0.0,
        zone_price_usd=10.0,
        bcv_rate=100.0,
    )
    assert inf.usd_to_add == 5.0
    assert inf.amount_usd_input == 5.0


def test_infer_converts_from_bs_when_rate_present() -> None:
    inf = infer_delivery_charge(
        amount_usd_input=0.0,
        amount_bs_input=500.0,
        delivery_amount_bs=0.0,
        zone_price_usd=0.0,
        bcv_rate=100.0,
    )
    assert inf.usd_to_add == 5.0
    assert inf.amount_usd_input == 5.0
    assert inf.amount_bs_input == 500.0


def test_infer_from_zone_price_when_no_inputs() -> None:
    inf = infer_delivery_charge(
        amount_usd_input=0.0,
        amount_bs_input=0.0,
        delivery_amount_bs=0.0,
        zone_price_usd=5.0,
        bcv_rate=100.0,
    )
    assert inf.usd_to_add == 5.0
    assert inf.amount_usd_input == 5.0
    assert inf.amount_bs_input == 500.0


def test_infer_from_zone_price_prefers_delivery_amount_bs_for_bs_value() -> None:
    inf = infer_delivery_charge(
        amount_usd_input=0.0,
        amount_bs_input=0.0,
        delivery_amount_bs=490.0,
        zone_price_usd=5.0,
        bcv_rate=100.0,
    )
    assert inf.usd_to_add == 5.0
    assert inf.amount_usd_input == 5.0
    assert inf.amount_bs_input == 490.0


def test_infer_from_delivery_amount_bs_as_last_resort() -> None:
    inf = infer_delivery_charge(
        amount_usd_input=0.0,
        amount_bs_input=0.0,
        delivery_amount_bs=330.0,
        zone_price_usd=0.0,
        bcv_rate=110.0,
    )
    assert inf.usd_to_add == 3.0
    assert inf.amount_usd_input == 3.0
    assert inf.amount_bs_input == 330.0


def test_infer_returns_zero_when_no_data() -> None:
    inf = infer_delivery_charge(
        amount_usd_input=0.0,
        amount_bs_input=0.0,
        delivery_amount_bs=0.0,
        zone_price_usd=0.0,
        bcv_rate=0.0,
    )
    assert inf.usd_to_add == 0.0
    assert inf.amount_usd_input == 0.0
    assert inf.amount_bs_input == 0.0
