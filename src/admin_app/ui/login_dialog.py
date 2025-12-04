from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QFrame,
    QWidget,
)
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsDropShadowEffect
from sqlalchemy.orm import sessionmaker
# Preferencias removidas (Recordarme eliminado)


class LoginDialog(QDialog):
    def __init__(self, parent=None, session_factory: sessionmaker | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Iniciar sesión")
        self.setModal(True)
        self.resize(420, 240)
        self._session_factory = session_factory

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)

        frame = QFrame(self)
        frame.setObjectName("LoginFrame")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_lyt = QVBoxLayout(frame)
        frame_lyt.setContentsMargins(20, 20, 20, 20)
        frame_lyt.setSpacing(12)

        # Sombra sutil
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 60))
        frame.setGraphicsEffect(shadow)

        # Logo de la empresa (opcional)
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        try:
            import os
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            logo_path = os.path.join(root, "assets", "img", "logo.png")
            if os.path.exists(logo_path):
                pm = QPixmap(logo_path)
                if not pm.isNull():
                    # Escalar suavemente a un ancho razonable
                    pm = pm.scaledToWidth(120, Qt.TransformationMode.SmoothTransformation)
                    logo_label.setPixmap(pm)
        except Exception:
            pass

        title = QLabel("Bienvenido")
        title.setObjectName("LoginTitle")
        subtitle = QLabel("Ingresa tus credenciales para continuar")
        subtitle.setObjectName("LoginSubtitle")

        form_widget = QWidget(self)
        form = QFormLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)

        self.user_edit = QLineEdit(self)
        self.user_edit.setPlaceholderText("usuario")
        self.pass_edit = QLineEdit(self)
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.setPlaceholderText("password")

        # Toggle mostrar/ocultar contraseña
        try:
            import os
            base = os.path.dirname(os.path.dirname(__file__))  # src/admin_app
            eye_icon = os.path.join(base, "assets", "icons", "eye.svg")
            eye_off_icon = os.path.join(base, "assets", "icons", "eye-off.svg")
            self._eye_icon = QIcon(eye_icon) if os.path.exists(eye_icon) else QIcon()
            self._eye_off_icon = QIcon(eye_off_icon) if os.path.exists(eye_off_icon) else QIcon()
        except Exception:
            self._eye_icon = QIcon()
            self._eye_off_icon = QIcon()

        self._showing_password = False
        self._action_toggle = self.pass_edit.addAction(self._eye_icon or QIcon(), QLineEdit.ActionPosition.TrailingPosition)
        # Alternar con el icono del campo
        self._action_toggle.triggered.connect(lambda checked=False: self._set_show_password(not self._showing_password))

        # Iconos en los campos
        try:
            import os
            base = os.path.dirname(os.path.dirname(__file__))  # src/admin_app
            user_icon = os.path.join(base, "assets", "icons", "users.svg")
            lock_icon = os.path.join(base, "assets", "icons", "lock.svg")
            if os.path.exists(user_icon):
                self.user_edit.addAction(QIcon(user_icon), QLineEdit.ActionPosition.LeadingPosition)
            if os.path.exists(lock_icon):
                self.pass_edit.addAction(QIcon(lock_icon), QLineEdit.ActionPosition.LeadingPosition)
        except Exception:
            pass

        form.addRow("Usuario", self.user_edit)
        form.addRow("Contraseña", self.pass_edit)

        # Recordarme eliminado
        self.show_pwd_chk = QCheckBox("Mostrar contraseña", self)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)

        # Insertar logo si está disponible
        frame_lyt.addWidget(logo_label)
        frame_lyt.addWidget(title)
        frame_lyt.addWidget(subtitle)
        frame_lyt.addWidget(form_widget)
        # Fila de opciones (Mostrar contraseña)
        opts_row = QHBoxLayout()
        opts_row.addStretch(1)
        opts_row.addWidget(self.show_pwd_chk)
        frame_lyt.addLayout(opts_row)

        frame_lyt.addWidget(btns)
        outer.addWidget(frame)

        # Enter para aceptar
        self.user_edit.returnPressed.connect(self._on_accept)
        self.pass_edit.returnPressed.connect(self._on_accept)
        # Checkbox de mostrar contraseña
        self.show_pwd_chk.toggled.connect(self._set_show_password)

        # Limpiar estado de error al escribir
        self.user_edit.textChanged.connect(lambda _: self._set_error(self.user_edit, False))
        self.pass_edit.textChanged.connect(lambda _: self._set_error(self.pass_edit, False))

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        # Centrar el diálogo en la pantalla
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen:
            geo = self.frameGeometry()
            geo.moveCenter(screen.center())
            self.move(geo.topLeft())

    def _on_accept(self) -> None:
        user = self.user_edit.text().strip()
        pwd = self.pass_edit.text().strip()
        invalid = []
        if not user:
            invalid.append(self.user_edit)
        if not pwd:
            invalid.append(self.pass_edit)
        if invalid:
            for w in invalid:
                self._set_error(w, True)
            (invalid[0]).setFocus()
            return

        # Autenticar contra la base de datos si se proporciona session_factory
        ok = False
        if self._session_factory is not None:
            try:
                from ..repository import authenticate_user
                with self._session_factory() as s:
                    u = authenticate_user(s, username=user, password=pwd)
                    ok = bool(u)
            except Exception:
                ok = False
        else:
            # Fallback mínimo (no recomendado): admin/admin
            ok = (user == "admin" and pwd == "admin")

        if ok:
            self.accept()
        else:
            QMessageBox.warning(self, "Login", "Credenciales inválidas")

    def get_credentials(self) -> tuple[str, str]:
        return self.user_edit.text().strip(), self.pass_edit.text().strip()

    def _set_show_password(self, on: bool) -> None:
        # Actualiza echo mode, icono y sincroniza checkbox
        self._showing_password = bool(on)
        self.pass_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if self._showing_password else QLineEdit.EchoMode.Password
        )
        if not self._eye_icon.isNull() and not self._eye_off_icon.isNull():
            if hasattr(self, "_action_toggle") and self._action_toggle is not None:
                self._action_toggle.setIcon(self._eye_off_icon if self._showing_password else self._eye_icon)
        # Sincronizar checkbox si hace falta
        if hasattr(self, "show_pwd_chk") and self.show_pwd_chk.isChecked() != self._showing_password:
            was_blocked = self.show_pwd_chk.blockSignals(True)
            try:
                self.show_pwd_chk.setChecked(self._showing_password)
            finally:
                self.show_pwd_chk.blockSignals(was_blocked)

    def _set_error(self, widget: QLineEdit, on: bool) -> None:
        # Bordes rojos al invalidar
        base_style = ""
        err_style = "border: 1px solid #ef4444; border-radius: 6px;"
        widget.setStyleSheet(err_style if on else base_style)
