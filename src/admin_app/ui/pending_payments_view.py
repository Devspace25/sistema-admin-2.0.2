from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QDialog, QFormLayout,
    QDoubleSpinBox, QComboBox, QLineEdit, QAbstractItemView, QTabWidget,
    QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from ..repository import get_pending_sales, register_payment, get_payments_history
from .sale_dialog import MoneySpinBox
from ..exchange import get_bcv_rate

class PaymentDialog(QDialog):
    def __init__(self, sale_data, parent=None):
        super().__init__(parent)
        self.sale_data = sale_data
        self.setWindowTitle(f"Registrar Pago - Orden {sale_data.numero_orden}")
        self.resize(850, 550)
        
        layout = QVBoxLayout(self)
        
        # Info Header
        info_group = QDialog(self) # Just a container, but QGroupBox is better
        # Actually let's use QGroupBox
        from PySide6.QtWidgets import QGroupBox, QGridLayout
        
        info_group = QGroupBox("Información de la Venta", self)
        info_layout = QGridLayout(info_group)
        info_layout.addWidget(QLabel("Cliente:", self), 0, 0)
        info_layout.addWidget(QLabel(f"{sale_data.cliente or 'N/A'}", self), 0, 1)
        info_layout.addWidget(QLabel("Orden:", self), 0, 2)
        info_layout.addWidget(QLabel(f"{sale_data.numero_orden}", self), 0, 3)
        
        info_layout.addWidget(QLabel("Total Venta:", self), 1, 0)
        info_layout.addWidget(QLabel(f"${sale_data.total_usd:.2f}", self), 1, 1)
        info_layout.addWidget(QLabel("Restante Actual:", self), 1, 2)
        self.lbl_restante_orig = QLabel(f"${sale_data.restante:.2f}", self)
        self.lbl_restante_orig.setStyleSheet("font-weight: bold; color: red;")
        info_layout.addWidget(self.lbl_restante_orig, 1, 3)
        
        layout.addWidget(info_group)
        
        # Payment Methods Section
        self.grp_metodos_pago = QGroupBox("Métodos de Pago", self)
        pay_layout = QVBoxLayout(self.grp_metodos_pago)
        
        # Table
        self.tbl_payments = QTableWidget(self)
        self.tbl_payments.setColumnCount(6)
        self.tbl_payments.setHorizontalHeaderLabels([
            "Forma de Pago", "Monto Bs", "Monto $", "Banco/Serial", "Referencia", ""
        ])
        header = self.tbl_payments.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.tbl_payments.setColumnWidth(5, 30)
        self.tbl_payments.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        pay_layout.addWidget(self.tbl_payments)
        
        # Add Button
        self.btn_add_payment = QPushButton("+ Agregar Método de Pago", self)
        self.btn_add_payment.setStyleSheet("background-color: #e0e0e0; padding: 6px; font-weight: bold;")
        pay_layout.addWidget(self.btn_add_payment)
        
        # Footer (Totals)
        footer_layout = QGridLayout()
        
        self.lbl_total_bs_payments = QLabel("Total Bs: 0.00", self)
        self.lbl_total_bs_payments.setStyleSheet("color: #00aaff; font-weight: bold;")
        self.lbl_total_usd_payments = QLabel("Total $: 0.00", self)
        self.lbl_total_usd_payments.setStyleSheet("color: #28a745; font-weight: bold;")
        
        totals_box = QHBoxLayout()
        totals_box.addWidget(self.lbl_total_bs_payments)
        totals_box.addWidget(self.lbl_total_usd_payments)
        totals_box.addStretch()
        footer_layout.addLayout(totals_box, 0, 0, 1, 4)
        
        # Fields
        footer_layout.addWidget(QLabel("Tasa BCV (Bs/$):", self), 1, 0)
        self.edt_tasa_bcv_payments = QDoubleSpinBox(self)
        self._conf_money(self.edt_tasa_bcv_payments, prefix="", maxv=999.99)
        
        # Load Rate
        try:
            rate = get_bcv_rate()
        except:
            rate = 0.0
        self.edt_tasa_bcv_payments.setValue(rate)
        
        footer_layout.addWidget(self.edt_tasa_bcv_payments, 1, 1)
        
        footer_layout.addWidget(QLabel("Abono Total $:", self), 2, 0)
        self.edt_abono_payments = QDoubleSpinBox(self)
        self._conf_money(self.edt_abono_payments, prefix="", maxv=999999.99)
        self.edt_abono_payments.setReadOnly(True)
        footer_layout.addWidget(self.edt_abono_payments, 2, 1)
        
        footer_layout.addWidget(QLabel("Nuevo Restante $:", self), 2, 2)
        self.out_restante_payments = QDoubleSpinBox(self)
        self._conf_money(self.out_restante_payments, prefix="", maxv=999999.99)
        self.out_restante_payments.setReadOnly(True)
        footer_layout.addWidget(self.out_restante_payments, 2, 3)
        
        pay_layout.addLayout(footer_layout)
        layout.addWidget(self.grp_metodos_pago)
        
        # Botones
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Registrar Pago")
        btn_ok.clicked.connect(self.accept)
        # Estilo consistente (blanco/gris)
        btn_ok.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
                color: #2c3e50;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ecf0f1;
            }
        """)
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
                color: #2c3e50;
            }
            QPushButton:hover {
                background-color: #ecf0f1;
            }
        """)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        
        # Signals
        self.btn_add_payment.clicked.connect(self._on_add_payment_row)
        self.edt_tasa_bcv_payments.valueChanged.connect(self._recalc_all_payments)
        
        # Initial Row
        self._on_add_payment_row()

    def _conf_money(self, widget, prefix="$ ", maxv=999999.99):
        widget.setPrefix(prefix)
        widget.setRange(0.0, maxv)
        widget.setDecimals(2)
        widget.setGroupSeparatorShown(True)

    def _on_add_payment_row(self) -> None:
        row = self.tbl_payments.rowCount()
        self.tbl_payments.insertRow(row)
        
        # 0. Forma de Pago
        cmb_method = QComboBox(self)
        cmb_method.addItems([
            "---- Seleccione ----",
            "Efectivo USD", "Zelle", "Banesco Panamá", "Binance", "PayPal",
            "Efectivo Bs.D", "Pago móvil", "Transferencia Bs.D", "Punto de Venta"
        ])
        self.tbl_payments.setCellWidget(row, 0, cmb_method)
        
        # 1. Monto Bs
        edt_monto_bs = MoneySpinBox(self)
        self._conf_money(edt_monto_bs, prefix="Bs ", maxv=999999999.99)
        self.tbl_payments.setCellWidget(row, 1, edt_monto_bs)
        
        # 2. Monto $
        edt_monto_usd = MoneySpinBox(self)
        self._conf_money(edt_monto_usd, prefix="$ ", maxv=999999.99)
        self.tbl_payments.setCellWidget(row, 2, edt_monto_usd)
        
        # 3. Banco/Serial
        edt_banco = QLineEdit(self)
        edt_banco.setPlaceholderText("Banco o Serial...")
        self.tbl_payments.setCellWidget(row, 3, edt_banco)
        
        # 4. Referencia
        edt_ref = QLineEdit(self)
        edt_ref.setPlaceholderText("Referencia...")
        self.tbl_payments.setCellWidget(row, 4, edt_ref)
        
        # 5. Delete
        btn_delete = QPushButton("🗑️", self)
        btn_delete.setFixedSize(24, 24)
        self.tbl_payments.setCellWidget(row, 5, btn_delete)
        
        # Signals
        edt_monto_bs.valueChanged.connect(lambda: self._recalc_payment_row(edt_monto_bs))
        edt_monto_usd.valueChanged.connect(lambda: self._recalc_payment_row(edt_monto_usd))
        btn_delete.clicked.connect(lambda: self._on_delete_payment_row(btn_delete))
        
        # Connect method change to auto-fill logic
        cmb_method.currentIndexChanged.connect(lambda: self._on_payment_method_changed(cmb_method))
        
        # Trigger update to get current remaining
        self._recalc_all_payments()
        
        # Auto-fill remaining balance
        self._apply_payment_autofill(row)

    def _is_bs_method(self, method_name: str) -> bool:
        bs_methods = [
            "Efectivo Bs.D", "Pago móvil", "Transferencia Bs.D", "Punto de Venta"
        ]
        return method_name in bs_methods

    def _apply_payment_autofill(self, row: int) -> None:
        cmb = self.tbl_payments.cellWidget(row, 0)
        if not cmb: return
        method = cmb.currentText()
        
        if not self._is_bs_method(method):
            edt_bs = self.tbl_payments.cellWidget(row, 1)
            if edt_bs:
                edt_bs.setValue(0.0)
            return
            
        # Calculate remaining excluding this row
        total_sale = float(self.sale_data.restante)
        current_paid = 0.0
        for r in range(self.tbl_payments.rowCount()):
            if r == row: continue
            w_usd = self.tbl_payments.cellWidget(r, 2)
            if w_usd:
                current_paid += w_usd.value()
        
        remaining = max(0.0, total_sale - current_paid)
        
        if remaining > 0:
            edt_usd = self.tbl_payments.cellWidget(row, 2)
            if edt_usd:
                edt_usd.setValue(remaining)

    def _on_payment_method_changed(self, cmb: QComboBox) -> None:
        row = -1
        for r in range(self.tbl_payments.rowCount()):
            if self.tbl_payments.cellWidget(r, 0) == cmb:
                row = r
                break
        if row == -1:
            return
        self._apply_payment_autofill(row)

    def _on_delete_payment_row(self, btn: QPushButton) -> None:
        for r in range(self.tbl_payments.rowCount()):
            if self.tbl_payments.cellWidget(r, 5) == btn:
                self.tbl_payments.removeRow(r)
                self._recalc_all_payments()
                break

    def _recalc_payment_row(self, sender_widget):
        row = -1
        for r in range(self.tbl_payments.rowCount()):
            if (self.tbl_payments.cellWidget(r, 1) == sender_widget or 
                self.tbl_payments.cellWidget(r, 2) == sender_widget):
                row = r
                break
        if row == -1: return
        
        edt_bs = self.tbl_payments.cellWidget(row, 1)
        edt_usd = self.tbl_payments.cellWidget(row, 2)
        rate = self.edt_tasa_bcv_payments.value()
        
        sender_widget.blockSignals(True)
        try:
            if sender_widget == edt_usd:
                val_bs = edt_usd.value() * rate
                edt_bs.blockSignals(True)
                edt_bs.setValue(val_bs)
                edt_bs.blockSignals(False)
            elif sender_widget == edt_bs:
                if rate > 0:
                    val_usd = edt_bs.value() / rate
                    edt_usd.blockSignals(True)
                    edt_usd.setValue(val_usd)
                    edt_usd.blockSignals(False)
        finally:
            sender_widget.blockSignals(False)
            
        self._recalc_all_payments()

    def _recalc_all_payments(self):
        total_bs = 0.0
        total_usd = 0.0
        
        for r in range(self.tbl_payments.rowCount()):
            w_bs = self.tbl_payments.cellWidget(r, 1)
            w_usd = self.tbl_payments.cellWidget(r, 2)
            if w_bs and w_usd:
                total_bs += w_bs.value()
                total_usd += w_usd.value()
                
        self.lbl_total_bs_payments.setText(f"Total Bs: {total_bs:,.2f}")
        self.lbl_total_usd_payments.setText(f"Total $: {total_usd:,.2f}")
        
        self.edt_abono_payments.setValue(total_usd)
        
        restante_orig = float(self.sale_data.restante)
        new_restante = max(0.0, restante_orig - total_usd)
        self.out_restante_payments.setValue(new_restante)

    def get_payments_data(self):
        payments = []
        for r in range(self.tbl_payments.rowCount()):
            cmb = self.tbl_payments.cellWidget(r, 0)
            monto_bs = self.tbl_payments.cellWidget(r, 1)
            monto_usd = self.tbl_payments.cellWidget(r, 2)
            banco = self.tbl_payments.cellWidget(r, 3)
            ref = self.tbl_payments.cellWidget(r, 4)
            
            if not cmb or cmb.currentIndex() == 0: continue
            
            val_usd = monto_usd.value()
            if val_usd <= 0: continue
            
            payments.append({
                'payment_method': cmb.currentText(),
                'amount_usd': val_usd,
                'amount_bs': monto_bs.value(),
                'exchange_rate': self.edt_tasa_bcv_payments.value(),
                'bank': banco.text(),
                'reference': ref.text()
            })
        return payments

class PendingPaymentsView(QWidget):
    def __init__(self, session_factory: sessionmaker, parent=None):
        super().__init__(parent)
        self._session_factory = session_factory
        self._setup_ui()
        self.refresh()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header Title
        title = QLabel("Cuentas por Cobrar")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # Tabs
        self.tabs = QTabWidget()
        
        # Tab 1: Pendientes
        self.tab_pending = QWidget()
        self._setup_pending_tab(self.tab_pending)
        self.tabs.addTab(self.tab_pending, "⏳ Pendientes")
        
        # Tab 2: Pagos Realizados
        self.tab_history = QWidget()
        self._setup_history_tab(self.tab_history)
        self.tabs.addTab(self.tab_history, "✅ Pagos realizados")
        
        layout.addWidget(self.tabs)
        
        # Connect tab change to refresh
        self.tabs.currentChanged.connect(self.refresh)

    def _setup_pending_tab(self, widget):
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        # Search
        lbl_search = QLabel("Búsqueda:")
        self.search_pending = QLineEdit()
        self.search_pending.setPlaceholderText("🔍 Buscar por orden, cliente...")
        self.search_pending.textChanged.connect(lambda: self._filter_table(self.table_pending, self.search_pending))
        
        toolbar.addWidget(lbl_search)
        toolbar.addWidget(self.search_pending, 1)
        
        # Buttons
        self.btn_pay = QPushButton("💰 Registrar Pago")
        self.btn_pay.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
                color: #2c3e50;
            }
            QPushButton:hover {
                background-color: #ecf0f1;
            }
        """)
        self.btn_pay.clicked.connect(self._on_pay)
        
        self.btn_refresh_pending = QPushButton("🔄 Actualizar")
        self.btn_refresh_pending.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
                color: #2c3e50;
            }
            QPushButton:hover {
                background-color: #ecf0f1;
            }
        """)
        self.btn_refresh_pending.clicked.connect(self.refresh)
        
        toolbar.addWidget(self.btn_pay)
        toolbar.addWidget(self.btn_refresh_pending)
        
        layout.addLayout(toolbar)
        
        # Table
        # Columns: ID, Fecha Venta, Núm. Orden, Cliente, Asesor, Artículo, Total $, Abonado $, Restante $, Días Pendiente
        cols = ["ID", "Fecha Venta", "Núm. Orden", "Cliente", "Asesor", "Artículo", "Total $", "Abonado $", "Restante $", "Días Pendiente"]
        self.table_pending = QTableWidget(0, len(cols))
        self.table_pending.setHorizontalHeaderLabels(cols)
        self._style_table(self.table_pending)
        layout.addWidget(self.table_pending)
        
        # Status label
        self.lbl_status_pending = QLabel("")
        self.lbl_status_pending.setStyleSheet("color: #7f8c8d; font-style: italic;")
        layout.addWidget(self.lbl_status_pending, 0, Qt.AlignmentFlag.AlignRight)

    def _setup_history_tab(self, widget):
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        # Search
        lbl_search = QLabel("Búsqueda:")
        self.search_history = QLineEdit()
        self.search_history.setPlaceholderText("🔍 Buscar por orden, usuario...")
        self.search_history.textChanged.connect(lambda: self._filter_table(self.table_history, self.search_history))
        
        toolbar.addWidget(lbl_search)
        toolbar.addWidget(self.search_history, 1)
        
        # Buttons
        self.btn_refresh_history = QPushButton("🔄 Actualizar")
        self.btn_refresh_history.clicked.connect(self.refresh)
        
        toolbar.addWidget(self.btn_refresh_history)
        
        layout.addLayout(toolbar)
        
        # Table
        # Columns: ID Pago, Fecha Pago, Núm. Orden, Cliente, Monto $, Usuario, Observaciones
        cols = ["ID Pago", "Fecha Pago", "Núm. Orden", "Cliente", "Monto $", "Usuario", "Observaciones"]
        self.table_history = QTableWidget(0, len(cols))
        self.table_history.setHorizontalHeaderLabels(cols)
        self._style_table(self.table_history)
        layout.addWidget(self.table_history)

    def _style_table(self, table):
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)

    def refresh(self):
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:
            self._refresh_pending()
        else:
            self._refresh_history()

    def _refresh_pending(self):
        try:
            with self._session_factory() as session:
                sales = get_pending_sales(session)
                self.table_pending.setRowCount(len(sales))
                self.sales_map = {} # Row -> Sale Object
                
                now = datetime.now()
                
                for i, sale in enumerate(sales):
                    # Guardamos datos para el diálogo
                    self.sales_map[i] = {
                        'id': sale.id,
                        'numero_orden': sale.numero_orden,
                        'cliente': sale.cliente,
                        'restante': sale.restante,
                        'total_usd': sale.venta_usd
                    }
                    
                    days_pending = (now - sale.fecha).days
                    
                    # Columns: ID, Fecha Venta, Núm. Orden, Cliente, Asesor, Artículo, Total $, Abonado $, Restante $, Días Pendiente
                    self.table_pending.setItem(i, 0, QTableWidgetItem(str(sale.id)))
                    self.table_pending.setItem(i, 1, QTableWidgetItem(sale.fecha.strftime("%d/%m/%Y")))
                    self.table_pending.setItem(i, 2, QTableWidgetItem(sale.numero_orden))
                    self.table_pending.setItem(i, 3, QTableWidgetItem(sale.cliente or "N/A"))
                    self.table_pending.setItem(i, 4, QTableWidgetItem(sale.asesor or "N/A"))
                    self.table_pending.setItem(i, 5, QTableWidgetItem(sale.articulo or ""))
                    self.table_pending.setItem(i, 6, QTableWidgetItem(f"${sale.venta_usd:.2f}"))
                    self.table_pending.setItem(i, 7, QTableWidgetItem(f"${(sale.abono_usd or 0.0):.2f}"))
                    
                    item_rest = QTableWidgetItem(f"${sale.restante:.2f}")
                    item_rest.setForeground(QColor("#e74c3c")) # Red
                    item_rest.setFont(QFont("", -1, QFont.Weight.Bold))
                    self.table_pending.setItem(i, 8, item_rest)
                    
                    self.table_pending.setItem(i, 9, QTableWidgetItem(str(days_pending)))
                
                self.lbl_status_pending.setText(f"{len(sales)} ventas pendientes")
                self._filter_table(self.table_pending, self.search_pending)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar pendientes: {e}")

    def _refresh_history(self):
        try:
            with self._session_factory() as session:
                payments = get_payments_history(session)
                self.table_history.setRowCount(len(payments))
                
                for i, pay in enumerate(payments):
                    # Columns: ID Pago, Fecha Pago, Núm. Orden, Cliente, Monto $, Usuario, Observaciones
                    self.table_history.setItem(i, 0, QTableWidgetItem(str(pay.id)))
                    self.table_history.setItem(i, 1, QTableWidgetItem(pay.payment_date.strftime("%d/%m/%Y %H:%M")))
                    
                    order_num = pay.sale.numero_orden if pay.sale else "N/A"
                    client = pay.sale.cliente if pay.sale else "N/A"
                    user = pay.sale.asesor if pay.sale else "N/A" # Usamos asesor de la venta por ahora
                    
                    self.table_history.setItem(i, 2, QTableWidgetItem(order_num))
                    self.table_history.setItem(i, 3, QTableWidgetItem(client))
                    
                    item_amount = QTableWidgetItem(f"${pay.amount_usd:.2f}")
                    item_amount.setForeground(QColor("#2ecc71")) # Green
                    self.table_history.setItem(i, 4, item_amount)
                    
                    self.table_history.setItem(i, 5, QTableWidgetItem(user))
                    
                    obs = f"{pay.payment_method}"
                    if pay.reference:
                        obs += f" - Ref: {pay.reference}"
                    if pay.bank:
                        obs += f" ({pay.bank})"
                    self.table_history.setItem(i, 6, QTableWidgetItem(obs))
                    
                self._filter_table(self.table_history, self.search_history)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar historial: {e}")

    def _filter_table(self, table, search_input):
        text = search_input.text().lower()
        for row in range(table.rowCount()):
            match = False
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item and text in item.text().lower():
                    match = True
                    break
            table.setRowHidden(row, not match)

    def _on_pay(self):
        row = self.table_pending.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Aviso", "Seleccione una cuenta por cobrar")
            return
            
        # Need to map visible row to data index if filtered?
        # Actually sales_map is keyed by index in the list, but table rows match list index if not sorted/filtered
        # If filtered, currentRow() is the visual row index.
        # But wait, if I hide rows, the row index in table widget remains the same? No.
        # If I hide row 0, row 1 becomes the first visible one but its index is still 1.
        # So currentRow() returns the correct index.
        # BUT if I sort, indices change. I disabled sorting for now.
        
        sale_dict = self.sales_map.get(row)
        if not sale_dict:
            return
            
        # Usamos un objeto simple para pasar al diálogo
        class SaleData:
            pass
        s = SaleData()
        s.id = sale_dict['id']
        s.numero_orden = sale_dict['numero_orden']
        s.cliente = sale_dict['cliente']
        s.restante = sale_dict['restante']
        s.total_usd = sale_dict.get('total_usd', 0.0)
        
        dlg = PaymentDialog(s, self)
        if dlg.exec():
            payments_data = dlg.get_payments_data()
            if not payments_data:
                return

            try:
                with self._session_factory() as session:
                    for p_data in payments_data:
                        register_payment(session, s.id, **p_data)
                QMessageBox.information(self, "Éxito", "Pagos registrados correctamente")
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al registrar pago: {e}")
