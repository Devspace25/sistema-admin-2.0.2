from __future__ import annotations

from typing import Dict, List, Any, Optional
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QCheckBox, QSpinBox,
    QTextEdit, QMessageBox, QDialogButtonBox, QLabel, QFrame,
    QHeaderView, QGroupBox, QWidget
)
from PySide6.QtGui import QFont

from ..repository import (
    create_product_parameter_table, update_product_parameter_table
)


class ParametrosTableDialog(QDialog):
    """Diálogo para crear y editar tablas de parámetros."""
    
    def __init__(self, session_factory, product_data: Dict[str, Any], parent=None, table_data: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.product_data = product_data
        self.table_data = table_data
        self.is_editing = table_data is not None
        
        self.setWindowTitle(f"{'Editar' if self.is_editing else 'Crear'} Tabla de Parámetros")
        self.setMinimumSize(800, 600)
        
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self):
        """Configurar la interfaz del diálogo."""
        layout = QVBoxLayout(self)
        
        # Información del producto
        info_label = QLabel(f"Producto: {self.product_data['name']}")
        info_font = QFont()
        info_font.setBold(True)
        info_font.setPointSize(11)
        info_label.setFont(info_font)
        layout.addWidget(info_label)
        
        # Separador
        separator = QFrame()
        separator.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Formulario de información básica
        basic_group = QGroupBox("Información de la Tabla")
        basic_layout = QFormLayout(basic_group)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nombre de la tabla (ej: Materiales, Espesores)")
        basic_layout.addRow("Nombre de la Tabla:", self.name_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        self.description_edit.setPlaceholderText("Descripción opcional de la tabla")
        basic_layout.addRow("Descripción:", self.description_edit)
        
        layout.addWidget(basic_group)
        
        # Sección de relaciones
        relations_group = QGroupBox("Relaciones con Otras Tablas")
        relations_layout = QVBoxLayout(relations_group)
        
        # Checkbox para habilitar relaciones
        self.enable_relations_cb = QCheckBox("Esta tabla tiene relación con otra tabla")
        relations_layout.addWidget(self.enable_relations_cb)
        
        # Widget contenedor para configuración de relaciones
        self.relations_widget = QFrame()
        relations_form = QFormLayout(self.relations_widget)
        
        # ComboBox para seleccionar tabla relacionada
        self.parent_table_combo = QComboBox()
        self.parent_table_combo.addItem("-- Seleccionar tabla --", None)
        relations_form.addRow("Tabla relacionada:", self.parent_table_combo)
        
        # Campo para nombre de columna de relación
        self.relation_column_edit = QLineEdit()
        self.relation_column_edit.setPlaceholderText("ej: id_materiales, id_categorias")
        relations_form.addRow("Nombre de columna de relación:", self.relation_column_edit)
        
        relations_layout.addWidget(self.relations_widget)
        self.relations_widget.setEnabled(False)  # Inicialmente deshabilitado
        
        layout.addWidget(relations_group)
        
        # Configuración del esquema
        schema_group = QGroupBox("Esquema de Columnas")
        schema_layout = QVBoxLayout(schema_group)
        
        # Botones de gestión de columnas
        column_buttons = QHBoxLayout()
        self.add_column_btn = QPushButton("+ Agregar Columna")
        self.remove_column_btn = QPushButton("- Eliminar Columna")
        
        column_buttons.addWidget(self.add_column_btn)
        column_buttons.addWidget(self.remove_column_btn)
        column_buttons.addStretch()
        
        schema_layout.addLayout(column_buttons)
        
        # Tabla de columnas
        self.columns_table = QTableWidget(0, 6)
        self.columns_table.setHorizontalHeaderLabels([
            "Nombre", "Tipo", "Requerido", "Clave Primaria", "Auto ID", "Descripción"
        ])
        
        # Configurar tabla de columnas
        header = self.columns_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        
        self.columns_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        schema_layout.addWidget(self.columns_table)
        
        layout.addWidget(schema_group)
        
        # Botones del diálogo
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Conectar eventos
        self.add_column_btn.clicked.connect(self._add_column)
        self.remove_column_btn.clicked.connect(self._remove_column)
        self.enable_relations_cb.toggled.connect(self._on_relations_toggled)
        
        # Cargar tablas disponibles para relaciones
        self._load_available_tables()
        
        # Agregar columna ID por defecto si es nueva tabla
        if not self.is_editing:
            self._add_default_id_column()
    
    def _add_default_id_column(self):
        """Agregar columna ID por defecto."""
        self._add_column_row("id", "INTEGER", True, True, True, "Identificador único automático")
    
    def _load_available_tables(self):
        """Cargar tablas disponibles para relaciones."""
        try:
            with self.session_factory() as session:
                from ..repository import get_product_parameter_tables
                tables = get_product_parameter_tables(session, self.product_data['id'])
                
                self.parent_table_combo.clear()
                self.parent_table_combo.addItem("-- Seleccionar tabla --", None)
                
                for table in tables:
                    # No incluir la tabla actual si estamos editando
                    if self.is_editing and self.table_data and table.get('id') == self.table_data.get('id'):
                        continue
                    
                    display_text = table['display_name']
                    if table.get('description'):
                        display_text += f" - {table['description']}"
                    
                    self.parent_table_combo.addItem(display_text, table)
                    
        except Exception as e:
            print(f"Error cargando tablas: {e}")
    
    def _on_relations_toggled(self, enabled: bool):
        """Habilitar/deshabilitar configuración de relaciones."""
        self.relations_widget.setEnabled(enabled)
        
        # Si se habilitan las relaciones, conectar el cambio de tabla
        if enabled:
            self.parent_table_combo.currentTextChanged.connect(self._on_parent_table_changed)
        else:
            try:
                self.parent_table_combo.currentTextChanged.disconnect(self._on_parent_table_changed)
            except:
                pass
    
    def _on_parent_table_changed(self):
        """Actualizar nombre de columna de relación cuando cambia la tabla padre."""
        selected_table = self.parent_table_combo.currentData()
        if selected_table:
            table_name = selected_table['display_name'].lower().replace(' ', '_').replace('-', '_')
            relation_name = f"id_{table_name}"
            self.relation_column_edit.setText(relation_name)
            
            # Agregar la columna automáticamente si no existe
            if not self._has_relation_column_in_table(relation_name):
                self._add_column_row(relation_name, "INTEGER", True, False, False, 
                                   f"Referencia a {selected_table['display_name']}")
    
    def _has_relation_column_in_table(self, column_name: str) -> bool:
        """Verificar si ya existe una columna con este nombre en la tabla."""
        for row in range(self.columns_table.rowCount()):
            name_widget = self.columns_table.cellWidget(row, 0)
            if isinstance(name_widget, QLineEdit):
                if name_widget.text().strip() == column_name:
                    return True
        return False
    
    def _has_relation_column(self) -> bool:
        """Verificar si ya existe una columna de relación definida."""
        relation_name = self.relation_column_edit.text().strip()
        if not relation_name:
            return False
            
        # Buscar en la tabla de columnas
        for row in range(self.columns_table.rowCount()):
            name_widget = self.columns_table.cellWidget(row, 0)
            if isinstance(name_widget, QLineEdit):
                if name_widget.text().strip() == relation_name:
                    return True
        return False
    
    def _add_column(self):
        """Agregar nueva columna."""
        self._add_column_row("", "TEXT", False, False, False, "")
    
    def _add_column_row(self, name: str, data_type: str, required: bool, primary_key: bool, auto_increment: bool, description: str):
        """Agregar una fila de columna con valores específicos."""
        row = self.columns_table.rowCount()
        self.columns_table.insertRow(row)
        
        # Nombre
        name_item = QLineEdit(name)
        self.columns_table.setCellWidget(row, 0, name_item)
        
        # Tipo
        type_combo = QComboBox()
        type_combo.addItems(["TEXT", "INTEGER", "REAL", "BOOLEAN"])
        type_combo.setCurrentText(data_type)
        self.columns_table.setCellWidget(row, 1, type_combo)
        
        # Requerido
        required_check = QCheckBox()
        required_check.setChecked(required)
        self.columns_table.setCellWidget(row, 2, required_check)
        
        # Clave primaria
        pk_check = QCheckBox()
        pk_check.setChecked(primary_key)
        self.columns_table.setCellWidget(row, 3, pk_check)
        
        # Auto ID
        auto_check = QCheckBox()
        auto_check.setChecked(auto_increment)
        self.columns_table.setCellWidget(row, 4, auto_check)
        
        # Descripción
        desc_item = QLineEdit(description)
        self.columns_table.setCellWidget(row, 5, desc_item)

        # Vincular cambio de nombre para forzar reglas de 'id'
        name_item.textChanged.connect(self._on_column_name_changed)

        # Si esta fila es 'id' desde el inicio, aplicar restricciones
        if name.strip().lower() == 'id':
            self._enforce_id_row(row)

    def _find_row_for_widget(self, widget) -> int:
        """Encontrar el índice de fila para un widget dentro de la tabla de columnas."""
        if widget is None:
            return -1
        for r in range(self.columns_table.rowCount()):
            if self.columns_table.cellWidget(r, 0) is widget:
                return r
        return -1

    def _on_column_name_changed(self, _text: str):
        """Cuando cambia el nombre de una columna, si es 'id' se aplica INTEGER+Req+PK+Auto y se bloquea edición."""
        sender = self.sender()
        row = self._find_row_for_widget(sender)
        if row < 0:
            return
        name_widget = self.columns_table.cellWidget(row, 0)
        name = name_widget.text().strip().lower() if isinstance(name_widget, QLineEdit) else ''
        if name == 'id':
            self._enforce_id_row(row)
        else:
            self._unset_id_row(row)

    def _enforce_id_row(self, row: int):
        """Configura la fila como 'id' fija: INTEGER + Requerido + PK + Auto y deshabilita edición de esos campos."""
        type_combo = self.columns_table.cellWidget(row, 1)
        req_chk = self.columns_table.cellWidget(row, 2)
        pk_chk = self.columns_table.cellWidget(row, 3)
        auto_chk = self.columns_table.cellWidget(row, 4)
        if isinstance(type_combo, QComboBox):
            type_combo.setCurrentText('INTEGER')
            type_combo.setDisabled(True)
        if isinstance(req_chk, QCheckBox):
            req_chk.setChecked(True)
            req_chk.setDisabled(True)
        if isinstance(pk_chk, QCheckBox):
            pk_chk.setChecked(True)
            pk_chk.setDisabled(True)
        if isinstance(auto_chk, QCheckBox):
            auto_chk.setChecked(True)
            auto_chk.setDisabled(True)

    def _unset_id_row(self, row: int):
        """Rehabilita edición de tipo/requerido/PK/Auto cuando la columna deja de ser 'id'."""
        type_combo = self.columns_table.cellWidget(row, 1)
        req_chk = self.columns_table.cellWidget(row, 2)
        pk_chk = self.columns_table.cellWidget(row, 3)
        auto_chk = self.columns_table.cellWidget(row, 4)
        if isinstance(type_combo, QComboBox):
            type_combo.setDisabled(False)
        if isinstance(req_chk, QCheckBox):
            req_chk.setDisabled(False)
        if isinstance(pk_chk, QCheckBox):
            pk_chk.setDisabled(False)
        if isinstance(auto_chk, QCheckBox):
            auto_chk.setDisabled(False)
    
    def _remove_column(self):
        """Eliminar columna seleccionada."""
        current_row = self.columns_table.currentRow()
        if current_row >= 0:
            # Verificar si es la columna ID
            name_widget = self.columns_table.cellWidget(current_row, 0)
            if (name_widget and isinstance(name_widget, QLineEdit) and 
                name_widget.text().lower() == 'id'):
                QMessageBox.warning(self, "Advertencia", "No se puede eliminar la columna ID.")
                return
            
            reply = QMessageBox.question(
                self, "Confirmar",
                "¿Está seguro de eliminar esta columna?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.columns_table.removeRow(current_row)
    
    def _load_data(self):
        """Cargar datos si estamos editando."""
        if not self.is_editing or not self.table_data:
            return
        
        # Cargar información básica
        self.name_edit.setText(self.table_data.get('display_name', ''))
        self.description_edit.setPlainText(self.table_data.get('description', ''))
        
        # Cargar esquema de columnas
        schema = self.table_data.get('schema', [])
        for column in schema:
            self._add_column_row(
                column.get('name', ''),
                column.get('type', 'TEXT'),
                column.get('required', False),
                column.get('primary_key', False),
                column.get('auto_increment', False),
                column.get('description', '')
            )
        # Reforzar reglas si existe una fila llamada 'id'
        for r in range(self.columns_table.rowCount()):
            name_widget = self.columns_table.cellWidget(r, 0)
            if isinstance(name_widget, QLineEdit) and name_widget.text().strip().lower() == 'id':
                self._enforce_id_row(r)
                break
    
    def _validate_data(self):
        """Validar los datos del formulario."""
        # Validar nombre de tabla
        table_name = self.name_edit.text().strip()
        if not table_name:
            QMessageBox.warning(self, "Validación", "El nombre de la tabla es requerido.")
            return False
        
        # Validar que haya al menos una columna
        if self.columns_table.rowCount() == 0:
            QMessageBox.warning(self, "Validación", "La tabla debe tener al menos una columna.")
            return False
        
        # Validar nombres de columnas y restricciones de ID/PK
        column_names = set()
        pk_count = 0
        auto_count = 0
        id_name_count = 0
        id_row_info = None
        for row in range(self.columns_table.rowCount()):
            name_widget = self.columns_table.cellWidget(row, 0)
            if not name_widget or not isinstance(name_widget, QLineEdit):
                continue
            
            name = name_widget.text().strip()
            if not name:
                QMessageBox.warning(self, "Validación", f"La columna en la fila {row + 1} debe tener un nombre.")
                return False
            
            if name in column_names:
                QMessageBox.warning(self, "Validación", f"El nombre de columna '{name}' está duplicado.")
                return False
            
            column_names.add(name)

            # Reglas de PK/Auto ID
            pk_widget = self.columns_table.cellWidget(row, 3)
            auto_widget = self.columns_table.cellWidget(row, 4)
            if isinstance(pk_widget, QCheckBox) and pk_widget.isChecked():
                pk_count += 1
            if isinstance(auto_widget, QCheckBox) and auto_widget.isChecked():
                auto_count += 1
            if name.lower() == 'id':
                id_name_count += 1
                id_row_info = {
                    'row': row,
                    'type_widget': self.columns_table.cellWidget(row, 1),
                    'required_widget': self.columns_table.cellWidget(row, 2),
                    'pk_widget': pk_widget,
                    'auto_widget': auto_widget,
                }
        
        if id_name_count > 1:
            QMessageBox.warning(self, "Validación", "Solo puede existir una columna llamada 'id'.")
            return False
        if pk_count > 1:
            QMessageBox.warning(self, "Validación", "Solo puede existir una única columna marcada como Clave Primaria.")
            return False
        if auto_count > 1:
            QMessageBox.warning(self, "Validación", "Solo puede existir una única columna con Auto ID.")
            return False

        # Si existe 'id', validar que sea INTEGER, requerida, PK y Auto ID
        if id_row_info is not None:
            type_ok = isinstance(id_row_info['type_widget'], QComboBox) and id_row_info['type_widget'].currentText() == 'INTEGER'
            req_ok = isinstance(id_row_info['required_widget'], QCheckBox) and id_row_info['required_widget'].isChecked()
            pk_ok = isinstance(id_row_info['pk_widget'], QCheckBox) and id_row_info['pk_widget'].isChecked()
            auto_ok = isinstance(id_row_info['auto_widget'], QCheckBox) and id_row_info['auto_widget'].isChecked()
            if not (type_ok and req_ok and pk_ok and auto_ok):
                QMessageBox.warning(
                    self,
                    "Validación",
                    "La columna 'id' debe ser de tipo INTEGER, requerida, Clave Primaria y Auto ID."
                )
                return False
        
        return True
    
    def _collect_schema(self) -> List[Dict[str, Any]]:
        """Recopilar el esquema de columnas."""
        schema = []
        
        # Obtener información de relaciones
        relation_info = None
        if self.enable_relations_cb.isChecked():
            parent_table = self.parent_table_combo.currentData()
            relation_column = self.relation_column_edit.text().strip()
            
            if parent_table and relation_column:
                relation_info = {
                    'parent_table_id': parent_table['id'],
                    'parent_table_name': parent_table['display_name'],
                    'column_name': relation_column
                }
        
        for row in range(self.columns_table.rowCount()):
            # Obtener widgets de la fila
            name_widget = self.columns_table.cellWidget(row, 0)
            type_widget = self.columns_table.cellWidget(row, 1)
            required_widget = self.columns_table.cellWidget(row, 2)
            pk_widget = self.columns_table.cellWidget(row, 3)
            auto_widget = self.columns_table.cellWidget(row, 4)
            desc_widget = self.columns_table.cellWidget(row, 5)
            
            if not name_widget or not isinstance(name_widget, QLineEdit):
                continue
            
            column_name = name_widget.text().strip()
            
            column = {
                'name': column_name,
                'type': type_widget.currentText() if isinstance(type_widget, QComboBox) else 'TEXT',
                'required': required_widget.isChecked() if isinstance(required_widget, QCheckBox) else False,
                'primary_key': pk_widget.isChecked() if isinstance(pk_widget, QCheckBox) else False,
                'auto_increment': auto_widget.isChecked() if isinstance(auto_widget, QCheckBox) else False,
                'description': desc_widget.text().strip() if isinstance(desc_widget, QLineEdit) else ''
            }
            
            # Marcar columna de relación si aplica
            if relation_info and column_name == relation_info['column_name']:
                column['is_foreign_key'] = True
                column['references_table'] = relation_info['parent_table_id']
                column['references_table_name'] = relation_info['parent_table_name']
            
            schema.append(column)
        
        return schema
    
    def accept(self):
        """Validar y guardar la tabla."""
        if not self._validate_data():
            return
        
        try:
            table_name = self.name_edit.text().strip()
            description = self.description_edit.toPlainText().strip()
            schema = self._collect_schema()
            
            with self.session_factory() as session:
                if self.is_editing and self.table_data:
                    # Actualizar tabla existente
                    # Determinar si el esquema ya incluye una columna id/PK
                    has_auto_id = not any(
                        (str(c.get('name', '')).strip().lower() == 'id' and (c.get('primary_key') or c.get('auto_increment'))) or c.get('primary_key')
                        for c in schema
                    )

                    update_product_parameter_table(
                        session, 
                        self.table_data['id'],
                        display_name=table_name,
                        description=description,
                        columns=schema,
                        has_auto_id=has_auto_id
                    )
                else:
                    # Crear nueva tabla
                    # Determinar si el esquema ya incluye una columna id/PK
                    has_auto_id = not any(
                        (str(c.get('name', '')).strip().lower() == 'id' and (c.get('primary_key') or c.get('auto_increment'))) or c.get('primary_key')
                        for c in schema
                    )

                    create_product_parameter_table(
                        session,
                        self.product_data['id'],
                        display_name=table_name,
                        description=description,
                        columns=schema,
                        has_auto_id=has_auto_id
                    )
                
                session.commit()
            
            super().accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar tabla: {str(e)}")