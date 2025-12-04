from __future__ import annotations

from datetime import date, datetime, timedelta
from sqlalchemy.orm import sessionmaker
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QMessageBox, QDialog, QFormLayout,
    QTextEdit, QDateEdit, QGroupBox, QDialogButtonBox, QFrame, QScrollArea,
    QApplication, QTabWidget
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont

from ..db import make_session_factory, make_engine
from ..repository import (
    check_daily_report_status, get_daily_sales_data, create_daily_report,
    get_pending_reports, list_daily_reports
)


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
        self.setWindowTitle("Reportes Diarios")
        self._setup_ui()
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
            info_label.setStyleSheet("color: #0078d4; font-weight: bold; padding: 8px;")
            info_layout.addWidget(info_label)
            
            layout.addWidget(info_group)
        
        alerts_group = QGroupBox("⚠️ Reportes Pendientes")
        alerts_layout = QVBoxLayout(alerts_group)
        
        self.alerts_container = QScrollArea()
        self.alerts_container.setMaximumHeight(150)
        self.alerts_container.setWidgetResizable(True)
        
        self.alerts_widget = QWidget()
        self.alerts_layout = QVBoxLayout(self.alerts_widget)
        self.alerts_container.setWidget(self.alerts_widget)
        
        alerts_layout.addWidget(self.alerts_container)
        layout.addWidget(alerts_group)

    def _setup_actions_section(self, layout):
        """Configurar sección de acciones rápidas."""
        actions_group = QGroupBox("🔧 Acciones Rápidas")
        actions_layout = QHBoxLayout(actions_group)

        # Botón para generar reporte de hoy
        self.btn_generate_today = QPushButton("📈 Generar Reporte de Hoy")
        self.btn_generate_today.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.btn_generate_today.clicked.connect(self._generate_today_report)
        actions_layout.addWidget(self.btn_generate_today)

        # Botón para generar reporte de fecha específica
        self.btn_generate_custom = QPushButton("📅 Generar Reporte de Fecha Específica")
        self.btn_generate_custom.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
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
        for i in reversed(range(self.alerts_layout.count())):
            child = self.alerts_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        try:
            with self._session_factory() as session:
                pending = get_pending_reports(session, days_back=7)
                
                if not pending:
                    # No hay reportes pendientes
                    no_alerts = QLabel("✅ No hay reportes pendientes")
                    no_alerts.setStyleSheet("color: green; font-weight: bold; padding: 10px;")
                    self.alerts_layout.addWidget(no_alerts)
                else:
                    # Mostrar alertas
                    for status in pending:
                        alert_frame = QFrame()
                        alert_frame.setStyleSheet("""
                            QFrame {
                                background-color: #fff3cd;
                                border: 1px solid #ffeaa7;
                                border-radius: 5px;
                                margin: 2px;
                                padding: 5px;
                            }
                        """)
                        alert_layout = QHBoxLayout(alert_frame)
                        
                        alert_text = QLabel(f"⚠️ Falta reporte del {status['date'].strftime('%d/%m/%Y')} ({status['sales_count']} ventas)")
                        alert_text.setStyleSheet("font-weight: bold; color: #856404;")
                        alert_layout.addWidget(alert_text)
                        
                        # Botón para generar reporte de esa fecha
                        btn_generate = QPushButton("Generar")
                        btn_generate.setStyleSheet("""
                            QPushButton {
                                background-color: #ffc107;
                                color: #212529;
                                border: none;
                                padding: 5px 15px;
                                border-radius: 3px;
                                font-weight: bold;
                            }
                            QPushButton:hover {
                                background-color: #e0a800;
                            }
                        """)
                        btn_generate.clicked.connect(
                            lambda checked, d=status['date']: self._generate_report_for_date(d)
                        )
                        alert_layout.addWidget(btn_generate)
                        
                        self.alerts_layout.addWidget(alert_frame)

        except Exception as e:
            error_label = QLabel(f"❌ Error al cargar alertas: {str(e)}")
            error_label.setStyleSheet("color: red; font-weight: bold; padding: 10px;")
            self.alerts_layout.addWidget(error_label)

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
                    if report.report_status == "GENERADO":
                        status_item.setBackground(Qt.GlobalColor.green)
                    elif report.report_status == "PENDIENTE":
                        status_item.setBackground(Qt.GlobalColor.yellow)
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
                    btn_details.setStyleSheet("""
                        QPushButton {
                            background-color: #007bff;
                            color: white;
                            border: none;
                            padding: 5px 10px;
                            border-radius: 3px;
                            font-weight: bold;
                        }
                        QPushButton:hover {
                            background-color: #0056b3;
                        }
                    """)
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
                    self.btn_generate_today.setStyleSheet("""
                        QPushButton {
                            background-color: #6c757d;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 5px;
                            font-weight: bold;
                        }
                    """)
                elif today_status['sales_count'] == 0:
                    self.btn_generate_today.setText("📈 Sin Ventas Hoy")
                    self.btn_generate_today.setEnabled(False)
                    self.btn_generate_today.setStyleSheet("""
                        QPushButton {
                            background-color: #6c757d;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 5px;
                            font-weight: bold;
                        }
                    """)
                else:
                    self.btn_generate_today.setText(f"📈 Generar Reporte de Hoy ({today_status['sales_count']} ventas)")
                    self.btn_generate_today.setEnabled(True)
                    self.btn_generate_today.setStyleSheet("""
                        QPushButton {
                            background-color: #4CAF50;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 5px;
                            font-weight: bold;
                        }
                        QPushButton:hover {
                            background-color: #45a049;
                        }
                    """)

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
        self.setWindowTitle(f"Detalles del Reporte - {report.report_date.strftime('%d/%m/%Y')}")
        self.setModal(True)
        self._setup_responsive_size()
        self._setup_ui()

    def _setup_responsive_size(self):
        """Configurar tamaño responsivo - más pequeño y adaptable."""
        # Tamaño más pequeño y limpio por defecto
        self.resize(850, 600)
        
        # Hacer que la ventana sea redimensionable por el usuario
        self.setMinimumSize(600, 450)
        self.setMaximumSize(1200, 900)

    def _setup_ui(self):
        """Configurar interfaz del diálogo de detalles con diseño limpio y moderno."""
        # Estilo general del diálogo
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Parsear datos del reporte
        import json
        report_data = {}
        try:
            if hasattr(self.report, 'report_data_json') and self.report.report_data_json:
                report_data = json.loads(self.report.report_data_json)
            else:
                print("Warning: Reporte sin datos JSON, usando valores por defecto")
                # Usar valores por defecto si no hay datos JSON
                report_data = {
                    'totals': {
                        'total_sales': getattr(self.report, 'total_sales', 0),
                        'total_amount_usd': getattr(self.report, 'total_amount_usd', 0),
                        'total_amount_bs': getattr(self.report, 'total_amount_bs', 0),
                        'total_monto_usd_calculado': 0,
                        'total_abono_usd': 0,
                        'total_restante': 0,
                        'total_iva': 0,
                        'total_diseno_usd': 0,
                        'total_ingresos_usd': getattr(self.report, 'total_ingresos_usd', 0)
                    },
                    'payment_methods': {},
                    'asesores_summary': {},
                    'sales_data': []
                }
        except Exception as e:
            print(f"Error parseando datos del reporte: {e}")
            QMessageBox.warning(self, "Error", f"No se pudieron cargar los datos detallados del reporte:\n{str(e)}")
            self.reject()
            return

        # Crear nueva interfaz simple
        self._create_simple_header(layout)
        self._create_summary_section(layout, report_data)
        self._create_details_section(layout, report_data)
        self._create_simple_buttons(layout)

    def _create_simple_header(self, layout):
        """Crear encabezado simple y claro."""
        # Título principal
        title = QLabel(f"Reporte Diario - {self.report.report_date.strftime('%d de %B de %Y')}")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px 0;
                border-bottom: 2px solid #e9ecef;
                margin-bottom: 15px;
            }
        """)
        layout.addWidget(title)

        # Información del estado
        status_layout = QHBoxLayout()
        
        status_label = QLabel(f"Estado: {self.report.report_status}")
        status_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        
        date_label = QLabel(f"Generado: {self.report.created_at.strftime('%d/%m/%Y a las %H:%M')}")
        date_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        
        status_layout.addWidget(status_label)
        status_layout.addStretch()
        status_layout.addWidget(date_label)
        
        layout.addLayout(status_layout)
        
        # Separador
        separator = QFrame()
        separator.setFrameStyle(QFrame.HLine)
        separator.setStyleSheet("background-color: #e9ecef; margin: 10px 0;")
        layout.addWidget(separator)

        # Icono y título
        title_layout = QVBoxLayout()
        
        main_title = QLabel(f"📊 Reporte Diario - {self.report.report_date.strftime('%d de %B de %Y')}")
        main_title.setStyleSheet("""
            color: #2c3e50;
            font-size: 20px;
            font-weight: bold;
            margin: 0;
        """)
        
        subtitle = QLabel(f"Estado: {self.report.report_status} • Generado: {self.report.created_at.strftime('%d/%m/%Y a las %H:%M')}")
        subtitle.setStyleSheet("""
            color: #6c757d;
            font-size: 13px;
            margin: 5px 0 0 0;
        """)
        
        title_layout.addWidget(main_title)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)
        
        header_layout.addStretch()
        
        # Badge de estado
        status_badge = QLabel(self.report.report_status)
        status_color = "#28a745" if self.report.report_status == "GENERADO" else "#ffc107"
        text_color = "white" if self.report.report_status == "GENERADO" else "#212529"
        status_badge.setStyleSheet(f"""
            background-color: {status_color};
            color: {text_color};
            padding: 6px 12px;
            border-radius: 15px;
            font-weight: bold;
            font-size: 11px;
        """)
        header_layout.addWidget(status_badge)
        
        layout.addWidget(header_frame)

    def _create_financial_cards(self, layout, totals):
        """Crear tarjetas de resumen financiero."""
        cards_frame = QFrame()
        cards_layout = QHBoxLayout(cards_frame)
        cards_layout.setSpacing(15)

        # Datos para las tarjetas
        card_data = [
            {
                'title': 'Total Ventas',
                'value': str(totals.get('total_sales', 0)),
                'subtitle': 'operaciones',
                'icon': '🛍️',
                'color': '#28a745'
            },
            {
                'title': 'Ingresos USD',
                'value': f"${totals.get('total_ingresos_usd', 0):,.2f}",
                'subtitle': 'dólares americanos',
                'icon': '💰',
                'color': '#17a2b8'
            },
            {
                'title': 'Ventas USD',
                'value': f"${totals.get('total_amount_usd', 0):,.2f}",
                'subtitle': 'valor total',
                'icon': '💵',
                'color': '#007bff'
            },
            {
                'title': 'Pendiente',
                'value': f"${totals.get('total_restante', 0):,.2f}",
                'subtitle': 'por cobrar',
                'icon': '⏳',
                'color': '#ffc107'
            }
        ]

        for card_info in card_data:
            card = self._create_financial_card(
                card_info['title'], 
                card_info['value'], 
                card_info['subtitle'],
                card_info['icon'], 
                card_info['color']
            )
            cards_layout.addWidget(card)

        layout.addWidget(cards_frame)

    def _create_financial_card(self, title, value, subtitle, icon, color):
        """Crear una tarjeta financiera individual."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border: 1px solid {color};
                border-radius: 8px;
                padding: 15px;
            }}
            QFrame:hover {{
                background-color: #f8f9fa;
            }}
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icono
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px; margin-bottom: 8px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label)
        
        # Título
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {color};
            font-size: 14px;
            font-weight: bold;
            margin: 0;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_label)
        
        # Valor principal
        value_label = QLabel(value)
        value_label.setStyleSheet("""
            color: #2c3e50;
            font-size: 24px;
            font-weight: bold;
            margin: 5px 0;
        """)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(value_label)
        
        # Subtítulo
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("""
            color: #6c757d;
            font-size: 12px;
            margin: 0;
        """)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(subtitle_label)
        
        return card

    def _create_tabs_section(self, layout, report_data):
        """Crear sección de pestañas con información detallada."""
        from PySide6.QtWidgets import QTabWidget
        
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                background: white;
            }
            QTabBar::tab {
                background: #f8f9fa;
                padding: 12px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 2px solid #007bff;
            }
            QTabBar::tab:hover {
                background: #e9ecef;
            }
        """)
        
        # Pestaña 1: Resumen General Mejorado
        summary_tab = self._create_summary_tab(report_data)
        tab_widget.addTab(summary_tab, "📋 Resumen")
        
        # Pestaña 2: Por Forma de Pago
        payment_tab = self._create_payment_methods_tab(report_data)
        tab_widget.addTab(payment_tab, "💳 Formas de Pago")

        # Pestaña 3: Por Asesor
        asesor_tab = self._create_advisors_tab(report_data)
        tab_widget.addTab(asesor_tab, "👨‍💼 Asesores")

        # Pestaña 4: Ventas Detalladas
        sales_tab = self._create_sales_detail_tab(report_data)
        tab_widget.addTab(sales_tab, "📊 Ventas Detalladas")

        layout.addWidget(tab_widget)

    def _create_summary_tab(self, report_data):
        """Crear pestaña de resumen con diseño mejorado."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        totals = report_data.get('totals', {})
        
        # Crear scroll area para el contenido
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # Información general
        info_group = self._create_styled_group("ℹ️ Información General", [
            ("Fecha del reporte", self.report.report_date.strftime('%d de %B de %Y')),
            ("Estado", self.report.report_status),
            ("Generado el", self.report.created_at.strftime('%d/%m/%Y a las %H:%M:%S')),
            ("Total de operaciones", str(totals.get('total_sales', 0)))
        ])
        content_layout.addWidget(info_group)

        # Resumen financiero detallado
        financial_group = self._create_styled_group("💰 Resumen Financiero", [
            ("Total Venta USD", f"${totals.get('total_amount_usd', 0):,.2f}"),
            ("Total Monto Bs", f"Bs. {totals.get('total_amount_bs', 0):,.2f}"),
            ("Total USD Calculado", f"${totals.get('total_monto_usd_calculado', 0):,.2f}"),
            ("Total Abono USD", f"${totals.get('total_abono_usd', 0):,.2f}"),
            ("Total Restante", f"${totals.get('total_restante', 0):,.2f}"),
            ("Total IVA", f"${totals.get('total_iva', 0):,.2f}"),
            ("Total Diseño USD", f"${totals.get('total_diseno_usd', 0):,.2f}"),
            ("Total Ingresos USD", f"${totals.get('total_ingresos_usd', 0):,.2f}")
        ])
        content_layout.addWidget(financial_group)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        return tab

    def _create_payment_methods_tab(self, report_data):
        """Crear pestaña de formas de pago mejorada."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)

        payment_methods = report_data.get('payment_methods', {})
        
        if not payment_methods:
            no_data_label = QLabel("📋 No hay datos de formas de pago disponibles")
            no_data_label.setStyleSheet("""
                color: #6c757d;
                font-size: 16px;
                padding: 40px;
                text-align: center;
            """)
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_data_label)
            return tab

        # Crear tarjetas para cada forma de pago
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        for method, data in payment_methods.items():
            method_card = self._create_payment_method_card(method, data)
            content_layout.addWidget(method_card)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        return tab

    def _create_advisors_tab(self, report_data):
        """Crear pestaña de asesores mejorada."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)

        asesores = report_data.get('asesores_summary', {})
        
        if not asesores:
            no_data_label = QLabel("👨‍💼 No hay datos de asesores disponibles")
            no_data_label.setStyleSheet("""
                color: #6c757d;
                font-size: 16px;
                padding: 40px;
                text-align: center;
            """)
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_data_label)
            return tab

        # Crear tarjetas para cada asesor
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        for asesor, data in asesores.items():
            asesor_card = self._create_advisor_card(asesor, data)
            content_layout.addWidget(asesor_card)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        return tab

    def _create_sales_detail_tab(self, report_data):
        """Crear pestaña de detalles de ventas mejorada."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)

        sales_data = report_data.get('sales_data', [])
        
        if not sales_data:
            no_data_label = QLabel("📊 No hay ventas registradas para este día")
            no_data_label.setStyleSheet("""
                color: #6c757d;
                font-size: 16px;
                padding: 40px;
                text-align: center;
            """)
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_data_label)
            return tab

        # Tabla mejorada de ventas
        sales_table = QTableWidget()
        sales_table.setRowCount(len(sales_data))
        sales_table.setColumnCount(10)  # Columnas principales simplificadas
        sales_table.setHorizontalHeaderLabels([
            "Orden", "Artículo", "Asesor", "Venta USD", "Forma Pago",
            "Abono USD", "Restante", "Ingresos USD", "Estado", "Fecha"
        ])
        
        # Estilo de la tabla
        sales_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #f8f9fa;
                gridline-color: #dee2e6;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #007bff;
                color: white;
                padding: 10px;
                font-weight: bold;
                border: none;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #dee2e6;
            }
            QTableWidget::item:selected {
                background-color: #cce7ff;
            }
        """)
        
        sales_table.setAlternatingRowColors(True)
        
        for row, sale in enumerate(sales_data):
            # Datos principales simplificados
            sales_table.setItem(row, 0, QTableWidgetItem(sale.get('numero_orden', '') or ''))
            sales_table.setItem(row, 1, QTableWidgetItem(sale.get('articulo', '') or ''))
            sales_table.setItem(row, 2, QTableWidgetItem(sale.get('asesor', '') or ''))
            
            # Formatear valores monetarios con manejo seguro de None
            venta_usd = sale.get('venta_usd', 0) or 0
            venta_item = QTableWidgetItem(f"${venta_usd:,.2f}")
            venta_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            sales_table.setItem(row, 3, venta_item)
            
            sales_table.setItem(row, 4, QTableWidgetItem(sale.get('forma_pago', '') or ''))
            
            abono_usd = sale.get('abono_usd', 0) or 0
            abono_item = QTableWidgetItem(f"${abono_usd:,.2f}")
            abono_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            sales_table.setItem(row, 5, abono_item)
            
            restante = sale.get('restante', 0) or 0
            restante_item = QTableWidgetItem(f"${restante:,.2f}")
            restante_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            sales_table.setItem(row, 6, restante_item)
            
            ingresos_usd = sale.get('ingresos_usd', 0) or 0
            ingresos_item = QTableWidgetItem(f"${ingresos_usd:,.2f}")
            ingresos_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            sales_table.setItem(row, 7, ingresos_item)
            
            # Estado basado en el restante
            estado = "✅ Pagado" if restante <= 0 else "⏳ Pendiente"
            estado_item = QTableWidgetItem(estado)
            if restante <= 0:
                estado_item.setBackground(Qt.GlobalColor.green)
            else:
                estado_item.setBackground(Qt.GlobalColor.yellow)
            sales_table.setItem(row, 8, estado_item)
            
            fecha = sale.get('fecha', '') or ''
            fecha_display = fecha[:10] if fecha else ''
            sales_table.setItem(row, 9, QTableWidgetItem(fecha_display))
        
        # Ajustar columnas
        sales_table.resizeColumnsToContents()
        header = sales_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(sales_table)
        
        return tab

    def _create_styled_group(self, title, items):
        """Crear un grupo estilizado con elementos de información."""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 16px;
                border: 2px solid #007bff;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 10px 0 10px;
                color: #007bff;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        for label, value in items:
            item_layout = QHBoxLayout()
            
            label_widget = QLabel(f"{label}:")
            label_widget.setStyleSheet("font-weight: bold; color: #495057;")
            
            value_widget = QLabel(str(value))
            value_widget.setStyleSheet("color: #212529; font-size: 14px;")
            
            item_layout.addWidget(label_widget)
            item_layout.addStretch()
            item_layout.addWidget(value_widget)
            
            layout.addLayout(item_layout)
        
        return group

    def _create_payment_method_card(self, method, data):
        """Crear tarjeta para forma de pago."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
                margin: 5px;
            }
            QFrame:hover {
                border-color: #007bff;
            }
        """)
        
        layout = QVBoxLayout(card)
        
        # Título de la forma de pago
        title = QLabel(f"💳 {method}")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #007bff; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Información en dos columnas
        info_layout = QHBoxLayout()
        
        # Columna izquierda
        left_col = QVBoxLayout()
        left_col.addWidget(QLabel(f"Operaciones: {data.get('count', 0)}"))
        left_col.addWidget(QLabel(f"Venta USD: ${data.get('venta_usd', 0):,.2f}"))
        
        # Columna derecha
        right_col = QVBoxLayout()
        right_col.addWidget(QLabel(f"Abono USD: ${data.get('abono_usd', 0):,.2f}"))
        right_col.addWidget(QLabel(f"Ingresos: ${data.get('ingresos_usd', 0):,.2f}"))
        
        info_layout.addLayout(left_col)
        info_layout.addLayout(right_col)
        layout.addLayout(info_layout)
        
        return card

    def _create_advisor_card(self, asesor, data):
        """Crear tarjeta para asesor."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
                margin: 5px;
            }
            QFrame:hover {
                border-color: #28a745;
            }
        """)
        
        layout = QVBoxLayout(card)
        
        # Título del asesor
        title = QLabel(f"👨‍💼 {asesor}")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #28a745; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Información en dos columnas
        info_layout = QHBoxLayout()
        
        # Columna izquierda
        left_col = QVBoxLayout()
        left_col.addWidget(QLabel(f"Ventas: {data.get('count', 0)}"))
        left_col.addWidget(QLabel(f"Total USD: ${data.get('venta_usd', 0):,.2f}"))
        
        # Columna derecha
        right_col = QVBoxLayout()
        right_col.addWidget(QLabel(f"Abono: ${data.get('abono_usd', 0):,.2f}"))
        right_col.addWidget(QLabel(f"Ingresos: ${data.get('ingresos_usd', 0):,.2f}"))
        
        info_layout.addLayout(left_col)
        info_layout.addLayout(right_col)
        layout.addLayout(info_layout)
        
        return card

    def _create_action_buttons(self, layout):
        """Crear botones de acción mejorados."""
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout(buttons_frame)
        buttons_layout.setSpacing(15)

        # Botón Generar PDF e Imprimir
        btn_print = QPushButton("🖨️ Imprimir")
        btn_print.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        btn_print.clicked.connect(self._print_report)
        buttons_layout.addWidget(btn_print)
        
        # Botón Guardar como PDF
        btn_export_pdf = QPushButton("💾 Guardar PDF")
        btn_export_pdf.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        btn_export_pdf.clicked.connect(self._export_to_pdf)
        buttons_layout.addWidget(btn_export_pdf)
        
        buttons_layout.addStretch()
        
        # Botón Cerrar
        btn_close = QPushButton("✕ Cerrar")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #545b62;
            }
            QPushButton:pressed {
                background-color: #495057;
            }
        """)
        btn_close.clicked.connect(self.accept)
        buttons_layout.addWidget(btn_close)
        
        layout.addWidget(buttons_frame)



    def _print_report(self):
        """Generar PDF del reporte y abrirlo para imprimir."""
        try:
            import tempfile
            import os
            
            # Crear archivo temporal PDF
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file.close()
            
            # Generar PDF
            pdf_path = self._generate_report_pdf(temp_file.name)
            
            if pdf_path:
                # Abrir PDF con aplicación predeterminada
                import subprocess
                subprocess.run(['start', '', pdf_path], shell=True)
                
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
            
            # Seleccionar ubicación para guardar
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Reporte PDF",
                f"Reporte_Diario_{self.report.report_date.strftime('%Y%m%d')}.pdf",
                "Archivos PDF (*.pdf)"
            )
            
            if filename:
                # Generar PDF
                pdf_path = self._generate_report_pdf(filename)
                
                if pdf_path:
                    QMessageBox.information(self, "Éxito", 
                        f"Reporte PDF exportado exitosamente:\n{filename}")
                    
                    # Preguntar si desea abrir el archivo
                    reply = QMessageBox.question(self, "Abrir PDF", 
                        "¿Desea abrir el archivo PDF generado?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        import subprocess
                        subprocess.run(['start', '', filename], shell=True)
                else:
                    QMessageBox.warning(self, "Error", "No se pudo generar el PDF.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al exportar PDF: {str(e)}")

    def _generate_report_pdf(self, output_path: str) -> str | None:
        """Generar PDF del reporte siguiendo el formato de diario11.pdf."""
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch, cm
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
            import json
            import os
            
            # Crear documento PDF en orientación horizontal con márgenes reducidos para tabla más grande
            doc = SimpleDocTemplate(output_path, pagesize=landscape(A4),
                                    rightMargin=0.5*cm, leftMargin=0.5*cm,
                                    topMargin=1.2*cm, bottomMargin=2*cm)
            
            # Estilos personalizados
            styles = getSampleStyleSheet()
            
            # Estilo para el título principal
            title_style = ParagraphStyle(
                'ReportTitle',
                parent=styles['Normal'],
                fontSize=14,  # Reducido 20% de 18 a 14
                spaceAfter=20,  # Espacio ajustado
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            # Estilo para los encabezados de sección más grandes
            section_style = ParagraphStyle(
                'SectionHeader',
                parent=styles['Normal'],
                fontSize=14,  # Aumentado de 12 a 14
                spaceAfter=15,  # Más espacio después
                fontName='Helvetica-Bold'
            )
            
            # Parsear datos del reporte
            report_data = {}
            try:
                if self.report.report_data_json:
                    report_data = json.loads(self.report.report_data_json)
            except:
                report_data = {}
            
            totals = report_data.get('totals', {})
            sales_data = report_data.get('sales_data', [])
            
            # Aplicar filtro adicional si el usuario no puede ver todas las ventas
            if not self._can_view_all_sales and sales_data:
                # Filtrar datos de ventas para mostrar solo las del usuario actual
                filtered_sales = [sale for sale in sales_data if sale.get('asesor') == self._current_user]
                
                # Recalcular totales basados en las ventas filtradas
                if filtered_sales != sales_data:
                    sales_data = filtered_sales
                    totals = {
                        'total_sales': len(filtered_sales),
                        'total_amount_usd': sum((sale.get('venta_usd', 0) or 0) for sale in filtered_sales),
                        'total_amount_bs': sum((sale.get('monto_bs', 0) or 0) for sale in filtered_sales),
                        'total_monto_usd_calculado': sum((sale.get('monto_usd_calculado', 0) or 0) for sale in filtered_sales),
                        'total_abono_usd': sum((sale.get('abono_usd', 0) or 0) for sale in filtered_sales),
                        'total_restante': sum((sale.get('restante', 0) or 0) for sale in filtered_sales),
                        'total_iva': sum((sale.get('iva', 0) or 0) for sale in filtered_sales),
                        'total_diseno_usd': sum((sale.get('diseno_usd', 0) or 0) for sale in filtered_sales),
                        'total_ingresos_usd': sum((sale.get('ingresos_usd', 0) or 0) for sale in filtered_sales)
                    }
            
            # Contenido del PDF siguiendo el formato de diario11.pdf
            story = []
            
            # Crear encabezado con logo y título
            logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', '..', 'assets', 'img', 'logo.png')
            
            # Verificar si existe el logo
            if os.path.exists(logo_path):
                # Crear imagen del logo más grande manteniendo proporciones
                logo = Image(logo_path, width=3.5*cm, height=3.5*cm, kind='proportional')
                
                # Título del reporte con fecha
                fecha_str = self.report.report_date.strftime('%d de %B de %Y')
                title_text = f"INGRESOS DIARIOS {fecha_str.upper()}"
                title_paragraph = Paragraph(title_text, title_style)
                
                # Crear tabla con logo y título ajustando el espacio para logo más grande
                header_table = Table([[logo, title_paragraph]], colWidths=[5*cm, 23*cm])
                header_table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (0, 0), (0, 0), 'LEFT'),    # Logo a la izquierda
                    ('ALIGN', (1, 0), (1, 0), 'CENTER'),  # Título centrado
                    ('LEFTPADDING', (0, 0), (0, 0), 0),   # Sin padding izquierdo en logo
                    ('RIGHTPADDING', (0, 0), (0, 0), 10), # Pequeño espacio entre logo y título
                ]))
                
                story.append(header_table)
            else:
                # Si no hay logo, solo el título
                fecha_str = self.report.report_date.strftime('%d de %B de %Y')
                title_text = f"INGRESOS DIARIOS {fecha_str.upper()}"
                story.append(Paragraph(title_text, title_style))
            
            story.append(Spacer(1, 20))
            
            # Tabla principal con el formato exacto del diario11.pdf
            # Encabezados: ORDEN ARTICULO ASESOR VENTA $ FORMA SERIAL DV BANCO REF FECHA PAGO MONTO MONTO $ ABONO $ RESTANTE $ I.V.A DISEÑO $
            
            main_table_data = []
            
            # Encabezado de la tabla con títulos optimizados
            headers = [
                'ORDEN', 'ARTICULO', 'ASESOR', 'VENTA $', 'FORMA', 'SERIAL\nDV', 
                'BANCO', 'REF', 'FECHA\nPAGO', 'MONTO', 'MONTO\n$', 'ABONO\n$', 
                'RESTANTE\n$', 'I.V.A', 'DISEÑO\n$', 'INGRESOS\n$'
            ]
            main_table_data.append(headers)
            
            # Agregar datos de ventas con formato controlado
            for sale in sales_data:
                row = [
                    sale.get('numero_orden', '')[:10],  # Limitar orden
                    sale.get('articulo', '')[:15],      # Limitar artículo
                    sale.get('asesor', '')[:12],        # Limitar asesor
                    f"{sale.get('venta_usd', 0):.0f}",  # Venta sin decimales
                    sale.get('forma_pago', '')[:12] if sale.get('forma_pago') else '',  # Forma pago limitada
                    sale.get('serial_billete', '')[:12] if sale.get('serial_billete') else '',  # Serial limitado
                    sale.get('banco', '')[:10] if sale.get('banco') else '',  # Banco limitado
                    sale.get('referencia', '')[:8] if sale.get('referencia') else '',  # Ref limitada
                    sale.get('fecha_pago', '')[:10] if sale.get('fecha_pago') else '',  # Fecha formato estándar
                    f"{sale.get('monto_bs', 0):.0f}" if sale.get('monto_bs') else '',  # Monto Bs sin decimales
                    f"{sale.get('monto_usd_calculado', 0):.0f}" if sale.get('monto_usd_calculado') else '',  # Monto USD calc
                    f"{sale.get('abono_usd', 0):.0f}" if sale.get('abono_usd') else '',  # Abono sin decimales
                    f"{sale.get('restante', 0):.0f}" if sale.get('restante') else '',  # Restante sin decimales
                    f"{sale.get('iva', 0):.0f}" if sale.get('iva') else '',  # IVA sin decimales
                    f"{sale.get('diseno_usd', 0):.0f}" if sale.get('diseno_usd') else '',  # Diseño sin decimales
                    f"{sale.get('ingresos_usd', 0):.0f}" if sale.get('ingresos_usd') else ''  # Ingresos sin decimales (AGREGADO)
                ]
                main_table_data.append(row)
            
            # Línea de totales (como en el formato original)
            total_row = [
                'TOTAL',
                str(totals.get('total_sales', 0)),
                '-',
                f"{totals.get('total_amount_usd', 0):.0f}",
                '',
                '',
                '',
                '',
                '',
                f"{totals.get('total_amount_bs', 0):.0f}",
                f"{totals.get('total_monto_usd_calculado', 0):.0f}",
                f"{totals.get('total_abono_usd', 0):.0f}",
                f"{totals.get('total_restante', 0):.0f}",
                f"{totals.get('total_iva', 0):.0f}",
                f"{totals.get('total_diseno_usd', 0):.0f}",
                f"{totals.get('total_ingresos_usd', 0):.0f}"  # Total ingresos agregado
            ]
            main_table_data.append(total_row)
            
            # Crear tabla principal más grande con anchos aumentados
            # Ancho total disponible en horizontal con márgenes reducidos: ~30cm
            col_widths = [
                1.7*cm,   # ORDEN 
                2.4*cm,   # ARTICULO 
                1.8*cm,   # ASESOR 
                1.5*cm,   # VENTA $ 
                2.0*cm,   # FORMA 
                1.8*cm,   # SERIAL DV 
                1.6*cm,   # BANCO 
                1.2*cm,   # REF 
                2.4*cm,   # FECHA PAGO 
                1.5*cm,   # MONTO 
                1.4*cm,   # MONTO $ 
                1.4*cm,   # ABONO $ 
                1.5*cm,   # RESTANTE $ 
                1.2*cm,   # I.V.A 
                1.4*cm,   # DISEÑO $ 
                1.4*cm    # INGRESOS $ (AGREGADO)
            ]
            
            # Crear tabla con altura de filas diferenciada
            row_heights = [1.2*cm] + [0.7*cm] * (len(main_table_data) - 1)  # Encabezado más alto, datos normales
            main_table = Table(main_table_data, colWidths=col_widths, repeatRows=1, rowHeights=row_heights)
            
            # Estilo de la tabla principal con encabezados optimizados
            main_table.setStyle(TableStyle([
                # Encabezado
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 7),  # Reducido para que quepa en las columnas
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                
                # Datos - alineación específica por tipo de columna
                ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -2), 9),  # Aumentado para mejor legibilidad
                ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
                
                # Alineación por columnas: texto a la izquierda, números a la derecha
                ('ALIGN', (0, 1), (2, -1), 'LEFT'),    # ORDEN, ARTICULO, ASESOR - izquierda
                ('ALIGN', (3, 1), (3, -1), 'RIGHT'),   # VENTA $ - derecha
                ('ALIGN', (4, 1), (8, -1), 'LEFT'),    # FORMA, SERIAL, BANCO, REF, FECHA - izquierda
                ('ALIGN', (9, 1), (-1, -1), 'RIGHT'),  # Todos los montos - derecha
                
                # Fila de totales
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 10),  # Aumentado para mejor legibilidad
                ('ALIGN', (0, -1), (2, -1), 'LEFT'),   # Texto TOTAL a la izquierda
                ('ALIGN', (3, -1), (-1, -1), 'RIGHT'), # Números de totales a la derecha
                
                # Bordes más definidos
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),  # Línea gruesa bajo encabezado
            ]))
            
            story.append(main_table)
            
            # Sección de firmas con líneas apropiadas
            # Agregar espacio antes de las firmas
            story.append(Spacer(1, 30))
            
            # Crear líneas para las firmas
            signature_lines = Table([
                ['_' * 30, '_' * 30],
                ['YOLY MENDOZA', 'MIGUEL ROSALES'],
                ['ASISTENTE ADMINISTRATIVO', 'PRESIDENTE']
            ], colWidths=[4*inch, 4*inch])
            
            signature_lines.setStyle(TableStyle([
                # Líneas superiores
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                # Nombres
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, 1), 11),
                ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
                ('TOPPADDING', (0, 1), (-1, 1), 10),
                # Cargos
                ('FONTNAME', (0, 2), (-1, 2), 'Helvetica'),
                ('FONTSIZE', (0, 2), (-1, 2), 9),
                ('ALIGN', (0, 2), (-1, 2), 'CENTER'),
                ('TOPPADDING', (0, 2), (-1, 2), 5),
            ]))
            
            story.append(signature_lines)
            
            # Construir PDF
            doc.build(story)
            
            return output_path
            
        except Exception as e:
            print(f"Error generando PDF: {e}")
            return None

    def _generate_report_html(self) -> str:
        """Generar HTML completo del reporte para impresión/exportación."""
        import json
        
        report_data = {}
        try:
            if self.report.report_data_json:
                report_data = json.loads(self.report.report_data_json)
        except:
            report_data = {}
        
        totals = report_data.get('totals', {})
        payment_methods = report_data.get('payment_methods', {})
        asesores = report_data.get('asesores_summary', {})
        sales_data = report_data.get('sales_data', [])
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Reporte Diario - {self.report.report_date.strftime('%d/%m/%Y')}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    font-size: 10px;
                    margin: 0;
                    padding: 20px;
                }}
                h1 {{ font-size: 18px; text-align: center; color: #2c3e50; }}
                h2 {{ font-size: 14px; color: #34495e; border-bottom: 1px solid #bdc3c7; }}
                h3 {{ font-size: 12px; color: #7f8c8d; }}
                table {{ 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin: 10px 0;
                    font-size: 9px;
                }}
                th, td {{ 
                    border: 1px solid #bdc3c7; 
                    padding: 4px; 
                    text-align: left; 
                }}
                th {{ 
                    background-color: #ecf0f1; 
                    font-weight: bold; 
                }}
                .summary-box {{
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    padding: 10px;
                    margin: 10px 0;
                }}
                .total-row {{ font-weight: bold; background-color: #e8f4f8; }}
            </style>
        </head>
        <body>
            <h1>📊 Reporte Diario de Ventas</h1>
            <h2>Fecha: {self.report.report_date.strftime('%d/%m/%Y')}</h2>
            
            <div class="summary-box">
                <h3>📋 Resumen General</h3>
                <p><strong>Estado:</strong> {self.report.report_status}</p>
                <p><strong>Generado:</strong> {self.report.created_at.strftime('%d/%m/%Y %H:%M:%S')}</p>
                <p><strong>Total de Ventas:</strong> {totals.get('total_sales', 0)} operaciones</p>
            </div>
            
            <div class="summary-box">
                <h3>💰 Totales Financieros</h3>
                <table>
                    <tr><td><strong>Total Venta USD:</strong></td><td>${totals.get('total_amount_usd', 0):,.2f}</td></tr>
                    <tr><td><strong>Total Monto Bs:</strong></td><td>Bs. {totals.get('total_amount_bs', 0):,.2f}</td></tr>
                    <tr><td><strong>Total Monto USD Calculado:</strong></td><td>${totals.get('total_monto_usd_calculado', 0):,.2f}</td></tr>
                    <tr><td><strong>Total Abono USD:</strong></td><td>${totals.get('total_abono_usd', 0):,.2f}</td></tr>
                    <tr><td><strong>Total Restante:</strong></td><td>${totals.get('total_restante', 0):,.2f}</td></tr>
                    <tr><td><strong>Total IVA:</strong></td><td>${totals.get('total_iva', 0):,.2f}</td></tr>
                    <tr><td><strong>Total Diseño USD:</strong></td><td>${totals.get('total_diseno_usd', 0):,.2f}</td></tr>
                    <tr class="total-row"><td><strong>Total Ingresos USD:</strong></td><td>${totals.get('total_ingresos_usd', 0):,.2f}</td></tr>
                </table>
            </div>
        """
        
        # Resumen por forma de pago
        if payment_methods:
            html += """
            <div class="summary-box">
                <h3>💳 Resumen por Forma de Pago</h3>
                <table>
                    <tr>
                        <th>Forma de Pago</th>
                        <th>Cantidad</th>
                        <th>Venta USD</th>
                        <th>Monto Bs</th>
                        <th>Abono USD</th>
                        <th>Ingresos USD</th>
                    </tr>
            """
            for method, data in payment_methods.items():
                html += f"""
                    <tr>
                        <td>{method}</td>
                        <td>{data.get('count', 0)}</td>
                        <td>${data.get('venta_usd', 0):,.2f}</td>
                        <td>Bs. {data.get('monto_bs', 0):,.2f}</td>
                        <td>${data.get('abono_usd', 0):,.2f}</td>
                        <td>${data.get('ingresos_usd', 0):,.2f}</td>
                    </tr>
                """
            html += "</table></div>"
        
        # Resumen por asesor
        if asesores:
            html += """
            <div class="summary-box">
                <h3>👨‍💼 Resumen por Asesor</h3>
                <table>
                    <tr>
                        <th>Asesor</th>
                        <th>Cantidad</th>
                        <th>Venta USD</th>
                        <th>Monto Bs</th>
                        <th>Abono USD</th>
                        <th>Ingresos USD</th>
                    </tr>
            """
            for asesor, data in asesores.items():
                html += f"""
                    <tr>
                        <td>{asesor}</td>
                        <td>{data.get('count', 0)}</td>
                        <td>${data.get('venta_usd', 0):,.2f}</td>
                        <td>Bs. {data.get('monto_bs', 0):,.2f}</td>
                        <td>${data.get('abono_usd', 0):,.2f}</td>
                        <td>${data.get('ingresos_usd', 0):,.2f}</td>
                    </tr>
                """
            html += "</table></div>"
        
        # Ventas detalladas
        if sales_data:
            html += """
            <h2>📊 Ventas Detalladas</h2>
            <table>
                <tr>
                    <th>Orden</th>
                    <th>Fecha</th>
                    <th>Artículo</th>
                    <th>Asesor</th>
                    <th>Venta USD</th>
                    <th>Forma Pago</th>
                    <th>Monto Bs</th>
                    <th>Abono USD</th>
                    <th>Restante</th>
                    <th>Ingresos USD</th>
                </tr>
            """
            for sale in sales_data:
                html += f"""
                    <tr>
                        <td>{sale.get('numero_orden', '')}</td>
                        <td>{sale.get('fecha', '')[:10]}</td>
                        <td>{sale.get('articulo', '')}</td>
                        <td>{sale.get('asesor', '')}</td>
                        <td>${sale.get('venta_usd', 0):,.2f}</td>
                        <td>{sale.get('forma_pago', '')}</td>
                        <td>{f"Bs. {sale.get('monto_bs', 0):,.2f}" if sale.get('monto_bs') else ''}</td>
                        <td>${sale.get('abono_usd', 0):,.2f}</td>
                        <td>${sale.get('restante', 0):,.2f}</td>
                        <td>${sale.get('ingresos_usd', 0):,.2f}</td>
                    </tr>
                """
            html += "</table>"
        
        html += """
        </body>
        </html>
        """
        
        return html


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