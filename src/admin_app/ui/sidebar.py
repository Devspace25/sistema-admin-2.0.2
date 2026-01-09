from __future__ import annotations

from PySide6.QtCore import Signal, Qt, QRect
from PySide6.QtGui import QIcon, QPainter, QColor, QBrush
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy, QSpacerItem, QLabel


class NotificationButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._notification_count = 0

    def set_notification(self, count: int | bool):
        # Allow bool for compatibility (True=1, False=0)
        target = 0
        if isinstance(count, bool):
            target = 1 if count else 0
        else:
            target = int(count)
            
        if self._notification_count != target:
            self._notification_count = target
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._notification_count > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # config text
            text = str(self._notification_count)
            if self._notification_count > 99:
                text = "99+"
            
            # Badge size
            size = 18
            margin = 5
            
            # Top-right position
            rect = QRect(self.width() - size - margin, margin, size, size)
            
            # Orange background #FF6900
            painter.setBrush(QBrush(QColor("#FF6900")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(rect)
            
            # Text white centered
            painter.setPen(QColor(Qt.GlobalColor.white))
            font = painter.font()
            font.setBold(True)
            # Adjust font size to fit
            font.setPixelSize(10)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


class SidebarNav(QWidget):
    moduleSelected = Signal(str)  # values: home|clientes|productos|ventas|reportes_diarios|reportes|pedidos|configuracion
    logoutRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarNav")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._buttons: dict[str, NotificationButton] = {}

        # Rótulo con usuario (si MainWindow lo expone). Se actualizará en construcción.
        try:
            mw = self.window()
            user = getattr(mw, "_current_user", None)
            if user:
                user_lbl = QLabel(f"Usuario: {user}")
                user_lbl.setObjectName("SidebarUserLabel")
                layout.addWidget(user_lbl)
        except Exception:
            pass
        icon_map = {
            "home": "assets/icons/home.svg",
            "clientes": "assets/icons/users.svg",
            "productos": "assets/icons/box.svg",
            "ventas": "assets/icons/cart.svg",
            "cuentas_por_cobrar": "assets/icons/clipboard.svg",
            "cuentas_por_pagar": "assets/icons/clipboard.svg",
            "contabilidad": "assets/icons/book.svg",
            "entregas": "assets/icons/truck.svg",
            "zonas": "assets/icons/map.svg",
            "reportes_diarios": "assets/icons/chart.svg",
            "pedidos": "assets/icons/clipboard.svg",
            "trabajadores": "assets/icons/users.svg",
            "configuracion": "assets/icons/lock.svg",
        }
        for key, text in [
            ("home", "Home"),
            ("clientes", "Clientes"),
            ("productos", "Productos"),
            ("ventas", "Ventas"),
            ("cuentas_por_cobrar", "Cuentas por Cobrar"),
            ("cuentas_por_pagar", "Cuentas por Pagar"),
            ("contabilidad", "Contabilidad"),
            ("entregas", "Delivery"),
            ("reportes_diarios", "Reportes Diarios"),
            ("pedidos", "Pedidos"),
            ("trabajadores", "Trabajadores"),
            ("configuracion", "Configuración"),
        ]:
            btn = NotificationButton(text, self)
            btn.setObjectName(f"nav_{key}")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._on_click(k))
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            icon_rel = icon_map.get(key)
            if icon_rel:
                btn.setIcon(QIcon.fromTheme("", QIcon(self._resource_path(icon_rel))))
            layout.addWidget(btn)
            self._buttons[key] = btn

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Botón de cierre de sesión al fondo
        self._btn_logout = QPushButton("Cerrar sesión", self)
        self._btn_logout.setObjectName("nav_logout")
        self._btn_logout.setCheckable(False)
        self._btn_logout.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Icono opcional si existiera en assets/icons/logout.svg
        try:
            import os
            icon_path = self._resource_path("assets/icons/logout.svg")
            if os.path.exists(icon_path):
                self._btn_logout.setIcon(QIcon.fromTheme("", QIcon(icon_path)))
        except Exception:
            pass
        self._btn_logout.clicked.connect(self._on_logout_click)
        layout.addWidget(self._btn_logout)

        self.select_module("home")
    
    def set_notification(self, key: str, count: int | bool) -> None:
        """Activa o desactiva la notificación (badge con número) en el botón del módulo."""
        btn = self._buttons.get(key)
        if btn and hasattr(btn, 'set_notification'):
            btn.set_notification(count)


    def _on_click(self, key: str) -> None:
        self.select_module(key)
        self.moduleSelected.emit(key)

    def select_module(self, key: str) -> None:
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)

    def _resource_path(self, rel: str) -> str:
        # Devuelve ruta absoluta dentro del paquete para los recursos
        import os, sys
        # Si estamos en un ejecutable PyInstaller, los datos están en sys._MEIPASS
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return os.path.join(getattr(sys, "_MEIPASS"), rel)
        # En desarrollo, resolver respecto al paquete fuente (src/admin_app)
        base = os.path.dirname(os.path.dirname(__file__))  # src/admin_app/ui -> src/admin_app
        return os.path.join(base, rel)

    def _on_logout_click(self) -> None:
        self.logoutRequested.emit()

    # --- Permisos/visibilidad ---
    def set_module_visible(self, module: str, visible: bool) -> None:
        """Muestra/oculta un botón del menú.

        Si se oculta y estaba seleccionado, vuelve a 'home'.
        """
        btn = self._buttons.get(module)
        if not btn:
            return
        btn.setVisible(bool(visible))
        if not visible and btn.isChecked():
            self.select_module("home")

    def set_config_visible(self, visible: bool) -> None:
        """Muestra/oculta el botón de Configuración.

        Si se oculta y estaba seleccionado, vuelve a 'home'.
        """
        self.set_module_visible("configuracion", visible)

    def configure_permissions(self, user_permissions: set[str]) -> None:
        """Configura la visibilidad de los módulos basado en los permisos del usuario."""
        # Mapeo de módulos a permisos requeridos
        module_permissions = {
            "home": "view_home",
            "clientes": "view_customers",
            "productos": "view_products", 
            "ventas": "view_sales",
            "reportes": "view_reports",
            "reportes_diarios": "view_daily_reports",
            "pedidos": "view_orders",
            "trabajadores": "view_workers",
            "configuracion": "view_config",
        }
        
        for module, required_perm in module_permissions.items():
            has_permission = required_perm in user_permissions
            self.set_module_visible(module, has_permission)
