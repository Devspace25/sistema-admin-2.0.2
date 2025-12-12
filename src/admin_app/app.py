from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
    QHBoxLayout,
    QStackedWidget,
    QLabel,
)
from PySide6.QtGui import QAction, QKeySequence, QIcon
from typing import cast
from pathlib import Path
import sys
import os
from sqlalchemy.orm import sessionmaker

from .db import make_engine, make_session_factory, get_data_dir
from .repository import init_db
from .ui.customers_view import CustomersView
from .ui.sidebar import SidebarNav
from .ui.placeholders import Placeholder
from .ui.orders_view import OrdersView
from .ui.home_view import HomeView
from .ui.sales_view import SalesView
from .ui.daily_reports_view import DailyReportsView
from .ui.config_view import ConfigView
from .ui.simple_products_view import SimpleProductsView
## Módulo ParametrosMaterialesView eliminado (consolidado en Productos)
## Módulo antiguo de producto eliminado
## Se eliminaron las siguientes importaciones:
## src.admin_app.ui.product_dialog, src.admin_app.ui.product_bom_dialog, src.admin_app.ui.product_categories_dialog


class MainWindow(QMainWindow):
    def __init__(self, current_user: str | None = None) -> None:
        super().__init__()
        self._current_user = current_user or "—"
        # Título con usuario
        self._update_window_title()

        # Inicializar DB y session factory
        engine = make_engine()
        init_db(engine, seed=True)
        # Asegurar schema del módulo corpóreo (sqlite separado)
        self._engine = engine
        self._session_factory: sessionmaker = make_session_factory(engine)

        # Acciones globales (mínimas)
        self._create_actions()

        # Layout central: sidebar + stack
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar = SidebarNav(self)
        layout.addWidget(self._sidebar, 0)
        self._stack = QStackedWidget(self)
        layout.addWidget(self._stack, 1)


        # Vistas (Home/Clientes/Productos/...) — Clientes tiene sus propios botones
        self._home_view = HomeView(self._session_factory, self._current_user)
        self._customers_view = CustomersView(self._session_factory)
        self._products_view = SimpleProductsView(self._session_factory)
        self._sales_view = SalesView(self._session_factory, self)
        self._daily_reports_view = DailyReportsView(self._session_factory, parent=self, current_user=self._current_user)

        # Importaciones locales para evitar ciclos y vistas adicionales
        self._orders_view = OrdersView(self._session_factory)
        self._config_view = ConfigView(self._session_factory)

        self._stack.addWidget(self._home_view)           # 0
        self._stack.addWidget(self._customers_view)      # 1
        self._stack.addWidget(self._products_view)       # 2
        self._stack.addWidget(self._sales_view)          # 3
        self._stack.addWidget(self._daily_reports_view)  # 4
        self._stack.addWidget(self._orders_view)         # 5
        self._stack.addWidget(self._config_view)         # 6

        self.setCentralWidget(container)

        # Menús
        self._create_menus()

        # Status bar
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Listo")
        # Etiqueta con usuario logueado al lado derecho
        self._user_label = QLabel(f"Usuario: {self._current_user}", self)
        self.statusBar().addPermanentWidget(self._user_label, 0)

        # Navegación
        self._sidebar.moduleSelected.connect(self.on_navigate)
        # Logout desde la barra lateral
        try:
            self._sidebar.logoutRequested.connect(self.on_logout)
        except Exception:
            pass
        # Configurar permisos del usuario en el sidebar
        try:
            from .repository import user_has_permission, user_has_role
            user_permissions = set()
            # Buscar ID de usuario si está autenticado
            with self._session_factory() as s:
                from .models import User
                u = s.query(User).filter(User.username == self._current_user).first()
                if u:
                    # Si el usuario tiene rol "ADMIN", darle todos los permisos automáticamente
                    is_admin = user_has_role(s, user_id=u.id, role_name="ADMIN")
                    if is_admin:
                        # Para admin, obtener todos los permisos disponibles de la base de datos
                        from .models import Permission
                        all_permissions = s.query(Permission).all()
                        user_permissions.update([p.code for p in all_permissions])
                    else:
                        # Para otros roles, verificar permisos individuales
                        # Lista de permisos que pueden ser relevantes para la interfaz
                        all_perms = [
                            "view_home", "view_customers", "edit_customers", "view_products", "edit_products",
                            "view_sales", "edit_sales", "view_daily_reports", "view_orders", 
                            "edit_orders", "view_parametros_materiales", "edit_parametros_materiales",
                            "view_config", "edit_config"
                        ]
                        for perm in all_perms:
                            if user_has_permission(s, user_id=u.id, permission_code=perm):
                                user_permissions.add(perm)
                    
                    # Guardar estado de administrador
                    self._is_admin = is_admin
            # Configurar sidebar con los permisos
            if hasattr(self._sidebar, "configure_permissions"):
                self._sidebar.configure_permissions(user_permissions)
            
            # Mantener compatibilidad con código existente
            self._can_view_config = "view_config" in user_permissions
            self._user_permissions = user_permissions
            
        except Exception as e:
            # En caso de error, dejar visible por defecto para no bloquear navegación durante desarrollo
            print(f"Error configurando permisos: {e}")
            self._can_view_config = True
            self._user_permissions = set()
            self._is_admin = False
        self.on_navigate("home")
        # Advertir si se está usando SQLite local (producción debe usar servidor)
        try:
            self._maybe_warn_sqlite()
        except Exception:
            pass

    def _maybe_warn_sqlite(self) -> None:
        """Muestra una advertencia si el backend es SQLite y permite suprimir futuros avisos."""
        try:
            backend = self._engine.url.get_backend_name()
        except Exception:
            backend = ""
        if backend != "sqlite":
            return

        # ¿Suprimido?
        try:
            data_dir = get_data_dir()
            flag = data_dir / "suppress_sqlite_warning.flag"
            if flag.exists():
                return
        except Exception:
            flag = None

        # Construir mensaje
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Advertencia: Modo SQLite")
        msg.setText(
            "Actualmente la aplicación está usando SQLite (base local).\n\n"
            "Para trabajo multiusuario estable y centralizado, configura DATABASE_URL para usar el servidor PostgreSQL.\n"
            "Seguir en SQLite en producción puede crear islas de datos en cada PC."
        )
        from PySide6.QtWidgets import QCheckBox
        chk = QCheckBox("No volver a mostrar")
        msg.setCheckBox(chk)
        msg.addButton("Entendido", QMessageBox.ButtonRole.AcceptRole)
        msg.exec()

        # Guardar supresión si aplica
        try:
            if chk.isChecked() and flag is not None:
                flag.touch(exist_ok=True)
        except Exception:
            pass

    # UI wiring
    def _create_actions(self) -> None:
        self.act_logout = QAction("&Cerrar sesión", self)
        self.act_logout.setShortcut(QKeySequence("Ctrl+L"))
        self.act_logout.triggered.connect(self.on_logout)

        self.act_exit = QAction("&Salir", self)
        self.act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_exit.triggered.connect(self.close)

        self.act_about = QAction("&Acerca de", self)
        self.act_about.triggered.connect(self.on_about)

    def _create_menus(self) -> None:
        menubar = self.menuBar()
        m_file = menubar.addMenu("&Archivo")
        m_file.addAction(self.act_logout)
        m_file.addAction(self.act_exit)

        m_help = menubar.addMenu("Ay&uda")
        m_help.addAction(self.act_about)

    # Action handlers (global)
    def on_about(self) -> None:
        QMessageBox.about(
            self,
            "Acerca de",
            "Sistema-Admin 2.0\nPython + PySide6 + SQLAlchemy + SQLite",
        )

    def _update_window_title(self) -> None:
        base = "Sistema-Admin 2.0"
        user = self._current_user or "—"
        self.setWindowTitle(f"{base} — {user}")

    def on_logout(self) -> None:
        """Cerrar la ventana principal y mostrar el Login para una nueva sesión.

        - Si el usuario cancela el login, se cierra la aplicación.
        - Si acepta, se crea una nueva ventana principal.
        """
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()

        # Confirmación
        reply = QMessageBox.question(
            self,
            "Cerrar sesión",
            "¿Seguro que deseas cerrar sesión?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Crear el login primero para mantener una ventana viva cuando cerremos la principal
        from .ui.login_dialog import LoginDialog
        # Importante: pasar session_factory para autenticar usuarios reales (no solo admin/admin)
        login = LoginDialog(session_factory=self._session_factory)

        # Cerrar esta ventana principal
        self.close()

        # Ejecutar login
        if login.exec() == 0:
            # Cancelado: salir por completo
            if app is not None:
                app.quit()
            return

        # Login aceptado: abrir nueva MainWindow
        # Obtener usuario tras login
        user, _ = login.get_credentials()
        new_window = MainWindow(current_user=user)
        # Guardar referencia en QApplication para evitar GC prematuro
        if app is not None:
            setattr(app, "_main_window", new_window)
        new_window.show()

    def on_navigate(self, module_key: str) -> None:
        # Verificar permisos para la navegación
        module_permissions = {
            "home": "view_home",
            "clientes": "view_customers",
            "productos": "view_products", 
            "ventas": "view_sales",
            "reportes_diarios": "view_daily_reports",
            "pedidos": "view_orders",
            "configuracion": "view_config",
        }
        
        user_permissions = getattr(self, "_user_permissions", set())
        is_admin = getattr(self, "_is_admin", False)
        required_perm = module_permissions.get(module_key)
        
        # Los administradores tienen acceso a todo, otros usuarios verifican permisos
        if not is_admin and required_perm and required_perm not in user_permissions:
            QMessageBox.warning(self, "Permisos", f"No tienes permiso para acceder a este módulo.")
            module_key = "home"
        
        index_map = {
            "home": 0,
            "clientes": 1,
            "productos": 2,
            "ventas": 3,
            "reportes_diarios": 4,
            "pedidos": 5,
            "configuracion": 6,
        }
        self._stack.setCurrentIndex(index_map.get(module_key, 0))
        # Las acciones específicas viven dentro de cada módulo


def create_qt_app():
    """Crea y retorna una instancia de QApplication.

    Separado para facilitar pruebas manuales y evitar crear múltiples instancias.
    """
    import sys

    app = cast(QApplication, QApplication.instance() or QApplication(sys.argv))
    # Resolver recursos según modo (dev vs ejecutable)
    def _resource_path(*parts: str) -> Path:
        # En PyInstaller, los datos se extraen en sys._MEIPASS
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return Path(getattr(sys, "_MEIPASS")) / Path(*parts)
        # En desarrollo, usar raíz del repo (cwd) como base para assets empaquetados
        return Path.cwd() / Path(*parts)

    # Cargar estilos QSS si existen (preferir los datos empaquetados en ./styles)
    try:
        theme = os.environ.get("APP_THEME", "light").lower()
        style_file = "styles-dark.qss" if theme == "dark" else "styles.qss"
        # Intento 1: datos empaquetados (dist/styles/*.qss)
        styles_path = _resource_path("styles", style_file)
        if not styles_path.exists():
            # Intento 2: junto al archivo fuente (dev)
            styles_path = Path(__file__).with_name(style_file)
        if styles_path.exists():
            app.setStyleSheet(styles_path.read_text(encoding="utf-8"))
    except Exception:
        pass

    # Establecer icono global de la app (logo)
    try:
        logo_path = _resource_path("assets", "img", "logo.png")
        if not logo_path.exists():
            # fallback dev
            logo_path = Path.cwd() / "assets" / "img" / "logo.png"
        if logo_path.exists():
            app.setWindowIcon(QIcon(str(logo_path)))
    except Exception:
        pass
    return app
