from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QLabel, QFrame, QGroupBox,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QScrollArea, QGridLayout,
    QSplitter, QListWidget, QListWidgetItem, QTextEdit, QToolButton
)
from PySide6.QtGui import QFont, QIcon
from sqlalchemy.orm import sessionmaker


class UserDialog(QDialog):
    """Diálogo para crear/editar usuarios."""
    
    def __init__(self, session_factory, parent=None, user_data=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.user_data = user_data
        self.is_editing = user_data is not None
        
        self.setWindowTitle("Editar Usuario" if self.is_editing else "Crear Usuario")
        self.setMinimumSize(400, 350)
        
        layout = QVBoxLayout(self)
        
        # Formulario
        form = QFormLayout()
        
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("ej: jperez")
        form.addRow("Usuario:", self.username_edit)
        
        self.fullname_edit = QLineEdit()
        self.fullname_edit.setPlaceholderText("ej: Juan Pérez")
        form.addRow("Nombre Completo:", self.fullname_edit)
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Contraseña")
        form.addRow("Contraseña:", self.password_edit)
        
        self.confirm_password_edit = QLineEdit()
        self.confirm_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_edit.setPlaceholderText("Confirmar contraseña")
        form.addRow("Confirmar:", self.confirm_password_edit)
        
        # Roles disponibles
        roles_group = QGroupBox("Roles")
        roles_layout = QVBoxLayout(roles_group)
        
        self.roles_area = QScrollArea()
        self.roles_widget = QWidget()
        self.roles_layout = QVBoxLayout(self.roles_widget)
        self.roles_area.setWidget(self.roles_widget)
        self.roles_area.setWidgetResizable(True)
        self.roles_area.setMaximumHeight(100)
        
        self.role_checkboxes = {}
        self._load_roles()
        
        roles_layout.addWidget(self.roles_area)
        
        # Estado activo
        self.active_checkbox = QCheckBox("Usuario Activo")
        self.active_checkbox.setChecked(True)
        
        layout.addLayout(form)
        layout.addWidget(roles_group)
        layout.addWidget(self.active_checkbox)
        
        # Botones
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout.addWidget(buttons)
        
        # Cargar datos si estamos editando
        if self.is_editing:
            self._load_user_data()
    
    def _load_roles(self):
        """Cargar roles disponibles."""
        try:
            from ..repository import list_roles
            with self.session_factory() as session:
                roles = list_roles(session)
                
                for role in roles:
                    checkbox = QCheckBox(f"{role.name}")
                    if role.description:
                        checkbox.setToolTip(role.description)
                    self.role_checkboxes[role.id] = checkbox
                    self.roles_layout.addWidget(checkbox)
                    
        except Exception as e:
            print(f"Error cargando roles: {e}")
    
    def _load_user_data(self):
        """Cargar datos del usuario para edición."""
        if not self.user_data:
            return
            
        self.username_edit.setText(self.user_data.get('username', ''))
        self.fullname_edit.setText(self.user_data.get('full_name', ''))
        
        # En edición, la contraseña es opcional
        self.password_edit.setPlaceholderText("Dejar vacío para mantener actual")
        self.confirm_password_edit.setPlaceholderText("Dejar vacío para mantener actual")
        
        # Cargar roles del usuario
        try:
            from ..repository import get_user_roles
            with self.session_factory() as session:
                user_roles = get_user_roles(session, self.user_data['id'])
                user_role_ids = [role.id for role in user_roles]
                
                for role_id, checkbox in self.role_checkboxes.items():
                    checkbox.setChecked(role_id in user_role_ids)
                    
        except Exception as e:
            print(f"Error cargando roles del usuario: {e}")
    
    def get_form_data(self):
        """Obtener datos del formulario."""
        return {
            'username': self.username_edit.text().strip(),
            'full_name': self.fullname_edit.text().strip(),
            'password': self.password_edit.text().strip(),
            'confirm_password': self.confirm_password_edit.text().strip(),
            'active': self.active_checkbox.isChecked(),
            'role_ids': [role_id for role_id, checkbox in self.role_checkboxes.items() if checkbox.isChecked()]
        }
    
    def validate_form(self):
        """Validar los datos del formulario."""
        data = self.get_form_data()
        
        if not data['username']:
            QMessageBox.warning(self, "Error", "El nombre de usuario es requerido.")
            return False
            
        if not data['full_name']:
            QMessageBox.warning(self, "Error", "El nombre completo es requerido.")
            return False
        
        # Validar contraseña solo si no estamos editando o si se proporcionó una nueva
        if not self.is_editing or data['password']:
            if len(data['password']) < 4:
                QMessageBox.warning(self, "Error", "La contraseña debe tener al menos 4 caracteres.")
                return False
                
            if data['password'] != data['confirm_password']:
                QMessageBox.warning(self, "Error", "Las contraseñas no coinciden.")
                return False
        
        if not data['role_ids']:
            QMessageBox.warning(self, "Error", "Debe asignar al menos un rol al usuario.")
            return False
            
        return True
    
    def accept(self):
        if self.validate_form():
            super().accept()


class RolePermissionsDialog(QDialog):
    """Diálogo para gestionar permisos de roles."""
    
    def __init__(self, session_factory, parent=None, role_data=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.role_data = role_data
        
        self.setWindowTitle(f"Permisos del Rol: {role_data['name'] if role_data else 'Nuevo'}")
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Información del rol
        if role_data:
            info_label = QLabel(f"Configurando permisos para: <b>{role_data['name']}</b>")
            info_label.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 4px;")
            layout.addWidget(info_label)
        
        # Lista de permisos
        perms_group = QGroupBox("Permisos Disponibles")
        perms_layout = QVBoxLayout(perms_group)
        
        self.permissions_area = QScrollArea()
        self.permissions_widget = QWidget()
        self.permissions_layout = QVBoxLayout(self.permissions_widget)
        self.permissions_area.setWidget(self.permissions_widget)
        self.permissions_area.setWidgetResizable(True)
        
        self.permission_checkboxes = {}
        self._load_permissions()
        
        perms_layout.addWidget(self.permissions_area)
        layout.addWidget(perms_group)
        
        # Botones
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout.addWidget(buttons)
        
        # Cargar permisos actuales del rol
        if role_data:
            self._load_role_permissions()
    
    def _load_permissions(self):
        """Cargar todos los permisos disponibles."""
        try:
            from ..repository import list_permissions
            with self.session_factory() as session:
                permissions = list_permissions(session)
                
                for perm in permissions:
                    checkbox = QCheckBox(f"{perm.code}")
                    if perm.description:
                        checkbox.setToolTip(perm.description)
                    self.permission_checkboxes[perm.id] = checkbox
                    self.permissions_layout.addWidget(checkbox)
                    
        except Exception as e:
            print(f"Error cargando permisos: {e}")
    
    def _load_role_permissions(self):
        """Cargar permisos actuales del rol."""
        if not self.role_data:
            return
            
        try:
            from ..repository import get_role_permissions
            with self.session_factory() as session:
                role_perms = get_role_permissions(session, self.role_data['id'])
                role_perm_ids = [perm.id for perm in role_perms]
                
                for perm_id, checkbox in self.permission_checkboxes.items():
                    checkbox.setChecked(perm_id in role_perm_ids)
                    
        except Exception as e:
            print(f"Error cargando permisos del rol: {e}")
    
    def get_selected_permissions(self):
        """Obtener permisos seleccionados."""
        return [perm_id for perm_id, checkbox in self.permission_checkboxes.items() if checkbox.isChecked()]


class EnhancedListTab(QWidget):
    """Pestaña de lista mejorada con mejor UI."""
    
    def __init__(self, parent=None, *, headers: list[str], title: str = "") -> None:
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Título y barra de herramientas
        if title:
            title_label = QLabel(title)
            title_label.setFont(QFont("", 12, QFont.Weight.Bold))
            title_label.setStyleSheet("color: #333; margin-bottom: 10px;")
            layout.addWidget(title_label)
        
        # Tabla
        self.table = QTableWidget(0, len(headers), self)
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        
        # Configurar columnas
        header = self.table.horizontalHeader()
        for i in range(len(headers)):
            if i == len(headers) - 1:  # Última columna se estira
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.table)
        
        # Barra de botones
        button_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("➕ Agregar")
        self.btn_edit = QPushButton("✏️ Editar") 
        self.btn_del = QPushButton("🗑️ Eliminar")
        self.btn_refresh = QPushButton("🔄 Actualizar")
        
        # Estilos de botones mejorados para mayor legibilidad
        button_style = """
            QPushButton {
                padding: 10px 16px;
                margin: 3px;
                border: 2px solid #007bff;
                border-radius: 6px;
                background-color: #ffffff;
                color: #007bff;
                font-weight: bold;
                font-size: 13px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #007bff;
                color: #ffffff;
                border-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #0056b3;
                border-color: #004085;
            }
            QPushButton:disabled {
                background-color: #f8f9fa;
                color: #6c757d;
                border-color: #dee2e6;
            }
        """
        
        # Estilo para botón de agregar (verde)
        add_style = """
            QPushButton {
                padding: 10px 16px;
                margin: 3px;
                border: 2px solid #28a745;
                border-radius: 6px;
                background-color: #ffffff;
                color: #28a745;
                font-weight: bold;
                font-size: 13px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #28a745;
                color: #ffffff;
                border-color: #1e7e34;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
                border-color: #155724;
            }
        """
        
        # Estilo para botón de eliminar (rojo)
        del_style = """
            QPushButton {
                padding: 10px 16px;
                margin: 3px;
                border: 2px solid #dc3545;
                border-radius: 6px;
                background-color: #ffffff;
                color: #dc3545;
                font-weight: bold;
                font-size: 13px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #dc3545;
                color: #ffffff;
                border-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #c82333;
                border-color: #bd2130;
            }
            QPushButton:disabled {
                background-color: #f8f9fa;
                color: #6c757d;
                border-color: #dee2e6;
            }
        """
        
        # Aplicar estilos específicos
        self.btn_add.setStyleSheet(add_style)
        self.btn_edit.setStyleSheet(button_style) 
        self.btn_del.setStyleSheet(del_style)
        self.btn_refresh.setStyleSheet(button_style)
        
        button_layout.addWidget(self.btn_add)
        button_layout.addWidget(self.btn_edit)
        button_layout.addWidget(self.btn_del)
        button_layout.addWidget(self.btn_refresh)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # Estado inicial de botones
        self.btn_edit.setEnabled(False)
        self.btn_del.setEnabled(False)
        
        # Conectar selección de tabla
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
    
    def _on_selection_changed(self):
        """Manejar cambios en la selección de la tabla."""
        has_selection = len(self.table.selectedItems()) > 0
        self.btn_edit.setEnabled(has_selection)
        self.btn_del.setEnabled(has_selection)
    
    def get_selected_row_data(self):
        """Obtener datos de la fila seleccionada."""
        row = self.table.currentRow()
        if row < 0:
            return None
            
        data = {}
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            header_item = self.table.horizontalHeaderItem(col)
            header = header_item.text() if header_item else f"Col_{col}"
            data[header] = item.text() if item else ""
            
        return data


class ConfigView(QWidget):
    def __init__(self, session_factory: sessionmaker, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Título principal
        title = QLabel("⚙️ Configuración del Sistema")
        title.setFont(QFont("", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #333; margin: 10px; padding: 10px;")
        layout.addWidget(title)
        
        # Pestañas
        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        
        # Pestañas mejoradas
        self.users_tab = EnhancedListTab(
            self, 
            headers=["ID", "Usuario", "Nombre Completo", "Roles", "Estado"], 
            title="Gestión de Usuarios"
        )
        self.roles_tab = EnhancedListTab(
            self, 
            headers=["ID", "Nombre", "Descripción", "Usuarios", "Permisos"], 
            title="Gestión de Roles"
        )
        self.perms_tab = EnhancedListTab(
            self, 
            headers=["ID", "Código", "Descripción", "Roles Asignados"], 
            title="Gestión de Permisos"
        )
        self.system_tab = self._create_system_config_tab()
        
        self.tabs.addTab(self.users_tab, "👥 Usuarios")
        self.tabs.addTab(self.roles_tab, "🏷️ Roles") 
        self.tabs.addTab(self.perms_tab, "🔑 Permisos")
        self.tabs.addTab(self.system_tab, "⚙️ Sistema")
        
        layout.addWidget(self.tabs)
        self._wire_events()
        
        # Conectar evento de cambio de pestaña
        self.tabs.currentChanged.connect(self._on_tab_changed)
        
        # Auto-refresh cada 30 segundos
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.reload_current_tab)
        self.refresh_timer.start(30000)
        
        self.reload()
    
    def _create_system_config_tab(self):
        """Crear pestaña de configuración del sistema."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Título
        title = QLabel("Configuración General del Sistema")
        title.setFont(QFont("", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Configuraciones
        config_group = QGroupBox("Parámetros del Sistema")
        config_layout = QFormLayout(config_group)
        
        self.sales_goal_spin = QDoubleSpinBox()
        self.sales_goal_spin.setRange(0, 999999)
        self.sales_goal_spin.setSuffix(" USD")
        self.sales_goal_spin.setDecimals(2)
        config_layout.addRow("Meta Mensual de Ventas:", self.sales_goal_spin)
        
        self.company_name_edit = QLineEdit()
        config_layout.addRow("Nombre de la Empresa:", self.company_name_edit)
        
        # Tasa Corpóreo - multiplicador para productos corpóreos
        self.tasa_corporeo_spin = QDoubleSpinBox()
        self.tasa_corporeo_spin.setRange(0.01, 99999.99)
        self.tasa_corporeo_spin.setValue(1.0)
        self.tasa_corporeo_spin.setDecimals(2)
        self.tasa_corporeo_spin.setSingleStep(0.01)
        self.tasa_corporeo_spin.setGroupSeparatorShown(True)
        # Configurar locale para separador de miles
        from PySide6.QtCore import QLocale
        locale = QLocale(QLocale.Language.Spanish, QLocale.Country.Venezuela)
        self.tasa_corporeo_spin.setLocale(locale)
        self.tasa_corporeo_spin.setToolTip("Multiplicador aplicado al subtotal de productos corpóreos antes de dividir por tasa BCV")
        config_layout.addRow("Tasa Corpóreo:", self.tasa_corporeo_spin)
        
        # Botón para guardar configuraciones
        save_btn = QPushButton("💾 Guardar Configuraciones")
        save_btn.clicked.connect(self._save_system_config)
        save_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)

        # Botón para probar conexión a BD
        test_btn = QPushButton("🧪 Probar conexión a Base de Datos")
        test_btn.clicked.connect(self._test_db_connection)

        layout.addWidget(config_group)
        layout.addWidget(test_btn)
        layout.addWidget(save_btn)
        layout.addStretch()
        
        # Cargar configuraciones actuales
        self._load_system_config()
        
        return widget

    def _test_db_connection(self):
        """Probar la conexión a la base de datos actual y mostrar resultado."""
        try:
            from ..db import make_engine, test_connection
            info = test_connection()
            if info.get("ok"):
                elapsed = info.get("elapsed_ms") or 0.0
                QMessageBox.information(
                    self,
                    "Conexión exitosa",
                    f"Se conectó correctamente a la base de datos.\n\n"
                    f"Backend: {info.get('backend')}\n"
                    f"URL: {info.get('url')}\n"
                    f"Latencia: {elapsed:.1f} ms"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Conexión fallida",
                    f"No fue posible conectar a la base de datos.\n\n"
                    f"Backend: {info.get('backend')}\n"
                    f"URL: {info.get('url')}\n"
                    f"Error: {info.get('error')}"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al probar conexión: {str(e)}")
    
    def _wire_events(self) -> None:
        """Conectar eventos de las pestañas."""
        # Usuarios
        self.users_tab.btn_add.clicked.connect(self._on_add_user)
        self.users_tab.btn_edit.clicked.connect(self._on_edit_user)
        self.users_tab.btn_del.clicked.connect(self._on_del_user)
        self.users_tab.btn_refresh.clicked.connect(self._refresh_users_manually)
        
        # Roles
        self.roles_tab.btn_add.clicked.connect(self._on_add_role)
        self.roles_tab.btn_edit.clicked.connect(self._on_edit_role)
        self.roles_tab.btn_del.clicked.connect(self._on_del_role)
        self.roles_tab.btn_refresh.clicked.connect(self._refresh_roles_manually)
        
        # Permisos
        self.perms_tab.btn_add.clicked.connect(self._on_add_perm)
        self.perms_tab.btn_edit.clicked.connect(self._on_edit_perm)
        self.perms_tab.btn_del.clicked.connect(self._on_del_perm)
        self.perms_tab.btn_refresh.clicked.connect(self._refresh_permissions_manually)
    
    def reload_current_tab(self):
        """Recargar la pestaña actual."""
        current_index = self.tabs.currentIndex()
        if current_index == 0:
            self._reload_users()
        elif current_index == 1:
            self._reload_roles()
        elif current_index == 2:
            self._reload_permissions()
        elif current_index == 3:
            self._load_system_config()
    
    def _on_tab_changed(self, index):
        """Se ejecuta cuando se cambia de pestaña."""
        print(f"Cambiando a pestaña {index}")  # Debug
        # Actualizar la pestaña activa
        if index == 0:
            self._reload_users()
        elif index == 1:
            self._reload_roles()
        elif index == 2:
            self._reload_permissions()
        elif index == 3:
            self._load_system_config()
    
    def _refresh_users_manually(self):
        """Actualizar usuarios manualmente con feedback visual."""
        print("Actualizando usuarios manualmente...")  # Debug
        self._reload_users()
        
        # Opcional: feedback visual simple
        self.users_tab.btn_refresh.setText("🔄 Actualizado")
        QTimer.singleShot(1500, lambda: self.users_tab.btn_refresh.setText("🔄 Actualizar"))
    
    def _refresh_roles_manually(self):
        """Actualizar roles manualmente con feedback visual."""
        print("Actualizando roles manualmente...")  # Debug
        self._reload_roles()
        
        # Feedback visual
        self.roles_tab.btn_refresh.setText("🔄 Actualizado")
        QTimer.singleShot(1500, lambda: self.roles_tab.btn_refresh.setText("🔄 Actualizar"))
    
    def _refresh_permissions_manually(self):
        """Actualizar permisos manualmente con feedback visual."""
        print("Actualizando permisos manualmente...")  # Debug
        self._reload_permissions()
        
        # Feedback visual
        self.perms_tab.btn_refresh.setText("🔄 Actualizado")
        QTimer.singleShot(1500, lambda: self.perms_tab.btn_refresh.setText("🔄 Actualizar"))
    
    def _load_system_config(self):
        """Cargar configuraciones del sistema."""
        try:
            from ..repository import get_monthly_sales_goal, get_system_config
            with self._session_factory() as session:
                # Meta de ventas
                goal = get_monthly_sales_goal(session)
                self.sales_goal_spin.setValue(goal)
                
                # Nombre de empresa
                company_name = get_system_config(session, "company_name", "Mi Empresa")
                self.company_name_edit.setText(company_name)
                
                # Tasa Corpóreo
                tasa_corporeo = float(get_system_config(session, "tasa_corporeo", "1.0"))
                self.tasa_corporeo_spin.setValue(tasa_corporeo)
                
        except Exception as e:
            print(f"Error cargando configuración del sistema: {e}")
    
    def _save_system_config(self):
        """Guardar configuraciones del sistema."""
        try:
            from ..repository import set_monthly_sales_goal, set_system_config
            with self._session_factory() as session:
                # Guardar meta de ventas
                set_monthly_sales_goal(session, self.sales_goal_spin.value())
                
                # Guardar nombre de empresa
                set_system_config(session, "company_name", self.company_name_edit.text().strip())
                
                # Guardar tasa corpóreo
                set_system_config(session, "tasa_corporeo", str(self.tasa_corporeo_spin.value()))
                
                session.commit()
                
            QMessageBox.information(self, "Éxito", "Configuraciones guardadas correctamente.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error guardando configuraciones: {str(e)}")
    
    # Métodos para usuarios
    def _on_add_user(self):
        """Agregar nuevo usuario."""
        dialog = UserDialog(self._session_factory, self)
        if dialog.exec():
            data = dialog.get_form_data()
            try:
                from ..repository import create_user, assign_user_roles
                with self._session_factory() as session:
                    # Crear usuario
                    user = create_user(
                        session,
                        username=data['username'],
                        password=data['password'],
                        full_name=data['full_name']
                    )
                    
                    # Asignar roles
                    assign_user_roles(session, user.id, data['role_ids'])
                    
                    session.commit()
                    
                print(f"Usuario creado: {user.username} con ID: {user.id}")  # Debug
                
                # Actualizar inmediatamente la vista
                self._reload_users()
                
                # Mostrar mensaje de éxito después de actualizar
                QMessageBox.information(self, "Éxito", f"Usuario '{data['username']}' creado correctamente.")
                
            except Exception as e:
                print(f"Error creando usuario: {e}")  # Debug  
                QMessageBox.critical(self, "Error", f"Error creando usuario: {str(e)}")
    
    def _on_edit_user(self):
        """Editar usuario seleccionado."""
        data = self.users_tab.get_selected_row_data()
        if not data:
            QMessageBox.warning(self, "Advertencia", "Seleccione un usuario para editar.")
            return
            
        user_data = {'id': int(data['ID']), 'username': data['Usuario'], 'full_name': data['Nombre Completo']}
        dialog = UserDialog(self._session_factory, self, user_data)
        
        if dialog.exec():
            form_data = dialog.get_form_data()
            try:
                from ..repository import update_user, assign_user_roles
                with self._session_factory() as session:
                    # Actualizar usuario
                    update_data = {
                        'full_name': form_data['full_name']
                    }
                    if form_data['password']:  # Solo actualizar contraseña si se proporcionó
                        update_data['password'] = form_data['password']
                        
                    update_user(session, user_id=user_data['id'], **update_data)
                    
                    # Actualizar roles
                    assign_user_roles(session, user_data['id'], form_data['role_ids'])
                    
                    session.commit()
                    
                QMessageBox.information(self, "Éxito", "Usuario actualizado correctamente.")
                self._reload_users()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error actualizando usuario: {str(e)}")
    
    def _on_del_user(self):
        """Eliminar usuario seleccionado.""" 
        data = self.users_tab.get_selected_row_data()
        if not data:
            QMessageBox.warning(self, "Advertencia", "Seleccione un usuario para eliminar.")
            return
            
        username = data['Usuario']
        if username.lower() == 'admin':
            QMessageBox.critical(self, "Error", "No se puede eliminar el usuario administrador.")
            return
            
        reply = QMessageBox.question(
            self, "Confirmar", 
            f"¿Está seguro de que desea eliminar el usuario '{username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from ..repository import delete_user
                with self._session_factory() as session:
                    delete_user(session, user_id=int(data['ID']))
                    session.commit()
                    
                QMessageBox.information(self, "Éxito", "Usuario eliminado correctamente.")
                self._reload_users()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error eliminando usuario: {str(e)}")
    
    # Métodos de recarga de datos
    def _reload_users(self):
        """Recargar datos de usuarios."""
        try:
            from ..repository import get_users_with_roles
            with self._session_factory() as session:
                users_data = get_users_with_roles(session)
                
                table = self.users_tab.table
                
                # Desactivar sorting temporalmente para evitar problemas
                table.setSortingEnabled(False)
                
                # Limpiar tabla completamente antes de recargar
                table.clearContents()
                table.setRowCount(len(users_data))
                
                print(f"Recargando {len(users_data)} usuarios")  # Debug
                
                for row, user in enumerate(users_data):
                    # Crear items con datos actualizados
                    id_item = QTableWidgetItem(str(user['id']))
                    username_item = QTableWidgetItem(user['username'])
                    fullname_item = QTableWidgetItem(user['full_name'])
                    roles_item = QTableWidgetItem(user['roles'])
                    status_item = QTableWidgetItem(user['status_text'])
                    
                    # Configurar items como no editables
                    for item in [id_item, username_item, fullname_item, roles_item, status_item]:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    
                    table.setItem(row, 0, id_item)
                    table.setItem(row, 1, username_item)
                    table.setItem(row, 2, fullname_item)
                    table.setItem(row, 3, roles_item)
                    table.setItem(row, 4, status_item)
                
                # Reactivar sorting
                table.setSortingEnabled(True)
                
                # Forzar actualización visual completa
                table.viewport().update()
                table.repaint()
                
        except Exception as e:
            print(f"Error recargando usuarios: {e}")
            QMessageBox.warning(self, "Error", f"No se pudieron cargar los usuarios: {str(e)}")
    
    def _reload_roles(self):
        """Recargar datos de roles."""
        try:
            from ..repository import get_roles_with_stats
            with self._session_factory() as session:
                roles_data = get_roles_with_stats(session)
                
                table = self.roles_tab.table
                
                # Desactivar sorting temporalmente para evitar problemas
                table.setSortingEnabled(False)
                
                # Limpiar tabla completamente antes de recargar
                table.clearContents()
                table.setRowCount(len(roles_data))
                
                print(f"Recargando {len(roles_data)} roles")  # Debug
                
                for row, role in enumerate(roles_data):
                    # Crear items con datos actualizados
                    id_item = QTableWidgetItem(str(role['id']))
                    name_item = QTableWidgetItem(role['name'])
                    desc_item = QTableWidgetItem(role['description'] or '')
                    users_item = QTableWidgetItem(str(role['user_count']))
                    perms_item = QTableWidgetItem(str(role['permission_count']))
                    
                    # Configurar items como no editables
                    for item in [id_item, name_item, desc_item, users_item, perms_item]:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    
                    table.setItem(row, 0, id_item)
                    table.setItem(row, 1, name_item)
                    table.setItem(row, 2, desc_item)
                    table.setItem(row, 3, users_item)
                    table.setItem(row, 4, perms_item)
                
                # Reactivar sorting
                table.setSortingEnabled(True)
                
                # Forzar actualización visual completa
                table.viewport().update()
                table.repaint()
                    
        except Exception as e:
            print(f"Error recargando roles: {e}")
            QMessageBox.warning(self, "Error", f"No se pudieron cargar los roles: {str(e)}")
    
    def _reload_permissions(self):
        """Recargar datos de permisos."""
        try:
            from ..repository import get_permissions_with_stats
            with self._session_factory() as session:
                permissions_data = get_permissions_with_stats(session)
                
                table = self.perms_tab.table
                
                # Desactivar sorting temporalmente para evitar problemas
                table.setSortingEnabled(False)
                
                # Limpiar tabla completamente antes de recargar
                table.clearContents()
                table.setRowCount(len(permissions_data))
                
                print(f"Recargando {len(permissions_data)} permisos")  # Debug
                
                for row, perm in enumerate(permissions_data):
                    # Crear items con datos actualizados
                    id_item = QTableWidgetItem(str(perm['id']))
                    code_item = QTableWidgetItem(perm['code'])
                    desc_item = QTableWidgetItem(perm['description'] or '')
                    roles_item = QTableWidgetItem(perm['roles'] or 'Sin asignar')
                    
                    # Configurar items como no editables
                    for item in [id_item, code_item, desc_item, roles_item]:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    
                    table.setItem(row, 0, id_item)
                    table.setItem(row, 1, code_item)
                    table.setItem(row, 2, desc_item)
                    table.setItem(row, 3, roles_item)
                
                # Reactivar sorting
                table.setSortingEnabled(True)
                
                # Forzar actualización visual completa
                table.viewport().update()
                table.repaint()
                    
        except Exception as e:
            print(f"Error recargando permisos: {e}")
            QMessageBox.warning(self, "Error", f"No se pudieron cargar los permisos: {str(e)}")
    
    # Métodos para roles
    def _on_add_role(self):
        """Agregar nuevo rol."""
        dialog = SimpleFormDialog(
            self, "Crear Rol", 
            [("Nombre:", ""), ("Descripción:", "")]
        )
        
        if dialog.exec():
            try:
                name, description = dialog.get_values()
                if not name.strip():
                    QMessageBox.warning(self, "Error", "El nombre del rol es requerido.")
                    return
                    
                from ..repository import ensure_role
                with self._session_factory() as session:
                    ensure_role(session, name=name.strip(), description=description.strip() or None)
                    session.commit()
                    
                QMessageBox.information(self, "Éxito", "Rol creado correctamente.")
                self._reload_roles()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error creando rol: {str(e)}")
    
    def _on_edit_role(self):
        """Editar rol seleccionado."""
        data = self.roles_tab.get_selected_row_data()
        if not data:
            QMessageBox.warning(self, "Advertencia", "Seleccione un rol para editar.")
            return
            
        # Mostrar diálogo de permisos
        role_data = {'id': int(data['ID']), 'name': data['Nombre']}
        dialog = RolePermissionsDialog(self._session_factory, self, role_data)
        
        if dialog.exec():
            try:
                selected_permissions = dialog.get_selected_permissions()
                from ..repository import assign_role_permissions
                with self._session_factory() as session:
                    assign_role_permissions(session, role_data['id'], selected_permissions)
                    session.commit()
                    
                QMessageBox.information(self, "Éxito", "Permisos del rol actualizados correctamente.")
                self._reload_roles()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error actualizando rol: {str(e)}")
    
    def _on_del_role(self):
        """Eliminar rol seleccionado."""
        data = self.roles_tab.get_selected_row_data()
        if not data:
            QMessageBox.warning(self, "Advertencia", "Seleccione un rol para eliminar.")
            return
            
        role_name = data['Nombre']
        if role_name.upper() in ['ADMIN', 'ADMINISTRACION']:
            QMessageBox.critical(self, "Error", "No se pueden eliminar roles del sistema.")
            return
            
        reply = QMessageBox.question(
            self, "Confirmar", 
            f"¿Está seguro de que desea eliminar el rol '{role_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Información", "Funcionalidad en desarrollo.")
    
    # Métodos para permisos
    def _on_add_perm(self):
        """Agregar nuevo permiso."""
        dialog = SimpleFormDialog(
            self, "Crear Permiso", 
            [("Código:", ""), ("Descripción:", "")]
        )
        
        if dialog.exec():
            try:
                code, description = dialog.get_values()
                if not code.strip():
                    QMessageBox.warning(self, "Error", "El código del permiso es requerido.")
                    return
                    
                from ..repository import ensure_permission
                with self._session_factory() as session:
                    ensure_permission(session, code=code.strip(), description=description.strip() or None)
                    session.commit()
                    
                QMessageBox.information(self, "Éxito", "Permiso creado correctamente.")
                self._reload_permissions()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error creando permiso: {str(e)}")
    
    def _on_edit_perm(self):
        """Editar permiso seleccionado."""
        data = self.perms_tab.get_selected_row_data()
        if not data:
            QMessageBox.warning(self, "Advertencia", "Seleccione un permiso para editar.")
            return
            
        dialog = SimpleFormDialog(
            self, "Editar Permiso", 
            [("Código:", data['Código']), ("Descripción:", data['Descripción'])]
        )
        
        if dialog.exec():
            try:
                code, description = dialog.get_values()
                if not code.strip():
                    QMessageBox.warning(self, "Error", "El código del permiso es requerido.")
                    return
                    
                from ..repository import update_permission
                with self._session_factory() as session:
                    update_permission(
                        session, 
                        permission_id=int(data['ID']), 
                        code=code.strip(), 
                        description=description.strip() or None
                    )
                    session.commit()
                    
                QMessageBox.information(self, "Éxito", "Permiso actualizado correctamente.")
                self._reload_permissions()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error actualizando permiso: {str(e)}")
    
    def _on_del_perm(self):
        """Eliminar permiso seleccionado."""
        QMessageBox.information(self, "Información", "La eliminación de permisos está deshabilitada por seguridad.")
    
    def showEvent(self, event):
        """Se ejecuta cuando la vista se muestra - actualizar datos automáticamente."""
        super().showEvent(event)
        # Actualizar los datos cuando se muestre la vista
        self.reload_current_tab()
    
    def reload(self):
        """Recargar todas las pestañas."""
        self._reload_users()
        self._reload_roles()
        self._reload_permissions()
        self._load_system_config()


# --- Diálogo simple para formularios ---
class SimpleFormDialog(QDialog):
    """Diálogo simple para formularios con campos de texto."""
    
    def __init__(self, parent, title, fields):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        
        # Formulario
        form = QFormLayout()
        self.fields = []
        
        for label, value in fields:
            edit = QLineEdit(value)
            form.addRow(label, edit)
            self.fields.append(edit)
        
        layout.addLayout(form)
        
        # Botones
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout.addWidget(buttons)
    
    def get_values(self):
        """Obtener valores de los campos."""
        return [field.text().strip() for field in self.fields]