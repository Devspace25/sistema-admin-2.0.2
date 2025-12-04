from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QDialog, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, 
    QMessageBox, QHeaderView, QListWidget, QListWidgetItem
)

from ..repository import (
    list_products, add_product, get_product_by_id, update_product, delete_product_by_id,
    get_product_parameter_tables, create_product_parameter_table
)
from .parametros_table_dialog import ParametrosTableDialog
from .parametros_values_dialog import ParametrosValuesDialog


class EavProductsView(QWidget):
    def __init__(self, session_factory):
        super().__init__()
        self.session_factory = session_factory
        self._build_ui()
        self._load_products()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Botones superiores
        buttons_layout = QHBoxLayout()
        layout.addLayout(buttons_layout)
        
        self.btn_new_product = QPushButton("Nuevo Producto")
        self.btn_assign_params = QPushButton("Asignar Parámetros")
        self.btn_assign_params.setEnabled(False)  # Deshabilitado inicialmente
        
        buttons_layout.addWidget(self.btn_new_product)
        buttons_layout.addWidget(self.btn_assign_params)
        buttons_layout.addStretch()
        
        # Tabla de productos
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(4)
        self.products_table.setHorizontalHeaderLabels(["ID", "Nombre", "Categoría", "Precio"])
        
        # Configurar tabla
        header = self.products_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)            # Nombre
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)   # Categoría
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)   # Precio
        
        self.products_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.products_table)
        
        # Conectar eventos
        self.btn_new_product.clicked.connect(self._new_product)
        self.btn_assign_params.clicked.connect(self._assign_parameters)
        self.products_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.products_table.itemDoubleClicked.connect(self._edit_product)

    def _load_products(self):
        """Cargar todos los productos en la tabla."""
        try:
            with self.session_factory() as session:
                products = list_products(session)
            
            self.products_table.setRowCount(len(products))
            
            for row, product in enumerate(products):
                # ID
                id_item = QTableWidgetItem(str(product.id))
                id_item.setData(Qt.ItemDataRole.UserRole, product.id)
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.products_table.setItem(row, 0, id_item)
                
                # Nombre
                name_item = QTableWidgetItem(product.name or "")
                self.products_table.setItem(row, 1, name_item)
                
                # Categoría
                category_item = QTableWidgetItem(product.category or "")
                self.products_table.setItem(row, 2, category_item)
                
                # Precio
                price_item = QTableWidgetItem(f"${product.price:.2f}")
                self.products_table.setItem(row, 3, price_item)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar productos: {str(e)}")

    def _on_selection_changed(self):
        """Activar/desactivar botón según selección."""
        has_selection = len(self.products_table.selectedItems()) > 0
        self.btn_assign_params.setEnabled(has_selection)

    def _get_selected_product_id(self) -> Optional[int]:
        """Obtener ID del producto seleccionado."""
        selected_rows = set(item.row() for item in self.products_table.selectedItems())
        if not selected_rows:
            return None
        
        row = list(selected_rows)[0]
        id_item = self.products_table.item(row, 0)
        return id_item.data(Qt.ItemDataRole.UserRole) if id_item else None

    def _new_product(self):
        """Crear un nuevo producto."""
        dialog = ProductDialog(self.session_factory, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_products()

    def _edit_product(self):
        """Editar el producto seleccionado."""
        product_id = self._get_selected_product_id()
        if not product_id:
            QMessageBox.warning(self, "Selección", "Seleccione un producto para editar.")
            return
            
        dialog = ProductDialog(self.session_factory, product_id=product_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_products()

    def _assign_parameters(self):
        """Abrir diálogo de asignación de parámetros."""
        product_id = self._get_selected_product_id()
        if not product_id:
            QMessageBox.warning(self, "Selección", "Seleccione un producto para asignar parámetros.")
            return
            
        dialog = ProductParametersDialog(self.session_factory, product_id=product_id, parent=self)
        dialog.exec()


class ProductDialog(QDialog):
    """Diálogo para crear/editar productos."""
    
    def __init__(self, session_factory, product_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.product_id = product_id
        self.setWindowTitle("Editar Producto" if product_id else "Nuevo Producto")
        self._build_ui()
        
        if self.product_id:
            self._load_product_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Formulario
        form_layout = QFormLayout()
        layout.addLayout(form_layout)
        
        self.name_edit = QLineEdit()
        self.category_edit = QLineEdit()
        self.price_edit = QDoubleSpinBox()
        self.price_edit.setMaximum(999999.99)
        self.price_edit.setDecimals(2)
        
        form_layout.addRow("Nombre:", self.name_edit)
        form_layout.addRow("Categoría:", self.category_edit)
        form_layout.addRow("Precio:", self.price_edit)
        
        # Botones
        buttons_layout = QHBoxLayout()
        layout.addLayout(buttons_layout)
        
        self.btn_save = QPushButton("Guardar")
        self.btn_cancel = QPushButton("Cancelar")
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_save)
        buttons_layout.addWidget(self.btn_cancel)
        
        # Conectar eventos
        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def _load_product_data(self):
        """Cargar datos del producto para edición."""
        if not self.product_id:
            return
            
        try:
            with self.session_factory() as session:
                product = get_product_by_id(session, self.product_id)
                if product:
                    self.name_edit.setText(product.name or "")
                    self.category_edit.setText(product.category or "")
                    self.price_edit.setValue(product.price or 0.0)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar producto: {str(e)}")

    def accept(self):
        """Guardar cambios."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validación", "El nombre es requerido.")
            return
            
        category = self.category_edit.text().strip() or None
        price = self.price_edit.value()
        
        try:
            with self.session_factory() as session:
                if self.product_id:
                    # Actualizar producto existente
                    success = update_product(
                        session, 
                        self.product_id,
                        name=name,
                        category=category,
                        price=price
                    )
                    if not success:
                        QMessageBox.critical(self, "Error", "No se pudo actualizar el producto.")
                        return
                else:
                    # Crear nuevo producto
                    add_product(
                        session,
                        name=name,
                        category=category,
                        price=price
                    )
                
            super().accept()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar producto: {str(e)}")


class ProductParametersDialog(QDialog):
    """Diálogo para gestionar parámetros de un producto."""
    
    def __init__(self, session_factory, product_id: int, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.product_id = product_id
        self.setWindowTitle("Parámetros del Producto")
        self.setMinimumSize(600, 400)
        self._build_ui()
        self._load_parameter_tables()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Título con nombre del producto
        try:
            with self.session_factory() as session:
                product = get_product_by_id(session, self.product_id)
                product_name = product.name if product else f"ID {self.product_id}"
        except:
            product_name = f"ID {self.product_id}"
            
        title_label = QLabel(f"Parámetros para: {product_name}")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Botones superiores
        buttons_layout = QHBoxLayout()
        layout.addLayout(buttons_layout)
        
        self.btn_new_table = QPushButton("Nueva Tabla")
        buttons_layout.addWidget(self.btn_new_table)
        buttons_layout.addStretch()
        
        # Lista de tablas de parámetros
        self.tables_list = QListWidget()
        layout.addWidget(self.tables_list)
        
        # Botones inferiores
        bottom_buttons = QHBoxLayout()
        layout.addLayout(bottom_buttons)
        
        self.btn_values = QPushButton("Ver/Editar Valores")
        self.btn_add_values = QPushButton("Agregar Valores")
        self.btn_values.setEnabled(False)
        self.btn_add_values.setEnabled(False)
        self.btn_close = QPushButton("Cerrar")
        
        bottom_buttons.addWidget(self.btn_values)
        bottom_buttons.addWidget(self.btn_add_values)
        bottom_buttons.addStretch()
        bottom_buttons.addWidget(self.btn_close)
        
        # Conectar eventos
        self.btn_new_table.clicked.connect(self._create_new_table)
        self.btn_values.clicked.connect(self._open_values_dialog)
        self.btn_add_values.clicked.connect(self._add_values_directly)
        self.btn_close.clicked.connect(self.accept)
        self.tables_list.itemSelectionChanged.connect(self._on_table_selection_changed)

    def _load_parameter_tables(self):
        """Cargar las tablas de parámetros del producto."""
        try:
            with self.session_factory() as session:
                tables = get_product_parameter_tables(session, self.product_id)
            
            self.tables_list.clear()
            
            for table in tables:
                item_text = f"{table['display_name']}"
                if table.get('description'):
                    item_text += f" - {table['description']}"
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, table)
                self.tables_list.addItem(item)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar tablas: {str(e)}")

    def _on_table_selection_changed(self):
        """Activar/desactivar botones según selección."""
        has_selection = self.tables_list.currentItem() is not None
        self.btn_values.setEnabled(has_selection)
        self.btn_add_values.setEnabled(has_selection)

    def _create_new_table(self):
        """Crear una nueva tabla de parámetros."""
        try:
            with self.session_factory() as session:
                product = get_product_by_id(session, self.product_id)
                if not product:
                    QMessageBox.critical(self, "Error", "Producto no encontrado.")
                    return
                    
                product_data = {
                    'id': product.id,
                    'name': product.name,
                    'category': product.category
                }
                
            dialog = ParametrosTableDialog(self.session_factory, product_data, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._load_parameter_tables()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al crear tabla: {str(e)}")

    def _open_values_dialog(self):
        """Abrir diálogo de valores para la tabla seleccionada."""
        current_item = self.tables_list.currentItem()
        if not current_item:
            return
            
        table_data = current_item.data(Qt.ItemDataRole.UserRole)
        if not table_data:
            return
            
        dialog = ParametrosValuesDialog(self.session_factory, table_data, parent=self)
        dialog.exec()

    def _add_values_directly(self):
        """Abrir diálogo de valores y activar inmediatamente el formulario de agregar."""
        current_item = self.tables_list.currentItem()
        if not current_item:
            return
            
        table_data = current_item.data(Qt.ItemDataRole.UserRole)
        if not table_data:
            return
            
        dialog = ParametrosValuesDialog(self.session_factory, table_data, parent=self, auto_add_row=True)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Recargar la lista de tablas si es necesario
            self._load_parameter_tables()
