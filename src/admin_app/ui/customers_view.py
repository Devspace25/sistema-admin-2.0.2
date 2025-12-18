from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QMessageBox,
    QSpacerItem,
    QSizePolicy,
    QAbstractItemView,
    QLineEdit,
    QLabel,
    QComboBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from sqlalchemy.orm import sessionmaker
from ..repository import list_customers, add_customers, delete_customer_by_id, update_customer
from ..models import Customer
from .customer_dialog import CustomerDialog


class _LoadCustomersThread(QThread):
    loaded = Signal(list)

    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__()
        self._session_factory = session_factory

    def run(self) -> None:  # type: ignore[override]
        try:
            with self._session_factory() as session:
                customers = list_customers(session)
                data = []
                for c in customers:
                    try:
                        data.append({
                            "id": c.id,
                            "first_name": (c.first_name or c.name) if hasattr(c, 'first_name') else c.name,
                            "last_name": getattr(c, 'last_name', None) or "",
                            "document": getattr(c, 'document', None) or "",
                            "short_address": getattr(c, 'short_address', None) or "",
                            "phone": getattr(c, 'phone', None) or "",
                            "email": c.email or "",
                        })
                    except Exception as e:
                        print(f"Error al cargar cliente {c.id}: {e}")
                self.loaded.emit(data)
        except Exception as e:
            print(f"Error en thread de carga: {e}")
            self.loaded.emit([])


class CustomersView(QWidget):
    def __init__(self, session_factory: sessionmaker, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._loader: _LoadCustomersThread | None = None
        self._can_edit = True
        self._can_delete = True
        self._setupUi()
        self.reload_async()

    def set_permissions(self, permissions: set[str]):
        """Configurar permisos de edición y eliminación."""
        self._can_edit = "edit_customers" in permissions
        self._can_create = "create_customers" in permissions
        self._can_delete = "edit_customers" in permissions # Asumimos mismo permiso por ahora
        
        self.btn_new.setVisible(self._can_create)
        self._on_selection_changed()

    def refresh(self):
        """Alias para reload_async compatible con la interfaz común."""
        self.reload_async()

    def _setupUi(self) -> None:
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        self.setMinimumHeight(400)

        # Top Bar (Search Left, Buttons Right)
        top_bar = QHBoxLayout()
        
        # Search
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)
        
        lbl_search = QLabel("Buscar:")
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("🔍 Buscar por nombre, apellido, documento o email...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)
        
        self.filter_document = QComboBox(self)
        self.filter_document.addItems(["Todos", "V-", "J-", "E-", "G-"])
        self.filter_document.setToolTip("Filtrar por tipo de documento")
        self.filter_document.currentTextChanged.connect(self._apply_filter)
        
        search_layout.addWidget(lbl_search)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.filter_document)
        
        top_bar.addWidget(search_container, 1)
        
        # Botones de acción
        self.btn_new = QPushButton("➕ Nuevo Cliente", self)
        self.btn_edit = QPushButton("✏️ Editar", self)
        self.btn_delete = QPushButton("🗑️ Eliminar", self)
        self.btn_export = QPushButton("📄 Exportar", self)
        self.btn_refresh = QPushButton("🔄 Actualizar", self)
        
        self.btn_new.clicked.connect(self._on_new)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_export.clicked.connect(self._on_export)
        self.btn_refresh.clicked.connect(self.reload_async)
        
        # Style buttons
        for btn in [self.btn_new, self.btn_edit, self.btn_delete, self.btn_export, self.btn_refresh]:
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
            
        main_layout.addLayout(top_bar)

        # Tabla
        self._table = self._setupTable()
        main_layout.addWidget(self._table)
        
        # Estado
        self._status_label = QLabel("Cargando...", self)
        self._status_label.setStyleSheet("color: #666; font-style: italic; padding: 4px;")
        main_layout.addWidget(self._status_label)

    def _setupTable(self) -> QTableWidget:
        table = QTableWidget(0, 7, self)
        table.setHorizontalHeaderLabels(["ID", "Nombre", "Apellido", "C.I./Rif.", "Dirección corta", "Teléfono", "Email"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        
        # Configurar columnas
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)  # Nombre
        header.setSectionResizeMode(2, header.ResizeMode.Stretch)  # Apellido
        header.setSectionResizeMode(3, header.ResizeMode.ResizeToContents)  # Documento
        header.setSectionResizeMode(4, header.ResizeMode.Stretch)  # Dirección
        header.setSectionResizeMode(5, header.ResizeMode.ResizeToContents)  # Teléfono
        header.setSectionResizeMode(6, header.ResizeMode.Stretch)  # Email
        
        # Conectar eventos
        table.itemSelectionChanged.connect(self._on_selection_changed)
        table.itemDoubleClicked.connect(self._on_edit)
        
        # Configurar ordenamiento
        table.setSortingEnabled(True)
        
        return table

    def reload_async(self) -> None:
        """Recarga los datos de clientes de forma asíncrona."""
        self.setEnabled(False)
        self._loader = _LoadCustomersThread(self._session_factory)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.finished.connect(lambda: self.setEnabled(True))
        self._loader.start()

    def _on_loaded(self, customers: list[dict]) -> None:
        """Maneja la carga de datos en la tabla."""
        self._table.setUpdatesEnabled(False)
        self._table.setSortingEnabled(False)
        
        try:
            # Limpiar tabla
            self._table.clearContents()
            self._table.setRowCount(0)
            
            # Insertar datos
            for c in customers:
                row = self._table.rowCount()
                self._table.insertRow(row)
                
                # ID como número para ordenamiento correcto
                id_item = QTableWidgetItem()
                try:
                    id_val = int(c.get("id", 0))
                    id_item.setData(Qt.ItemDataRole.DisplayRole, id_val)
                except (ValueError, TypeError):
                    id_item.setText("0")
                
                # Crear y asignar items
                items = [
                    id_item,
                    QTableWidgetItem(str(c.get("first_name") or c.get("name") or "")),
                    QTableWidgetItem(str(c.get("last_name") or "")),
                    QTableWidgetItem(str(c.get("document") or "")),
                    QTableWidgetItem(str(c.get("short_address") or "")),
                    QTableWidgetItem(str(c.get("phone") or "")),
                    QTableWidgetItem(str(c.get("email") or ""))
                ]
                
                for col, item in enumerate(items):
                    if item:  # Asegurar que el item existe
                        self._table.setItem(row, col, item)
            
            # Actualizar estado
            total = self._table.rowCount()
            self._status_label.setText(f"Total: {total} clientes")
            
        finally:
            self._table.setSortingEnabled(True)
            self._table.setUpdatesEnabled(True)
            self._apply_filter()

    def _apply_filter(self, text: str = "") -> None:
        """Aplica filtros de búsqueda y tipo de documento."""
        if not hasattr(self, '_table') or not self._table:
            return
            
        search_text = self.search_edit.text().lower() if hasattr(self, 'search_edit') else text.lower()
        doc_filter = self.filter_document.currentText() if hasattr(self, 'filter_document') else "Todos"
        
        self._table.setUpdatesEnabled(False)
        visible_count = 0
        total_count = self._table.rowCount()
        
        try:
            for row in range(total_count):
                text_match = True
                doc_match = True
                
                # Filtro de texto
                if search_text.strip():
                    text_match = False
                    for col in range(1, self._table.columnCount()):
                        item = self._table.item(row, col)
                        if item and item.text() and search_text in item.text().lower():
                            text_match = True
                            break
                
                # Filtro de documento
                if doc_filter != "Todos":
                    doc_item = self._table.item(row, 3)
                    if doc_item and doc_item.text():
                        doc_text = doc_item.text().upper().strip()
                        # Usar startswith directamente ya que el filtro es "V-", "J-", etc.
                        doc_match = doc_text.startswith(doc_filter.upper())
                    else:
                        doc_match = False
                
                # Aplicar visibilidad
                is_visible = text_match and doc_match
                self._table.setRowHidden(row, not is_visible)
                if is_visible:
                    visible_count += 1
                    
            self._status_label.setText(f"Mostrando {visible_count} de {total_count} clientes")
            
        finally:
            self._table.setUpdatesEnabled(True)

    def _on_new(self) -> None:
        """Maneja la creación de un nuevo cliente."""
        dlg = CustomerDialog(self)
        if dlg.exec():
            try:
                data = dlg.get_data()
                with self._session_factory() as session:
                    cust = Customer(
                        name=data.get("first_name") or "",
                        first_name=data.get("first_name"),
                        last_name=data.get("last_name"),
                        document=data.get("document"),
                        short_address=data.get("short_address"),
                        phone=data.get("phone"),
                        email=data.get("email"),
                    )
                    add_customers(session, [cust])
                self.reload_async()
                QMessageBox.information(self, "Éxito", "Cliente agregado correctamente")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo agregar el cliente:\n{str(e)}")

    def _on_edit(self) -> None:
        """Maneja la edición de un cliente existente."""
        if not self._can_edit:
            return
            
        cid = self.selected_customer_id()
        if cid is None:
            QMessageBox.information(self, "Editar", "Selecciona un cliente primero")
            return
        
        row = self._table.currentRow()
        current_data = {
            "first_name": self._table.item(row, 1).text() if self._table.item(row, 1) else "",
            "last_name": self._table.item(row, 2).text() if self._table.item(row, 2) else "",
            "document": self._table.item(row, 3).text() if self._table.item(row, 3) else "",
            "short_address": self._table.item(row, 4).text() if self._table.item(row, 4) else "",
            "phone": self._table.item(row, 5).text() if self._table.item(row, 5) else "",
            "email": self._table.item(row, 6).text() if self._table.item(row, 6) else "",
        }

        dlg = CustomerDialog(self)
        dlg.setWindowTitle("Editar cliente")
        dlg.set_data(current_data)
        
        if dlg.exec():
            try:
                new_data = dlg.get_data()
                with self._session_factory() as session:
                    update_customer(session, cid, 
                                 name=(new_data.get("first_name") or ""), 
                                 email=new_data.get("email"))
                    obj = session.get(Customer, cid)
                    if obj:
                        obj.first_name = new_data.get("first_name")
                        obj.last_name = new_data.get("last_name")
                        obj.document = new_data.get("document")
                        obj.short_address = new_data.get("short_address")
                        obj.phone = new_data.get("phone")
                        session.commit()
                        self.reload_async()
                        QMessageBox.information(self, "Éxito", "Cliente actualizado correctamente")
                    else:
                        QMessageBox.warning(self, "Error", "No se encontró el cliente para actualizar")
                        self.reload_async()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo actualizar el cliente:\n{str(e)}")
                self.reload_async()

    def _on_delete(self) -> None:
        """Maneja la eliminación de un cliente."""
        cid = self.selected_customer_id()
        if cid is None:
            QMessageBox.warning(self, "Eliminar", "Selecciona un cliente primero")
            return
            
        row = self._table.currentRow()
        name = self._table.item(row, 1).text() if self._table.item(row, 1) else ""
        last_name = self._table.item(row, 2).text() if self._table.item(row, 2) else ""
        document = self._table.item(row, 3).text() if self._table.item(row, 3) else ""
        
        reply = QMessageBox.question(
            self,
            "Confirmar Eliminación",
            f"¿Estás seguro de que deseas eliminar este cliente?\n\n"
            f"ID: {cid}\n"
            f"Nombre: {name} {last_name}\n"
            f"Documento: {document}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with self._session_factory() as session:
                    if delete_customer_by_id(session, cid):
                        self._table.removeRow(row)
                        total = self._table.rowCount()
                        visible = sum(1 for r in range(total) if not self._table.isRowHidden(r))
                        self._status_label.setText(f"Total: {total} clientes")
                        QMessageBox.information(self, "Éxito", "Cliente eliminado correctamente")
                    else:
                        QMessageBox.warning(self, "Error", "No se encontró el cliente para eliminar")
                        self.reload_async()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo eliminar el cliente:\n{str(e)}")
                self.reload_async()

    def _on_selection_changed(self) -> None:
        """Actualiza el estado de los botones según la selección."""
        has_sel = self.selected_customer_id() is not None
        self.btn_edit.setEnabled(has_sel and self._can_edit)
        self.btn_delete.setEnabled(has_sel and self._can_delete)

    def selected_customer_id(self) -> int | None:
        """Obtiene el ID del cliente seleccionado actualmente."""
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if not item:
            return None
        try:
            return int(item.text())
        except (ValueError, TypeError):
            return None

    def _on_export(self) -> None:
        """Exporta la lista de clientes a CSV."""
        try:
            from PySide6.QtWidgets import QFileDialog
            import csv
            from datetime import datetime
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar Clientes",
                f"clientes_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if not file_path:
                return
            
            data = []
            headers = ["ID", "Nombre", "Apellido", "Documento", "Dirección", "Teléfono", "Email"]
            
            for row in range(self._table.rowCount()):
                if not self._table.isRowHidden(row):
                    row_data = []
                    for col in range(7):
                        item = self._table.item(row, col)
                        row_data.append(item.text() if item else "")
                    data.append(row_data)
            
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(data)
            
            QMessageBox.information(
                self, 
                "Exportar", 
                f"Se exportaron {len(data)} clientes a:\n{file_path}"
            )
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al exportar: {str(e)}")