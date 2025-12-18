
import pytest
from PySide6.QtWidgets import QApplication, QTableWidget
from datetime import datetime
from src.admin_app.ui.daily_reports_view import ReportDetailsDialog

# Mock Report object
class MockReport:
    def __init__(self):
        self.report_date = datetime.now()
        self.report_status = "GENERADO"
        self.total_sales = 1
        self.total_amount_usd = 100.0
        self.total_amount_bs = 0.0
        self.total_ingresos_usd = 100.0
        self.report_data_json = """
        {
            "sales_data": [
                {
                    "id": 1,
                    "fecha": "2023-10-27T10:00:00",
                    "numero_orden": "ORD-001",
                    "articulo": "Item 1",
                    "asesor": "User",
                    "cliente": "Client A",
                    "venta_usd": 100.0,
                    "forma_pago": "Zelle",
                    "monto_bs": 0.0,
                    "monto_usd_calculado": 100.0,
                    "tasa_bcv": 35.0,
                    "abono_usd": 100.0,
                    "restante": 0.0,
                    "iva": 0.0,
                    "diseno_usd": 0.0,
                    "ingresos_usd": 100.0
                }
            ],
            "totals": {}
        }
        """

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

def test_report_details_dialog_columns(qapp):
    report = MockReport()
    dialog = ReportDetailsDialog(report)
    
    # Find the table
    table = dialog.findChild(QTableWidget)
    assert table is not None
    
    # Check column count (should be 20 now)
    assert table.columnCount() == 20
    
    # Check headers
    headers = []
    for i in range(table.columnCount()):
        headers.append(table.horizontalHeaderItem(i).text())
    
    expected_headers = [
        'ID', 'Fecha', 'Núm. Orden', 'Artículo', 'Asesor', 'Cliente', 
        'Venta $', 'Forma Pago', 'Serial Billete', 'Banco', 'Referencia', 
        'Fecha Pago', 'Monto Bs.D', 'Monto $ Calc.', 'Tasa BCV', 
        'Abono $', 'IVA', 'Por Cobrar $', 'Diseño $', 'Ingresos $'
    ]
    
    assert headers == expected_headers
    
    # Check data in first row
    assert table.item(0, 5).text() == "Client A" # Cliente column
    
    dialog.close()
