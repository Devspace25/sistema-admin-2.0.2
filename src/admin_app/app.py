from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QStackedWidget,
    QLabel,
)
from PySide6.QtGui import QAction, QKeySequence, QIcon
from PySide6.QtCore import QTimer
from typing import cast
from pathlib import Path
import sys
import os
from sqlalchemy.orm import sessionmaker

from .db import make_engine, make_session_factory, get_data_dir
from .repository import init_db
from .models import User, Role, Order, DailyReport
from .utils.db_watcher import DbWatcher  # <-- Import Watcher

from .ui.customers_view import CustomersView
from .ui.sidebar import SidebarNav
from .ui.placeholders import Placeholder
from .ui.orders_view import OrdersView
from .ui.home_view import HomeView
from .ui.sales_view import SalesView
from .ui.daily_reports_view import DailyReportsView
from .ui.config_view import ConfigView
from .ui.simple_products_view import SimpleProductsView
from .ui.workers_view import WorkersView
from .ui.pending_payments_view import PendingPaymentsView
from .ui.deliveries_view import DeliveriesView
from .ui.delivery_zones_view import DeliveryZonesView
from .ui.accounting_view import AccountingView
from .ui.payables_view import PayablesView
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

        # --- Resolve User Role ---
        self.current_user_role = "user"
        if self._current_user and self._current_user != "—":
            try:
                with self._session_factory() as session:
                    user_obj = session.query(User).filter(User.username == self._current_user).first()
                    if user_obj:
                        # Check default role
                        if user_obj.default_role_id:
                            role_obj = session.get(Role, user_obj.default_role_id)
                            if role_obj and role_obj.name:
                                self.current_user_role = role_obj.name.lower()
                        
                        # Fallback for admin user if role lookup failed or is missing
                        if self.current_user_role == "user" and user_obj.username == "admin":
                             self.current_user_role = "admin"
            except Exception as e:
                print(f"Error resolving role: {e}")
        # -------------------------

        # Acciones globales (mínimas)
        self._create_actions()

        # Layout central: sidebar + stack
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar = SidebarNav(self)
        layout.addWidget(self._sidebar, 0)
        
        # Right container to hold Header + Stack
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # Top Header Bar for Date/Time functionality
        self.top_header = QWidget()
        self.top_header.setStyleSheet("background-color: #1E1E1E; border-bottom: 2px solid #FF6900;")
        self.top_header.setFixedHeight(40)
        
        header_layout = QHBoxLayout(self.top_header)
        header_layout.setContentsMargins(15, 0, 15, 0)
        
        # Spacer to push text to right (or title on left if needed later)
        header_layout.addStretch()
        
        # Date/Time Label
        self.lbl_datetime = QLabel("--/--/---- --:--:--")
        self.lbl_datetime.setStyleSheet("color: #e5e7eb; font-weight: bold; font-family: 'Segoe UI'; font-size: 14px;")
        header_layout.addWidget(self.lbl_datetime)
        
        right_layout.addWidget(self.top_header)

        self._stack = QStackedWidget(self)
        right_layout.addWidget(self._stack, 1) # Expand stack to fill remaining space
        
        layout.addWidget(right_container, 1)

        # Timer for clock
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock() # Initial call

        # --- DB Watcher Integration ---
        # Watch the main DB file for external changes (or writes from other views)
        db_file = os.path.join(get_data_dir(), "app.db")
        self._watcher = DbWatcher(db_file, interval=3000, parent=self)
        self._watcher.start()
        # Connect to specific slot that propagates refresh
        self._watcher.db_updated.connect(self._on_global_data_changed)

        # Determinar permisos del usuario actual
        permissions = set()
        self._role_name = ""
        try:
            with self._session_factory() as session:
                user = session.query(User).filter(User.username == self._current_user).first()
                if user:
                    # Verificar si es admin (por rol por defecto)
                    is_admin = False
                    if user.default_role_id:
                        role = session.get(Role, user.default_role_id)
                        if role:
                            self._role_name = role.name.lower()
                            if self._role_name in ("admin", "administrador"):
                                is_admin = True
                    
                    # Si es admin, otorgar permisos
                    if is_admin:
                        permissions.add("edit_customers")
                        permissions.add("create_customers")
                        permissions.add("edit_products")
                        permissions.add("create_products")
                        permissions.add("edit_workers")
                        permissions.add("create_workers")
                        permissions.add("edit_orders")
                        permissions.add("edit_sales")
                        permissions.add("create_sales")
        except Exception as e:
            print(f"Error al cargar permisos: {e}")

        # Vistas (Home/Clientes/Productos/...) — Clientes tiene sus propios botones
        self._home_view = HomeView(self._session_factory, self._current_user)
        self._home_view.navigate_requested.connect(self.on_navigate)
        self._customers_view = CustomersView(self._session_factory)
        self._customers_view.set_permissions(permissions)

        self._products_view = SimpleProductsView(self._session_factory)
        self._products_view.set_permissions(permissions)

        self._sales_view = SalesView(self._session_factory, self)
        self._sales_view.set_permissions(permissions)
        self._daily_reports_view = DailyReportsView(self._session_factory, parent=self, current_user=self._current_user)

        # Importaciones locales para evitar ciclos y vistas adicionales
        self._orders_view = OrdersView(self._session_factory, current_user=self._current_user)
        self._orders_view.set_permissions(permissions)
        self._workers_view = WorkersView(self._session_factory)
        self._workers_view.set_permissions(permissions)

        self._config_view = ConfigView(self._session_factory)
        self._pending_payments_view = PendingPaymentsView(self._session_factory)
        self._deliveries_view = DeliveriesView(self._session_factory)
        self._delivery_zones_view = DeliveryZonesView(self._session_factory)
        self._accounting_view = AccountingView(self._session_factory, parent=self)
        self._payables_view = PayablesView(self._session_factory)

        self._stack.addWidget(self._home_view)           # 0
        self._stack.addWidget(self._customers_view)      # 1
        self._stack.addWidget(self._products_view)       # 2
        self._stack.addWidget(self._sales_view)          # 3
        self._stack.addWidget(self._daily_reports_view)  # 4
        self._stack.addWidget(self._orders_view)         # 5
        self._stack.addWidget(self._workers_view)        # 6 (antes 6 era config)
        self._stack.addWidget(self._config_view)         # 7
        self._stack.addWidget(self._pending_payments_view) # 8
        self._stack.addWidget(self._deliveries_view)     # 9
        self._stack.addWidget(self._delivery_zones_view) # 10
        self._stack.addWidget(self._accounting_view)     # 11
        self._stack.addWidget(self._payables_view)       # 12

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
            from .repository import get_user_permissions, user_has_role
            user_permissions = set()
            # Buscar ID de usuario si está autenticado
            with self._session_factory() as s:
                # User ya está importado globalmente
                u = s.query(User).filter(User.username == self._current_user).first()
                if u:
                    # Obtener permisos reales desde la base de datos
                    perms = get_user_permissions(s, u.id)
                    user_permissions.update(perms)
                    
                    # Guardar estado de administrador (solo para referencia, no para bypass)
                    self._is_admin = user_has_role(s, user_id=u.id, role_name="ADMIN")
            
            # Configurar sidebar con los permisos
            if hasattr(self._sidebar, "configure_permissions"):
                self._sidebar.configure_permissions(user_permissions)
            
            # Mantener compatibilidad con código existente
            self._can_view_config = "view_config" in user_permissions
            self._user_permissions = user_permissions
            
            # Configurar permisos en vistas específicas
            if hasattr(self._workers_view, "set_permissions"):
                if hasattr(self._workers_view, "set_current_user"):
                    self._workers_view.set_current_user(self._current_user)
                self._workers_view.set_permissions(user_permissions)
            if hasattr(self._sales_view, "set_current_user"):
                self._sales_view.set_current_user(self._current_user)
            if hasattr(self._sales_view, "set_permissions"):
                self._sales_view.set_permissions(user_permissions)
            if hasattr(self._customers_view, "set_current_user"):
                self._customers_view.set_current_user(self._current_user)
            if hasattr(self._customers_view, "set_permissions"):
                self._customers_view.set_permissions(user_permissions)
            if hasattr(self._products_view, "set_current_user"):
                self._products_view.set_current_user(self._current_user)
            if hasattr(self._products_view, "set_permissions"):
                self._products_view.set_permissions(user_permissions)
            if hasattr(self._orders_view, "set_permissions"):
                self._orders_view.set_permissions(user_permissions)
            if hasattr(self._daily_reports_view, "set_permissions"):
                self._daily_reports_view.set_permissions(user_permissions)
            
        except Exception as e:
            # En caso de error, dejar visible por defecto para no bloquear navegación durante desarrollo
            print(f"Error configurando permisos: {e}")
            self._can_view_config = True
            self._user_permissions = set()
            self._is_admin = False

        # Configurar timer de notificaciones
        self._notification_timer = QTimer(self)
        self._notification_timer.timeout.connect(self._check_notifications)
        self._notification_timer.start(10000) # Check every 10 seconds
        QTimer.singleShot(2000, self._check_notifications)

        self.on_navigate("home")
        # Advertir si se está usando SQLite local (producción debe usar servidor)
        try:
            self._maybe_warn_sqlite()
        except Exception:
            pass

    def on_navigate(self, route_name: str) -> None:
        """Cambiar la vista en base al nombre."""
        if route_name == "home":
            self._stack.setCurrentWidget(self._home_view)
        elif route_name == "orders":
            self._stack.setCurrentWidget(self._orders_view)
            self._orders_view.load_data()
        elif route_name == "sales":
            self._stack.setCurrentWidget(self._sales_view)
            self._sales_view.load_data()
        elif route_name == "customers":
            self._stack.setCurrentWidget(self._customers_view)
            self._customers_view.load_data()
        elif route_name == "daily_reports":
            self._stack.setCurrentWidget(self._daily_reports_view)
            self._daily_reports_view.load_data()
        elif route_name == "products":
            self._stack.setCurrentWidget(self._products_view)
            self._products_view.load_data()
        elif route_name == "workers":
            self._stack.setCurrentWidget(self._workers_view)
            self._workers_view.load_data()
        elif route_name == "pending":
            self._stack.setCurrentWidget(self._pending_payments_view)
            self._pending_payments_view.load_data()
        elif route_name == "deliveries":
            self._stack.setCurrentWidget(self._deliveries_view)
            self._deliveries_view.load_data()
        elif route_name == "delivery_zones":
            self._stack.setCurrentWidget(self._delivery_zones_view)
            self._delivery_zones_view.load_data()
        elif route_name == "accounting":
            self._stack.setCurrentWidget(self._accounting_view)
            self._accounting_view.load_data()
        elif route_name == "payables":
            self._stack.setCurrentWidget(self._payables_view)
            self._payables_view.load_data()
        elif route_name == "config":
            self._stack.setCurrentWidget(self._config_view)

    def _on_global_data_changed(self) -> None:
        """Called when DB changes are detected. Trigger reload on active view."""
        current_widget = self._stack.currentWidget()
        if hasattr(current_widget, "load_data"):
            # Call load_data on the visible widget to refresh it
            current_widget.load_data()
            
            # Also refresh Home if it's not active (to keep KPIs fresh)
            if current_widget != self._home_view:
                self._home_view.load_data()

    def _check_notifications(self) -> None:
        """Verifica estado de pedidos/reportes y actualiza notificaciones en sidebar."""
        try:
            with self._session_factory() as session:
                total_notifications = 0

                # 1. Chequear nuevos pedidos
                # Solicitud: "si el administrador agrega un pedido, los de produccion y diseño deben ver la notificacion"
                check_orders = True 
                if check_orders:
                    # Contar pedidos con status 'NUEVO' (diseño) o 'POR_PRODUCIR' (directo a producción)
                    new_orders = session.query(Order).filter(Order.status.in_(['NUEVO', 'POR_PRODUCIR'])).count()
                    self._sidebar.set_notification('pedidos', new_orders)
                    if new_orders > 0:
                        total_notifications += new_orders

                # 2. Chequear reportes diarios pendientes (para Admin/Gerencia)
                # Solicitud: "si produccion envia un reporte, el administrador debe ver la notificacion"
                check_reports = self._role_name in ('admin', 'administrador')
                if check_reports:
                    pending_reports = session.query(DailyReport).filter(DailyReport.status == 'PENDIENTE').count()
                    self._sidebar.set_notification('reportes_diarios', pending_reports)
                    if pending_reports > 0:
                        total_notifications += pending_reports
                
                # Actualizar home con el total
                self._sidebar.set_notification('home', total_notifications)

        except Exception as e:
            # Silencioso para no spammear consola en loop
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

    def _update_clock(self):
        from PySide6.QtCore import QDateTime, QLocale
        from datetime import datetime
        now = datetime.now()
        # Format: DD/MM/YYYY HH:MM:SS AM/PM
        self.lbl_datetime.setText(now.strftime("%d/%m/%Y %I:%M:%S %p"))

    def _update_window_title(self) -> None:
        base = "Sistema-Admin 2.0.3"
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
            "entregas": "view_orders",
            "zonas": "view_config",
        }
        
        user_permissions = getattr(self, "_user_permissions", set())
        is_admin = getattr(self, "_is_admin", False)
        required_perm = module_permissions.get(module_key)
        
        # Verificar permisos (incluso para admin, para respetar configuración)
        if required_perm and required_perm not in user_permissions:
            QMessageBox.warning(self, "Permisos", f"No tienes permiso para acceder a este módulo.")
            module_key = "home"
        
        index_map = {
            "home": 0,
            "clientes": 1,
            "productos": 2,
            "ventas": 3,
            "reportes_diarios": 4,
            "pedidos": 5,
            "trabajadores": 6,
            "configuracion": 7,
            "cuentas_por_cobrar": 8,
            "entregas": 9,
            "zonas": 10,
            "contabilidad": 11,
            "cuentas_por_pagar": 12,
        }
        self._stack.setCurrentIndex(index_map.get(module_key, 0))
        
        # Refrescar vista si es necesario
        if module_key == "clientes":
            self._customers_view.refresh()
        elif module_key == "productos":
            self._products_view.refresh()
        elif module_key == "ventas":
            self._sales_view.refresh()
        elif module_key == "reportes_diarios":
            self._daily_reports_view.refresh()
        elif module_key == "pedidos":
            self._orders_view.refresh()
        elif module_key == "trabajadores":
            self._workers_view.refresh()
        elif module_key == "configuracion":
            self._config_view.refresh()
        elif module_key == "cuentas_por_cobrar":
            self._pending_payments_view.refresh()
        elif module_key == "entregas":
            self._deliveries_view.refresh()
        elif module_key == "zonas":
            self._delivery_zones_view.refresh()
        elif module_key == "contabilidad":
            pass
        elif module_key == "cuentas_por_pagar":
            self._payables_view.refresh_all()


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
