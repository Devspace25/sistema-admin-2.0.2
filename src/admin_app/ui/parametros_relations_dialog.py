from __future__ import annotations

from typing import Dict, List, Any, Optional
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QComboBox, QLabel, QMessageBox, QDialogButtonBox, QGroupBox,
    QListWidget, QListWidgetItem, QFrame, QTextEdit
)
from PySide6.QtGui import QFont

from ..repository import get_product_parameter_tables


class ParametrosRelationsDialog(QDialog):
    """Diálogo para configurar relaciones entre tablas de parámetros."""
    
    def __init__(self, session_factory, product_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.product_data = product_data
        self.parameter_tables = []
        
        self.setWindowTitle("Configurar Relaciones entre Tablas")
        self.setMinimumSize(700, 500)
        
        self._setup_ui()
        self._load_tables()
    
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
        
        # Explicación
        explanation = QLabel(
            "Configure las relaciones entre tablas para establecer jerarquías y dependencias. "
            "Por ejemplo, una tabla 'Materiales' puede relacionarse con una tabla 'Espesores' "
            "para indicar qué espesores están disponibles para cada material."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(explanation)
        
        # Contenido principal
        main_layout = QHBoxLayout()
        
        # Panel izquierdo - Lista de tablas
        left_group = QGroupBox("Tablas Disponibles")
        left_layout = QVBoxLayout(left_group)
        
        self.tables_list = QListWidget()
        left_layout.addWidget(self.tables_list)
        
        main_layout.addWidget(left_group)
        
        # Panel derecho - Configuración de relación
        right_group = QGroupBox("Configurar Relación")
        right_layout = QVBoxLayout(right_group)
        
        # Formulario de relación
        form_layout = QFormLayout()
        
        self.parent_table_combo = QComboBox()
        self.parent_table_combo.addItem("-- Seleccionar tabla padre --", None)
        form_layout.addRow("Tabla Padre:", self.parent_table_combo)
        
        self.child_table_combo = QComboBox()
        self.child_table_combo.addItem("-- Seleccionar tabla hija --", None)
        form_layout.addRow("Tabla Hija:", self.child_table_combo)
        
        self.relationship_name_edit = QLineEdit()
        self.relationship_name_edit.setPlaceholderText("ej: material_id, categoria_id")
        form_layout.addRow("Nombre de Columna FK:", self.relationship_name_edit)
        
        right_layout.addLayout(form_layout)
        
        # Descripción de la relación
        self.relationship_desc = QTextEdit()
        self.relationship_desc.setMaximumHeight(80)
        self.relationship_desc.setPlaceholderText("Descripción opcional de la relación")
        right_layout.addWidget(QLabel("Descripción:"))
        right_layout.addWidget(self.relationship_desc)
        
        # Botones de acción
        buttons_layout = QHBoxLayout()
        self.create_relation_btn = QPushButton("Crear Relación")
        self.remove_relation_btn = QPushButton("Eliminar Relación")
        
        buttons_layout.addWidget(self.create_relation_btn)
        buttons_layout.addWidget(self.remove_relation_btn)
        buttons_layout.addStretch()
        
        right_layout.addLayout(buttons_layout)
        
        # Lista de relaciones existentes
        right_layout.addWidget(QLabel("Relaciones Existentes:"))
        self.relations_list = QListWidget()
        right_layout.addWidget(self.relations_list)
        
        main_layout.addWidget(right_group)
        
        layout.addLayout(main_layout)
        
        # Botones del diálogo
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Conectar eventos
        self.tables_list.itemSelectionChanged.connect(self._on_table_selected)
        self.parent_table_combo.currentTextChanged.connect(self._on_parent_changed)
        self.create_relation_btn.clicked.connect(self._create_relation)
        self.remove_relation_btn.clicked.connect(self._remove_relation)
    
    def _load_tables(self):
        """Cargar las tablas de parámetros disponibles."""
        try:
            with self.session_factory() as session:
                self.parameter_tables = get_product_parameter_tables(
                    session, self.product_data['id']
                )
                
                # Limpiar listas
                self.tables_list.clear()
                self.parent_table_combo.clear()
                self.child_table_combo.clear()
                
                # Agregar opción por defecto
                self.parent_table_combo.addItem("-- Seleccionar tabla padre --", None)
                self.child_table_combo.addItem("-- Seleccionar tabla hija --", None)
                
                # Llenar listas
                for table in self.parameter_tables:
                    # Lista de tablas
                    item = QListWidgetItem(table['display_name'])
                    item.setData(Qt.ItemDataRole.UserRole, table)
                    self.tables_list.addItem(item)
                    
                    # Combos de relaciones
                    self.parent_table_combo.addItem(table['display_name'], table)
                    self.child_table_combo.addItem(table['display_name'], table)
                
                self._load_existing_relations()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar tablas: {str(e)}")
    
    def _load_existing_relations(self):
        """Cargar relaciones existentes."""
        self.relations_list.clear()
        
        for table in self.parameter_tables:
            if table.get('parent_table_id'):
                # Encontrar tabla padre
                parent_table = None
                for t in self.parameter_tables:
                    if t['id'] == table['parent_table_id']:
                        parent_table = t
                        break
                
                if parent_table:
                    relation_text = (
                        f"{parent_table['display_name']} → {table['display_name']} "
                        f"(columna: {table.get('relationship_column', 'N/A')})"
                    )
                    item = QListWidgetItem(relation_text)
                    item.setData(Qt.ItemDataRole.UserRole, table)
                    self.relations_list.addItem(item)
    
    def _on_table_selected(self):
        """Manejar selección de tabla."""
        current_item = self.tables_list.currentItem()
        if current_item:
            table_data = current_item.data(Qt.ItemDataRole.UserRole)
            # Aquí podrías mostrar detalles de la tabla seleccionada
    
    def _on_parent_changed(self):
        """Manejar cambio en tabla padre."""
        # Auto-generar nombre de columna FK basado en tabla padre
        parent_data = self.parent_table_combo.currentData()
        if parent_data:
            base_name = parent_data['display_name'].lower().replace(' ', '_')
            self.relationship_name_edit.setText(f"{base_name}_id")
    
    def _create_relation(self):
        """Crear nueva relación."""
        parent_data = self.parent_table_combo.currentData()
        child_data = self.child_table_combo.currentData()
        fk_column = self.relationship_name_edit.text().strip()
        
        if not parent_data:
            QMessageBox.warning(self, "Validación", "Seleccione una tabla padre.")
            return
        
        if not child_data:
            QMessageBox.warning(self, "Validación", "Seleccione una tabla hija.")
            return
        
        if not fk_column:
            QMessageBox.warning(self, "Validación", "Ingrese el nombre de la columna de clave foránea.")
            return
        
        if parent_data['id'] == child_data['id']:
            QMessageBox.warning(self, "Validación", "Una tabla no puede relacionarse consigo misma.")
            return
        
        # Verificar si ya existe una relación
        if child_data.get('parent_table_id'):
            reply = QMessageBox.question(
                self, "Relación Existente",
                f"La tabla '{child_data['display_name']}' ya tiene una relación padre. "
                "¿Desea reemplazarla?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            # Aquí implementarías la lógica para establecer la relación
            # Por ahora, simular la creación
            QMessageBox.information(
                self, "Relación Creada",
                f"Relación creada exitosamente:\n"
                f"{parent_data['display_name']} → {child_data['display_name']}\n"
                f"Columna FK: {fk_column}"
            )
            
            # Recargar tablas y relaciones
            self._load_tables()
            
            # Limpiar formulario
            self.parent_table_combo.setCurrentIndex(0)
            self.child_table_combo.setCurrentIndex(0)
            self.relationship_name_edit.clear()
            self.relationship_desc.clear()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al crear relación: {str(e)}")
    
    def _remove_relation(self):
        """Eliminar relación seleccionada."""
        current_item = self.relations_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Selección", "Seleccione una relación para eliminar.")
            return
        
        table_data = current_item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, "Confirmar Eliminación",
            f"¿Está seguro de eliminar la relación de la tabla '{table_data['display_name']}'?\n"
            "Esto eliminará la columna de clave foránea y todos los datos relacionados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Aquí implementarías la lógica para eliminar la relación
                QMessageBox.information(
                    self, "Relación Eliminada",
                    f"Relación eliminada de la tabla '{table_data['display_name']}'."
                )
                
                # Recargar
                self._load_tables()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar relación: {str(e)}")