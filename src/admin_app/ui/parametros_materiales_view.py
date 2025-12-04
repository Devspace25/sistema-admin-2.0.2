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
        current_item = self.products_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Selección", "Seleccione un producto primero.")
            return
        
        product_data = current_item.data(Qt.ItemDataRole.UserRole)
        
        from .parametros_table_dialog import ParametrosTableDialog
        dialog = ParametrosTableDialog(self.session_factory, product_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_product_tables(product_data['id'])
    
    def _edit_table(self):
        """Editar tabla seleccionada."""
        current_row = self.tables_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Selección", "Seleccione una tabla para editar.")
            return
        
        product_item = self.products_list.currentItem()
        if not product_item:
            return
            
        product_data = product_item.data(Qt.ItemDataRole.UserRole)
        
        # Obtener datos de la tabla seleccionada
        try:
            with self.session_factory() as session:
                from ..repository import get_product_parameter_tables
                tables = get_product_parameter_tables(session, product_data['id'])
                
                if current_row < len(tables):
                    table_data = tables[current_row]
                    
                    from .parametros_table_dialog import ParametrosTableDialog
                    dialog = ParametrosTableDialog(self.session_factory, product_data, self, table_data)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        self._load_product_tables(product_data['id'])
                        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al editar tabla: {str(e)}")
    
    def _delete_table(self):
        """Eliminar tabla seleccionada."""
        current_row = self.tables_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Selección", "Seleccione una tabla para eliminar.")
            return
        
        product_item = self.products_list.currentItem()
        if not product_item:
            return
            
        product_data = product_item.data(Qt.ItemDataRole.UserRole)
        
        try:
            with self.session_factory() as session:
                from ..repository import get_product_parameter_tables
                tables = get_product_parameter_tables(session, product_data['id'])
                
                if current_row < len(tables):
                    table_data = tables[current_row]
                    
                    reply = QMessageBox.question(
                        self, "Confirmar eliminación",
                        f"¿Está seguro de eliminar la tabla '{table_data['display_name']}'?\n"
                        f"Esto eliminará permanentemente todos los datos de la tabla.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        try:
                            from ..repository import delete_product_parameter_table
                            stats = delete_product_parameter_table(session, table_data['id'])
                            session.commit()
                            QMessageBox.information(
                                self, "Eliminada",
                                f"Tabla eliminada. Filas desactivadas: {stats.get('values_deactivated', 0)}."
                            )
                            self._load_product_tables(product_data['id'])
                        except Exception as del_err:
                            QMessageBox.critical(self, "No se pudo eliminar", str(del_err))
                        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al eliminar tabla: {str(e)}")
    
    def _manage_relations(self):
        """Gestionar relaciones entre tablas."""
        current_item = self.products_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Selección", "Seleccione un producto primero.")
            return
        
        product_data = current_item.data(Qt.ItemDataRole.UserRole)
        
        from .parametros_relations_dialog import ParametrosRelationsDialog
        dialog = ParametrosRelationsDialog(self.session_factory, product_data, self)
        dialog.exec()
    
    def _manage_values(self):
        """Gestionar valores de las tablas."""
        current_item = self.products_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Selección", "Seleccione un producto primero.")
            return
        
        product_data = current_item.data(Qt.ItemDataRole.UserRole)
        
        # Verificar si hay una tabla específica seleccionada en la interfaz
        current_row = self.tables_table.currentRow()
        if current_row >= 0:
            # La primera columna almacena el dict de la tabla en UserRole
            name_item = self.tables_table.item(current_row, 0)
            if name_item:
                selected_table = name_item.data(Qt.ItemDataRole.UserRole)
                if selected_table:
                    # Abrir directamente el diálogo de valores para la tabla seleccionada
                    from .parametros_values_dialog import ParametrosValuesDialog
                    dialog = ParametrosValuesDialog(
                        self.session_factory, selected_table, self, auto_add_row=True
                    )
                    dialog.exec()
                    return
        
        # Lógica original para cuando no hay tabla específica seleccionada
        try:
            with self.session_factory() as session:
                from ..repository import get_product_parameter_tables
                tables = get_product_parameter_tables(session, product_data['id'])
                
                if not tables:
                    QMessageBox.information(
                        self, "Sin tablas", 
                        f"El producto '{product_data['name']}' no tiene tablas de parámetros configuradas.\n"
                        "Use 'Gestionar Tablas' para crear una primero."
                    )
                    return
                
                # Si hay una sola tabla, abrirla directamente
                if len(tables) == 1:
                    from .parametros_values_dialog import ParametrosValuesDialog
                    dialog = ParametrosValuesDialog(self.session_factory, tables[0], self)
                    dialog.exec()
                else:
                    # Mostrar selector de tabla
                    self._show_table_selector(tables)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar tablas: {str(e)}")
    
    def _show_table_selector(self, tables):
        """Mostrar selector de tablas para gestionar valores."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Seleccionar Tabla")
        dialog.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Seleccione una tabla para gestionar sus valores:"))
        
        tables_list = QListWidget()
        for table in tables:
            item = QListWidgetItem(f"{table['display_name']}")
            if table.get('description'):
                item.setToolTip(table['description'])
            item.setData(Qt.ItemDataRole.UserRole, table)
            tables_list.addItem(item)
        
        layout.addWidget(tables_list)
        
        # Botones
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        def open_selected_table():
            current_item = tables_list.currentItem()
            if current_item:
                table_data = current_item.data(Qt.ItemDataRole.UserRole)
                from .parametros_values_dialog import ParametrosValuesDialog
                values_dialog = ParametrosValuesDialog(self.session_factory, table_data, self)
                values_dialog.exec()
        
        tables_list.itemDoubleClicked.connect(lambda: (dialog.accept(), open_selected_table()))
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            open_selected_table()


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
    
    def accept(self):
        """Validar y guardar datos."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validación", "El nombre del producto es requerido.")
            return
        
        try:
            with self.session_factory() as session:
                if self.is_editing and self.product_data:
                    update_configurable_product(session, self.product_data['id'], name)
                else:
                    create_configurable_product(session, name)
                session.commit()
            
            super().accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar producto: {str(e)}")