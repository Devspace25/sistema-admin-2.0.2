from __future__ import annotations

from datetime import date, datetime, timedelta
from sqlalchemy.orm import sessionmaker
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QMessageBox, QDialog, QFormLayout,
    QTextEdit, QDateEdit, QGroupBox, QDialogButtonBox, QFrame, QScrollArea,
    QApplication, QTabWidget, QToolButton, QCheckBox, QGridLayout
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont, QColor

from ..db import make_session_factory, make_engine
from ..repository import (
    check_daily_report_status, get_daily_sales_data, create_daily_report,
    get_pending_reports, list_daily_reports
)
from ..receipts import print_daily_report_excel_pdf


class DailyReportsView(QWidget):
    """Vista para gestionar reportes diarios de ventas."""

    def __init__(self, session_factory: sessionmaker | None = None, parent=None, current_user: str | None = None):
        super().__init__(parent)
        # Si no se pasa session_factory, crear uno
        if session_factory is None:
            engine = make_engine()
            session_factory = make_session_factory(engine)
        self._session_factory = session_factory
        self._current_user = current_user or "—"
        self._can_view_all_sales = self._check_can_view_all_sales()
        self._can_edit = True # Default, updated by set_permissions
        self.setWindowTitle("Reportes Diarios")
        self._setup_ui()
        self._load_data()

    def set_permissions(self, permissions: set[str]):
        """Configurar permisos."""
        # Por ahora solo usamos esto para habilitar/deshabilitar generación
        # Podríamos tener un permiso específico 'create_daily_reports'
        self._can_edit = "view_daily_reports" in permissions 
        
        self.btn_generate_today.setVisible(self._can_edit)
        self.btn_generate_custom.setVisible(self._can_edit)

    def refresh(self):
        """Alias para _load_data compatible con la interfaz común."""
        self._load_data()

    def _setup_ui(self):
        """Configurar la interfaz de usuario."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Título
        title = QLabel("📊 Reportes Diarios de Ventas")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Sección de alertas/pendientes
        self._setup_alerts_section(layout)

        # Sección de acciones rápidas
        self._setup_actions_section(layout)

        # Tabla de reportes existentes
        self._setup_reports_table(layout)

    def _setup_alerts_section(self, layout):
        """Configurar sección de alertas de reportes pendientes."""
        # Agregar mensaje informativo para usuarios no-admin
        if not self._check_can_view_all_sales():
            info_group = QGroupBox("ℹ️ Información")
            info_layout = QVBoxLayout(info_group)

            info_label = QLabel("Nota: Como vendedor, solo puedes ver tus propias ventas en los reportes.")
            info_label.setStyleSheet("color: #9ca3af; font-weight: bold; padding: 8px;")
            info_layout.addWidget(info_label)

            layout.addWidget(info_group)
        
        self.alerts_group = QGroupBox("⚠️ Reportes Pendientes")
        self.alerts_group_layout = QVBoxLayout(self.alerts_group)
        self.alerts_group_layout.setContentsMargins(10, 15, 10, 10)
        
        # 1. Widget para cuando NO hay alertas (Compacto)
        self.no_alerts_widget = QWidget()
        no_alerts_layout = QHBoxLayout(self.no_alerts_widget)
        no_alerts_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_icon = QLabel("✅")
        lbl_icon.setStyleSheet("font-size: 14px;")
        lbl_msg = QLabel("Todo al día. No hay reportes pendientes.")
        lbl_msg.setStyleSheet("color: #4ade80; font-weight: bold;")
        
        no_alerts_layout.addStretch()
        no_alerts_layout.addWidget(lbl_icon)
        no_alerts_layout.addWidget(lbl_msg)
        no_alerts_layout.addStretch()
        
        self.alerts_group_layout.addWidget(self.no_alerts_widget)

        # 2. ScrollArea para cuando SI hay alertas
        self.alerts_container = QScrollArea()
        self.alerts_container.setMaximumHeight(120) # Altura reducida
        self.alerts_container.setWidgetResizable(True)
        self.alerts_container.setFrameShape(QFrame.Shape.NoFrame)
        self.alerts_container.setStyleSheet("background: transparent;")
        
        self.alerts_content_widget = QWidget()
        self.alerts_content_widget.setStyleSheet("background: transparent;")
        self.alerts_list_layout = QVBoxLayout(self.alerts_content_widget)
        self.alerts_list_layout.setContentsMargins(0, 0, 0, 0)
        self.alerts_list_layout.setSpacing(5)
        
        self.alerts_container.setWidget(self.alerts_content_widget)
        self.alerts_group_layout.addWidget(self.alerts_container)
        
        layout.addWidget(self.alerts_group)

    def _setup_actions_section(self, layout):
        """Configurar sección de acciones rápidas."""
        actions_group = QGroupBox("🔧 Acciones Rápidas")
        actions_layout = QHBoxLayout(actions_group)

        # Botón para generar reporte de hoy
        self.btn_generate_today = QPushButton("📈 Generar Reporte de Hoy")
        self.btn_generate_today.setProperty("accent", "primary")
        self.btn_generate_today.clicked.connect(self._generate_today_report)
        actions_layout.addWidget(self.btn_generate_today)

        # Botón para generar reporte de fecha específica
        self.btn_generate_custom = QPushButton("📅 Generar Reporte de Fecha Específica")
        # Marcar como primario para aplicar el acento vía QSS
        self.btn_generate_custom.setProperty("accent", "primary")
        self.btn_generate_custom.clicked.connect(self._generate_custom_report)
        actions_layout.addWidget(self.btn_generate_custom)

        # Botón para refrescar
        self.btn_refresh = QPushButton("🔄 Actualizar")
        self.btn_refresh.clicked.connect(self._load_data)
        actions_layout.addWidget(self.btn_refresh)

        actions_layout.addStretch()
        layout.addWidget(actions_group)

    def _setup_reports_table(self, layout):
        """Configurar tabla de reportes existentes."""
        reports_group = QGroupBox("📋 Reportes Generados")
        reports_layout = QVBoxLayout(reports_group)

        self.reports_table = QTableWidget()
        self.reports_table.setColumnCount(9)
        self.reports_table.setHorizontalHeaderLabels([
            "Fecha", "Estado", "Ventas", "Total USD", "Total Bs", "Abono USD", "Restante", "Ingresos USD", "Ver Detalles"
        ])

        # Configurar tabla
        header = self.reports_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Fecha
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Estado
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Ventas
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Total USD
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Total Bs
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Abono USD
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # Restante
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)  # Ingresos USD
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)  # Ver Detalles

        self.reports_table.setAlternatingRowColors(True)
        self.reports_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        reports_layout.addWidget(self.reports_table)
        layout.addWidget(reports_group)

    def _load_data(self):
        """Cargar datos de reportes y alertas."""
        self._load_pending_alerts()
        self._load_reports_table()
        self._update_today_button_status()

    def _load_pending_alerts(self):
        """Cargar alertas de reportes pendientes."""
        # Limpiar alertas anteriores
        for i in reversed(range(self.alerts_list_layout.count())):
            child = self.alerts_list_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        try:
            with self._session_factory() as session:
                pending = get_pending_reports(session, days_back=7)
                
                if not pending:
                    # Mostrar estado "Todo OK"
                    self.no_alerts_widget.setVisible(True)
                    self.alerts_container.setVisible(False)
                    # Estilo relajado y compacto
                    self.alerts_group.setStyleSheet("QGroupBox { border: 1px solid #334155; border-radius: 6px; margin-top: 10px; } QGroupBox::title { color: #94a3b8; }")
                else:
                    # Mostrar lista de alertas
                    self.no_alerts_widget.setVisible(False)
                    self.alerts_container.setVisible(True)
                    # Estilo de advertencia
                    self.alerts_group.setStyleSheet("QGroupBox { border: 1px solid #f59e0b; border-radius: 6px; margin-top: 10px; } QGroupBox::title { color: #f59e0b; font-weight: bold; }")
                    
                    for status in pending:
                        alert_frame = QFrame()
                        alert_frame.setStyleSheet("QFrame { background-color: #451a03; border: 1px solid #78350f; border-radius: 4px; padding: 4px; }")
                        alert_layout = QHBoxLayout(alert_frame)
                        alert_layout.setContentsMargins(8, 4, 8, 4)
                        
                        alert_text = QLabel(f"⚠️ Falta reporte del {status['date'].strftime('%d/%m/%Y')} ({status['sales_count']} ventas)")
                        alert_text.setStyleSheet("font-weight: bold; color: #fbbf24; border: none; background: transparent;")
                        alert_layout.addWidget(alert_text)
                        
                        alert_layout.addStretch()
                        
                        # Botón para generar reporte de esa fecha
                        btn_generate = QPushButton("Generar")
                        btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
                        btn_generate.setStyleSheet("QPushButton { background-color: #f59e0b; color: #000; border: none; border-radius: 3px; padding: 2px 10px; font-weight: bold; } QPushButton:hover { background-color: #fbbf24; }")
                        btn_generate.clicked.connect(
                            lambda checked, d=status['date']: self._generate_report_for_date(d)
                        )
                        alert_layout.addWidget(btn_generate)
                        
                        self.alerts_list_layout.addWidget(alert_frame)

        except Exception as e:
            # Fallback error display
            self.no_alerts_widget.setVisible(False)
            self.alerts_container.setVisible(True)
            error_label = QLabel(f"❌ Error al cargar alertas: {str(e)}")
            error_label.setStyleSheet("color: #ef4444; font-weight: bold; padding: 10px;")
            self.alerts_list_layout.addWidget(error_label)

    def _load_reports_table(self):
        """Cargar tabla de reportes existentes."""
        try:
            with self._session_factory() as session:
                reports = list_daily_reports(session, limit=50)
                
                self.reports_table.setRowCount(len(reports))
                
                for row, report in enumerate(reports):
                    # Parsear datos del reporte para obtener totales completos
                    import json
                    report_data = {}
                    try:
                        if report.report_data_json:
                            report_data = json.loads(report.report_data_json)
                    except:
                        pass
                    
                    totals = report_data.get('totals', {})
                    
                    # Fecha
                    self.reports_table.setItem(row, 0, QTableWidgetItem(
                        report.report_date.strftime("%d/%m/%Y")
                    ))
                    
                    # Estado
                    status_item = QTableWidgetItem(report.report_status)
                    status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if report.report_status == "GENERADO":
                        status_item.setForeground(QColor("#00ff00"))
                        font = status_item.font()
                        font.setBold(True)
                        status_item.setFont(font)
                    elif report.report_status == "PENDIENTE":
                        status_item.setForeground(QColor("#ffcc00"))
                        font = status_item.font()
                        font.setBold(True)
                        status_item.setFont(font)
                    self.reports_table.setItem(row, 1, status_item)
                    
                    # Ventas
                    self.reports_table.setItem(row, 2, QTableWidgetItem(str(report.total_sales)))
                    
                    # Total USD
                    self.reports_table.setItem(row, 3, QTableWidgetItem(f"${report.total_amount_usd:,.2f}"))
                    
                    # Total Bs
                    self.reports_table.setItem(row, 4, QTableWidgetItem(f"Bs. {report.total_amount_bs:,.2f}"))
                    
                    # Abono USD
                    abono_usd = totals.get('total_abono_usd', 0.0)
                    self.reports_table.setItem(row, 5, QTableWidgetItem(f"${abono_usd:,.2f}"))
                    
                    # Restante
                    restante = totals.get('total_restante', 0.0)
                    self.reports_table.setItem(row, 6, QTableWidgetItem(f"${restante:,.2f}"))
                    
                    # Ingresos USD
                    self.reports_table.setItem(row, 7, QTableWidgetItem(f"${report.total_ingresos_usd:,.2f}"))
                    
                    # Botón Ver Detalles
                    btn_details = QPushButton("📊 Ver")
                    btn_details.clicked.connect(
                        lambda checked, r=report: self._show_report_details(r)
                    )
                    self.reports_table.setCellWidget(row, 8, btn_details)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar reportes: {str(e)}")

    def _update_today_button_status(self):
        """Actualizar estado del botón de reporte de hoy."""
        try:
            with self._session_factory() as session:
                today_status = check_daily_report_status(session)
                
                if today_status['has_report']:
                    self.btn_generate_today.setText("✅ Reporte de Hoy Generado")
                    self.btn_generate_today.setEnabled(False)
                elif today_status['sales_count'] == 0:
                    self.btn_generate_today.setText("📈 Sin Ventas Hoy")
                    self.btn_generate_today.setEnabled(False)
                else:
                    self.btn_generate_today.setText(f"📈 Generar Reporte de Hoy ({today_status['sales_count']} ventas)")
                    self.btn_generate_today.setEnabled(True)

        except Exception as e:
            print(f"Error al actualizar botón: {e}")

    def _generate_today_report(self):
        """Generar reporte para el día de hoy."""
        self._generate_report_for_date(date.today())

    def _generate_custom_report(self):
        """Mostrar diálogo para generar reporte de fecha específica."""
        dialog = CustomReportDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            target_date = dialog.get_selected_date()
            self._generate_report_for_date(target_date)

    def _generate_report_for_date(self, target_date: date):
        """Generar reporte para una fecha específica."""
        try:
            with self._session_factory() as session:
                # Verificar estado actual - convertir date a datetime
                from datetime import datetime as dt
                target_datetime = dt.combine(target_date, dt.min.time())
                status = check_daily_report_status(session, target_datetime)
                
                if status['has_report']:
                    QMessageBox.information(
                        self, "Información", 
                        f"Ya existe un reporte para el {target_date.strftime('%d/%m/%Y')}"
                    )
                    return
                
                if status['sales_count'] == 0:
                    QMessageBox.warning(
                        self, "Advertencia", 
                        f"No hay ventas registradas para el {target_date.strftime('%d/%m/%Y')}"
                    )
                    return
                
                # Obtener usuario actual y determinar filtros
                from ..models import User
                current_user = session.query(User).filter(User.username == self._current_user).first()
                current_user_id = current_user.id if current_user else 1
                
                # Aplicar filtro por usuario si no es admin/administración
                user_filter = None if self._can_view_all_sales else self._current_user
                
                # Generar reporte con filtro apropiado
                from datetime import datetime
                target_datetime = datetime.combine(target_date, datetime.min.time())
                report = create_daily_report(session, current_user_id, target_datetime, user_filter=user_filter)
                
                QMessageBox.information(
                    self, "Éxito", 
                    f"Reporte generado exitosamente para el {target_date.strftime('%d/%m/%Y')}\n"
                    f"Total de ventas: {report.total_sales}\n"
                    f"Total USD: ${report.total_amount_usd:,.2f}\n"
                    f"Total Ingresos: ${report.total_ingresos_usd:,.2f}"
                )
                
                # Recargar datos
                self._load_data()

        except ValueError as e:
            QMessageBox.warning(self, "Advertencia", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al generar reporte: {str(e)}")

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

    def _show_report_details(self, report):
        """Mostrar detalles completos de un reporte."""
        try:
            dialog = ReportDetailsDialog(report, self, self._current_user, self._can_view_all_sales)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al mostrar detalles del reporte:\n{str(e)}")
            print(f"Error en _show_report_details: {e}")
            import traceback
            traceback.print_exc()


class ReportDetailsDialog(QDialog):
    """Diálogo que muestra todos los detalles de un reporte diario con una interfaz mejorada."""

    def __init__(self, report, parent=None, current_user: str | None = None, can_view_all_sales: bool = True):
        super().__init__(parent)
        self.report = report
        self._current_user = current_user or "—"
        self._can_view_all_sales = can_view_all_sales
        self.setWindowTitle(f"Reporte Detallado - {report.report_date.strftime('%d/%m/%Y')}")
        self.setModal(True)
        self._setup_responsive_size()
        self._setup_ui()

    def _setup_responsive_size(self):
        """Configurar tamaño optimizado para tabla de ventas."""
        self.resize(1300, 700)
        self.setMinimumSize(1000, 600)

    def _setup_ui(self):
        """Configurar interfaz del diálogo."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Fondo oscuro general
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")

        # Parsear datos del reporte
        import json
        self.report_data = {}
        try:
            if hasattr(self.report, 'report_data_json') and self.report.report_data_json:
                self.report_data = json.loads(self.report.report_data_json)
            else:
                self.report_data = {
                    'totals': {
                        'total_sales': getattr(self.report, 'total_sales', 0),
                        'total_amount_usd': getattr(self.report, 'total_amount_usd', 0),
                        'total_amount_bs': getattr(self.report, 'total_amount_bs', 0),
                        'total_ingresos_usd': getattr(self.report, 'total_ingresos_usd', 0)
                    },
                    'sales_data': []
                }
        except Exception:
            self.report_data = {'totals': {}, 'sales_data': []}

        totals = self.report_data.get('totals', {})

        # 1. Header
        self._create_report_header(layout, totals)
        
        # 2. Tabla
        self._create_main_sales_table(layout, self.report_data)

        # Separador
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #444; margin-top: 10px; margin-bottom: 10px;")
        layout.addWidget(line)

        # 3. Footer (Totales)
        self._create_footer_totals(layout, totals)

        # 4. Botones
        self._create_action_buttons(layout)

    def _create_report_header(self, layout, totals):
        """Crear header con título y resumen de una línea."""
        header_widget = QWidget()
        h_layout = QVBoxLayout(header_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(5)

        # Título Principal
        title_row = QHBoxLayout()
        icon_label = QLabel("📊") # O usar un icono real
        icon_label.setStyleSheet("font-size: 18px; background-color: transparent;")
        
        title_label = QLabel(f"Reporte Diario - {self.report.report_date.strftime('%d/%m/%Y')}")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff; background-color: transparent;")
        
        title_row.addWidget(icon_label)
        title_row.addWidget(title_label)
        title_row.addStretch()
        h_layout.addLayout(title_row)

        # Subtítulo con info
        status = (self.report.report_status or 'GENERADO').upper()
        total_sales = totals.get('total_sales', 0)
        total_usd = totals.get('total_amount_usd', 0.0)
        
        subtitle = QLabel(f"Estado: {status} | Total Ventas: {total_sales} | Total USD: ${total_usd:,.2f}")
        subtitle.setStyleSheet("font-size: 13px; color: #cccccc; font-weight: bold; background-color: transparent;")
        h_layout.addWidget(subtitle)

        layout.addWidget(header_widget)

    def _create_main_sales_table(self, layout, report_data):
        """Crear tabla de ventas."""
        # Título de sección
        title_label = QLabel("📄 Ventas del Día")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; margin-top: 10px; background-color: transparent;")
        layout.addWidget(title_label)

        sales_table = QTableWidget()
        
        # Columnas según imagen
        columns = [
            ('Nº Orden', 80),
            ('Artículo', 150),
            ('Asesor', 100),
            ('Venta $', 80),
            ('Forma Pago', 100),
            ('Serial', 80),
            ('Banco', 80),
            ('Referencia', 80),
            ('Fecha Pago', 90),
            ('Monto Bs', 100),
            ('Monto $', 80),
            ('Abono $', 80),
            ('Restante $', 80),
            ('Por Cobrar', 80),
            ('IVA', 60),
            ('Diseño $', 70),
            ('Inst', 50),
            ('Ingresos $', 80)
        ]
        
        sales_table.setColumnCount(len(columns))
        sales_table.setHorizontalHeaderLabels([c[0] for c in columns])
        
        # Configurar anchos
        for i, (_, width) in enumerate(columns):
            sales_table.setColumnWidth(i, width)

        # Estilo de la tabla (Dark Theme)
        sales_table.setStyleSheet("""
            QTableWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                gridline-color: #444444;
                border: none;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #333333;
                color: #cccccc;
                padding: 5px;
                border: 1px solid #444444;
                font-weight: bold;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #444444;
            }
        """)
        
        sales_table.verticalHeader().setVisible(False)
        
        # Llenar datos
        sales_data = report_data.get('sales_data', []) or []
        if not self._can_view_all_sales and sales_data:
            sales_data = [s for s in sales_data if (s.get('asesor') or '') == (self._current_user or '')]
            
        sales_table.setRowCount(len(sales_data))
        
        from PySide6.QtGui import QColor

        for row, sale in enumerate(sales_data):
            # Helper formatters
            def fmt_usd(v): return f"${(v or 0):,.2f}"
            def fmt_bs(v): return f"Bs. {(v or 0):,.2f}"
            
            # Mapeo de valores a columnas
            # 0: Nº Orden, 1: Artículo, 2: Asesor, 3: Venta $, 4: Forma Pago
            # 5: Serial, 6: Banco, 7: Referencia, 8: Fecha Pago, 9: Monto Bs
            # 10: Monto $, 11: Abono $, 12: Restante $, 13: Por Cobrar, 14: IVA, 15: Diseño $, 16: Inst, 17: Ingresos $
            
            values = [
                sale.get('numero_orden', ''),
                sale.get('articulo', ''),
                sale.get('asesor', ''),
                fmt_usd(sale.get('venta_usd')),
                sale.get('forma_pago', ''),
                sale.get('serial_billete', ''),
                sale.get('banco', ''),
                sale.get('referencia', ''),
                (sale.get('fecha_pago') or '')[:10],
                fmt_bs(sale.get('monto_bs')),
                fmt_usd(sale.get('monto_usd_calculado')), # Monto $ (pagado en esta txn)
                fmt_usd(sale.get('abono_usd')),
                "", # Restante $ (Cobro de deuda - Placeholder)
                fmt_usd(sale.get('restante')), # Por Cobrar (Deuda actual)
                fmt_usd(sale.get('iva')),
                fmt_usd(sale.get('diseno_usd')),
                "0", # Inst (placeholder)
                fmt_usd(sale.get('ingresos_usd'))
            ]
            
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                # Colores específicos
                if col == 13: # Por Cobrar
                    restante = sale.get('restante', 0) or 0
                    if restante > 0.01:
                        item.setForeground(QColor("#ff4d4d")) # Rojo
                    else:
                        item.setForeground(QColor("#cccccc"))
                elif col == 17: # Ingresos $
                    item.setForeground(QColor("#00ff00")) # Verde
                else:
                    item.setForeground(QColor("#ffffff"))
                    
                sales_table.setItem(row, col, item)

        layout.addWidget(sales_table)

    def _create_footer_totals(self, layout, totals):
        """Crear sección de totales al pie."""
        from PySide6.QtWidgets import QCheckBox, QGridLayout
        
        footer_widget = QWidget()
        f_layout = QVBoxLayout(footer_widget)
        f_layout.setContentsMargins(0, 0, 0, 0)
        
        # Checkbox
        chk_totals = QCheckBox("Totales del Día")
        chk_totals.setChecked(True)
        chk_totals.setStyleSheet("QCheckBox { color: #ffffff; font-weight: bold; } QCheckBox::indicator { width: 16px; height: 16px; }")
        chk_totals.setEnabled(False) # Solo visual según imagen
        f_layout.addWidget(chk_totals)
        
        # Grid de totales
        grid = QGridLayout()
        grid.setSpacing(10)
        
        # Helper para etiquetas de totales
        def add_total(row, col, label, value, color="#ffffff"):
            lbl = QLabel(f"{label} {value}")
            lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 13px; background-color: transparent;")
            grid.addWidget(lbl, row, col)

        # Fila 1
        add_total(0, 0, "Total Ventas:", str(totals.get('total_sales', 0)))
        add_total(0, 1, "Total USD:", f"${totals.get('total_amount_usd', 0):,.2f}")
        add_total(0, 2, "Total Bs:", f"Bs. {totals.get('total_amount_bs', 0):,.2f}")
        
        # Fila 2
        add_total(1, 0, "Ingresos USD:", f"${totals.get('total_ingresos_usd', 0):,.2f}", "#00ff00")
        add_total(1, 1, "Abonos USD:", f"${totals.get('total_abono_usd', 0):,.2f}")
        add_total(1, 2, "Por Cobrar:", f"${totals.get('total_restante', 0):,.2f}", "#ff4d4d")
        
        # Fila 3
        # IVA Total, Diseño Total, Cobros Restantes (Calculado o placeholder)
        # Asumimos Cobros Restantes = 0.00 si no está en totals
        add_total(2, 0, "IVA Total:", f"${totals.get('total_iva', 0):,.2f}") # Necesitamos calcular IVA total si no viene
        add_total(2, 1, "Diseño Total:", f"${totals.get('total_diseno', 0):,.2f}") # Necesitamos calcular Diseño total
        add_total(2, 2, "Restante $:", "$0.00", "#00ff00") # Placeholder según imagen

        f_layout.addLayout(grid)
        layout.addWidget(footer_widget)

    def _create_action_buttons(self, layout):
        """Crear botones de acción mejorados."""
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        # Botón Imprimir PDF (Azul)
        btn_print = QPushButton("🖨️ Imprimir PDF")
        btn_print.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_print.setStyleSheet("""
            QPushButton {
                background-color: #007bff; 
                color: white; 
                border: none; 
                padding: 8px 15px; 
                border-radius: 4px; 
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0069d9; }
        """)
        btn_print.clicked.connect(self._print_report)
        btn_layout.addWidget(btn_print)
        
        # Botón Cerrar (Blanco/Gris)
        btn_close = QPushButton("Cerrar")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa; 
                color: #333; 
                border: 1px solid #ddd; 
                padding: 8px 15px; 
                border-radius: 4px; 
                font-weight: bold;
            }
            QPushButton:hover { background-color: #e2e6ea; }
        """)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)

    def _print_report(self):
        """Generar PDF del reporte y abrirlo para imprimir."""
        try:
            # Obtener datos de ventas
            sales_data = self.report_data.get('sales_data', [])
            
            # Generar PDF usando la nueva función
            pdf_path = print_daily_report_excel_pdf(sales_data, self.report.report_date)
            
            if pdf_path and pdf_path.exists():
                # Abrir PDF con aplicación predeterminada
                import subprocess
                subprocess.run(['start', '', str(pdf_path)], shell=True)
                
                QMessageBox.information(self, "Éxito", 
                    "Reporte PDF generado y abierto para imprimir.")
            else:
                QMessageBox.warning(self, "Error", "No se pudo generar el PDF.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al generar PDF: {str(e)}")

    def _export_to_pdf(self):
        """Exportar el reporte directamente a PDF."""
        try:
            from PySide6.QtWidgets import QFileDialog
            import shutil
            
            # Seleccionar ubicación para guardar
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Reporte PDF",
                f"Reporte_Diario_{self.report.report_date.strftime('%Y%m%d')}.pdf",
                "Archivos PDF (*.pdf)"
            )
            
            if filename:
                # Generar PDF
                sales_data = self.report_data.get('sales_data', [])
                pdf_path = print_daily_report_excel_pdf(sales_data, self.report.report_date)
                
                if pdf_path and pdf_path.exists():
                    shutil.copy2(pdf_path, filename)
                    QMessageBox.information(self, "Éxito", "Reporte guardado exitosamente.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al exportar PDF: {str(e)}")


class CustomReportDialog(QDialog):
    """Diálogo para seleccionar fecha para reporte personalizado."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generar Reporte de Fecha Específica")
        self.setModal(True)
        self.resize(300, 150)
        self._setup_ui()

    def _setup_ui(self):
        """Configurar interfaz del diálogo."""
        layout = QVBoxLayout(self)

        # Selector de fecha
        form_layout = QFormLayout()
        
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate().addDays(-1))  # Ayer por defecto
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setMaximumDate(QDate.currentDate())  # No permitir fechas futuras
        form_layout.addRow("Fecha del Reporte:", self.date_edit)
        
        layout.addLayout(form_layout)

        # Botones
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_date(self) -> date:
        """Obtener la fecha seleccionada."""
        qdate = self.date_edit.date()
        return date(qdate.year(), qdate.month(), qdate.day())
