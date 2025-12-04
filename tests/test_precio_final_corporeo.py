"""Test para verificar el cálculo de precio_final_corporeo_usd en CorporeoDialog."""
from __future__ import annotations

import os
import sys
import pytest
from unittest.mock import patch

# Forzar backend offscreen para Qt
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.admin_app.db import make_engine, make_session_factory
from src.admin_app.repository import ensure_corporeo_eav, get_system_config, set_system_config
from src.admin_app.ui.corporeo_dialog import CorporeoDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def session_factory():
    engine = make_engine()
    Session = make_session_factory(engine)
    return Session


def test_precio_final_corporeo_usd_calculation(qapp, session_factory):
    """Verifica que precio_final_usd se calcule correctamente con tasa_corporeo y tasa_bcv."""
    
    # Configurar tasa_corporeo en el sistema
    with session_factory() as session:
        type_id = ensure_corporeo_eav(session)
        set_system_config(session, "tasa_corporeo", "1.5", "Tasa de conversión para productos corpóreos")
        session.commit()
    
    # Mockear get_bcv_rate para tener una tasa BCV controlada
    with patch('src.admin_app.ui.corporeo_dialog.get_bcv_rate') as mock_bcv:
        mock_bcv.return_value = 40.0  # Tasa BCV fija de 40
        
        dlg = CorporeoDialog(session_factory, type_id=type_id)
        
        # Configurar un cálculo simple: 100 Bs de subtotal
        dlg.spin_alto.setValue(100.0)  # 1m²
        dlg.spin_ancho.setValue(100.0)
        
        # Precio material: 100 Bs/m²
        if hasattr(dlg, 'spin_esp_precio') and dlg.spin_esp_precio is not None:
            dlg.spin_esp_precio.setValue(100.0)
        else:
            dlg._esp_precio_val = 100.0
            dlg.lbl_esp_precio.setText("100.00")
        
        # Forzar recalc
        dlg._recalc()
        
        # Obtener summary
        summary = dlg.get_pricing_summary()
        
        # Verificar área
        assert summary['area'] == pytest.approx(1.0, rel=1e-3), "Área debe ser 1 m²"
        
        # Verificar subtotal (precio_unitario en Bs)
        assert summary['subtotal'] == pytest.approx(100.0, rel=1e-2), "Subtotal debe ser 100 Bs"
        
        # Verificar precio_final_usd: (100 * 1.5) / 40 = 150 / 40 = 3.75 USD
        expected_precio_final_usd = (100.0 * 1.5) / 40.0
        assert summary['precio_final_usd'] == pytest.approx(expected_precio_final_usd, rel=1e-2), \
            f"precio_final_usd debe ser {expected_precio_final_usd} USD"
        
        # Verificar que el label también se actualizó
        precio_final_label = float(dlg.lbl_precio_final_corporeo_usd.text())
        assert precio_final_label == pytest.approx(expected_precio_final_usd, rel=1e-2), \
            f"Label precio_final debe mostrar {expected_precio_final_usd} USD"


def test_precio_final_usd_default_values(qapp, session_factory):
    """Verifica que precio_final_usd se calcule correctamente con la fórmula."""
    
    with session_factory() as session:
        type_id = ensure_corporeo_eav(session)
        # Configurar una tasa_corporeo conocida para el test
        set_system_config(session, "tasa_corporeo", "2.0", "Tasa de conversión para productos corpóreos")
        session.commit()
    
    # Mockear get_bcv_rate para retornar un valor conocido
    with patch('src.admin_app.ui.corporeo_dialog.get_bcv_rate') as mock_bcv:
        mock_bcv.return_value = 50.0  # Tasa BCV fija
        
        dlg = CorporeoDialog(session_factory, type_id=type_id)
        
        # Configurar subtotal simple: 1m² * 100 Bs/m² = 100 Bs
        dlg.spin_alto.setValue(100.0)  # 1 m alto
        dlg.spin_ancho.setValue(100.0)  # 1 m ancho = 1 m²
        
        # Precio material: 100 Bs/m²
        if hasattr(dlg, 'spin_esp_precio') and dlg.spin_esp_precio is not None:
            dlg.spin_esp_precio.setValue(100.0)
        else:
            dlg._esp_precio_val = 100.0
            dlg.lbl_esp_precio.setText("100.00")
        
        dlg._recalc()
        summary = dlg.get_pricing_summary()
        
        # Verificar que el cálculo se hizo correctamente
        # La fórmula es: precio_final_usd = (subtotal * tasa_corporeo) / tasa_bcv
        subtotal = summary['subtotal']
        precio_final_usd = summary['precio_final_usd']
        
        # Obtener las tasas que realmente se usaron
        tasa_corporeo_used = dlg._get_tasa_corporeo()
        tasa_bcv_used = dlg._get_tasa_bcv()
        
        # Calcular el valor esperado con las tasas reales
        expected_precio_final_usd = (subtotal * tasa_corporeo_used) / tasa_bcv_used
        
        assert precio_final_usd == pytest.approx(expected_precio_final_usd, rel=1e-2), \
            f"precio_final_usd ({precio_final_usd}) debe coincidir con " \
            f"(subtotal={subtotal} * tasa_corporeo={tasa_corporeo_used}) / tasa_bcv={tasa_bcv_used} " \
            f"= {expected_precio_final_usd}"
        
        # Verificar que tasa_corporeo sea 2.0 como configuramos
        assert tasa_corporeo_used == pytest.approx(2.0, rel=1e-3), \
            f"tasa_corporeo debe ser 2.0 como configurada, obtenido: {tasa_corporeo_used}"
