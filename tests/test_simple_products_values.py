
import pytest
import sys
from PySide6.QtWidgets import QApplication
from unittest.mock import MagicMock, patch
from src.admin_app.ui.simple_products_view import SimpleProductsView

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app

def test_manage_values_no_selection(qapp, session_factory):
    """Verificar que muestra advertencia si no hay producto seleccionado."""
    view = SimpleProductsView(session_factory)
    
    with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
        view._on_manage_values()
        mock_warning.assert_called_once()
        assert "Seleccione un producto" in mock_warning.call_args[0][2]

def test_manage_values_no_tables(qapp, session_factory):
    """Verificar que muestra advertencia si el producto no tiene tablas."""
    view = SimpleProductsView(session_factory)
    
    # Mock _selected_product
    view._selected_product = MagicMock(return_value={'id': 1, 'name': 'Test Product'})
    
    # Mock get_product_parameter_tables to return empty list
    with patch('src.admin_app.repository.get_product_parameter_tables', return_value=[]):
        with patch('PySide6.QtWidgets.QMessageBox.warning') as mock_warning:
            view._on_manage_values()
            mock_warning.assert_called_once()
            assert "Debe crear tablas de relaciones" in mock_warning.call_args[0][2]

def test_manage_values_single_table(qapp, session_factory):
    """Verificar que abre diálogo directamente si hay una sola tabla."""
    view = SimpleProductsView(session_factory)
    view._selected_product = MagicMock(return_value={'id': 1, 'name': 'Test Product'})
    
    tables = [{'id': 10, 'display_name': 'Tabla 1'}]
    
    with patch('src.admin_app.repository.get_product_parameter_tables', return_value=tables):
        with patch('src.admin_app.ui.parametros_values_dialog.ParametrosValuesDialog') as MockDialog:
            mock_instance = MockDialog.return_value
            view._on_manage_values()
            
            MockDialog.assert_called_once()
            args = MockDialog.call_args[0]
            assert args[1] == tables[0] # Check table passed
            mock_instance.exec.assert_called_once()

def test_manage_values_multiple_tables_cancel(qapp, session_factory):
    """Verificar que no abre diálogo si cancela selección de tabla."""
    view = SimpleProductsView(session_factory)
    view._selected_product = MagicMock(return_value={'id': 1, 'name': 'Test Product'})
    
    tables = [{'id': 10, 'display_name': 'Tabla 1'}, {'id': 11, 'display_name': 'Tabla 2'}]
    
    with patch('src.admin_app.repository.get_product_parameter_tables', return_value=tables):
        with patch('PySide6.QtWidgets.QInputDialog.getItem', return_value=("", False)): # Cancelled
            with patch('src.admin_app.ui.parametros_values_dialog.ParametrosValuesDialog') as MockDialog:
                view._on_manage_values()
                MockDialog.assert_not_called()

def test_manage_values_multiple_tables_select(qapp, session_factory):
    """Verificar que abre diálogo con tabla seleccionada."""
    view = SimpleProductsView(session_factory)
    view._selected_product = MagicMock(return_value={'id': 1, 'name': 'Test Product'})
    
    tables = [{'id': 10, 'display_name': 'Tabla 1'}, {'id': 11, 'display_name': 'Tabla 2'}]
    
    with patch('src.admin_app.repository.get_product_parameter_tables', return_value=tables):
        with patch('PySide6.QtWidgets.QInputDialog.getItem', return_value=("Tabla 2", True)): # Select Tabla 2
            with patch('src.admin_app.ui.parametros_values_dialog.ParametrosValuesDialog') as MockDialog:
                mock_instance = MockDialog.return_value
                view._on_manage_values()
                
                MockDialog.assert_called_once()
                args = MockDialog.call_args[0]
                assert args[1] == tables[1] # Check table 2 passed
                mock_instance.exec.assert_called_once()
