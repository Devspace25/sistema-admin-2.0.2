from __future__ import annotations

from typing import Dict, List, Any, Optional, Callable, ContextManager
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QMessageBox, QDialogButtonBox, QLabel, QFrame,
    QHeaderView, QGroupBox, QFormLayout, QTextEdit, QWidget
)
from PySide6.QtGui import QFont, QColor

from ..repository import (
    get_parameter_table_data, add_parameter_table_row,
    update_parameter_table_row, delete_parameter_table_row
)


class ParametrosValuesDialog(QDialog):
    """Diálogo para gestionar los valores de una tabla de parámetros."""
    
    def __init__(self, session_factory: Callable[[], ContextManager[Any]], table_data: Dict[str, Any], parent=None, auto_add_row: bool = False):
        super().__init__(parent)
        self.session_factory = session_factory
        self.table_data = table_data
        self.schema = []
        self.table_rows = []
        self.auto_add_row = auto_add_row
        self.has_pending_changes = False
        # Caché de opciones FK: {parent_table_id: {id: text}}
        self._fk_cache: Dict[int, Dict[int, str]] = {}
        
        self.setWindowTitle(f"Valores: {table_data['display_name']}")
        self.setMinimumSize(900, 600)
        
        self._parse_schema()
        self._setup_ui()
        self._load_data()
        
        # Si se requiere auto-agregar, abrir el diálogo después de cargar
        if self.auto_add_row:
            # Usar QTimer para que se ejecute después de que el diálogo esté visible
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._add_row)
    
    def _parse_schema(self):
        """Parsear el esquema JSON de la tabla."""
        try:
            # Preferir 'schema' ya parseado si está disponible
            parsed_schema = self.table_data.get('schema')
            if isinstance(parsed_schema, list):
                self.schema = parsed_schema
            else:
                # Compatibilidad: algunas rutas entregan 'schema_json'
                schema_json = self.table_data.get('schema_json', '[]')
                if isinstance(schema_json, str):
                    self.schema = json.loads(schema_json)
                elif isinstance(schema_json, list):
                    self.schema = schema_json
                else:
                    self.schema = []
            
            # Validar que el esquema tenga datos válidos
            if not self.schema:
                # Esquema por defecto si está vacío
                self.schema = [
                    {'name': 'id', 'type': 'INTEGER', 'primary_key': True, 'auto_increment': True},
                    {'name': 'nombre', 'type': 'TEXT', 'required': True},
                    {'name': 'descripcion', 'type': 'TEXT', 'required': False}
                ]

            # Normalización: tipos y duplicados de 'id'
            normalized: list[dict] = []
            seen_id = False
            for col in self.schema:
                name = str(col.get('name', '')).strip()
                ctype = col.get('type')
                # Tipo por defecto si falta o es vacío
                if not ctype:
                    ctype = 'TEXT'
                else:
                    ctype = str(ctype).upper()
                # Sinónimos comunes
                if ctype in ('VARCHAR', 'CHAR', 'STRING'):
                    ctype = 'TEXT'
                elif ctype in ('INT', 'BIGINT', 'SMALLINT'):
                    ctype = 'INTEGER'
                elif ctype in ('FLOAT', 'DOUBLE', 'DECIMAL', 'NUMERIC'):
                    ctype = 'REAL'
                elif ctype in ('BOOL',):
                    ctype = 'BOOLEAN'
                col['type'] = ctype

                # Deduplicar 'id'
                if name.lower() == 'id':
                    if seen_id:
                        # saltar duplicados de id
                        continue
                    seen_id = True
                    # Asegurar flags para id
                    col['type'] = 'INTEGER'
                    col['primary_key'] = True
                    col['auto_increment'] = True
                    col['required'] = True
                normalized.append(col)

            self.schema = normalized

            # Si después de normalizar solo queda ID (sin campos editables),
            # añadimos un campo 'nombre' por defecto para permitir edición básica.
            try:
                editable_cols = [
                    c for c in self.schema
                    if not c.get('primary_key')
                    and not c.get('auto_increment')
                    and str(c.get('name', '')).strip().lower() != 'id'
                ]
                if len(editable_cols) == 0:
                    self.schema.append({
                        'name': 'nombre',
                        'type': 'TEXT',
                        'required': True,
                        'description': 'Nombre del ítem'
                    })
            except Exception:
                # En caso de cualquier inconsistencia, aseguramos al menos 'nombre'
                self.schema.append({
                    'name': 'nombre',
                    'type': 'TEXT',
                    'required': True
                })

                
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            print(f"Error parseando esquema: {e}")
            # Esquema de emergencia
            self.schema = [
                {'name': 'id', 'type': 'INTEGER', 'primary_key': True, 'auto_increment': True},
                {'name': 'valor', 'type': 'TEXT', 'required': True}
            ]
    
    def _setup_ui(self):
        """Configurar la interfaz del diálogo."""
        layout = QVBoxLayout(self)

        # Información de la tabla
        info_group = QGroupBox("Información de la Tabla")
        info_layout = QFormLayout(info_group)

        name_label = QLabel(self.table_data['display_name'])
        name_font = QFont()
        name_font.setBold(True)
        name_label.setFont(name_font)
        info_layout.addRow("Nombre:", name_label)

        if self.table_data.get('description'):
            desc_label = QLabel(self.table_data['description'])
            desc_label.setWordWrap(True)
            info_layout.addRow("Descripción:", desc_label)

        layout.addWidget(info_group)

        # Botones de gestión
        buttons_layout = QHBoxLayout()
        self.add_row_btn = QPushButton("+ Agregar Fila")
        self.edit_row_btn = QPushButton("Editar Fila")
        self.delete_row_btn = QPushButton("- Eliminar Fila")
        self.refresh_btn = QPushButton("🔄 Actualizar")

        buttons_layout.addWidget(self.add_row_btn)
        buttons_layout.addWidget(self.edit_row_btn)
        buttons_layout.addWidget(self.delete_row_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.refresh_btn)

        layout.addLayout(buttons_layout)

        # Tabla de datos
        self.data_table = QTableWidget()
        self.data_table.setObjectName("ParamValuesTable")
        self._setup_table_columns()
        layout.addWidget(self.data_table)

        # Botones del diálogo
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Close
        )
        self.save_button = button_box.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText("Guardar Cambios")
        self.save_button.setEnabled(False)  # Inicialmente deshabilitado

        button_box.accepted.connect(self._save_changes)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Conectar eventos
        self.add_row_btn.clicked.connect(self._add_row)
        self.edit_row_btn.clicked.connect(self._edit_row)
        self.delete_row_btn.clicked.connect(self._delete_row)
        self.refresh_btn.clicked.connect(self._load_data)
        self.data_table.itemDoubleClicked.connect(self._edit_row)
        self.data_table.itemSelectionChanged.connect(self._update_buttons_state)

        self._update_buttons_state()
    
    def _setup_table_columns(self):
        """Configurar las columnas de la tabla según el esquema."""
        if not self.schema:
            return
        
        # Configurar número de columnas
        self.data_table.setColumnCount(len(self.schema))
        
        # Configurar headers con información clara
        headers = []
        def _norm(s: Any) -> str:
            return str(s or '').strip().lower().replace(' ', '_')

        for i, column in enumerate(self.schema):
            # Detectar FK por metadata o por relación definida en la tabla (comparación normalizada)
            is_fk = bool(column.get('is_foreign_key') or column.get('references_table') or column.get('foreign_key'))
            if not is_fk:
                rel_col = self.table_data.get('relationship_column')
                parent_id = self.table_data.get('parent_table_id')
                if rel_col and parent_id and _norm(column.get('name')) == _norm(rel_col):
                    is_fk = True
                    column['references_table'] = parent_id
                    column['references_table_name'] = self.table_data.get('parent_table_name')
            if is_fk:
                parent_name = column.get('references_table_name')
                header = f"Nombre {parent_name}".strip() if parent_name else "Nombre"
            else:
                header = column.get('name', f'col_{i}')
            
            # Agregar indicadores
            if column.get('required'):
                header += " *"
            if column.get('primary_key'):
                header = f"🔑 {header}"
                
            headers.append(header)
        
        self.data_table.setHorizontalHeaderLabels(headers)
        
        # Configurar comportamiento de la tabla
        self.data_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.data_table.setAlternatingRowColors(True)
        
        # Mostrar headers verticales y horizontales
        self.data_table.verticalHeader().setVisible(True)
        self.data_table.horizontalHeader().setVisible(True)
        
        # Ajustar ancho de columnas de forma más inteligente
        header = self.data_table.horizontalHeader()
        for i, column in enumerate(self.schema):
            if column.get('primary_key'):  # Columnas ID más pequeñas
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
            elif column.get('type') == 'TEXT' and not column.get('required'):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        
        print("✅ Tabla configurada correctamente")
    
    def _load_data(self):
        """Cargar datos de la tabla."""
        try:
            with self.session_factory() as session:
                self.table_rows = get_parameter_table_data(
                    session, self.table_data['id']
                )
            
            self._populate_table()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar datos: {str(e)}")
    
    def _populate_table(self):
        """Poblar la tabla con los datos."""
        if not self.schema:
            return
            
        self.data_table.setRowCount(len(self.table_rows))
        
        for row_idx, row_record in enumerate(self.table_rows):
            
            # Los datos pueden estar en 'data' o directamente en el registro
            if isinstance(row_record, dict) and 'data' in row_record:
                actual_data = row_record.get('data', {})
                record_id = row_record.get('id')
            else:
                actual_data = row_record
                record_id = row_record.get('id')
            
            for col_idx, column in enumerate(self.schema):
                column_name = column.get('name', '')
                
                # Determinar el valor a mostrar
                if column.get('primary_key') and column_name in ['id', 'ID']:
                    value = record_id or ''
                else:
                    value = self._get_value_from_data(actual_data, column_name)
                
                # Si es FK, mostrar el nombre en vez del ID
                # Detección con fallback por relación de tabla (normalizado)
                is_fk = bool(column.get('is_foreign_key') or column.get('references_table') or column.get('foreign_key'))
                if not is_fk:
                    rel_col = self.table_data.get('relationship_column')
                    parent_id = self.table_data.get('parent_table_id')
                    def _norm(s):
                        return str(s or '').strip().lower().replace(' ', '_')
                    if rel_col and parent_id and _norm(column_name) == _norm(rel_col):
                        is_fk = True
                        column['references_table'] = parent_id
                        column['references_table_name'] = self.table_data.get('parent_table_name')
                if is_fk:
                    parent_id = column.get('references_table') or column.get('foreign_key')
                    display_value = self._fk_text(parent_id, value)
                else:
                    display_value = str(value) if value is not None else ''
                item = QTableWidgetItem(display_value)
                
                # Configurar apariencia según el tipo de columna
                if column.get('primary_key') or column.get('auto_increment'):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    # Fondo oscuro para campos auto-generados (antes: lightGray)
                    item.setBackground(QColor("#2d2d2d"))
                    item.setToolTip("Campo auto-generado")
                elif column.get('required'):
                    # Fondo oscuro para campos requeridos (antes: white)
                    item.setBackground(QColor("#2d2d2d"))
                    item.setToolTip("Campo requerido")
                
                # Insertar el item en la celda correspondiente
                self.data_table.setItem(row_idx, col_idx, item)

        # Actualizar estado de botones después de poblar
        self._update_buttons_state()
    def _get_value_from_data(self, data: Dict[str, Any], column_name: str) -> Any:
        """Intentar obtener el valor probando variantes del nombre de columna para datos antiguos.
        Orden: exacto -> lower -> snake_case(lower)
        """
        if column_name in data:
            return data.get(column_name)
        lower = column_name.lower()
        if lower in data:
            return data.get(lower)
        snake = lower.replace(' ', '_')
        if snake in data:
            return data.get(snake)
        return ''
        
    def _fk_text(self, parent_table_id: Optional[int], value: Any) -> str:
        """Resolver nombre mostrado para un valor de FK usando caché y opciones del repositorio."""
        try:
            if parent_table_id is None:
                return str(value) if value is not None else ''
            mapping = self._get_fk_mapping(parent_table_id)
            if isinstance(value, int) and mapping and value in mapping:
                return mapping[value]
            return str(value) if value is not None else ''
        except Exception:
            return str(value) if value is not None else ''

    def _get_fk_mapping(self, parent_table_id: int) -> Dict[int, str]:
        """Obtener y cachear el mapeo id->texto para una tabla padre."""
        mapping = self._fk_cache.get(parent_table_id)
        if mapping is not None:
            return mapping
        if not callable(self.session_factory):
            return {}
        try:
            with self.session_factory() as session:
                from ..repository import get_parent_table_options
                options = get_parent_table_options(session, parent_table_id)
            mapping = {opt['id']: opt['text'] for opt in options}
            self._fk_cache[parent_table_id] = mapping
            return mapping
        except Exception:
            return {}

    
    def _update_buttons_state(self):
        """Actualizar estado de los botones según la selección."""
        has_selection = len(self.data_table.selectedItems()) > 0
        self.edit_row_btn.setEnabled(has_selection)
        self.delete_row_btn.setEnabled(has_selection)
    
    def _add_row(self):
        """Agregar nueva fila."""
        if not self.schema:
            QMessageBox.warning(
                self, "Error", 
                "No se puede agregar filas: la tabla no tiene esquema definido."
            )
            return
        
        dialog = RowEditDialog(self.schema, None, self, self.session_factory, fk_mapping_provider=self._get_fk_mapping)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                row_data = dialog.get_row_data()
                
                if not row_data:
                    QMessageBox.warning(self, "Sin Datos", "No hay datos para guardar.")
                    return
                
                with self.session_factory() as session:
                    add_parameter_table_row(
                        session, self.table_data['id'], row_data
                    )
                    session.commit()
                
                self._load_data()
                self._mark_changes()
                QMessageBox.information(self, "Éxito", "Fila agregada exitosamente.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al agregar fila: {str(e)}")
    
    def _edit_row(self):
        """Editar fila seleccionada."""
        current_row = self.data_table.currentRow()
        if current_row < 0 or current_row >= len(self.table_rows):
            QMessageBox.warning(self, "Selección", "Seleccione una fila para editar.")
            return
        
        row_record = self.table_rows[current_row]
        
        # Extraer los datos para editar
        if isinstance(row_record, dict) and 'data' in row_record:
            edit_data = row_record.get('data', {}).copy()
            if row_record.get('id'):
                edit_data['id'] = row_record['id']
        else:
            edit_data = row_record.copy() if row_record else {}
        
        dialog = RowEditDialog(self.schema, edit_data, self, self.session_factory, fk_mapping_provider=self._get_fk_mapping)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                new_data = dialog.get_row_data()
                row_id = edit_data.get('id')
                
                if not row_id:
                    QMessageBox.critical(self, "Error", "No se pudo identificar la fila.")
                    return
                
                with self.session_factory() as session:
                    update_parameter_table_row(session, row_id, new_data)
                    session.commit()
                
                self._load_data()
                self._mark_changes()
                QMessageBox.information(self, "Éxito", "Fila actualizada exitosamente.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al actualizar fila: {str(e)}")
    
    def _delete_row(self):
        """Eliminar fila seleccionada."""
        current_row = self.data_table.currentRow()
        if current_row < 0 or current_row >= len(self.table_rows):
            QMessageBox.warning(self, "Selección", "Seleccione una fila para eliminar.")
            return
        
        row_data = self.table_rows[current_row]
        row_id = row_data.get('id')
        
        if not row_id:
            QMessageBox.critical(self, "Error", "No se pudo identificar la fila.")
            return
        
        reply = QMessageBox.question(
            self, "Confirmar Eliminación",
            "¿Está seguro de eliminar esta fila?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with self.session_factory() as session:
                    delete_parameter_table_row(session, row_id)
                    session.commit()
                
                self._load_data()
                self._mark_changes()
                QMessageBox.information(self, "Éxito", "Fila eliminada exitosamente.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar fila: {str(e)}")
    
    def _mark_changes(self):
        """Marcar que hay cambios pendientes."""
        self.has_pending_changes = True
        self.save_button.setEnabled(True)
        self.setWindowTitle(f"Valores: {self.table_data['display_name']} *")
    
    def _save_changes(self):
        """Guardar todos los cambios pendientes."""
        if not self.has_pending_changes:
            QMessageBox.information(self, "Sin Cambios", "No hay cambios pendientes para guardar.")
            return
        
        try:
            # Recargar datos para asegurar que están actualizados
            self._load_data()
            
            self.has_pending_changes = False
            self.save_button.setEnabled(False)
            self.setWindowTitle(f"Valores: {self.table_data['display_name']}")
            
            QMessageBox.information(self, "Éxito", "Todos los cambios han sido guardados correctamente.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar cambios: {str(e)}")

    def closeEvent(self, event):
        """Manejar el cierre del diálogo con cambios pendientes."""
        if self.has_pending_changes:
            reply = QMessageBox.question(
                self, "Cambios Pendientes",
                "Hay cambios sin guardar. ¿Desea guardarlos antes de cerrar?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )
            
            if reply == QMessageBox.StandardButton.Save:
                self._save_changes()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:  # Cancel
                event.ignore()
        else:
            event.accept()


class RowEditDialog(QDialog):
    """Diálogo simplificado para editar filas de datos."""
    
    def __init__(self, schema: List[Dict], row_data: Optional[Dict] = None, parent=None, session_factory=None, fk_mapping_provider: Optional[Callable[[int], Dict[int, str]]] = None):
        super().__init__(parent)
        self.schema = schema or []
        self.row_data = row_data or {}
        self.session_factory = session_factory
        self.fk_mapping_provider = fk_mapping_provider
        self.field_widgets = {}
        
        is_editing = bool(row_data)
        self.setWindowTitle("Editar Fila" if is_editing else "Agregar Nueva Fila")
        self.setMinimumWidth(450)
        self.setMinimumHeight(300)
        

        
        self._setup_ui()
        self._load_values()
    
    def _setup_ui(self):
        """Configurar la interfaz del diálogo."""
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel("Complete los siguientes campos:")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Área de scroll para muchos campos
        scroll_area = QWidget()
        form_layout = QFormLayout(scroll_area)
        
        if not self.schema:
            error_label = QLabel("❌ Error: No hay esquema definido para esta tabla")
            error_label.setStyleSheet("color: red; font-weight: bold;")
            form_layout.addRow(error_label)
        else:
            # Crear campos para cada columna del esquema
            for i, column in enumerate(self.schema):
                field_widget = self._create_field_widget(column)
                if field_widget:
                    column_name = column.get('name', f'campo_{i}')
                    self.field_widgets[column_name] = field_widget
                    
                    # Crear etiqueta con información del campo
                    label_text = self._format_label(column)
                    form_layout.addRow(label_text, field_widget)
            # Si no se añadió ningún widget (por ejemplo, todos eran id/auto ocultos)
            if not self.field_widgets:
                # Ofrecer acción para añadir un campo 'nombre' si el esquema está vacío de editables
                container = QWidget()
                from PySide6.QtWidgets import QHBoxLayout, QPushButton
                hl = QHBoxLayout(container)
                hl.setContentsMargins(0,0,0,0)
                info = QLabel("No hay campos editables en esta tabla (solo ID).")
                info.setStyleSheet("color: #bbb;")
                add_btn = QPushButton("➕ Añadir campo 'nombre'")
                add_btn.setToolTip("Agrega un campo de texto básico 'nombre' al esquema para poder editar")
                def _add_default_field():
                    try:
                        self.schema.append({'name': 'nombre', 'type': 'TEXT', 'required': True})
                        # Reconstruir UI con el nuevo campo
                        for i in reversed(range(form_layout.rowCount())):
                            form_layout.removeRow(i)
                        self.field_widgets.clear()
                        # Recrear widgets
                        for i, column in enumerate(self.schema):
                            field_widget = self._create_field_widget(column)
                            if field_widget:
                                column_name = column.get('name', f'campo_{i}')
                                self.field_widgets[column_name] = field_widget
                                label_text = self._format_label(column)
                                form_layout.addRow(label_text, field_widget)
                    except Exception:
                        pass
                add_btn.clicked.connect(_add_default_field)
                hl.addWidget(info)
                hl.addStretch(1)
                hl.addWidget(add_btn)
                form_layout.addRow(container)
        
        layout.addWidget(scroll_area)
        
        # Botones
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def _format_label(self, column: Dict) -> str:
        """Crear etiqueta formateada para el campo."""
        # Para FK usar una etiqueta amigable "Nombre [Tabla]"
        is_fk = bool(column.get('is_foreign_key') or column.get('references_table') or column.get('foreign_key'))
        if is_fk:
            parent_name = column.get('references_table_name')
            base = f"Nombre {parent_name}".strip() if parent_name else "Nombre"
            label_parts = [base]
        else:
            name = column.get('name', 'Campo')
            label_parts = [name.capitalize()]
        
        if column.get('required'):
            label_parts.append("*")
        if column.get('primary_key'):
            label_parts.insert(0, "🔑")
        
        label = " ".join(label_parts)
        
        # Para FK no agregamos el tipo (INTEGER); para otros tipos sí
        if not is_fk:
            field_type = column.get('type', 'TEXT')
            if field_type != 'TEXT':
                label += f" ({field_type})"
            
        return label
    
    def _create_field_widget(self, column: Dict) -> Optional[QWidget]:
        """Crear widget apropiado para el tipo de columna."""
        column_type = column.get('type', 'TEXT').upper()
        column_name = column.get('name', '')
        # Detectar FK (compatibilidad) o por relación de la tabla (comparación normalizada)
        is_foreign_key = bool(column.get('is_foreign_key') or column.get('references_table') or column.get('foreign_key'))
        if not is_foreign_key:
            parent = self.parent() if hasattr(self, 'parent') else None
            rel_name = getattr(getattr(parent, 'table_data', {}), 'get', lambda *_: None)('relationship_column') if parent else None
            parent_id = getattr(getattr(parent, 'table_data', {}), 'get', lambda *_: None)('parent_table_id') if parent else None
            def _norm(s: Any) -> str:
                return str(s or '').strip().lower().replace(' ', '_')
            if rel_name and parent_id and _norm(column_name) == _norm(rel_name):
                is_foreign_key = True
                column['references_table'] = parent_id
                column['references_table_name'] = getattr(getattr(parent, 'table_data', {}), 'get', lambda *_: None)('parent_table_name') if parent else None

        # Heurística adicional: si el nombre del campo parece ser una FK por convención (id_xxx o xxx_id),
        # intentar resolver automáticamente contra tablas del mismo producto para mostrar ComboBox con nombres.
        if not is_foreign_key:
            try:
                base_name = None
                name_norm = str(column_name or '').strip().lower().replace(' ', '_')
                if name_norm.startswith('id_') and len(name_norm) > 3:
                    base_name = name_norm[3:]
                elif name_norm.endswith('_id') and len(name_norm) > 3:
                    base_name = name_norm[:-3]

                if base_name:
                    # Obtener product_id desde el nombre de la tabla actual: params_{product_id}_...
                    parent = self.parent() if hasattr(self, 'parent') else None
                    table_name = getattr(getattr(parent, 'table_data', {}), 'get', lambda *_: None)('table_name') if parent else None
                    import re
                    m = re.match(r'^params_(\d+)_', str(table_name or ''))
                    if m and callable(self.session_factory):
                        product_id = int(m.group(1))
                        from ..repository import get_product_parameter_tables
                        with self.session_factory() as s:
                            tables = get_product_parameter_tables(s, product_id)
                        # Índice por nombre normalizado (display_name)
                        def _n(x: str) -> str:
                            return str(x or '').strip().lower().replace(' ', '_')
                        match = None
                        for t in tables:
                            if _n(t.get('display_name', '')) == base_name:
                                match = t
                                break
                        # Si no coincide con display_name exacto, intentar contiene
                        if not match:
                            for t in tables:
                                if base_name in _n(t.get('display_name', '')):
                                    match = t
                                    break
                        if match and match.get('id'):
                            column['references_table'] = match['id']
                            column['references_table_name'] = match.get('display_name')
                            is_foreign_key = True
            except Exception:
                pass

        # No mostrar campos auto-generados (id/PK/auto_increment) en el formulario
        if column.get('primary_key') or column.get('auto_increment') or column_name.lower() == 'id':
            return None
        
        # Si es clave foránea, crear ComboBox con opciones de la tabla relacionada
        if is_foreign_key and (column.get('references_table') or column.get('foreign_key')):
            widget = self._create_foreign_key_widget(column)
        else:
            # Crear el widget según el tipo normal
            widget = None
            if column_type == 'BOOLEAN':
                widget = QCheckBox()
                widget.setText("Sí/No")
            elif column_type == 'INTEGER':
                widget = QSpinBox()
                widget.setRange(-999999, 999999)
                widget.setValue(0)
            elif column_type == 'REAL':
                widget = QDoubleSpinBox()
                widget.setRange(-999999.0, 999999.0)
                widget.setDecimals(2)
                widget.setValue(0.0)
            else:  # TEXT por defecto
                widget = QLineEdit()
                widget.setPlaceholderText(f"Ingrese {column_name.lower()}")
        
        if not widget:
            return None
            
        # Configurar comportamiento especial
        is_pk = column.get('primary_key', False)
        is_auto = column.get('auto_increment', False)
        is_editing = bool(self.row_data)

        if is_auto or (is_pk and is_editing):
            widget.setEnabled(False)
            widget.setToolTip("Este campo se genera automáticamente")
            if isinstance(widget, QLineEdit):
                widget.setStyleSheet("background-color: #2d2d2d; color: #e5e7eb;")
        elif column.get('required'):
            widget.setToolTip("Este campo es obligatorio")
            if isinstance(widget, QLineEdit):
                widget.setStyleSheet("border: 1px solid #ff9999;")
        
        return widget
    
    def _create_foreign_key_widget(self, column: Dict) -> QComboBox:
        """Crear ComboBox para clave foránea con opciones de la tabla relacionada."""
        combo = QComboBox()
        parent_name = column.get('references_table_name') or ''
        placeholder = f"-- Seleccionar {parent_name} --".strip()
        combo.addItem(placeholder if parent_name else "-- Seleccionar --", None)
        
        try:
            # Obtener datos de la tabla relacionada
            # Aceptar 'references_table' o 'foreign_key'
            referenced_table_id = column.get('references_table') or column.get('foreign_key')
            if referenced_table_id:
                mapping = {}
                if callable(self.fk_mapping_provider):
                    mapping = self.fk_mapping_provider(referenced_table_id)
                # Poblar combo con nombres y asociar id como data
                for fk_id, text in mapping.items():
                    combo.addItem(str(text), fk_id)
                    idx = combo.count() - 1
                    combo.setItemData(idx, f"ID: {fk_id}", Qt.ItemDataRole.ToolTipRole)
                        
        except Exception as e:
            print(f"Error cargando datos de relación: {e}")
            combo.addItem(f"Error cargando datos", None)
        
        return combo

    
    
    def _load_values(self):
        """Cargar valores existentes si estamos editando."""
        if not self.row_data:
            return
        
        for column_name, widget in self.field_widgets.items():
            value = self.row_data.get(column_name)
            if value is None:
                continue
            
            try:
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QComboBox):
                    # Buscar el valor en el ComboBox
                    index = widget.findData(value)
                    if index >= 0:
                        widget.setCurrentIndex(index)
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value))
                elif isinstance(widget, QSpinBox):
                    widget.setValue(int(value))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(value))
            except (ValueError, TypeError):
                pass
    
    def get_row_data(self) -> Dict[str, Any]:
        """Obtener los datos de la fila desde los widgets."""
        data = {}
        
        for column in self.schema:
            column_name = column.get('name', '')
            widget = self.field_widgets.get(column_name)
            
            if not widget or not widget.isEnabled():
                # Saltar campos deshabilitados (auto-increment, etc.)
                continue
            
            try:
                if isinstance(widget, QCheckBox):
                    data[column_name] = widget.isChecked()
                elif isinstance(widget, QComboBox):
                    data[column_name] = widget.currentData()
                elif isinstance(widget, QSpinBox):
                    data[column_name] = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    data[column_name] = widget.value()
                elif isinstance(widget, QLineEdit):
                    text = widget.text().strip()
                    data[column_name] = text if text else None
            except Exception:
                pass
        return data
    
    def accept(self):
        """Validar datos antes de aceptar."""
        # Validar campos requeridos
        for column in self.schema:
            if not column.get('required', False):
                continue
            
            column_name = column.get('name', '')
            widget = self.field_widgets.get(column_name)
            
            if not widget or not widget.isEnabled():
                continue
            
            # Verificar si el campo requerido está vacío
            is_empty = False
            if isinstance(widget, QLineEdit):
                is_empty = not widget.text().strip()
            elif isinstance(widget, QComboBox):
                is_empty = widget.currentData() is None
            elif isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                # Los spinbox siempre tienen valor, no pueden estar vacíos
                pass
            elif isinstance(widget, QCheckBox):
                # Los checkbox tampoco están "vacíos"
                pass
            
            if is_empty:
                QMessageBox.warning(
                    self, "Campo Requerido", 
                    f"El campo '{column_name}' es obligatorio."
                )
                widget.setFocus()
                return
        
        super().accept()