
import sys
import pytest
from PySide6.QtWidgets import QApplication
from src.admin_app.ui.pending_payments_view import PaymentDialog
from src.admin_app.db import make_session_factory

class MockSaleData:
    def __init__(self):
        self.id = 1
        self.numero_orden = "ORD-001"
        self.cliente = "Test Client"
        self.restante = 100.00
        self.total_usd = 200.00

def test_payment_dialog_init(qtbot):
    # Create app if not exists
    if not QApplication.instance():
        app = QApplication(sys.argv)
    
    sale_data = MockSaleData()
    dlg = PaymentDialog(sale_data)
    qtbot.addWidget(dlg)
    
    assert dlg.windowTitle() == "Registrar Pago - Orden ORD-001"
    assert dlg.lbl_restante_orig.text() == "$100.00"
    
    # Check if table exists
    assert dlg.tbl_payments.columnCount() == 6
    
    # Check if add button exists
    assert dlg.btn_add_payment is not None
    
    # Add a row
    dlg._on_add_payment_row()
    assert dlg.tbl_payments.rowCount() == 1
    
    # Check autofill
    # Row 0, col 2 (USD) should be 100.00
    w_usd = dlg.tbl_payments.cellWidget(0, 2)
    assert w_usd.value() == 100.00
    
    dlg.close()
