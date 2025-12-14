from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QScrollArea, QDialog, QFormLayout, QDoubleSpinBox, QDialogButtonBox, 
    QMessageBox, QGraphicsDropShadowEffect, QGridLayout, QProgressBar,
    QSizePolicy, QGroupBox
)
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QBarSeries, QBarSet, QValueAxis, QBarCategoryAxis
from PySide6.QtGui import QPainter, QFont, QColor, QIcon, QPixmap, QBrush, QLinearGradient
from PySide6.QtCore import Qt, QTimer, QSize, QMargins
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

from ..repository import (
    get_dashboard_kpis, get_sales_by_user, get_weekly_sales_data, get_daily_sales_data,
    get_monthly_sales_goal, set_monthly_sales_goal, set_user_monthly_goal
)

# --- Utils ---
def get_icon_path(name: str) -> str:
    """Helper to get icon path."""
    # Adjust path based on your project structure
    base_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icons")
    return os.path.join(base_path, name)

class ModernKpiCard(QFrame):
    def __init__(self, title: str, value: str, icon_name: str, color: str, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(100)
        
        # Shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 12px;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)
        
        # Icon Container
        icon_container = QFrame()
        icon_container.setFixedSize(50, 50)
        icon_container.setStyleSheet(f"""
            background-color: {color}20; /* 20% opacity */
            border-radius: 25px;
        """)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel()
        icon_path = get_icon_path(icon_name)
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            # Colorize icon
            mask = pixmap.createMaskFromColor(Qt.GlobalColor.transparent, Qt.MaskMode.MaskInColor)
            pixmap.fill(QColor(color))
            pixmap.setMask(mask)
            icon_label.setPixmap(pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            icon_label.setText("📊") # Fallback
            
        icon_layout.addWidget(icon_label)
        
        # Text Container
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setFont(QFont("Segoe UI", 10))
        self.title_lbl.setStyleSheet("color: #7f8c8d;")
        
        self.value_lbl = QLabel(value)
        self.value_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.value_lbl.setStyleSheet("color: #2c3e50;")
        
        text_layout.addWidget(self.title_lbl)
        text_layout.addWidget(self.value_lbl)
        
        layout.addWidget(icon_container)
        layout.addWidget(text_container)
        layout.addStretch()

    def update_value(self, new_value: str):
        self.value_lbl.setText(new_value)

class VendorListItem(QFrame):
    def __init__(self, name: str, amount: float, goal: float, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border-bottom: 1px solid #f0f0f0;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 10, 5, 10)
        layout.setSpacing(15)
        
        # Avatar (Initials)
        avatar = QLabel(name[:2].upper())
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        avatar.setStyleSheet("""
            background-color: #e0e0e0;
            color: #555;
            border-radius: 18px;
        """)
        
        # Info
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #333; border: none;")
        
        # Progress Bar
        percentage = (amount / goal * 100) if goal > 0 else 0
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(int(percentage))
        progress.setFixedHeight(6)
        progress.setTextVisible(False)
        
        # Color logic
        color = "#FF6900" # Default orange
        if percentage >= 100: color = "#2ecc71" # Green
        elif percentage >= 50: color = "#f1c40f" # Yellow
        
        progress.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: #f0f0f0;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)
        
        info_layout.addWidget(name_lbl)
        info_layout.addWidget(progress)
        
        # Amount
        amount_lbl = QLabel(f"${amount:,.2f}")
        amount_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        amount_lbl.setStyleSheet("color: #2c3e50; border: none;")
        amount_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Percent text
        pct_lbl = QLabel(f"{percentage:.0f}%")
        pct_lbl.setFont(QFont("Segoe UI", 9))
        pct_lbl.setStyleSheet("color: #7f8c8d; border: none;")
        pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0,0,0,0)
        right_layout.setSpacing(0)
        right_layout.addWidget(amount_lbl)
        right_layout.addWidget(pct_lbl)

        layout.addWidget(avatar)
        layout.addWidget(info_widget, 1)
        layout.addWidget(right_widget)

class UserGoalsDialog(QDialog):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.setWindowTitle("Configurar Metas por Usuario")
        self.setFixedSize(400, 500)
        self.setStyleSheet("""
            QDialog { background-color: white; }
            QLabel { font-size: 14px; color: #333; }
            QDoubleSpinBox { 
                padding: 5px; 
                border: 1px solid #ccc; 
                border-radius: 4px;
            }
        """)
        self.setup_ui()
        self.load_users()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        lbl = QLabel("Establezca la meta mensual para cada usuario:")
        lbl.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.form_layout = QFormLayout(self.container)
        self.form_layout.setSpacing(15)
        self.scroll.setWidget(self.container)
        
        layout.addWidget(self.scroll)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def load_users(self):
        self.spinboxes = {}
        try:
            with self.session_factory() as session:
                from ..models import User
                users = session.query(User).filter(User.is_active == True).all()
                for user in users:
                    sb = QDoubleSpinBox()
                    sb.setRange(0, 1000000)
                    sb.setPrefix("$ ")
                    sb.setValue(user.monthly_goal)
                    self.form_layout.addRow(user.username, sb)
                    self.spinboxes[user.username] = sb
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error cargando usuarios: {e}")

    def save_goals(self):
        try:
            with self.session_factory() as session:
                from ..repository import set_user_monthly_goal
                for username, sb in self.spinboxes.items():
                    set_user_monthly_goal(session, username, sb.value())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error guardando metas: {e}")

class HomeView(QWidget):
    def __init__(self, session_factory: sessionmaker, current_user: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._current_user = current_user or "—"
        self._can_view_all_sales = self._check_can_view_all_sales()
        
        self.kpi_cards = {}
        
        self._setup_ui()
        
        # Timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_data)
        self.update_timer.start(30000)
        
        self.refresh_data()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)
        
        # --- Header ---
        header_layout = QHBoxLayout()
        
        welcome_widget = QWidget()
        welcome_layout = QVBoxLayout(welcome_widget)
        welcome_layout.setContentsMargins(0, 0, 0, 0)
        welcome_layout.setSpacing(2)
        
        greet_lbl = QLabel(f"Hola, {self._current_user} 👋")
        greet_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        greet_lbl.setStyleSheet("color: #2c3e50;")
        
        date_lbl = QLabel(datetime.now().strftime("%A, %d de %B de %Y").capitalize())
        date_lbl.setFont(QFont("Segoe UI", 11))
        date_lbl.setStyleSheet("color: #7f8c8d;")
        
        welcome_layout.addWidget(greet_lbl)
        welcome_layout.addWidget(date_lbl)
        
        header_layout.addWidget(welcome_widget)
        header_layout.addStretch()
        
        # Goal Config Button (Admin only)
        if self._can_view_all_sales:
            self.goal_btn = QPushButton("🎯 Configurar Meta")
            self.goal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.goal_btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 6px;
                    padding: 8px 16px;
                    color: #555;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #f8f9fa;
                    border-color: #d0d0d0;
                }
            """)
            self.goal_btn.clicked.connect(self.change_sales_goal)
            header_layout.addWidget(self.goal_btn)

        # Refresh Button
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setToolTip("Actualizar datos")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px 12px;
                color: #555;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #d0d0d0;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_data)
        header_layout.addWidget(self.refresh_btn)
            
        main_layout.addLayout(header_layout)
        
        # --- KPI Grid ---
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(20)
        
        # Define KPIs: Title, Icon, Color
        kpis = [
            ("Clientes", "users.svg", "#3498db"),
            ("Ventas del Mes", "chart.svg", "#2ecc71"),
            ("Pedidos del Mes", "clipboard.svg", "#9b59b6"),
            ("Ventas Hoy", "box.svg", "#e67e22")
        ]
        
        for title, icon, color in kpis:
            card = ModernKpiCard(title, "...", icon, color)
            self.kpi_cards[title] = card
            kpi_layout.addWidget(card)
            
        main_layout.addLayout(kpi_layout)
        
        # --- Main Content (Chart + Team) ---
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        # 1. Chart Section
        chart_container = QFrame()
        chart_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
            }
        """)
        chart_shadow = QGraphicsDropShadowEffect(chart_container)
        chart_shadow.setBlurRadius(15)
        chart_shadow.setColor(QColor(0, 0, 0, 30))
        chart_shadow.setYOffset(2)
        chart_container.setGraphicsEffect(chart_shadow)
        
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(20, 20, 20, 20)
        
        chart_title = QLabel("Rendimiento Diario (Últimos 7 días)")
        chart_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        chart_title.setStyleSheet("color: #2c3e50; border: none;")
        chart_layout.addWidget(chart_title)
        
        self.chart = QChart()
        self.chart.setBackgroundVisible(False)
        self.chart.layout().setContentsMargins(0, 0, 0, 0)
        self.chart.legend().setVisible(False)
        
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setStyleSheet("background: transparent; border: none;")
        self.chart_view.setFixedHeight(300)
        
        chart_layout.addWidget(self.chart_view)
        
        # 2. Team Section
        team_container = QFrame()
        team_container.setFixedWidth(350) # Fixed width for sidebar feel
        team_container.setFixedHeight(380)
        team_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
            }
        """)
        team_shadow = QGraphicsDropShadowEffect(team_container)
        team_shadow.setBlurRadius(15)
        team_shadow.setColor(QColor(0, 0, 0, 30))
        team_shadow.setYOffset(2)
        team_container.setGraphicsEffect(team_shadow)
        
        team_layout = QVBoxLayout(team_container)
        team_layout.setContentsMargins(20, 20, 20, 20)
        
        # Team Header
        team_header = QHBoxLayout()
        team_title = QLabel("Equipo de Ventas")
        team_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        team_title.setStyleSheet("color: #2c3e50; border: none;")
        
        self.goal_label = QLabel("Meta: $0")
        self.goal_label.setFont(QFont("Segoe UI", 9))
        self.goal_label.setStyleSheet("color: #7f8c8d; border: none;")
        
        team_header.addWidget(team_title)
        team_header.addStretch()
        team_header.addWidget(self.goal_label)
        
        team_layout.addLayout(team_header)
        
        # Scroll Area for list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        self.team_list_widget = QWidget()
        self.team_list_widget.setStyleSheet("background: transparent;")
        self.team_list_layout = QVBoxLayout(self.team_list_widget)
        self.team_list_layout.setContentsMargins(0, 10, 0, 0)
        self.team_list_layout.setSpacing(0)
        self.team_list_layout.addStretch()
        
        scroll.setWidget(self.team_list_widget)
        team_layout.addWidget(scroll)
        
        # Add to content layout
        content_layout.addWidget(chart_container, 2) # Chart takes 2/3
        content_layout.addWidget(team_container, 1)  # Team takes 1/3
        
        main_layout.addLayout(content_layout)
        main_layout.addStretch()

    def refresh_data(self):
        """Actualizar todos los datos del dashboard."""
        try:
            with self._session_factory() as session:
                filter_user = None
                if not self._can_view_all_sales:
                    filter_user = self._current_user

                # Actualizar KPIs
                kpis = get_dashboard_kpis(session, filter_user=filter_user)
                self.kpi_cards["Clientes"].update_value(str(kpis['total_customers']))
                self.kpi_cards["Ventas del Mes"].update_value(f"${kpis['monthly_sales']:,.2f}")
                self.kpi_cards["Pedidos del Mes"].update_value(str(kpis['monthly_orders']))
                self.kpi_cards["Ventas Hoy"].update_value(f"${kpis['today_sales']:,.2f}")
                
                # Actualizar meta actual
                current_goal = get_monthly_sales_goal(session)
                self.goal_label.setText(f"Meta: ${current_goal:,.0f}")
                
                # Actualizar gráfico diario
                self.update_daily_chart(session, filter_user=filter_user)
                
                # Actualizar lista de vendedores (Mostrar TODOS para motivar, sin filtro)
                self.update_sales_team_list(session, current_goal, filter_user=None)
                
        except Exception as e:
            print(f"Error actualizando datos del dashboard: {e}")

    def update_daily_chart(self, session, filter_user=None):
        try:
            daily_data = get_daily_sales_data(session, days_back=7, filter_user=filter_user)
            self.chart.removeAllSeries()
            
            # Remove axes properly
            for axis in self.chart.axes():
                self.chart.removeAxis(axis)
            
            if daily_data['daily_data']:
                series = QBarSeries()
                series.setBarWidth(0.5) # Barras más delgadas
                
                bar_set = QBarSet("Ventas")
                
                # Gradient Color
                gradient = QLinearGradient(0, 0, 0, 1)
                gradient.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
                gradient.setColorAt(0.0, QColor("#FF9F43")) # Naranja más claro arriba
                gradient.setColorAt(1.0, QColor("#FF6900")) # Naranja base abajo
                bar_set.setBrush(QBrush(gradient))
                bar_set.setBorderColor(QColor("#FF6900"))
                
                categories = []
                max_val = 0
                
                for day_info in daily_data['daily_data']:
                    day_label = day_info['date'].strftime("%d/%m")
                    categories.append(day_label)
                    val = day_info['total_sales']
                    bar_set.append(val)
                    if val > max_val: max_val = val
                
                series.append(bar_set)
                self.chart.addSeries(series)
                
                # Axes Styling
                axis_x = QBarCategoryAxis()
                axis_x.append(categories)
                axis_x.setGridLineVisible(False)
                axis_x.setLabelsFont(QFont("Segoe UI", 9))
                axis_x.setLabelsColor(QColor("#7f8c8d"))
                self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
                series.attachAxis(axis_x)
                
                axis_y = QValueAxis()
                axis_y.setRange(0, max_val * 1.1 if max_val > 0 else 100) # 10% padding
                axis_y.setLabelFormat("$%.0f")
                axis_y.setLabelsFont(QFont("Segoe UI", 9))
                axis_y.setLabelsColor(QColor("#7f8c8d"))
                axis_y.setGridLineColor(QColor("#f0f0f0"))
                self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
                series.attachAxis(axis_y)
                
                self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
                
        except Exception as e:
            print(f"Error chart: {e}")

    def update_sales_team_list(self, session, goal, filter_user=None):
        try:
            # Clear list (keep stretch at end)
            while self.team_list_layout.count() > 1:
                item = self.team_list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            sales_data = get_sales_by_user(session, filter_user=filter_user)
            if not sales_data:
                lbl = QLabel("Sin ventas registradas")
                lbl.setStyleSheet("color: #999; padding: 20px;")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.team_list_layout.insertWidget(0, lbl)
                return

            sales_data_sorted = sorted(sales_data, key=lambda x: x['total_sales'], reverse=True)
            
            for data in sales_data_sorted:
                # Use individual goal if > 0, else fallback to global goal
                user_goal = data.get('monthly_goal', 0.0)
                target_goal = user_goal if user_goal > 0 else goal
                
                item = VendorListItem(data['asesor'], data['total_sales'], target_goal)
                self.team_list_layout.insertWidget(self.team_list_layout.count()-1, item)
                
        except Exception as e:
            print(f"Error team list: {e}")

    def change_sales_goal(self):
        """Abrir diálogo para cambiar la meta de ventas por usuario."""
        dialog = UserGoalsDialog(self._session_factory, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.save_goals()
            QMessageBox.information(self, "Metas Actualizadas", "Las metas mensuales han sido actualizadas.")
            self.refresh_data()

    def _check_can_view_all_sales(self) -> bool:
        try:
            with self._session_factory() as session:
                from ..models import User
                from ..repository import user_has_role
                user = session.query(User).filter(User.username == self._current_user).first()
                if not user: return False
                is_admin = user_has_role(session, user_id=user.id, role_name="ADMIN")
                is_administracion = user_has_role(session, user_id=user.id, role_name="ADMINISTRACION")
                return is_admin or is_administracion
        except Exception:
            return False
