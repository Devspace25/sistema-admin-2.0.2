from __future__ import annotations

from datetime import date, datetime, timedelta
from sqlalchemy.orm import sessionmaker
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QMessageBox, QDialog, QFormLayout,
    QTextEdit, QDateEdit, QGroupBox, QDialogButtonBox, QFrame, QScrollArea,
    QApplication, QTabWidget, QGridLayout
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont

from ..db import make_session_factory, make_engine
from ..repository import (
    check_daily_report_status, get_daily_sales_data, create_daily_report,
    get_pending_reports, list_daily_reports
)


class DailyReportsView(QWidget):
    """Vista principal para gestionar reportes diarios de ventas."""
    
    def __init__(self, parent=None, session_factory=None, current_user: str | None = None, can_view_all_sales: bool = True):
        super().__init__(parent)
        self._session_factory = session_factory or make_session_factory()
        self._current_user = current_user or "—"
        self._can_view_all_sales = can_view_all_sales
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Configurar la interfaz principal."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Título de la sección
        title = QLabel("📊 Reportes Diarios")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title)

        # Alertas de reportes pendientes
        self._create_alerts_section(layout)

        # Botones de acciones principales
        self._create_action_buttons(layout)

        # Tabla de reportes existentes
        self._create_reports_table(layout)

    def _create_alerts_section(self, layout):
        """Crear sección de alertas para reportes pendientes."""
        alerts_group = QGroupBox("⚠️ Alertas de Reportes")
        alerts_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ffc107;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fff3cd;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #856404;
            }
        """)
        
        alerts_layout = QVBoxLayout(alerts_group)
        self.alerts_layout = alerts_layout
        
        layout.addWidget(alerts_group)

    def _create_action_buttons(self, layout):
        """Crear botones de acción principal."""
        buttons_layout = QHBoxLayout()
        
        # Botón generar reporte de hoy
        btn_generate_today = QPushButton("📊 Generar Reporte de Hoy")
        btn_generate_today.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        btn_generate_today.clicked.connect(lambda: self._generate_report_for_date(date.today()))
        buttons_layout.addWidget(btn_generate_today)
        
        buttons_layout.addStretch()
        
        # Botón refrescar
        btn_refresh = QPushButton("🔄 Refrescar")
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #545b62;
            }
        """)
        btn_refresh.clicked.connect(self._load_data)
        buttons_layout.addWidget(btn_refresh)
        
        layout.addLayout(buttons_layout)

    def _create_reports_table(self, layout):
        """Crear tabla de reportes existentes."""
        table_group = QGroupBox("📋 Reportes Existentes")
        table_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        table_layout = QVBoxLayout(table_group)
        
        # Tabla
        self.reports_table = QTableWidget()
        self.reports_table.setColumnCount(6)
        self.reports_table.setHorizontalHeaderLabels([
            "Fecha", "Estado", "Ventas", "Total USD", "Total Bs", "Acciones"
        ])
        
        # Configurar tabla
        header = self.reports_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        
        self.reports_table.setAlternatingRowColors(True)
        self.reports_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        table_layout.addWidget(self.reports_table)
        layout.addWidget(table_group)

    def _load_data(self):
        """Cargar datos de reportes y alertas."""
        self._load_alerts()
        self._load_reports_table()

    def _load_alerts(self):
        """Cargar alertas de reportes pendientes."""
        try:
            # Limpiar alertas anteriores
            for i in reversed(range(self.alerts_layout.count())):
                child = self.alerts_layout.itemAt(i).widget()
                if child:
                    child.setParent(None)
            
            with self._session_factory() as session:
                # Obtener fechas con reportes pendientes
                pending_status = get_pending_reports(session, days_back=7)
                
                if not pending_status:
                    no_alerts_label = QLabel("✅ No hay reportes pendientes")
                    no_alerts_label.setStyleSheet("color: #28a745; font-weight: bold; padding: 5px;")
                    self.alerts_layout.addWidget(no_alerts_label)
                    return
                
                for status in pending_status:
                    if status['status'] in ['PENDIENTE', 'ERROR']:
                        alert_frame = QFrame()
                        alert_frame.setStyleSheet("background-color: #fff; border-radius: 3px; padding: 5px; margin: 2px;")
                        alert_layout = QHBoxLayout(alert_frame)
                        
                        # Mensaje de alerta
                        message = f"⚠️ Reporte del {status['date'].strftime('%d/%m/%Y')} está {status['status']}"
                        alert_label = QLabel(message)
                        alert_label.setStyleSheet("color: #856404;")
                        alert_layout.addWidget(alert_label)
                        
                        # Botón para generar
                        btn_generate = QPushButton("Generar")
                        btn_generate.setStyleSheet("""
                            QPushButton {
                                background-color: #ffc107;
                                color: #212529;
                                border: none;
                                padding: 5px 10px;
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
                    # Fecha
                    date_item = QTableWidgetItem(report.report_date.strftime('%d/%m/%Y'))
                    self.reports_table.setItem(row, 0, date_item)
                    
                    # Estado
                    status_item = QTableWidgetItem(report.report_status)
                    if report.report_status == "GENERADO":
                        status_item.setBackground(Qt.GlobalColor.green)
                    elif report.report_status == "PENDIENTE":
                        status_item.setBackground(Qt.GlobalColor.yellow)
                    self.reports_table.setItem(row, 1, status_item)
                    
                    # Ventas
                    sales_item = QTableWidgetItem(str(report.total_sales or 0))
                    self.reports_table.setItem(row, 2, sales_item)
                    
                    # Total USD
                    usd_item = QTableWidgetItem(f"${report.total_amount_usd or 0:.2f}")
                    self.reports_table.setItem(row, 3, usd_item)
                    
                    # Total Bs
                    bs_item = QTableWidgetItem(f"Bs. {report.total_amount_bs or 0:.2f}")
                    self.reports_table.setItem(row, 4, bs_item)
                    
                    # Botón Ver
                    btn_view = QPushButton("📊 Ver")
                    btn_view.setStyleSheet("""
                        QPushButton {
                            background-color: #007bff;
                            color: white;
                            border: none;
                            padding: 5px 10px;
                            border-radius: 3px;
                        }
                        QPushButton:hover {
                            background-color: #0056b3;
                        }
                    """)
                    btn_view.clicked.connect(
                        lambda checked, r=report: self._show_report_details(r)
                    )
                    self.reports_table.setCellWidget(row, 5, btn_view)
                    
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cargar reportes: {str(e)}")

    def _generate_report_for_date(self, target_date: date):
        """Generar reporte para una fecha específica."""
        try:
            with self._session_factory() as session:
                # Convertir date a datetime
                from datetime import datetime
                target_datetime = datetime.combine(target_date, datetime.min.time())
                
                # Obtener datos de ventas para la fecha
                sales_data = get_daily_sales_data(session, target_datetime)
                
                if not sales_data:
                    QMessageBox.information(
                        self, 
                        "Sin Datos", 
                        f"No hay datos de ventas para el {target_date.strftime('%d/%m/%Y')}"
                    )
                    return
                
                # Crear el reporte (user_id, target_date, notes)
                report = create_daily_report(session, 1, target_datetime, "Generado automáticamente")
                
                QMessageBox.information(
                    self, 
                    "Éxito", 
                    f"Reporte generado exitosamente para el {target_date.strftime('%d/%m/%Y')}"
                )
                
                # Refrescar la vista
                self._load_data()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al generar reporte: {str(e)}")

    def _show_report_details(self, report):
        """Mostrar detalles del reporte en un diálogo."""
        try:
            dialog = SimpleReportDetailsDialog(report, self, self._current_user, self._can_view_all_sales)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al mostrar detalles del reporte: {str(e)}")
            print(f"Error detallado: {e}")


class SimpleReportDetailsDialog(QDialog):
    """Diálogo simple y claro para mostrar detalles de reportes."""

    def __init__(self, report, parent=None, current_user: str | None = None, can_view_all_sales: bool = True):
        super().__init__(parent)
        self.report = report
        self._current_user = current_user or "—"
        self._can_view_all_sales = can_view_all_sales
        self.setWindowTitle(f"Detalles del Reporte - {report.report_date.strftime('%d/%m/%Y')}")
        self.setModal(True)
        
        # Tamaño adaptable
        self.resize(800, 600)
        self.setMinimumSize(600, 400)
        
        self._setup_ui()

    def _setup_ui(self):
        """Configurar interfaz simple y clara."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Parsear datos del reporte
        import json
        try:
            if hasattr(self.report, 'report_data_json') and self.report.report_data_json:
                self.report_data = json.loads(self.report.report_data_json)
            else:
                self.report_data = self._create_default_data()
        except Exception as e:
            print(f"Error al parsear datos: {e}")
            self.report_data = self._create_default_data()

        # Título
        title = QLabel(f"📊 Reporte del {self.report.report_date.strftime('%d de %B de %Y')}")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
                border-bottom: 2px solid #e9ecef;
                margin-bottom: 15px;
            }
        """)
        layout.addWidget(title)

        # Crear scroll area para el contenido
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Resumen principal
        self._create_main_summary(content_layout)
        
        # Detalles por método de pago
        if self.report_data.get('payment_methods'):
            self._create_payment_methods_section(content_layout)
        
        # Detalles por asesor
        if self.report_data.get('asesores_summary'):
            self._create_advisors_section(content_layout)
            
        # Tabla de ventas
        if self.report_data.get('sales_data'):
            self._create_sales_table(content_layout)
        
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        # Botones
        self._create_buttons(layout)

    def _create_default_data(self):
        """Crear datos por defecto."""
        return {
            'totals': {
                'total_sales': getattr(self.report, 'total_sales', 0),
                'total_amount_usd': getattr(self.report, 'total_amount_usd', 0),
                'total_amount_bs': getattr(self.report, 'total_amount_bs', 0),
                'total_ingresos_usd': getattr(self.report, 'total_ingresos_usd', 0)
            },
            'payment_methods': {},
            'asesores_summary': {},
            'sales_data': []
        }

    def _create_main_summary(self, layout):
        """Crear resumen principal con tarjetas simples."""
        summary_group = QGroupBox("📊 Resumen General")
        summary_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        grid = QGridLayout(summary_group)
        totals = self.report_data.get('totals', {})
        
        # Crear tarjetas de resumen
        cards_data = [
            ("🛒", "Total Ventas", f"{totals.get('total_sales', 0)}", "operaciones"),
            ("💵", "Ventas USD", f"${totals.get('total_amount_usd', 0):.2f}", "valor total"),
            ("💰", "Ventas Bs", f"Bs. {totals.get('total_amount_bs', 0):,.2f}", "bolívares"),
            ("💎", "Ingresos USD", f"${totals.get('total_ingresos_usd', 0):.2f}", "ingresos reales")
        ]
        
        for i, (icon, title, value, subtitle) in enumerate(cards_data):
            card = self._create_summary_card(icon, title, value, subtitle)
            grid.addWidget(card, i // 2, i % 2)
        
        layout.addWidget(summary_group)

    def _create_summary_card(self, icon, title, value, subtitle):
        """Crear una tarjeta de resumen simple."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e9ecef;
                border-radius: 5px;
                padding: 15px;
                margin: 5px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icono y título
        header_layout = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 20px;")
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; color: #495057;")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Valor principal
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin: 5px 0;")
        layout.addWidget(value_label)
        
        # Subtítulo
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(subtitle_label)
        
        return card

    def _create_payment_methods_section(self, layout):
        """Crear sección de métodos de pago."""
        payment_group = QGroupBox("💳 Resumen por Método de Pago")
        payment_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        payment_layout = QVBoxLayout(payment_group)
        
        for method, data in self.report_data.get('payment_methods', {}).items():
            method_frame = QFrame()
            method_frame.setStyleSheet("""
                QFrame {
                    background-color: #f8f9fa;
                    border: 1px solid #e9ecef;
                    border-radius: 5px;
                    padding: 10px;
                    margin: 2px;
                }
            """)
            
            method_layout = QHBoxLayout(method_frame)
            
            # Nombre del método
            method_label = QLabel(f"💳 {method}")
            method_label.setStyleSheet("font-weight: bold; color: #495057;")
            method_layout.addWidget(method_label)
            
            # Estadísticas
            stats_text = f"Ventas: {data.get('count', 0)} | USD: ${data.get('venta_usd', 0):.2f} | Bs: {data.get('monto_bs', 0):,.2f}"
            stats_label = QLabel(stats_text)
            stats_label.setStyleSheet("color: #6c757d;")
            method_layout.addWidget(stats_label)
            
            payment_layout.addWidget(method_frame)
        
        layout.addWidget(payment_group)

    def _create_advisors_section(self, layout):
        """Crear sección de asesores."""
        advisors_group = QGroupBox("👥 Resumen por Asesor")
        advisors_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        advisors_layout = QVBoxLayout(advisors_group)
        
        for advisor, data in self.report_data.get('asesores_summary', {}).items():
            advisor_frame = QFrame()
            advisor_frame.setStyleSheet("""
                QFrame {
                    background-color: #f8f9fa;
                    border: 1px solid #e9ecef;
                    border-radius: 5px;
                    padding: 10px;
                    margin: 2px;
                }
            """)
            
            advisor_layout = QHBoxLayout(advisor_frame)
            
            # Nombre del asesor
            advisor_label = QLabel(f"👨‍💼 {advisor}")
            advisor_label.setStyleSheet("font-weight: bold; color: #495057;")
            advisor_layout.addWidget(advisor_label)
            
            # Estadísticas
            stats_text = f"Ventas: {data.get('count', 0)} | USD: ${data.get('venta_usd', 0):.2f} | Ingresos: ${data.get('ingresos_usd', 0):.2f}"
            stats_label = QLabel(stats_text)
            stats_label.setStyleSheet("color: #6c757d;")
            advisor_layout.addWidget(stats_label)
            
            advisors_layout.addWidget(advisor_frame)
        
        layout.addWidget(advisors_group)

    def _create_sales_table(self, layout):
        """Crear tabla de ventas detallada."""
        sales_group = QGroupBox("📋 Detalle de Ventas")
        sales_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        table_layout = QVBoxLayout(sales_group)
        
        # Tabla
        table = QTableWidget()
        sales_data = self.report_data.get('sales_data', [])
        
        if not sales_data:
            no_data_label = QLabel("No hay datos de ventas detallados")
            no_data_label.setStyleSheet("color: #6c757d; font-style: italic; padding: 20px;")
            table_layout.addWidget(no_data_label)
        else:
            table.setRowCount(len(sales_data))
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels([
                "Orden", "Artículo", "Asesor", "Venta USD", "Abono USD", "Restante"
            ])
            
            for row, sale in enumerate(sales_data):
                table.setItem(row, 0, QTableWidgetItem(str(sale.get('numero_orden', ''))))
                table.setItem(row, 1, QTableWidgetItem(str(sale.get('articulo', ''))))
                table.setItem(row, 2, QTableWidgetItem(str(sale.get('asesor', ''))))
                table.setItem(row, 3, QTableWidgetItem(f"${sale.get('venta_usd', 0):.2f}"))
                table.setItem(row, 4, QTableWidgetItem(f"${sale.get('abono_usd', 0):.2f}"))
                table.setItem(row, 5, QTableWidgetItem(f"${sale.get('restante', 0):.2f}"))
            
            # Configurar tabla
            header = table.horizontalHeader()
            header.setStretchLastSection(True)
            for i in range(6):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
            
            table.setAlternatingRowColors(True)
            table.setMaximumHeight(300)
            
            table_layout.addWidget(table)
        
        layout.addWidget(sales_group)

    def _create_buttons(self, layout):
        """Crear botones de acción."""
        buttons_layout = QHBoxLayout()
        
        # Botón Imprimir
        btn_print = QPushButton("🖨️ Imprimir")
        btn_print.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        btn_print.clicked.connect(self._print_report)
        buttons_layout.addWidget(btn_print)
        
        # Botón Guardar PDF
        btn_export = QPushButton("💾 Guardar PDF")
        btn_export.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        btn_export.clicked.connect(self._export_to_pdf)
        buttons_layout.addWidget(btn_export)
        
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
            }
            QPushButton:hover {
                background-color: #545b62;
            }
        """)
        btn_close.clicked.connect(self.accept)
        buttons_layout.addWidget(btn_close)
        
        layout.addLayout(buttons_layout)

    def _print_report(self):
        """Imprimir reporte."""
        QMessageBox.information(self, "Imprimir", "Funcionalidad de impresión en desarrollo")

    def _export_to_pdf(self):
        """Exportar a PDF."""
        QMessageBox.information(self, "Exportar", "Funcionalidad de exportación en desarrollo")