"""Test para verificar la lógica de pricing de productos corpóreos en sale_dialog."""
from __future__ import annotations

import os
import sys
import pytest

# Forzar backend offscreen para Qt
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.admin_app.db import make_engine, make_session_factory
from src.admin_app.ui.sale_dialog import SaleDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def session_factory():
    engine = make_engine()
    Session = make_session_factory(engine)
    return Session


def test_corporeo_pricing_usd_payment(qapp, session_factory):
    """Verificar que con pago en USD se usa precio_unitario."""
    dlg = SaleDialog(session_factory=session_factory)
    
    # Simular producto corpóreo configurado
    dlg._is_corporeo_product = True
    dlg._precio_corporeo_tasa_bcv = 5000.0  # 100 USD * 50 tasa_bcv
    
    # Configurar método de pago en divisas
    dlg.cmb_forma_pago.setCurrentText("Efectivo USD")
    
    # Configurar precio unitario en USD
    dlg.edt_precio_unitario.setValue(100.0)
    dlg.edt_tasa_bcv.setValue(50.0)
    
    # Calcular precio en Bs
    dlg._calc_precio_unitario_bs()
    
    # Para pago en USD, debe usar precio_unitario * tasa_bcv = 100 * 50 = 5000
    precio_bs = dlg.edt_precio_unitario_bs.value()
    assert precio_bs == pytest.approx(5000.0, rel=1e-2), \
        f"Con pago en USD, precio_unitario_bs debe ser {100 * 50} Bs, obtenido: {precio_bs}"


def test_corporeo_pricing_bs_payment_efectivo(qapp, session_factory):
    """Verificar que con pago en Efectivo Bs.D se usa precio_corporeo_tasa_bcv."""
    dlg = SaleDialog(session_factory=session_factory)
    
    # Simular producto corpóreo con precio especial en Bs
    dlg._is_corporeo_product = True
    dlg._precio_corporeo_tasa_bcv = 7500.0  # (100 * 1.5 tasa_corporeo) / 50 tasa_bcv * 50 = 7500
    
    # Configurar método de pago en Bs
    dlg.cmb_forma_pago.setCurrentText("Efectivo Bs.D")
    
    # Configurar precio unitario en USD
    dlg.edt_precio_unitario.setValue(100.0)
    dlg.edt_tasa_bcv.setValue(50.0)
    
    # Calcular precio en Bs
    dlg._calc_precio_unitario_bs()
    
    # Para pago en Bs, debe usar precio_corporeo_tasa_bcv = 7500
    precio_bs = dlg.edt_precio_unitario_bs.value()
    assert precio_bs == pytest.approx(7500.0, rel=1e-2), \
        f"Con pago en Efectivo Bs.D, precio_unitario_bs debe ser {7500.0} Bs, obtenido: {precio_bs}"


def test_corporeo_pricing_bs_payment_transferencia(qapp, session_factory):
    """Verificar que con pago en Transferencia Bs.D se usa precio_corporeo_tasa_bcv."""
    dlg = SaleDialog(session_factory=session_factory)
    
    # Simular producto corpóreo
    dlg._is_corporeo_product = True
    dlg._precio_corporeo_tasa_bcv = 6000.0
    
    # Configurar método de pago en Bs
    dlg.cmb_forma_pago.setCurrentText("Transferencia Bs.D")
    
    # Configurar precio unitario en USD
    dlg.edt_precio_unitario.setValue(100.0)
    dlg.edt_tasa_bcv.setValue(50.0)
    
    # Calcular precio en Bs
    dlg._calc_precio_unitario_bs()
    
    # Para pago en Bs, debe usar precio_corporeo_tasa_bcv
    precio_bs = dlg.edt_precio_unitario_bs.value()
    assert precio_bs == pytest.approx(6000.0, rel=1e-2), \
        f"Con pago en Transferencia Bs.D, precio_unitario_bs debe ser {6000.0} Bs, obtenido: {precio_bs}"


def test_corporeo_pricing_bs_payment_pago_movil(qapp, session_factory):
    """Verificar que con pago en Pago móvil se usa precio_corporeo_tasa_bcv."""
    dlg = SaleDialog(session_factory=session_factory)
    
    # Simular producto corpóreo
    dlg._is_corporeo_product = True
    dlg._precio_corporeo_tasa_bcv = 8000.0
    
    # Configurar método de pago en Bs (Pago móvil)
    dlg.cmb_forma_pago.setCurrentText("Pago móvil")
    
    # Configurar precio unitario en USD
    dlg.edt_precio_unitario.setValue(100.0)
    dlg.edt_tasa_bcv.setValue(50.0)
    
    # Calcular precio en Bs
    dlg._calc_precio_unitario_bs()
    
    # Para pago móvil, debe usar precio_corporeo_tasa_bcv
    precio_bs = dlg.edt_precio_unitario_bs.value()
    assert precio_bs == pytest.approx(8000.0, rel=1e-2), \
        f"Con Pago móvil, precio_unitario_bs debe ser {8000.0} Bs, obtenido: {precio_bs}"


def test_non_corporeo_product_normal_pricing(qapp, session_factory):
    """Verificar que productos no corpóreos usan cálculo normal independiente del método de pago."""
    dlg = SaleDialog(session_factory=session_factory)
    
    # Producto normal (no corpóreo)
    dlg._is_corporeo_product = False
    dlg._precio_corporeo_tasa_bcv = 0.0
    
    # Configurar método de pago en Bs (debería ignorarse)
    dlg.cmb_forma_pago.setCurrentText("Efectivo Bs.D")
    
    # Configurar precio unitario en USD
    dlg.edt_precio_unitario.setValue(50.0)
    dlg.edt_tasa_bcv.setValue(40.0)
    
    # Calcular precio en Bs
    dlg._calc_precio_unitario_bs()
    
    # Para producto no corpóreo, siempre usa precio_unitario * tasa_bcv
    precio_bs = dlg.edt_precio_unitario_bs.value()
    expected = 50.0 * 40.0
    assert precio_bs == pytest.approx(expected, rel=1e-2), \
        f"Producto no corpóreo debe usar cálculo normal: {expected} Bs, obtenido: {precio_bs}"
