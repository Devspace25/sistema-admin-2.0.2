from __future__ import annotations

import os
import sys
import pytest

# Forzar backend offscreen para Qt
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.admin_app.db import make_engine, make_session_factory
from src.admin_app.repository import ensure_corporeo_eav
from src.admin_app.ui.corporeo_dialog import CorporeoDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_basic_calc_round_with_led_strip(qapp):
    engine = make_engine()
    Session = make_session_factory(engine)
    # Asegurar tipo EAV
    with Session() as s:
        type_id = ensure_corporeo_eav(s)
    dlg = CorporeoDialog(Session, type_id=type_id)

    # Configuración: redondo, diámetro 1000 mm (1m), material acrílico 5mm, LED cinta 10 $/u
    # Seleccionar "Redondo" de las opciones ya cargadas por EAV
    idx_red = next((i for i in range(dlg.cbo_corte.count()) if 'redon' in dlg.cbo_corte.itemText(i).lower()), -1)
    assert idx_red != -1, "Opción 'Redondo' no encontrada en Tipo de Corte"
    dlg.cbo_corte.setCurrentIndex(idx_red)
    dlg.spin_diam.setValue(1000.0)

    # Material: Acrílico
    idx_mat = next((i for i in range(dlg.cbo_material.count()) if 'acrí' in dlg.cbo_material.itemText(i).lower() or 'acri' in dlg.cbo_material.itemText(i).lower()), -1)
    assert idx_mat != -1, "Opción 'Acrílico' no encontrada en Material"
    dlg.cbo_material.setCurrentIndex(idx_mat)

    # Espesor: 5 mm
    idx_esp = next((i for i in range(dlg.cbo_espesor.count()) if '5' in dlg.cbo_espesor.itemText(i)), -1)
    assert idx_esp != -1, "Opción '5 mm' no encontrada en Espesor"
    dlg.cbo_espesor.setCurrentIndex(idx_esp)

    # Precio material por m2 (se autocompleta desde params, pero lo fijamos explícito para el test)
    spin_esp = getattr(dlg, 'spin_esp_precio', None)
    if spin_esp is not None:
        spin_esp.setValue(60.0)
    else:
        dlg._esp_precio_val = 60.0
        dlg.lbl_esp_precio.setText("60.00")

    # Luces: Cinta LED con precio unitario conocido
    idx_luz = next((i for i in range(dlg.cbo_luz_tipo.count()) if 'cinta' in dlg.cbo_luz_tipo.itemText(i).lower()), -1)
    assert idx_luz != -1, "Opción 'Cinta LED' no encontrada en Tipo de Luz"
    dlg.cbo_luz_tipo.setCurrentIndex(idx_luz)
    dlg.spin_luz_precio.setValue(10.0)  # unit por m lineal

    # Recalcular
    dlg._recalc()
    summary = dlg.get_pricing_summary()

    # Área = pi * (0.5^2) ~ 0.7854; Base subtotal ~= 0.7854 * 60 = 47.12
    assert summary['area'] == pytest.approx(0.7854, rel=1e-3)
    assert summary['subtotal'] >= 47.0
    # Luz usa perímetro: pi * 1m ~ 3.1416 * 10 = 31.41
    assert summary['total'] >= summary['subtotal']  # total incluye extras si caja


def test_silueta_price_includes_and_persists(qapp):
    engine = make_engine()
    Session = make_session_factory(engine)
    with Session() as s:
        type_id = ensure_corporeo_eav(s)

    dlg = CorporeoDialog(Session, type_id=type_id)

    # Definir un área conocida de 1 m² (100 cm x 100 cm)
    dlg.spin_alto.setValue(100.0)
    dlg.spin_ancho.setValue(100.0)

    # Asegurar que el material/base no aporten costo
    spin_esp = getattr(dlg, 'spin_esp_precio', None)
    if spin_esp is not None:
        spin_esp.setValue(0.0)
    dlg._esp_precio_val = 0.0
    dlg.lbl_esp_precio.setText("0")
    dlg.cbo_luz_tipo.setCurrentIndex(0)
    dlg.spin_luz_precio.setValue(0.0)
    dlg.spin_soporte_qty.setValue(0)
    dlg.spin_reg_cant.setValue(0)
    dlg.spin_caja_pct.setValue(0.0)
    for cb, _, _ in getattr(dlg, 'tipo_corp_checkboxes', []) or []:
        cb.setChecked(False)

    # Ubicar la checkbox de Silueta y simular un precio proveniente de parámetros
    chk_silueta = next(
        cb for cb in dlg.cut_checkboxes if 'silueta' in (cb.text() or '').lower()
    )
    chk_silueta.setProperty('price_m2', 30.0)
    dlg._set_silueta_price(30.0)
    chk_silueta.setChecked(True)

    dlg._recalc()

    # Con área 1.0 y precio 30.0, el subtotal debe reflejar exactamente ese valor
    assert float(dlg.lbl_subtotal.text()) == pytest.approx(30.0, rel=1e-3)
    assert float(dlg.lbl_total.text()) == pytest.approx(30.0, rel=1e-3)
    assert dlg.lbl_costo_silueta.text() == "Costo silueta: $30.00/m²"

    dlg._on_accept()
    payload = dlg.accepted_data
    assert payload is not None
    assert payload['silueta']['price_m2'] == pytest.approx(30.0, rel=1e-3)
    assert payload['silueta']['subtotal'] == pytest.approx(30.0, rel=1e-3)
    assert payload['subtotal'] == pytest.approx(30.0, rel=1e-3)
    assert payload['total'] == pytest.approx(30.0, rel=1e-3)

