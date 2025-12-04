
import pytest
from unittest.mock import MagicMock, patch
from src.admin_app.ui.simple_products_view import SimpleProductsView

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app

def test_delete_protected_product_corporeo(qapp, session_factory):
    """Verificar que no se puede eliminar el producto 'Corporeo'."""
    view = SimpleProductsView(session_factory)
    
    # Mock selected product
    view._selected_product = MagicMock(return_value={'id': 1, 'name': 'Corporeo'})
    
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        view._on_delete_product()
        
        mock_warning.assert_called_once()
        args = mock_warning.call_args[0]
        assert "Acción denegada" in args[1]
        assert "no puede ser eliminado" in args[2]

def test_delete_protected_product_talonario(qapp, session_factory):
    """Verificar que no se puede eliminar el producto 'talonario'."""
    view = SimpleProductsView(session_factory)
    
    # Mock selected product (case insensitive check)
    view._selected_product = MagicMock(return_value={'id': 2, 'name': 'Talonario'})
    
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        view._on_delete_product()
        
        mock_warning.assert_called_once()
        assert "Acción denegada" in mock_warning.call_args[0][1]

def test_delete_normal_product(qapp, session_factory):
    """Verificar que sí permite eliminar otros productos."""
    view = SimpleProductsView(session_factory)
    
    # Mock selected product
    view._selected_product = MagicMock(return_value={'id': 3, 'name': 'Otro Producto'})
    
    # Mock confirmation dialog to say NO (to avoid actual deletion logic in this test)
    with patch('PySide6.QtWidgets.QMessageBox.question', return_value=MagicMock()) as mock_question:
        # We just want to ensure it reaches the question dialog, meaning it passed the protection check
        view._on_delete_product()
        mock_question.assert_called_once()
        assert "Confirmar eliminación" in mock_question.call_args[0][1]
