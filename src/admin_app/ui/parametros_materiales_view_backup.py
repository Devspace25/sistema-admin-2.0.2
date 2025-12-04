from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, 
    QMessageBox, QLabel, QFrame, QHeaderView, QDialog, QDialogButtonBox, 
    QFormLayout, QLineEdit, QSplitter, QListWidget, QListWidgetItem,
    QTabWidget, QTextEdit, QGroupBox
)
from PySide6.QtGui import QFont

from ..repository import (
    list_configurable_products, create_configurable_product,
    update_configurable_product, delete_configurable_product,
    get_product_parameter_tables
)


class ParametrosMaterialesView(QWidget):
    """Vista principal del módulo Parámetros y Materiales."""
    
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.setObjectName("ParametrosMaterialesView")
        self._setup_ui()
        self._load_products()
    
    def _setup_ui(self):
        """Configurar la interfaz principal."""
        # Layout principal con splitter
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Panel izquierdo - Lista de productos
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Título del panel
        title_label = QLabel("Productos Configurables")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        left_layout.addWidget(title_label)
        
        # Botones de gestión de productos
        product_buttons = QHBoxLayout()
        self.add_product_btn = QPushButton("+ Agregar")
        self.edit_product_btn = QPushButton("✏ Editar")
        self.delete_product_btn = QPushButton("🗑 Eliminar")
        
        product_buttons.addWidget(self.add_product_btn)
        product_buttons.addWidget(self.edit_product_btn)
        product_buttons.addWidget(self.delete_product_btn)
        product_buttons.addStretch()
        left_layout.addLayout(product_buttons)
        
        # Lista de productos
        self.products_list = QListWidget()
        self.products_list.currentItemChanged.connect(self._on_product_selected)
        left_layout.addWidget(self.products_list)
        
        # Panel derecho - Tablas de parámetros
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Información del producto seleccionado
        self.product_info_label = QLabel("Seleccione un producto para ver sus tablas")
        product_info_font = QFont()
        product_info_font.setBold(True)
        self.product_info_label.setFont(product_info_font)
        right_layout.addWidget(self.product_info_label)
        
        # Botones de gestión de tablas
        table_buttons = QHBoxLayout()
        self.add_table_btn = QPushButton("+ Nueva Tabla")
        self.edit_table_btn = QPushButton("✏ Editar Tabla")
        self.delete_table_btn = QPushButton("🗑 Eliminar Tabla")
        self.relations_btn = QPushButton("🔗 Relaciones")
        self.values_btn = QPushButton("📝 Valores")
        
        table_buttons.addWidget(self.add_table_btn)
        table_buttons.addWidget(self.edit_table_btn)
        table_buttons.addWidget(self.delete_table_btn)
        table_buttons.addWidget(self.relations_btn)
        table_buttons.addWidget(self.values_btn)
        table_buttons.addStretch()
        right_layout.addLayout(table_buttons)
        
        # Tabla de parámetros
        self.tables_table = QTableWidget(0, 4)
        self.tables_table.setHorizontalHeaderLabels(["Nombre", "Columnas", "Registros", "Tipo"])
        
        # Configurar tabla
        header = self.tables_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        self.tables_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tables_table.setAlternatingRowColors(True)
        right_layout.addWidget(self.tables_table)
        
        # Configurar splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700])  # Proporción inicial
        
        # Conectar eventos
        self._connect_events()
        
        # Deshabilitar botones inicialmente
        self._update_button_states()
    
    def _connect_events(self):
        """Conectar eventos de la interfaz."""
        # Productos
        self.add_product_btn.clicked.connect(self._add_product)
        self.edit_product_btn.clicked.connect(self._edit_product)
        self.delete_product_btn.clicked.connect(self._delete_product)
        
        # Tablas
        self.add_table_btn.clicked.connect(self._add_table)
        self.edit_table_btn.clicked.connect(self._edit_table)
        self.delete_table_btn.clicked.connect(self._delete_table)
        self.relations_btn.clicked.connect(self._manage_relations)
        self.values_btn.clicked.connect(self._manage_values)
        
        # Cambios de selección
        self.tables_table.currentItemChanged.connect(self._on_table_selected)
    
    def _load_products(self):
        """Cargar lista de productos configurables."""
        try:
            with self.session_factory() as session:
                products = list_configurable_products(session)
                
                self.products_list.clear()
                for product in products:
                    item = QListWidgetItem(product['name'])
                    item.setData(Qt.ItemDataRole.UserRole, product)
                    self.products_list.addItem(item)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar productos: {str(e)}")
    
    def _on_product_selected(self, current, previous):
        """Manejar selección de producto."""
        if current:
            product_data = current.data(Qt.ItemDataRole.UserRole)
            self.product_info_label.setText(f"Tablas de parámetros: {product_data['name']}")
            self._load_product_tables(product_data['id'])
        else:
            self.product_info_label.setText("Seleccione un producto para ver sus tablas")
            self.tables_table.setRowCount(0)
        
        self._update_button_states()
    
    def _load_product_tables(self, product_id):
        """Cargar tablas de parámetros del producto seleccionado."""
        try:
            with self.session_factory() as session:
                tables = get_product_parameter_tables(session, product_id)
                
                self.tables_table.setRowCount(len(tables))
                
                for row, table in enumerate(tables):
                    # Nombre
                    name_item = QTableWidgetItem(table['display_name'])
                    name_item.setData(Qt.ItemDataRole.UserRole, table)
                    self.tables_table.setItem(row, 0, name_item)
                    
                    # Número de columnas
                    schema = table.get('schema', [])
                    col_count = len(schema)
                    col_item = QTableWidgetItem(str(col_count))
                    self.tables_table.setItem(row, 1, col_item)
                    
                    # Número de registros (placeholder - implementar después)
                    record_count = table.get('record_count', 0)
                    records_item = QTableWidgetItem(str(record_count))
                    self.tables_table.setItem(row, 2, records_item)
                    
                    # Tipo de tabla
                    table_type = "Padre" if table.get('parent_table_name') is None else "Hijo"
                    type_item = QTableWidgetItem(table_type)
                    self.tables_table.setItem(row, 3, type_item)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar tablas: {str(e)}")
    
    def _on_table_selected(self):
        """Manejar selección de tabla."""
        self._update_button_states()
    
    def _update_button_states(self):
        """Actualizar estado de botones según selección."""
        # Botones de productos
        has_product = self.products_list.currentItem() is not None
        self.edit_product_btn.setEnabled(has_product)
        self.delete_product_btn.setEnabled(has_product)
        
        # Botones de tablas
        has_table = self.tables_table.currentItem() is not None
        self.add_table_btn.setEnabled(has_product)
        self.edit_table_btn.setEnabled(has_table)
        self.delete_table_btn.setEnabled(has_table)
        self.relations_btn.setEnabled(has_product)
        self.values_btn.setEnabled(has_table)
    
    # ===== GESTIÓN DE PRODUCTOS =====
    
    def _add_product(self):
        """Agregar nuevo producto configurable."""
        dialog = ProductDialog(self.session_factory, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_products()
    
    def _edit_product(self):
        """Editar producto seleccionado."""
        current_item = self.products_list.currentItem()
        if not current_item:
            return
        
        product_data = current_item.data(Qt.ItemDataRole.UserRole)
        dialog = ProductDialog(self.session_factory, self, product_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_products()
    
    def _delete_product(self):
        """Eliminar producto seleccionado."""
        current_item = self.products_list.currentItem()
        if not current_item:
            return
        
        product_data = current_item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Está seguro de eliminar el producto '{product_data['name']}'?\n"
            f"Esto también eliminará todas sus tablas y datos.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with self.session_factory() as session:
                    delete_configurable_product(session, product_data['id'])
                    session.commit()
                    
                QMessageBox.information(self, "Éxito", "Producto eliminado correctamente.")
                self._load_products()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar producto: {str(e)}")
    
    # ===== GESTIÓN DE TABLAS =====
    
    def _add_table(self):
        """Agregar nueva tabla de parámetros."""
        QMessageBox.information(self, "Funcionalidad", "Crear tabla - En desarrollo")
    
    def _edit_table(self):
        """Editar tabla seleccionada."""
        QMessageBox.information(self, "Funcionalidad", "Editar tabla - En desarrollo")
    
    def _delete_table(self):
        """Eliminar tabla seleccionada."""
        QMessageBox.information(self, "Funcionalidad", "Eliminar tabla - En desarrollo")
    
    def _manage_relations(self):
        """Gestionar relaciones entre tablas."""
        QMessageBox.information(self, "Funcionalidad", "Gestionar relaciones - En desarrollo")
    
    def _manage_values(self):
        """Gestionar valores de la tabla seleccionada."""
        QMessageBox.information(self, "Funcionalidad", "Gestionar valores - En desarrollo")


class ProductDialog(QDialog):
    """Diálogo para crear/editar productos configurables."""
    
    def __init__(self, session_factory, parent=None, product_data=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.product_data = product_data
        self.is_editing = product_data is not None
        
        self.setWindowTitle("Editar Producto" if self.is_editing else "Crear Producto")
        self.setMinimumSize(400, 200)
        
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self):
        """Configurar la interfaz del diálogo."""
        layout = QVBoxLayout(self)
        
        # Formulario
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Ingrese el nombre del producto")
        form_layout.addRow("Nombre del Producto:", self.name_edit)
        
        layout.addLayout(form_layout)
        
        # Botones
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _load_data(self):
        """Cargar datos si estamos editando."""
        if self.is_editing and self.product_data:
            self.name_edit.setText(self.product_data['name'])
    
    def get_data(self):
        """Obtener los datos del formulario."""
        return {
            'name': self.name_edit.text().strip()
        }


class ParametrosMaterialesView(QWidget):
    """Vista principal del módulo Parámetros y Materiales - Configurar Productos."""

    def __init__(self, session_factory, parent=None) -> None:
        super().__init__(parent)
        self.session_factory = session_factory
        self.setObjectName("ParametrosMaterialesView")
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Título
        title_label = QLabel("Configurar Productos")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Separador
        separator = QFrame()
        separator.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Botones de acción
        buttons_layout = QHBoxLayout()
        
        self.add_button = QPushButton("Agregar Producto")
        self.add_button.setMinimumHeight(35)
        self.add_button.clicked.connect(self._add_product)
        buttons_layout.addWidget(self.add_button)
        
        self.edit_button = QPushButton("Editar")
        self.edit_button.setMinimumHeight(35)
        self.edit_button.clicked.connect(self._edit_product)
        self.edit_button.setEnabled(False)
        buttons_layout.addWidget(self.edit_button)
        
        self.delete_button = QPushButton("Eliminar")
        self.delete_button.setMinimumHeight(35)
        self.delete_button.clicked.connect(self._delete_product)
        self.delete_button.setEnabled(False)
        buttons_layout.addWidget(self.delete_button)
        
        self.assign_params_button = QPushButton("Asignar Parámetros")
        self.assign_params_button.setMinimumHeight(35)
        self.assign_params_button.clicked.connect(self._assign_parameters)
        self.assign_params_button.setEnabled(False)
        buttons_layout.addWidget(self.assign_params_button)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        # Tabla de productos configurables
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre del Producto", "Fecha Creación"])
        
        # Configurar la tabla
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        
        layout.addWidget(self.table)

    def refresh(self) -> None:
        """Actualizar los datos de la tabla."""
        try:
            with self.session_factory() as session:
                products = list_configurable_products(session)
                
                self.table.setRowCount(len(products))
                
                for row, product in enumerate(products):
                    self.table.setItem(row, 0, QTableWidgetItem(str(product['id'])))
                    self.table.setItem(row, 1, QTableWidgetItem(product['name']))
                    self.table.setItem(row, 2, QTableWidgetItem(
                        product['created_at'].strftime('%d/%m/%Y %H:%M') if product['created_at'] else ''
                    ))
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar productos: {str(e)}")
    
    def _on_selection_changed(self):
        """Manejar cambio de selección en la tabla."""
        has_selection = len(self.table.selectionModel().selectedRows()) > 0
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        self.assign_params_button.setEnabled(has_selection)
    
    def _get_selected_product(self):
        """Obtener el producto seleccionado."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        
        row = selected_rows[0].row()
        id_item = self.table.item(row, 0)
        name_item = self.table.item(row, 1)
        
        if not id_item or not name_item:
            return None
            
        product_id = int(id_item.text())
        product_name = name_item.text()
        
        return {
            'id': product_id,
            'name': product_name
        }
    
    def _add_product(self):
        """Agregar nuevo producto."""
        dialog = ProductDialog(self.session_factory, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data['name']:
                QMessageBox.warning(self, "Advertencia", "El nombre del producto es obligatorio.")
                return
            
            try:
                with self.session_factory() as session:
                    create_configurable_product(session, data['name'])
                    session.commit()
                self.refresh()
                QMessageBox.information(self, "Éxito", "Producto creado exitosamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al crear producto: {str(e)}")
    
    def _edit_product(self):
        """Editar producto seleccionado."""
        product = self._get_selected_product()
        if not product:
            return
        
        dialog = ProductDialog(self.session_factory, self, product)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data['name']:
                QMessageBox.warning(self, "Advertencia", "El nombre del producto es obligatorio.")
                return
            
            try:
                with self.session_factory() as session:
                    update_configurable_product(session, product['id'], data['name'])
                    session.commit()
                self.refresh()
                QMessageBox.information(self, "Éxito", "Producto actualizado exitosamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al actualizar producto: {str(e)}")
    
    def _delete_product(self):
        """Eliminar producto seleccionado."""
        product = self._get_selected_product()
        if not product:
            return
        
        reply = QMessageBox.question(
            self, "Confirmar",
            f"¿Está seguro de que desea eliminar el producto '{product['name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with self.session_factory() as session:
                    delete_configurable_product(session, product['id'])
                    session.commit()
                self.refresh()
                QMessageBox.information(self, "Éxito", "Producto eliminado exitosamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar producto: {str(e)}")
    
    def _assign_parameters(self):
        """Asignar parámetros al producto seleccionado."""
        product = self._get_selected_product()
        if not product:
            return
        
        try:
            from .product_parameters_dialog import ProductParametersDialog
            dialog = ProductParametersDialog(self.session_factory, product, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al abrir diálogo de parámetros: {str(e)}")


