from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox,
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QStyle,
    QWidget, QComboBox
)
from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator


class ValidatedLineEdit(QWidget):
    """QLineEdit con validación y ayuda contextual."""
    def __init__(self, placeholder: str = "", helper_text: str = "", regex: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4) # Más espacio entre input y ayuda
        
        # Campo de entrada
        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.setMinimumHeight(35) # Altura más cómoda
        if regex:
            self.line_edit.setValidator(QRegularExpressionValidator(QRegularExpression(regex)))
        layout.addWidget(self.line_edit)
        
        # Texto de ayuda
        if helper_text:
            helper = QLabel(helper_text, self)
            # Color neutro legible en ambos temas (gris medio)
            helper.setStyleSheet("color: #888888; font-size: 11px; font-style: italic; margin-left: 2px;")
            layout.addWidget(helper)
            
    def text(self) -> str:
        return self.line_edit.text()
        
    def setText(self, text: str) -> None:
        self.line_edit.setText(text)


class CustomerDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cliente")
        self.resize(550, 520) # Un poco más alto
        self.setSizeGripEnabled(True)

        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(25) # Más aire entre secciones
        main_layout.setContentsMargins(30, 30, 30, 30) # Márgenes más amplios
        
        # Marco para datos personales
        personal_group = QWidget(self)
        personal_layout = QFormLayout(personal_group)
        personal_layout.setContentsMargins(0, 0, 0, 0)
        personal_layout.setSpacing(15)
        personal_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft) # Alinear etiquetas
        
        # Título de la sección
        title = QLabel("Datos Personales", personal_group)
        title.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        personal_layout.addRow(title)
        
        # Campos con ayuda
        self.first_name_edit = ValidatedLineEdit(
            placeholder="Ingrese nombre",
            helper_text="Campo requerido"
        )
        self.last_name_edit = ValidatedLineEdit(
            placeholder="Ingrese apellido",
            helper_text="Opcional"
        )
        
        # Documento con Tipo
        doc_layout = QHBoxLayout()
        doc_layout.setContentsMargins(0, 0, 0, 0)
        doc_layout.setSpacing(10)
        
        self.doc_type_combo = QComboBox()
        self.doc_type_combo.addItems(["V", "J", "E", "G", "P"])
        self.doc_type_combo.setFixedWidth(60)
        self.doc_type_combo.setMinimumHeight(35)
        self.doc_type_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.document_edit = ValidatedLineEdit(
            placeholder="Número",
            helper_text="Campo requerido"
        )
        
        doc_layout.addWidget(self.doc_type_combo)
        doc_layout.addWidget(self.document_edit)
        
        personal_layout.addRow("Nombre (*)", self.first_name_edit)
        personal_layout.addRow("Apellido", self.last_name_edit)
        personal_layout.addRow("C.I./RIF (*)", doc_layout)
        
        # Separador visual
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #e0e0e0; margin-top: 10px; margin-bottom: 10px;")
        
        # Marco para datos de contacto
        contact_group = QWidget(self)
        contact_layout = QFormLayout(contact_group)
        contact_layout.setContentsMargins(0, 0, 0, 0)
        contact_layout.setSpacing(15)
        contact_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Título de contacto
        contact_title = QLabel("Información de Contacto", contact_group)
        contact_title.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        contact_layout.addRow(contact_title)
        
        self.short_address_edit = ValidatedLineEdit(
            placeholder="Dirección resumida",
            helper_text="Ubicación principal del cliente"
        )
        
        # Teléfono con código de área
        phone_layout = QHBoxLayout()
        phone_layout.setContentsMargins(0, 0, 0, 0)
        phone_layout.setSpacing(10)
        
        self.phone_code_combo = QComboBox()
        self.phone_code_combo.addItems(["0412", "0414", "0424", "0416", "0426", "0212"])
        self.phone_code_combo.setEditable(True) # Permitir otros códigos si es necesario
        self.phone_code_combo.setFixedWidth(90)
        self.phone_code_combo.setMinimumHeight(35)
        self.phone_code_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.phone_edit = ValidatedLineEdit(
            placeholder="Número (ej. 1234567)",
            helper_text="Campo requerido",
            regex=r"^\d{7}$" # Validar 7 dígitos
        )
        
        phone_layout.addWidget(self.phone_code_combo)
        phone_layout.addWidget(self.phone_edit)
        
        self.email_edit = ValidatedLineEdit(
            placeholder="Correo electrónico",
            helper_text="Opcional"
        )
        
        contact_layout.addRow("Dirección", self.short_address_edit)
        contact_layout.addRow("Teléfono (*)", phone_layout)
        contact_layout.addRow("Email", self.email_edit)
        
        # Agregar grupos al layout principal
        main_layout.addWidget(personal_group)
        main_layout.addWidget(line) # Separador
        main_layout.addWidget(contact_group)
        main_layout.addStretch()
        
        # Botones de acción
        button_layout = QHBoxLayout()
        button_layout.addStretch() # Alinear a la derecha
        
        self.btn_cancel = QPushButton("Cancelar", self)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px 16px;
                color: #2c3e50;
            }
            QPushButton:hover { background-color: #eef2f7; }
        """)
        
        self.btn_ok = QPushButton("Guardar", self)
        self.btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        # Estilo verde moderno pero más limpio
        self.btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        
        button_layout.addWidget(self.btn_cancel)
        button_layout.addWidget(self.btn_ok)
        
        main_layout.addLayout(button_layout)
        
        # Conectar señales
        self.btn_ok.clicked.connect(self._on_accept)
        self.btn_cancel.clicked.connect(self.reject)

    def _on_accept(self) -> None:
        # Validar solo que los campos requeridos no estén vacíos
        first_name = self.first_name_edit.text().strip()
        document = self.document_edit.text().strip()
        phone = self.phone_edit.text().strip()
        
        errors = []
        
        if not first_name:
            errors.append("El nombre es obligatorio")
            
        if not document:
            errors.append("El documento de identidad es obligatorio")
            
        if not phone:
            errors.append("El teléfono es obligatorio")
            
        if errors:
            QMessageBox.warning(
                self,
                "Validación",
                "Por favor complete los campos requeridos:\n\n" + "\n".join(f"• {e}" for e in errors)
            )
            return
            
        self.accept()

    def get_data(self) -> dict:
        doc_number = self.document_edit.text().strip()
        doc_full = f"{self.doc_type_combo.currentText()}-{doc_number}" if doc_number else ""
        
        phone_number = self.phone_edit.text().strip()
        phone_full = f"{self.phone_code_combo.currentText()}-{phone_number}" if phone_number else ""
        
        return {
            "first_name": self.first_name_edit.text().strip(),
            "last_name": self.last_name_edit.text().strip() or None,
            "document": doc_full or None,
            "short_address": self.short_address_edit.text().strip() or None,
            "phone": phone_full or None,
            "email": self.email_edit.text().strip() or None,
        }

    def set_data(self, data: dict) -> None:
        self.first_name_edit.setText(data.get("first_name", "") or "")
        self.last_name_edit.setText(data.get("last_name", "") or "")
        
        doc = data.get("document", "") or ""
        if "-" in doc:
            parts = doc.split("-", 1)
            index = self.doc_type_combo.findText(parts[0])
            if index >= 0:
                self.doc_type_combo.setCurrentIndex(index)
            self.document_edit.setText(parts[1])
        else:
            self.document_edit.setText(doc)
            
        self.short_address_edit.setText(data.get("short_address", "") or "")
        
        phone = data.get("phone", "") or ""
        if "-" in phone:
            parts = phone.split("-", 1)
            index = self.phone_code_combo.findText(parts[0])
            if index >= 0:
                self.phone_code_combo.setCurrentIndex(index)
            else:
                self.phone_code_combo.setEditText(parts[0])
            self.phone_edit.setText(parts[1])
        else:
            self.phone_edit.setText(phone)
            
        self.email_edit.setText(data.get("email", "") or "")
