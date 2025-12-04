from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QSplitter, QGroupBox, QScrollArea, QDialog, QFormLayout,
    QDoubleSpinBox, QDialogButtonBox, QMessageBox
)
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QBarSeries, QBarSet
from PySide6.QtGui import QPainter, QFont, QColor
from PySide6.QtCore import Qt, QTimer, Signal
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

# Sin matplotlib - usar solo PySide6 Charts

from ..repository import (
    get_dashboard_kpis, get_sales_by_user, get_weekly_sales_data,
    get_monthly_sales_goal, set_monthly_sales_goal
)


class KpiCard(QFrame):
    def __init__(self, title: str, value: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("KpiCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame#KpiCard {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: #f8f9fa;
                margin: 5px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setProperty("kpiTitle", True)
        self.title_lbl.setFont(QFont("", 9, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet("color: #666;")
        
        self.value_lbl = QLabel(value)
        self.value_lbl.setProperty("kpiValue", True)
        self.value_lbl.setFont(QFont("", 14, QFont.Weight.Bold))
        # KPI value en naranja para destacar
        self.value_lbl.setStyleSheet("color: #FF6900;")
        self.value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)
    
    def update_value(self, new_value: str):
        """Actualizar el valor mostrado en la tarjeta KPI."""
        self.value_lbl.setText(new_value)


class HomeView(QWidget):
    def __init__(self, session_factory: sessionmaker, current_user: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._current_user = current_user or "—"
        self._can_view_all_sales = self._check_can_view_all_sales()
        
        root = QVBoxLayout(self)

        # Saludo con el usuario actual (si está disponible en MainWindow)
        try:
            mw = self.window()
            user = getattr(mw, "_current_user", None)
            if user:
                greet = QLabel(f"Hola, {user}")
                greet.setProperty("homeGreeting", True)
                root.addWidget(greet)
        except Exception:
            pass

        # KPIs row
        self.kpis_layout = QHBoxLayout()
        self.kpi_cards = {}
        self.setup_kpi_cards()
        root.addLayout(self.kpis_layout)
        
        # Splitter para dividir gráficos y lista de vendedores
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo - Gráficos
        charts_widget = QWidget()
        charts_layout = QVBoxLayout(charts_widget)
        
        # Gráfico de ventas semanales
        self.setup_weekly_chart(charts_layout)
        
        # Panel derecho - Lista de vendedores y configuración
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Configuración de meta (solo para admin)
        self.setup_goal_config(right_layout)
        
        # Lista de vendedores
        self.setup_sales_team_list(right_layout)
        
        # Agregar al splitter
        splitter.addWidget(charts_widget)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)  # Gráficos ocupan más espacio
        splitter.setStretchFactor(1, 1)  # Lista menos espacio
        
        root.addWidget(splitter, 1)
        
        # Timer para actualizar datos automáticamente
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_data)
        self.update_timer.start(30000)  # Actualizar cada 30 segundos
        
        # Cargar datos iniciales
        self.refresh_data()

    def setup_kpi_cards(self):
        """Configurar las tarjetas KPI."""
        kpi_names = ["Clientes", "Ventas del Mes", "Pedidos del Mes", "Ventas Hoy"]
        for name in kpi_names:
            card = KpiCard(name, "Cargando...")
            self.kpi_cards[name] = card
            self.kpis_layout.addWidget(card)
    
    def setup_weekly_chart(self, layout):
        """Configurar el gráfico de ventas semanales."""
        chart_group = QGroupBox("📊 Ventas Semanales")
        chart_layout = QVBoxLayout(chart_group)
        
        # Crear gráfico con PySide6 Charts
        self.chart = QChart()
        self.chart.setTitle("Ventas por Semana")
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        chart_layout.addWidget(self.chart_view)
        layout.addWidget(chart_group)
    
    def setup_goal_config(self, layout):
        """Configurar panel de configuración de meta (solo para admin)."""
        if self._can_view_all_sales:
            goal_group = QGroupBox("⚙️ Configuración de Meta")
            goal_layout = QVBoxLayout(goal_group)
            
            # Botón para cambiar meta
            self.change_goal_btn = QPushButton("Cambiar Meta Mensual")
            self.change_goal_btn.clicked.connect(self.change_sales_goal)
            goal_layout.addWidget(self.change_goal_btn)
            
            # Label para mostrar meta actual
            self.current_goal_label = QLabel("Meta actual: Cargando...")
            goal_layout.addWidget(self.current_goal_label)
            
            layout.addWidget(goal_group)
    
    def setup_sales_team_list(self, layout):
        """Configurar la lista de vendedores con progreso."""
        team_group = QGroupBox("👥 Equipo de Ventas - Progreso Mensual")
        team_layout = QVBoxLayout(team_group)
        
        # Cabecera de la lista
        header_widget = QFrame()
        header_widget.setStyleSheet("""
            QFrame { 
                background-color: #e9ecef; 
                border: 1px solid #dee2e6; 
                border-radius: 4px; 
                margin: 2px;
                padding: 8px;
            }
        """)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        name_header = QLabel("Vendedor")
        name_header.setFont(QFont("", 9, QFont.Weight.Bold))
        name_header.setStyleSheet("color: #495057;")
        name_header.setMinimumWidth(120)
        
        total_header = QLabel("Total Vendido")
        total_header.setFont(QFont("", 9, QFont.Weight.Bold))
        total_header.setStyleSheet("color: #495057;")
        total_header.setAlignment(Qt.AlignmentFlag.AlignRight)
        total_header.setMinimumWidth(80)
        
        percentage_header = QLabel("% Meta")
        percentage_header.setFont(QFont("", 9, QFont.Weight.Bold))
        percentage_header.setStyleSheet("color: #495057;")
        percentage_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        percentage_header.setMinimumWidth(50)
        
        header_layout.addWidget(name_header)
        header_layout.addWidget(total_header)
        header_layout.addWidget(percentage_header)
        
        team_layout.addWidget(header_widget)
        
        # Scroll area para la lista
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(300)
        
        self.sales_team_widget = QWidget()
        self.sales_team_layout = QVBoxLayout(self.sales_team_widget)
        
        scroll_area.setWidget(self.sales_team_widget)
        team_layout.addWidget(scroll_area)
        
        layout.addWidget(team_group)
    
    def refresh_data(self):
        """Actualizar todos los datos del dashboard."""
        try:
            with self._session_factory() as session:
                # Actualizar KPIs
                kpis = get_dashboard_kpis(session)
                self.kpi_cards["Clientes"].update_value(str(kpis['total_customers']))
                self.kpi_cards["Ventas del Mes"].update_value(f"${kpis['monthly_sales']:,.2f}")
                self.kpi_cards["Pedidos del Mes"].update_value(str(kpis['monthly_orders']))
                self.kpi_cards["Ventas Hoy"].update_value(f"${kpis['today_sales']:,.2f}")
                
                # Actualizar meta actual
                current_goal = get_monthly_sales_goal(session)
                if hasattr(self, 'current_goal_label'):
                    self.current_goal_label.setText(f"Meta actual: ${current_goal:,.2f}")
                
                # Actualizar gráfico semanal
                self.update_weekly_chart(session)
                
                # Actualizar lista de vendedores
                self.update_sales_team_list(session, current_goal)
                
        except Exception as e:
            print(f"Error actualizando datos del dashboard: {e}")
    
    def update_weekly_chart(self, session):
        """Actualizar el gráfico de ventas semanales."""
        try:
            weekly_data = get_weekly_sales_data(session)
            
            # Limpiar series anteriores
            self.chart.removeAllSeries()
            
            if weekly_data['weekly_data'] and len(weekly_data['weekly_data']) > 0:
                # Crear serie de barras
                series = QBarSeries()
                bar_set = QBarSet("Ventas")
                
                categories = []
                
                for week_info in weekly_data['weekly_data']:
                    week_start = week_info['week_start']
                    sales_amount = week_info['total_sales']
                    
                    # Formatear fecha para mostrar
                    week_label = week_start.strftime("%d/%m")
                    categories.append(week_label)
                    bar_set.append(sales_amount)
                
                # Color naranja para las barras
                bar_set.setColor(QColor("#FF6900"))
                series.append(bar_set)
                self.chart.addSeries(series)
                
                # Crear ejes
                self.chart.createDefaultAxes()
                
                # Configurar título
                self.chart.setTitle("Ventas por Semana (USD)")
                
                # Configurar leyenda
                self.chart.legend().setVisible(True)
                self.chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
                
            else:
                # Mostrar mensaje cuando no hay datos
                self.chart.setTitle("Ventas por Semana - Sin datos disponibles")
                
        except Exception as e:
            print(f"Error actualizando gráfico semanal: {e}")
            self.chart.setTitle("Error cargando datos de ventas")
    
    def update_sales_team_list(self, session, goal):
        """Actualizar la lista de vendedores con progreso."""
        try:
            # Limpiar lista actual
            for i in reversed(range(self.sales_team_layout.count())):
                child = self.sales_team_layout.itemAt(i).widget()
                if child:
                    child.setParent(None)
            
            # Obtener datos de ventas por usuario
            sales_data = get_sales_by_user(session)
            
            if not sales_data:
                no_data_label = QLabel("No hay datos de ventas este mes")
                no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                no_data_label.setStyleSheet("color: #666; font-style: italic; padding: 20px;")
                self.sales_team_layout.addWidget(no_data_label)
                return
            
            # Ordenar por total de ventas (de mayor a menor)
            sales_data_sorted = sorted(sales_data, key=lambda x: x['total_sales'], reverse=True)
            
            # Crear widget para cada vendedor con alternancia de colores
            for i, data in enumerate(sales_data_sorted):
                vendor_widget = self.create_vendor_widget(data, goal, i % 2 == 0)
                self.sales_team_layout.addWidget(vendor_widget)
            
            # Agregar espacio flexible al final
            self.sales_team_layout.addStretch()
            
        except Exception as e:
            print(f"Error actualizando lista de vendedores: {e}")
    
    def create_vendor_widget(self, sales_data, goal, is_even=True):
        """Crear widget individual simplificado para cada vendedor."""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Shape.Box)
        
        # Alternar color de fondo
        bg_color = "#fafafa" if is_even else "#f0f0f0"
        
        widget.setStyleSheet(f"""
            QFrame {{ 
                margin: 1px; 
                padding: 6px; 
                border: 1px solid #e0e0e0; 
                border-radius: 3px; 
                background-color: {bg_color};
            }}
        """)
        
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Calcular porcentaje respecto a la meta
        percentage = (sales_data['total_sales'] / goal) * 100 if goal > 0 else 0
        
        # Nombre del vendedor
        name_label = QLabel(sales_data['asesor'])
        name_label.setFont(QFont("", 9, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #333;")
        name_label.setMinimumWidth(120)
        
        # Total vendido
        total_label = QLabel(f"${sales_data['total_sales']:,.2f}")
        total_label.setFont(QFont("", 9))
        total_label.setStyleSheet("color: #FF6900; font-weight: bold;")
        total_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        total_label.setMinimumWidth(80)
        
        # Porcentaje de la meta
        percentage_label = QLabel(f"{percentage:.1f}%")
        percentage_label.setFont(QFont("", 9, QFont.Weight.Bold))
        percentage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        percentage_label.setMinimumWidth(50)
        
        # Color del porcentaje según progreso
        if percentage >= 100:
            percentage_label.setStyleSheet("color: #28a745; font-weight: bold;")  # Verde
        elif percentage >= 75:
            percentage_label.setStyleSheet("color: #ffc107; font-weight: bold;")  # Amarillo
        else:
            percentage_label.setStyleSheet("color: #dc3545; font-weight: bold;")  # Rojo
        
        layout.addWidget(name_label)
        layout.addWidget(total_label)
        layout.addWidget(percentage_label)
        
        return widget
    
    def change_sales_goal(self):
        """Abrir diálogo para cambiar la meta de ventas."""
        try:
            with self._session_factory() as session:
                current_goal = get_monthly_sales_goal(session)
                
            dialog = QDialog(self)
            dialog.setWindowTitle("Cambiar Meta Mensual")
            dialog.setModal(True)
            dialog.resize(300, 150)
            
            layout = QFormLayout(dialog)
            
            # SpinBox para la meta
            goal_spinbox = QDoubleSpinBox()
            goal_spinbox.setRange(0, 999999)
            goal_spinbox.setValue(current_goal)
            goal_spinbox.setPrefix("$ ")
            goal_spinbox.setDecimals(2)
            
            layout.addRow("Nueva meta mensual:", goal_spinbox)
            
            # Botones
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addRow(buttons)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_goal = goal_spinbox.value()
                
                with self._session_factory() as session:
                    set_monthly_sales_goal(session, new_goal)
                
                QMessageBox.information(
                    self, 
                    "Meta Actualizada", 
                    f"La meta mensual se ha actualizado a ${new_goal:,.2f}"
                )
                
                # Refrescar datos
                self.refresh_data()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cambiar la meta: {e}")
    
    def _check_can_view_all_sales(self) -> bool:
        """Verifica si el usuario actual puede ver todas las ventas o solo las suyas."""
        try:
            with self._session_factory() as session:
                from ..models import User
                from ..repository import user_has_role
                
                # Buscar el usuario actual
                user = session.query(User).filter(User.username == self._current_user).first()
                if not user:
                    return False
                
                # Si el usuario tiene rol ADMIN o ADMINISTRACION, puede ver todas las ventas
                is_admin = user_has_role(session, user_id=user.id, role_name="ADMIN")
                is_administracion = user_has_role(session, user_id=user.id, role_name="ADMINISTRACION")
                
                return is_admin or is_administracion
        except Exception:
            return False
