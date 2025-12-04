"""
Diálogo para gestionar parámetros de productos configurables.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QMessageBox
)
from PySide6.QtCore import Qt
from ..models import ConfigurableProduct
from ..repository import get_product_parameter_tables
import json


class ProductParametersDialog(QDialog):
    """Diálogo principal para gestionar parámetros de productos configurables."""
    
    def __init__(self, session_factory, product_id: int, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.product_id = product_id
        
        self.setWindowTitle("Gestionar Parámetros de Producto")
        self.setModal(True)
        self.resize(800, 600)
        
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        """Configurar la interfaz de usuario."""
        layout = QVBoxLayout(self)
        
        # Título
        title_label = QLabel("Parámetros de Producto")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Tabla de parámetros
        self.parameters_table = QTableWidget()
        self.parameters_table.setColumnCount(3)
        self.parameters_table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Descripción"
        ])
        
        # Configurar header
        header = self.parameters_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.parameters_table)
        
        # Botones
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
    
    def load_data(self):
        """Cargar datos básicos."""
        try:
            # Intentar cargar tablas de parámetros reales para el producto
            from ..repository import get_product_parameter_tables
            with self.session_factory() as session:
                tables = get_product_parameter_tables(session, self.product_id, include_inactive=True)
                # Normalizar a filas (ID, Nombre, Descripción)
                self.parameters_table.setRowCount(len(tables))
                for r, t in enumerate(tables):
                    id_item = QTableWidgetItem(str(t.get('id') or ''))
                    id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    name_item = QTableWidgetItem(t.get('display_name') or t.get('table_name') or '')
                    name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    desc_item = QTableWidgetItem(t.get('description') or '')
                    desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.parameters_table.setItem(r, 0, id_item)
                    self.parameters_table.setItem(r, 1, name_item)
                    self.parameters_table.setItem(r, 2, desc_item)
                if not tables:
                    # Mensaje informativo si no hay tablas configuradas
                    self.parameters_table.setRowCount(1)
                    info_item = QTableWidgetItem("No hay tablas de parámetros configuradas para este producto.")
                    info_item.setFlags(info_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.parameters_table.setItem(0, 0, info_item)
                    self.parameters_table.setSpan(0, 0, 1, 3)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar datos: {str(e)}")


class TableValuesDialog(QDialog):
    """Diálogo básico para compatibilidad."""
    
    def __init__(self, session_factory, product_id: int, table_definition: dict, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.product_id = product_id
        self.table_definition = table_definition
        
        self.setWindowTitle("Valores de Tabla")
        self.setModal(True)
        self.resize(400, 200)
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel("Funcionalidad en desarrollo.")
        layout.addWidget(info_label)
        
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
