from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox,
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QStyle,
    QWidget
)
from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator


class ValidatedLineEdit(QWidget):
    """QLineEdit con validación y ayuda contextual."""
    def __init__(self, placeholder: str = "", helper_text: str = "", regex: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Campo de entrada
        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText(placeholder)
        if regex:
            self.line_edit.setValidator(QRegularExpressionValidator(QRegularExpression(regex)))
        layout.addWidget(self.line_edit)
        
        # Texto de ayuda
        if helper_text:
            helper = QLabel(helper_text, self)
            helper.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
            layout.addWidget(helper)
            
    def text(self) -> str:
        return self.line_edit.text()
        
    def setText(self, text: str) -> None:
        self.line_edit.setText(text)


class CustomerDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cliente")
        self.resize(600, 500)
        self.setSizeGripEnabled(True)

        # Layout principal
        main_layout = QVBoxLayout(self)
        
        # Marco para datos personales
        personal_group = QFrame(self)
        personal_group.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        personal_layout = QFormLayout(personal_group)
        personal_layout.setContentsMargins(12, 12, 12, 12)
        
        # Título de la sección
        title = QLabel("Datos Personales", personal_group)
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #333; margin-bottom: 8px;")
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
        self.document_edit = ValidatedLineEdit(
            placeholder="Documento de identidad o RIF",
            helper_text="Campo requerido"
        )
        
        personal_layout.addRow("Nombre (*)", self.first_name_edit)
        personal_layout.addRow("Apellido", self.last_name_edit)
        personal_layout.addRow("C.I./RIF (*)", self.document_edit)
        
        # Marco para datos de contacto
        contact_group = QFrame(self)
        contact_group.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        contact_layout = QFormLayout(contact_group)
        contact_layout.setContentsMargins(12, 12, 12, 12)
        
        # Título de contacto
        contact_title = QLabel("Información de Contacto", contact_group)
        contact_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #333; margin-bottom: 8px;")
        contact_layout.addRow(contact_title)
        
        self.short_address_edit = ValidatedLineEdit(
            placeholder="Dirección resumida",
            helper_text="Ubicación principal del cliente"
        )
        self.phone_edit = ValidatedLineEdit(
            placeholder="Número de teléfono",
            helper_text="Campo requerido"
        )
        self.email_edit = ValidatedLineEdit(
            placeholder="Correo electrónico",
            helper_text="Opcional"
        )
        
        contact_layout.addRow("Dirección", self.short_address_edit)
        contact_layout.addRow("Teléfono (*)", self.phone_edit)
        contact_layout.addRow("Email", self.email_edit)
        
        # Agregar grupos al layout principal
        main_layout.addWidget(personal_group)
        main_layout.addWidget(contact_group)
        
        # Botones de acción
        button_layout = QHBoxLayout()
        
        self.btn_ok = QPushButton("Guardar", self)
        self.btn_ok.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOkButton))
        self.btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.btn_cancel = QPushButton("Cancelar", self)
        self.btn_cancel.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
            }
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
        return {
            "first_name": self.first_name_edit.text().strip(),
            "last_name": self.last_name_edit.text().strip() or None,
            "document": self.document_edit.text().strip() or None,
            "short_address": self.short_address_edit.text().strip() or None,
            "phone": self.phone_edit.text().strip() or None,
            "email": self.email_edit.text().strip() or None,
        }

    def set_data(self, data: dict) -> None:
        self.first_name_edit.setText(data.get("first_name", "") or "")
        self.last_name_edit.setText(data.get("last_name", "") or "")
        self.document_edit.setText(data.get("document", "") or "")
        self.short_address_edit.setText(data.get("short_address", "") or "")
        self.phone_edit.setText(data.get("phone", "") or "")
        self.email_edit.setText(data.get("email", "") or "")
