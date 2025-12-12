import pytest
from src.admin_app.ui.talonario_dialog import TalonarioDialog

def test_talonario_build_config_summary():
    # Mock TalonarioDialog
    class MockTalonarioDialog(TalonarioDialog):
        def __init__(self):
            self.accepted_data = None
            
    dlg = MockTalonarioDialog()
    
    # Case 1: No data
    assert dlg.build_config_summary() == ""
    
    # Case 2: Full data
    dlg.accepted_data = {
        'detalles': {
            'tipo_talonario': 'Factura',
            'tamano': 'Carta',
            'papel': 'Bond',
            'impresion': 'Full Color',
            'cantidad': 10,
            'copia_adicional': True,
            'descripcion': 'Serie A'
        }
    }
    summary = dlg.build_config_summary()
    assert "Factura" in summary
    assert "Carta" in summary
    assert "Bond" in summary
    assert "Full Color" in summary
    assert "10 unds" in summary
    assert "Con Copia" in summary
    assert "(Serie A)" in summary
    
    # Case 3: Partial data
    dlg.accepted_data = {
        'detalles': {
            'tipo_talonario': 'Recibo',
            'cantidad': 5
        }
    }
    summary = dlg.build_config_summary()
    assert "Recibo" in summary
    assert "5 unds" in summary
    assert "Carta" not in summary
