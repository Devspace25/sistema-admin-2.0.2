from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QMenu, QAbstractItemView, QDialog, QLineEdit,
    QInputDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QAction


class SimpleProductsView(QWidget):
    """Vista de productos configurables (gestión de tablas y valores)."""
    
    def __init__(self, session_factory):
        super().__init__()
        self.session_factory = session_factory
        self._can_edit = True
        self._build_ui()
        self._load_products()

    def set_permissions(self, permissions: set[str]):
        """Configurar permisos de edición."""
        self._can_edit = "edit_products" in permissions
        self._can_create = "create_products" in permissions
        
        self.btn_new.setVisible(self._can_create)
        self.btn_edit.setVisible(self._can_edit)
        self.btn_parameters.setVisible(self._can_edit)
        self.btn_values.setVisible(self._can_edit)
        self.btn_delete.setVisible(self._can_edit)
        
    def refresh(self):
        """Alias para _load_products compatible con la interfaz común."""
        self._load_products()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Top Bar (Search Left, Buttons Right)
        top_bar = QHBoxLayout()
        
        # Search
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)
        
        lbl_search = QLabel("Buscar:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Buscar producto...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_products)
        
        search_layout.addWidget(lbl_search)
        search_layout.addWidget(self.search_edit)
        
        top_bar.addWidget(search_container, 1)

        # Botones de acción (productos)
        self.btn_new = QPushButton("➕ Nuevo Producto")
        self.btn_edit = QPushButton("✏ Editar")
        self.btn_parameters = QPushButton("⚙ Parámetros")
        self.btn_values = QPushButton("📝 Valores")
        self.btn_delete = QPushButton("🗑 Eliminar")
        self.btn_refresh = QPushButton("🔄 Actualizar")
        
        # Style buttons
        for btn in [self.btn_new, self.btn_edit, self.btn_parameters, self.btn_values, self.btn_delete, self.btn_refresh]:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f8f9fa;
                    border: 1px solid #e0e0e0;
                    border-radius: 6px;
                    padding: 6px 12px;
                    color: #2c3e50;
                }
                QPushButton:hover {
                    background-color: #eef2f7;
                }
                QPushButton:disabled {
                    background-color: #f0f0f0;
                    color: #bdc3c7;
                }
            """)
            top_bar.addWidget(btn)
            
        layout.addLayout(top_bar)

        # Tabla de productos (vista única)
        self.table_products = QTableWidget()
        self.table_products.setColumnCount(3)
        self.table_products.setHorizontalHeaderLabels([
            "Nombre", "Creado por", "Fecha creación"
        ])
        header = self.table_products.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_products.setAlternatingRowColors(True)
        self.table_products.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_products.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.table_products)

        # Conectar señales
        self.btn_refresh.clicked.connect(self._load_products)
        self.btn_new.clicked.connect(self._on_add_product)
        self.btn_edit.clicked.connect(self._on_edit_product)
        self.btn_parameters.clicked.connect(self._open_parameters_dialog)
        self.btn_values.clicked.connect(self._on_manage_values)
        self.btn_delete.clicked.connect(self._on_delete_product)
        self.table_products.customContextMenuRequested.connect(self._show_context_menu)
        self.table_products.itemDoubleClicked.connect(self._configure_from_double_click)
        
    def _filter_products(self, text):
        """Filtrar filas de la tabla según el texto."""
        text = text.lower()
        for row in range(self.table_products.rowCount()):
            item = self.table_products.item(row, 0)
            match = text in item.text().lower() if item else False
            self.table_products.setRowHidden(row, not match)
        
    def _load_products(self):
        """Cargar productos configurables del sistema de parámetros."""
        try:
            with self.session_factory() as session:
                from ..repository import list_configurable_products
                products = list_configurable_products(session)
                
                self.table_products.setRowCount(len(products))
                
                for row, product in enumerate(products):
                    # Nombre
                    name_item = QTableWidgetItem(product['name'])
                    name_item.setData(Qt.ItemDataRole.UserRole, product['id'])
                    self.table_products.setItem(row, 0, name_item)
                    
                    # Creado por
                    self.table_products.setItem(row, 1, QTableWidgetItem(product['created_by']))
                    
                    # Fecha de creación
                    created_date = product['created_at'].strftime('%d/%m/%Y')
                    self.table_products.setItem(row, 2, QTableWidgetItem(created_date))
                
                # Nada más que hacer aquí; la gestión de tablas vive en el diálogo
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar productos: {str(e)}")
            print(f"Error cargando productos: {e}")
    def _selected_product(self):
        row = self.table_products.currentRow()
        if row < 0:
            return None
        name_item = self.table_products.item(row, 0)
        desc_item = self.table_products.item(row, 1)
        if not name_item:
            return None
        return {
            'id': name_item.data(Qt.ItemDataRole.UserRole),
            'name': name_item.text(),
            'description': desc_item.text() if desc_item else ""
        }

    def _open_parameters_dialog(self):
        prod = self._selected_product()
        if not prod:
            QMessageBox.warning(self, "Selección", "Seleccione un producto primero.")
            return
        dialog = ProductParametersPanelDialog(self.session_factory, prod, self)
        dialog.exec()

    def _on_delete_product(self):
        """Eliminar (desactivar) el producto seleccionado."""
        prod = self._selected_product()
        if not prod:
            QMessageBox.warning(self, "Selección", "Seleccione un producto para eliminar.")
            return
            
        # PROTECCIÓN: No permitir eliminar productos del sistema
        protected_names = ["corporeo", "talonario"]
        if prod['name'].lower() in protected_names:
            QMessageBox.warning(
                self, 
                "Acción denegada", 
                f"El producto '{prod['name']}' es un producto del sistema y no puede ser eliminado."
            )
            return

        reply = QMessageBox.question(
            self, 
            "Confirmar eliminación",
            f"¿Está seguro de que desea eliminar el producto '{prod['name']}'?\n"
            "Esta acción no se puede deshacer fácilmente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from ..repository import delete_configurable_product
                with self.session_factory() as session:
                    delete_configurable_product(session, prod['id'])
                    session.commit()
                
                QMessageBox.information(self, "Eliminado", f"Producto '{prod['name']}' eliminado correctamente.")
                self._load_products()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo eliminar el producto: {e}")

    def _on_add_product(self):
        """Mostrar diálogo para crear un nuevo producto configurable y guardarlo."""
        dlg = NewProductDialog(self)
        # PySide6: compare against DialogCode.Accepted for clarity
        from PySide6.QtWidgets import QDialog as _QDialog
        if dlg.exec() != _QDialog.DialogCode.Accepted:
            return
        name, desc = dlg.get_data()
        if not name:
            QMessageBox.warning(self, "Validación", "El nombre del producto no puede estar vacío.")
            return
        try:
            from ..repository import create_configurable_product
            with self.session_factory() as session:
                create_configurable_product(session, name=name, description=desc or None)
                session.commit()
            QMessageBox.information(self, "Creado", f"Producto '{name}' creado correctamente.")
            self._load_products()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo crear el producto: {e}")

    def _on_edit_product(self):
        """Editar nombre y descripción del producto seleccionado."""
        prod = self._selected_product()
        if not prod:
            QMessageBox.warning(self, "Selección", "Seleccione un producto para editar.")
            return
            
        dlg = NewProductDialog(self, name=prod['name'], description=prod['description'])
        from PySide6.QtWidgets import QDialog as _QDialog
        if dlg.exec() != _QDialog.DialogCode.Accepted:
            return
            
        name, desc = dlg.get_data()
        if not name:
            QMessageBox.warning(self, "Validación", "El nombre del producto no puede estar vacío.")
            return
            
        try:
            from ..repository import update_configurable_product
            with self.session_factory() as session:
                update_configurable_product(session, prod['id'], name=name, description=desc or None)
                session.commit()
            
            QMessageBox.information(self, "Actualizado", f"Producto '{name}' actualizado correctamente.")
            self._load_products()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo actualizar el producto: {e}")

    def _on_manage_values(self):
        """Gestionar valores de parámetros para el producto seleccionado."""
        prod = self._selected_product()
        if not prod:
            QMessageBox.warning(self, "Selección", "Seleccione un producto primero.")
            return
        
        try:
            from ..repository import get_product_parameter_tables
            with self.session_factory() as session:
                tables = get_product_parameter_tables(session, prod['id'])
            
            if not tables:
                QMessageBox.warning(self, "Sin tablas", "Debe crear tablas de relaciones para este producto antes de gestionar valores.")
                return
            
            selected_table = None
            if len(tables) == 1:
                selected_table = tables[0]
            else:
                # Show selection dialog
                item, ok = QInputDialog.getItem(
                    self, 
                    "Seleccionar Tabla", 
                    "Seleccione la tabla de parámetros:", 
                    [t['display_name'] for t in tables], 
                    0, 
                    False
                )
                if ok and item:
                    for t in tables:
                        if t['display_name'] == item:
                            selected_table = t
                            break
            
            if selected_table:
                from .parametros_values_dialog import ParametrosValuesDialog
                dialog = ParametrosValuesDialog(self.session_factory, selected_table, self)
                dialog.exec()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar tablas: {e}")

    def _configure_product_parameters(self, product_id: int, product_name: str):
        """Abrir el diálogo de configuración de parámetros (compatibilidad)."""
        try:
            from .product_parameters_dialog import ProductParametersDialog
            # Firma actual: (session_factory, product_id: int, parent=None)
            dialog = ProductParametersDialog(self.session_factory, product_id, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al abrir configuración de parámetros: {str(e)}")

    def _configure_from_double_click(self):
        """Configurar parámetros desde doble clic."""
        current_row = self.table_products.currentRow()
        if current_row >= 0:
            name_item = self.table_products.item(current_row, 0)
            if name_item:
                product_id = name_item.data(Qt.ItemDataRole.UserRole)
                product_name = name_item.text()
                self._configure_product_parameters(product_id, product_name)

    def _show_context_menu(self, position):
        """Mostrar menú contextual."""
        item = self.table_products.itemAt(position)
        if item is None:
            return
            
        menu = QMenu(self)
        
        config_action = QAction("⚙️ Configurar Parámetros", self)
        config_action.triggered.connect(lambda: self._configure_from_context())
        menu.addAction(config_action)
        
        menu.exec(self.table_products.mapToGlobal(position))

    def _configure_from_context(self):
        """Configurar parámetros desde menú contextual."""
        current_row = self.table_products.currentRow()
        if current_row >= 0:
            name_item = self.table_products.item(current_row, 0)
            if name_item:
                product_id = name_item.data(Qt.ItemDataRole.UserRole)
                product_name = name_item.text()
                # Abrir el mismo diálogo del botón "Parámetros"
                dialog = ProductParametersPanelDialog(self.session_factory, {'id': product_id, 'name': product_name}, self)
                dialog.exec()


class NewProductDialog(QDialog):
    """Diálogo simple para crear o editar un producto configurable."""
    def __init__(self, parent=None, name: str = "", description: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Editar Producto" if name else "Nuevo Producto")
        self.resize(400, 160)
        layout = QVBoxLayout(self)

        from PySide6.QtWidgets import QLabel
        lbl = QLabel("Nombre del producto:")
        self.txt_name = QLineEdit()
        self.txt_name.setText(name)
        layout.addWidget(lbl)
        layout.addWidget(self.txt_name)

        lbl2 = QLabel("Descripción (opcional):")
        self.txt_desc = QLineEdit()
        self.txt_desc.setText(description)
        layout.addWidget(lbl2)
        layout.addWidget(self.txt_desc)

        btns = QHBoxLayout()
        btns.addStretch()
        ok = QPushButton("Guardar" if name else "Crear")
        cancel = QPushButton("Cancelar")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def get_data(self) -> tuple[str, str]:
        return (self.txt_name.text().strip(), self.txt_desc.text().strip())



class ProductParametersPanelDialog(QDialog):
    """Diálogo que muestra la vista de tablas de parámetros para un producto."""
    def __init__(self, session_factory, product: dict, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.product = product
        self.setWindowTitle(f"Parámetros — {product['name']}")
        self.resize(900, 600)

        self._build_ui()
        self._load_param_tables()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Encabezado
        lbl = QLabel(f"Tablas de parámetros: {self.product['name']}")
        f = QFont(); f.setBold(True)
        lbl.setFont(f)
        layout.addWidget(lbl)

        # Botones
        btns = QHBoxLayout()
        self.btn_add_table = QPushButton("+ Nueva Tabla")
        self.btn_edit_table = QPushButton("✏ Editar Tabla")
        self.btn_delete_table = QPushButton("🗑 Eliminar Tabla")
        self.btn_relations = QPushButton("🔗 Relaciones")
        self.btn_values = QPushButton("📝 Valores")
        self.btn_force_delete = QPushButton("⚠ Forzar eliminación")
        self.btn_restore = QPushButton("↩ Restaurar tabla")
        self.btn_restore_chain = QPushButton("↩⤴ Restaurar en cadena")
        for b in (self.btn_add_table, self.btn_edit_table, self.btn_delete_table, self.btn_force_delete, self.btn_restore, self.btn_restore_chain, self.btn_relations, self.btn_values):
            btns.addWidget(b)
        btns.addStretch()
        layout.addLayout(btns)

        # Filtros
        from PySide6.QtWidgets import QCheckBox
        filters = QHBoxLayout()
        self.chk_show_inactive = QCheckBox("Mostrar inactivas")
        self.chk_show_inactive.setChecked(False)
        self.chk_show_inactive.toggled.connect(self._load_param_tables)
        filters.addWidget(self.chk_show_inactive)
        filters.addStretch()
        layout.addLayout(filters)

        # Tabla de tablas
        self.table_param_tables = QTableWidget(0, 5)
        self.table_param_tables.setHorizontalHeaderLabels(["Nombre", "Columnas", "Registros", "Tipo", "Estado"])
        hdr = self.table_param_tables.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_param_tables.setAlternatingRowColors(True)
        self.table_param_tables.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table_param_tables)

        # Conectar
        self.btn_add_table.clicked.connect(self._add_table)
        self.btn_edit_table.clicked.connect(self._edit_table)
        self.btn_delete_table.clicked.connect(self._delete_table)
        self.btn_relations.clicked.connect(self._manage_relations)
        self.btn_values.clicked.connect(self._manage_values)
        self.btn_force_delete.clicked.connect(self._force_delete_table)
        self.btn_restore.clicked.connect(self._restore_table)
        self.btn_restore_chain.clicked.connect(self._restore_table_chain)

    def _load_param_tables(self):
        try:
            from ..repository import get_product_parameter_tables
            with self.session_factory() as session:
                include_inactive = bool(self.chk_show_inactive.isChecked())
                tables = get_product_parameter_tables(session, self.product['id'], include_inactive=include_inactive)
                self.table_param_tables.setRowCount(len(tables))
                for r, table in enumerate(tables):
                    name_item = QTableWidgetItem(table['display_name'])
                    name_item.setData(Qt.ItemDataRole.UserRole, table)
                    # If the table is inactive, mark the name in red for quick visual
                    try:
                        if not table.get('is_active'):
                            from PySide6.QtGui import QBrush, QColor
                            name_item.setForeground(QBrush(QColor(200, 0, 0)))
                    except Exception:
                        pass
                    self.table_param_tables.setItem(r, 0, name_item)
                    schema = table.get('schema', [])
                    self.table_param_tables.setItem(r, 1, QTableWidgetItem(str(len(schema))))
                    record_count = table.get('record_count', 0)
                    self.table_param_tables.setItem(r, 2, QTableWidgetItem(str(record_count)))
                    table_type = "Padre" if table.get('parent_table_name') is None else "Hijo"
                    self.table_param_tables.setItem(r, 3, QTableWidgetItem(table_type))
                    # Show a red cross for inactive tables to make them obvious
                    try:
                        if table.get('is_active'):
                            estado_item = QTableWidgetItem("Activo")
                        else:
                            estado_item = QTableWidgetItem("✖ Inactivo")
                            try:
                                from PySide6.QtGui import QBrush, QColor
                                estado_item.setForeground(QBrush(QColor(200, 0, 0)))
                            except Exception:
                                pass
                    except Exception:
                        estado_item = QTableWidgetItem("Inactivo")
                    self.table_param_tables.setItem(r, 4, estado_item)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar tablas: {str(e)}")

    def _selected_table(self):
        row = self.table_param_tables.currentRow()
        if row < 0:
            return None
        item = self.table_param_tables.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add_table(self):
        from .parametros_table_dialog import ParametrosTableDialog
        dialog = ParametrosTableDialog(self.session_factory, self.product, self)
        if dialog.exec():
            self._load_param_tables()

    def _edit_table(self):
        table = self._selected_table()
        if not table:
            QMessageBox.warning(self, "Selección", "Seleccione una tabla para editar.")
            return
        from .parametros_table_dialog import ParametrosTableDialog
        dialog = ParametrosTableDialog(self.session_factory, self.product, self, table)
        if dialog.exec():
            self._load_param_tables()

    def _delete_table(self):
        table = self._selected_table()
        if not table:
            QMessageBox.warning(self, "Selección", "Seleccione una tabla para eliminar.")
            return
        # Verificar referencias
        try:
            from ..repository import check_parameter_table_references
            with self.session_factory() as session:
                refs = check_parameter_table_references(session, table['id'])
        except Exception:
            refs = {'orders': 0, 'sales': 0}

        # Si hay referencias, impedir eliminación estándar
        if refs.get('orders', 0):
            QMessageBox.warning(
                self,
                "No se puede eliminar",
                f"Se detectaron {refs['orders']} orden(es) que podrían referenciar esta tabla.\n"
                "Elimine/actualice esas referencias o use 'Forzar eliminación' bajo su responsabilidad."
            )
            return

        reply = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Está seguro de eliminar la tabla '{table.get('display_name')}'?\n"
            f"Esto desactivará permanentemente la tabla y sus datos.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            from ..repository import delete_product_parameter_table
            with self.session_factory() as session:
                stats = delete_product_parameter_table(session, table['id'])
                session.commit()
            QMessageBox.information(
                self, "Eliminada",
                f"Tabla eliminada. Filas desactivadas: {stats.get('values_deactivated', 0)}."
            )
            self._load_param_tables()
        except Exception as e:
            QMessageBox.critical(self, "No se pudo eliminar", str(e))

    def _force_delete_table(self):
        table = self._selected_table()
        if not table:
            QMessageBox.warning(self, "Selección", "Seleccione una tabla para eliminar.")
            return
        # Listar hijas activas
        try:
            from ..repository import get_child_parameter_tables, check_parameter_table_references
            with self.session_factory() as session:
                children = get_child_parameter_tables(session, table['id'], active_only=True)
                refs = check_parameter_table_references(session, table['id'])
        except Exception:
            children = []
            refs = {'orders': 0, 'sales': 0}
        child_lines = "\n".join([f" • {c['display_name']} (ID {c['id']})" for c in children]) or "(sin hijas)"
        ref_text = ""
        if refs.get('orders', 0):
            ref_text = f"\nAdvertencia: {refs['orders']} orden(es) podrían referenciar esta tabla."
        confirm = QMessageBox.warning(
            self,
            "Forzar eliminación",
            (
                f"Esta acción desactivará primero las tablas hijas y luego '{table.get('display_name')}'.\n"
                f"Tablas hijas activas:\n{child_lines}{ref_text}\n\n"
                "¿Desea continuar?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            from ..repository import delete_product_parameter_table
            with self.session_factory() as session:
                stats = delete_product_parameter_table(session, table['id'], cascade_values=True, force=True)
                session.commit()
            QMessageBox.information(
                self, "Eliminación forzada completada",
                f"Filas desactivadas totales: {stats.get('values_deactivated', 0)}. Tablas hijas afectadas: {stats.get('children_count', 0)}."
            )
            self._load_param_tables()
        except Exception as e:
            QMessageBox.critical(self, "Error en eliminación forzada", str(e))

    def _restore_table(self):
        table = self._selected_table()
        if not table:
            QMessageBox.warning(self, "Selección", "Seleccione una tabla para restaurar.")
            return
        # Confirmar restauración
        reply = QMessageBox.question(
            self, "Restaurar tabla",
            f"¿Desea reactivar la tabla '{table.get('display_name')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            from ..repository import restore_product_parameter_table
            with self.session_factory() as session:
                stats = restore_product_parameter_table(session, table['id'], with_children=False)
                session.commit()
            QMessageBox.information(self, "Restaurada", "La tabla fue reactivada.")
            self._load_param_tables()
        except Exception as e:
            QMessageBox.critical(self, "No se pudo restaurar", str(e))

    def _restore_table_chain(self):
        table = self._selected_table()
        if not table:
            QMessageBox.warning(self, "Selección", "Seleccione una tabla para restaurar.")
            return
        # Recolectar info de parentesco e hijas inactivas
        try:
            from ..repository import get_child_parameter_tables
            with self.session_factory() as session:
                children_all = get_child_parameter_tables(session, table['id'], active_only=False)
        except Exception:
            children_all = []
        inactive_children = [c for c in children_all if not c.get('is_active', True)]
        child_lines = "\n".join([f" • {c['display_name']} (ID {c['id']})" for c in inactive_children]) or "(ninguna)"
        # Confirmar
        reply = QMessageBox.question(
            self,
            "Restaurar en cadena",
            (
                f"Se restaurará la tabla '{table.get('display_name')}'.\n"
                f"También se intentará restaurar su padre si estuviese inactivo, y estas hijas inactivas:\n{child_lines}\n\n"
                "¿Desea continuar?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            from ..repository import restore_product_parameter_table
            with self.session_factory() as session:
                stats = restore_product_parameter_table(session, table['id'], with_children=True)
                session.commit()
            QMessageBox.information(self, "Restauración completada", "La tabla y su cadena fueron reactivadas (si aplicaba).")
            self._load_param_tables()
        except Exception as e:
            QMessageBox.critical(self, "No se pudo restaurar en cadena", str(e))

    def _manage_relations(self):
        from .parametros_relations_dialog import ParametrosRelationsDialog
        dialog = ParametrosRelationsDialog(self.session_factory, self.product, self)
        dialog.exec()

    def _manage_values(self):
        table = self._selected_table()
        if not table:
            QMessageBox.warning(self, "Selección", "Seleccione una tabla para gestionar valores.")
            return
        from .parametros_values_dialog import ParametrosValuesDialog
        dialog = ParametrosValuesDialog(self.session_factory, table, self)
        dialog.exec()