from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, 
    QPushButton, QTableWidget, QHeaderView, QTableWidgetItem,
    QMessageBox, QDialog, QFormLayout, QComboBox, QDoubleSpinBox,
    QLineEdit, QDateEdit, QTextEdit, QCheckBox, QFrame
)
from PySide6.QtCore import Qt, Signal, QDate, QTimer
from PySide6.QtGui import QColor
from datetime import datetime
from sqlalchemy import not_, func
from ..models import (
    AccountsPayable, Supplier, Worker, Transaction, 
    TransactionCategory, Account, Delivery, DeliveryPayment, User, Sale, SalePayment
)
from ..repository import get_bcv_rate, get_payroll_status_by_month
from .pay_worker_dialog import PayWorkerDialog

class PayablesView(QWidget):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        
        layout = QVBoxLayout(self)
        
        # Title
        header = QHBoxLayout()
        lbl_title = QLabel("Cuentas por Pagar")
        lbl_title.setObjectName("HeaderTitle")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 600; color: #e5e7eb; margin-bottom: 10px;")
        header.addWidget(lbl_title)
        
        btn_refresh = QPushButton("Actualizar")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self.refresh_all)
        header.addStretch()
        header.addWidget(btn_refresh)
        
        layout.addLayout(header)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane { border: 1px solid #243244; }")
        
        self.suppliers_tab = SuppliersPayableManager(session_factory, self)
        self.payroll_tab = PayrollManagerAll(session_factory, self)
        self.delivery_tab = DeliveryPayableManager(session_factory, self)
        self.commissions_tab = CommissionsManager(session_factory, self)
        self.bonuses_tab = BonusesManager(session_factory, self)
        
        self.tabs.addTab(self.suppliers_tab, "Proveedores (Facturas)")
        self.tabs.addTab(self.payroll_tab, "Empleados (Nómina)")
        self.tabs.addTab(self.delivery_tab, "Delivery (Motorizados)")
        self.tabs.addTab(self.commissions_tab, "Comisiones")
        self.tabs.addTab(self.bonuses_tab, "Bonos")
        
        layout.addWidget(self.tabs)
        
        # Optimize startup: Load data asynchronously/delayed
        QTimer.singleShot(100, self.refresh_all)
        
    def refresh_all(self):
        # Refresh all tabs
        self.suppliers_tab.load_data()
        self.payroll_tab.refresh()
        self.delivery_tab.load_data()
        self.bonuses_tab.load_data()


# --- TAB 1: SUPPLIERS (Moved from Accounting View) ---
class SuppliersPayableManager(QWidget):
    data_changed = Signal()

    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        layout = QVBoxLayout(self)
        
        bar = QHBoxLayout()
        self.btn_add = QPushButton("Registrar Factura")
        self.btn_add.setProperty("accent", "primary")
        self.btn_add.clicked.connect(self.on_add_bill)
        
        self.btn_pay = QPushButton("Pagar Seleccionada")
        self.btn_pay.clicked.connect(self.on_pay_bill)
        
        self.chk_show_paid = QCheckBox("Mostrar Pagadas")
        self.chk_show_paid.setChecked(False)
        self.chk_show_paid.stateChanged.connect(self.load_data)

        bar.addWidget(self.btn_add)
        bar.addWidget(self.btn_pay)
        bar.addStretch()
        bar.addWidget(self.chk_show_paid)
        layout.addLayout(bar)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Proveedor", "Fecha Emisión", "Vence", "Monto", "Estado", "Descripción"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # self.load_data() - Moved to delayed refresh

    def load_data(self):
        show_paid = self.chk_show_paid.isChecked()
        self.table.setRowCount(0)
        
        with self.session_factory() as session:
            query = session.query(AccountsPayable)
            if not show_paid:
                query = query.filter(AccountsPayable.status != 'PAID')
                
            bills = query.order_by(AccountsPayable.issue_date.desc()).all()
            
            self.table.setRowCount(len(bills))
            for i, bill in enumerate(bills):
                self.table.setItem(i, 0, QTableWidgetItem(str(bill.id)))
                self.table.setItem(i, 1, QTableWidgetItem(bill.supplier_name))
                self.table.setItem(i, 2, QTableWidgetItem(bill.issue_date.strftime("%d/%m/%Y")))
                due_str = bill.due_date.strftime("%d/%m/%Y") if bill.due_date else "-"
                self.table.setItem(i, 3, QTableWidgetItem(due_str))
                self.table.setItem(i, 4, QTableWidgetItem(f"{bill.currency} {bill.amount:,.2f}"))
                
                st_item = QTableWidgetItem(bill.status)
                if bill.status == 'PENDING': st_item.setForeground(QColor("#f1c40f")) 
                elif bill.status == 'OVERDUE': st_item.setForeground(QColor("#e74c3c"))
                elif bill.status == 'PAID': st_item.setForeground(QColor("#2ecc71"))
                self.table.setItem(i, 5, st_item)
                
                self.table.setItem(i, 6, QTableWidgetItem(bill.description))

    def on_add_bill(self):
        # We need to import the dialogs or define them in this file. 
        # For simplicity, assuming they are imported or redefined here.
        # Ideally, we should move the dialog classes to a shared file or keep them in this file.
        # Let's define them below in this file.
        dlg = RegisterBillDialog(self.session_factory, self)
        if dlg.exec():
            self.load_data()
            self.data_changed.emit()

    def on_pay_bill(self):
        row = self.table.currentRow()
        if row < 0: return
        bill_id = int(self.table.item(row, 0).text())
        status = self.table.item(row, 5).text()
        if status == 'PAID':
            QMessageBox.information(self, "Info", "Esta factura ya está pagada")
            return
        
        dlg = PayBillDialog(bill_id, self.session_factory, self)
        if dlg.exec():
            self.load_data()
            self.data_changed.emit()


# --- TAB 2: PAYROLL (Moved from Accounting View and Consolidated) ---
class PayrollManagerAll(QWidget):
    data_changed = Signal()

    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.designers_tab = PayrollList(session_factory, "SEMANAL", self)
        self.general_tab = PayrollList(session_factory, "QUINCENAL", self)

        self.tabs.addTab(self.designers_tab, "Semanal (Diseñadores/Obreros)")
        self.tabs.addTab(self.general_tab, "Quincenal (General)")
        layout.addWidget(self.tabs)

    def refresh(self):
        self.designers_tab.reload()
        self.general_tab.reload()


class PayrollList(QWidget):
    payment_made = Signal()

    def __init__(self, session_factory, worker_type, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.worker_type = worker_type 

        layout = QVBoxLayout(self)
        
        top = QHBoxLayout()
        # Account Selection for Payments
        top.addWidget(QLabel("Pagar desde:"))
        self.cb_account = QComboBox()
        self.cb_account.setMinimumWidth(150)
        # self._load_accounts() - Delayed
        top.addWidget(self.cb_account)
        
        btn_hist = QPushButton("📜 Historial de Pagos")
        btn_hist.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_hist.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50; 
                color: white; 
                border: 1px solid #34495e; 
                padding: 5px 10px; 
                border-radius: 4px;
                margin-left: 10px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
        """)
        btn_hist.clicked.connect(self.open_history)
        top.addWidget(btn_hist)

        top.addStretch()
        layout.addLayout(top)

        self.table = QTableWidget()
        self.config_columns()
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # self.load_data() - Delayed
    
    def config_columns(self):
        header = self.table.horizontalHeader()
        if self.worker_type == "QUINCENAL": # Quincenal
            headers = ["ID", "Nombre", "Cargo", "Salario Mensual", "1ra Quincena", "2da Quincena"]
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)
            
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(4, 140)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(5, 140)
            
        else: # Weekly
            headers = ["ID", "Nombre", "Cargo", "Salario Mensual", "Pago Est.", "Acción"]
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)
            
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(5, 140)

    def reload(self):
        self._load_accounts()
        self.load_data()

    def open_history(self):
        dlg = PayrollHistoryDialog(self.session_factory, self)
        dlg.exec()

    def _load_accounts(self):
        self.cb_account.clear()
        self.cb_account.addItem("-------- Seleccione --------", None)
        with self.session_factory() as session:
            accounts = session.query(Account).filter(Account.is_active == True).all()
            for a in accounts:
                self.cb_account.addItem(f"{a.name} ({a.currency}) - Saldo: {a.balance:,.2f}", a.id)

    def load_data(self):
        self.table.setRowCount(0)
        now = datetime.now()
        
        with self.session_factory() as session:
            # 1. Fetch Workers
            query = session.query(Worker).filter(Worker.is_active == True)
            
            # Use new payment_frequency column
            freq = "SEMANAL" if self.worker_type == "SEMANAL" else "QUINCENAL"
            query = query.filter(Worker.payment_frequency == freq)

            workers = query.all()
            
            # 2. Fetch Payment Status (only for Quincenal)
            status_map = {}
            if self.worker_type == "QUINCENAL":
                status_map = get_payroll_status_by_month(session, now.year, now.month)
            
            self.table.setRowCount(len(workers))

            for i, w in enumerate(workers):
                self.table.setItem(i, 0, QTableWidgetItem(str(w.id)))
                self.table.setItem(i, 1, QTableWidgetItem(w.full_name))
                self.table.setItem(i, 2, QTableWidgetItem(w.job_title or ""))
                
                salary = w.salary or 0.0
                self.table.setItem(i, 3, QTableWidgetItem(f"$ {salary:,.2f}"))
                
                if self.worker_type == "QUINCENAL":
                    # Quincenal Logic
                    half_salary = salary / 2.0
                    w_status = status_map.get(w.id, {'q1': False, 'q2': False})
                    
                    # Col 4: 1ra Quincena
                    if w_status['q1']:
                        lbl = QLabel("PAGADO")
                        lbl.setStyleSheet("color: green; font-weight: bold; qproperty-alignment: AlignCenter;")
                        self.table.setCellWidget(i, 4, lbl)
                    else:
                        btn1 = QPushButton("Pagar")
                        btn1.setCursor(Qt.CursorShape.PointingHandCursor)
                        btn1.setStyleSheet("background-color: #3498db; color: white; border-radius: 4px; padding: 4px;")
                        btn1.clicked.connect(lambda _, wid=w.id, name=w.full_name, amount=half_salary, q=1: self.pay_worker(wid, name, amount, q))
                        self.table.setCellWidget(i, 4, btn1)
                        
                    # Col 5: 2da Quincena
                    if w_status['q2']:
                        lbl = QLabel("PAGADO")
                        lbl.setStyleSheet("color: green; font-weight: bold; qproperty-alignment: AlignCenter;")
                        self.table.setCellWidget(i, 5, lbl)
                    else:
                        btn2 = QPushButton("Pagar")
                        btn2.setCursor(Qt.CursorShape.PointingHandCursor)
                        btn2.setStyleSheet("""
                            QPushButton { background-color: #3498db; color: white; border-radius: 4px; padding: 4px; }
                            QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }
                        """)
                        
                        # Disable logic: Only enable after the 25th
                        if now.day <= 25:
                            btn2.setEnabled(False)
                            btn2.setToolTip("Disponible después del día 25")
                        else:
                            btn2.setEnabled(True)
                            
                        btn2.clicked.connect(lambda _, wid=w.id, name=w.full_name, amount=half_salary, q=2: self.pay_worker(wid, name, amount, q))
                        self.table.setCellWidget(i, 5, btn2)

                else:
                    # Weekly Logic
                    est_pay = salary / 4.0 
                    self.table.setItem(i, 4, QTableWidgetItem(f"$ {est_pay:,.2f}"))

                    btn_pay = QPushButton("Pagar Semanal")
                    btn_pay.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_pay.setStyleSheet("background-color: #27ae60; color: white; border-radius: 4px; padding: 4px;")
                    btn_pay.clicked.connect(lambda _, wid=w.id, name=w.full_name, amount=est_pay: self.pay_worker(wid, name, amount)) 
                    self.table.setCellWidget(i, 5, btn_pay)

    def pay_worker(self, worker_id, name, estimated_amount, quincena_idx=None):
        acc_id = self.cb_account.currentData()
        if acc_id is None:
            QMessageBox.warning(self, "Error", "Seleccione una cuenta de origen.")
            return

        acc_text = self.cb_account.currentText()
        
        if self.worker_type == "QUINCENAL" and quincena_idx:
            period = "1ra Quincena" if quincena_idx == 1 else "2da Quincena"
        elif self.worker_type == "SEMANAL":
            period = "Semanal"
        else:
            period = "Nómina"

        dlg = PayWorkerDialog(self.session_factory, worker_id, acc_text, period, estimated_amount, parent=self)
        
        if dlg.exec():
            data = dlg.get_data()
            amount_usd = data["amount_usd"]
            amount_bs = data["amount_bs"]
            note = data["note"]
            
            with self.session_factory() as session:
                acc = session.query(Account).get(acc_id)
                if not acc:
                    return
                
                # Deduct based on currency
                # Assuming 'VES' or 'BS' for Bolivars
                deduction_amount = 0.0
                if acc.currency and acc.currency.upper() in ['VES', 'BS', 'BOLIVARES']:
                    deduction_amount = amount_bs
                    acc.balance -= amount_bs
                else:
                    deduction_amount = amount_usd
                    acc.balance -= amount_usd
                
                cat = session.query(TransactionCategory).filter(TransactionCategory.name == "Nómina").first()
                cat_id = cat.id if cat else None
                
                # Append Tag for Quincena tracking
                # Base description
                desc_parts = [f"{note} ({name})"]
                
                # Handle Cash Details
                if data.get("cash_details"):
                    cash_str_parts = []
                    for c in data["cash_details"]:
                        denom = c['denomination']
                        qty = c['quantity']
                        serials = c['serials']
                        cash_str_parts.append(f"${denom}x{qty} [{serials}]")
                    desc_parts.append(f"Detalle Efectivo: {', '.join(cash_str_parts)}")
                
                final_desc = " - ".join(desc_parts)
                if quincena_idx:
                    final_desc += f" [Q{quincena_idx}]"
                    
                # Use the reference from dialog
                ref_text = data.get("reference") or data.get("method")

                txn = Transaction(
                    date=datetime.now(),
                    amount=deduction_amount,
                    transaction_type="EXPENSE",
                    description=final_desc,
                    reference=ref_text,
                    account_id=acc_id,
                    category_id=cat_id,
                    related_table="workers",
                    related_id=worker_id
                )
                session.add(txn)
                session.commit()
                
                QMessageBox.information(self, "Éxito", "Pago registrado correctamente.")
                self.payment_made.emit()
                self.reload()
                session.add(txn)
                session.commit()
            QMessageBox.information(self, "Éxito", "Pago registrado.")


# --- TAB 3: DELIVERY PAYABLES ---
class DeliveryPayableManager(QWidget):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        layout = QVBoxLayout(self)
        
        top = QHBoxLayout()
        top.addWidget(QLabel("<b>Pagos a Motorizados</b>"))
        
        self.btn_pay_all = QPushButton("Pagar Todo lo Pendiente")
        self.btn_pay_all.clicked.connect(self.pay_all_dialog)
        top.addStretch()
        top.addWidget(self.btn_pay_all)
        layout.addLayout(top)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Motorizado", "Entregas Pendientes", "Monto Acumulado (Bs)", "Acción"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        # self.load_data() - Delayed
        
    def load_data(self):
        self.table.setRowCount(0)
        with self.session_factory() as session:
            # Query deliveries not paid (payment_id is NULL) and status='ENTREGADO' and payment_source='EMPRESA'
            query = session.query(
                User.full_name,
                func.count(Delivery.id),
                func.sum(Delivery.amount_bs)
            ).join(Delivery, Delivery.delivery_user_id == User.id)\
             .filter(
                 Delivery.status == 'ENTREGADO',
                 Delivery.payment_id == None,
                 Delivery.payment_source == 'EMPRESA'
             )\
             .group_by(User.id)
            
            results = query.all()
            self.table.setRowCount(len(results))
            
            for i, row in enumerate(results):
                name, count, total_bs = row
                self.table.setItem(i, 0, QTableWidgetItem(name))
                self.table.setItem(i, 1, QTableWidgetItem(str(count)))
                amount_str = f"Bs. {total_bs:,.2f}" if total_bs else "Bs. 0.00"
                self.table.setItem(i, 2, QTableWidgetItem(amount_str))
                
                btn = QPushButton("Pagar")
                btn.setStyleSheet("background-color: #3498db; color: white; padding: 4px;")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(self.pay_all_dialog)
                self.table.setItem(i, 3, QTableWidgetItem("")) # Placeholder
                self.table.setCellWidget(i, 3, btn)
                
    def pay_all_dialog(self):
        # Could re-use PaymentDialog from deliveries_view, 
        # but that one imports a lot. Better to make a simple one or import it.
        # "Pagar Todo" implies opening the bulk payment dialog.
        from .deliveries_view import PaymentDialog
        # Need date range. Assume "Beginning of time" to "Now"
        start = QDate(2000, 1, 1)
        end = QDate.currentDate()
        dlg = PaymentDialog(self.session_factory, start, end, self)
        if dlg.exec():
            self.load_data()


# --- DIALOGS (Suppliers) ---
class RegisterBillDialog(QDialog):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.setWindowTitle("Registrar Cuenta por Pagar")
        self.resize(450, 400)
        l = QFormLayout(self)
        
        self.txt_supplier = QLineEdit()
        self.txt_desc = QTextEdit()
        self.txt_desc.setMaximumHeight(60)
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.01, 1000000.0)
        self.date_issue = QDateEdit(QDate.currentDate())
        self.date_issue.setCalendarPopup(True)
        self.date_due = QDateEdit(QDate.currentDate().addDays(7))
        self.date_due.setCalendarPopup(True)
        
        l.addRow("Proveedor:", self.txt_supplier)
        l.addRow("Descripción:", self.txt_desc)
        l.addRow("Monto (USD):", self.spin_amount)
        l.addRow("Emisión:", self.date_issue)
        l.addRow("Vencimiento:", self.date_due)
        
        btn_save = QPushButton("Guardar")
        btn_save.clicked.connect(self.save)
        l.addRow(btn_save)
        
    def save(self):
        supp_name = self.txt_supplier.text().strip()
        amt = self.spin_amount.value()
        if not supp_name or amt <= 0: return

        with self.session_factory() as session:
            supplier = session.query(Supplier).filter(Supplier.name.ilike(supp_name)).first()
            if not supplier:
                supplier = Supplier(name=supp_name)
                session.add(supplier)
                session.flush()
            
            bill = AccountsPayable(
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                description=self.txt_desc.toPlainText(),
                amount=amt,
                currency="USD",
                issue_date=self.date_issue.date().toPython(),
                due_date=self.date_due.date().toPython(),
                status='PENDING'
            )
            session.add(bill)
            session.commit()
        self.accept()

class PayBillDialog(QDialog):
    def __init__(self, bill_id, session_factory, parent=None):
        super().__init__(parent)
        self.bill_id = bill_id
        self.session_factory = session_factory
        self.setWindowTitle("Pagar Factura")
        l = QFormLayout(self)
        
        self.cb_account = QComboBox()
        self._load_accounts()
        l.addRow("Cuenta:", self.cb_account)
        
        self.txt_ref = QLineEdit()
        l.addRow("Referencia:", self.txt_ref)
        
        btn = QPushButton("Pagar")
        btn.clicked.connect(self.pay)
        l.addRow(btn)

    def _load_accounts(self):
        with self.session_factory() as session:
            accounts = session.query(Account).filter(Account.is_active == True).all()
            for a in accounts:
                self.cb_account.addItem(f"{a.name} ({a.currency})", a.id)

    def pay(self):
        acc_id = self.cb_account.currentData()
        if not acc_id: return
        
        with self.session_factory() as session:
            bill = session.query(AccountsPayable).get(self.bill_id)
            acc = session.query(Account).get(acc_id)
            
            acc.balance -= bill.amount
            txn = Transaction(
                date=datetime.now(),
                amount=bill.amount,
                transaction_type='EXPENSE',
                description=f"Pago Factura #{bill.id} - {bill.supplier_name}",
                account_id=acc.id,
                reference=self.txt_ref.text(),
                related_table="accounts_payable",
                related_id=bill.id
            )
            session.add(txn)
            bill.status = 'PAID'
            bill.transaction_id = txn.id # will be set upon flush/commit
            session.commit()
        self.accept()

# --- TAB 4: COMMISSIONS ---
class CommissionsManager(QWidget):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        layout = QVBoxLayout(self)
        
        # Controls
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Desde:"))
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.setCalendarPopup(True)
        controls.addWidget(self.date_from)
        
        controls.addWidget(QLabel("Hasta:"))
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        controls.addWidget(self.date_to)
        
        btn_calc = QPushButton("Calcular Comisiones")
        btn_calc.clicked.connect(self.calculate_commissions)
        controls.addWidget(btn_calc)
        controls.addStretch()
        layout.addLayout(controls)
        
        # Table
        self.table = QTableWidget()
        headers = ["Trabajador", "Ventas Período ($)", "% Com.", "Comisión ($)", "Comisión (Bs)", "Acción"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.table)

    def calculate_commissions(self):
        start_date = self.date_from.date().toPython()
        # End date should include the full day
        end_date = datetime.combine(self.date_to.date().toPython(), datetime.max.time().replace(microsecond=0))
        # Start date at 00:00
        start_date = datetime.combine(start_date, datetime.min.time())
        
        self.table.setRowCount(0)
        
        with self.session_factory() as session:
            workers = session.query(Worker).filter(Worker.is_active == True, Worker.commission_pct > 0).all()
            
            row_idx = 0
            for worker in workers:
                if not worker.user_id:
                    continue
                user = session.get(User, worker.user_id)
                if not user:
                    continue
                
                # Queries sales by advisor/seller
                # FILTER: Only Fully Paid Sales (restante <= 0.01)
                # AND Only sales where commission has NOT been paid yet (commission_paid == False)
                sales_candidates = session.query(Sale).filter(
                    Sale.asesor == user.username,
                    Sale.restante <= 0.01 
                ).all()
                
                total_sales_usd_mapped = 0
                comm_usd = 0.0
                comm_bs = 0.0
                
                pct = worker.commission_pct / 100.0
                
                sales_in_batch = []

                # Identify currency based on payment method keywords
                # Default to USD unless method suggests BS
                BS_KEYWORDS = ['pago móvil', 'transferencia', 'punto', 'biopago', 'bs', 'bolivares']

                for sale in sales_candidates:
                    # Check flag first
                    if sale.commission_paid:
                        continue

                    # Determine Completion Date (When it became fully paid)
                    # We assume the date of the LAST payment is the completion date.
                    effective_date = sale.fecha
                    if sale.payments:
                        dates = [p.payment_date for p in sale.payments if p.payment_date]
                        if dates:
                            effective_date = max(dates)
                    
                    # Ensure effective_date is comparable (it is usually datetime)
                    # Input start_date / end_date are datetime
                    if not (start_date <= effective_date <= end_date):
                        continue

                    sales_in_batch.append(sale)

                    # Logic: Calculate commission based on payments registered for these sales
                    for pay in sale.payments:
                        method_lower = (pay.payment_method or '').lower()
                        is_bs = any(k in method_lower for k in BS_KEYWORDS) and 'zelle' not in method_lower and 'usd' not in method_lower and '$' not in method_lower

                        if is_bs:
                            # Commission in Bs
                            comm_bs += (pay.amount_bs * pct)
                        else:
                            # Commission in USD
                            comm_usd += (pay.amount_usd * pct)
                        
                    total_sales_usd_mapped += sale.venta_usd

                if comm_usd > 0.01 or comm_bs > 0.01:
                    self.table.insertRow(row_idx)
                    self.table.setItem(row_idx, 0, QTableWidgetItem(worker.full_name))
                    self.table.setItem(row_idx, 1, QTableWidgetItem(f"$ {total_sales_usd_mapped:,.2f}"))
                    self.table.setItem(row_idx, 2, QTableWidgetItem(f"{worker.commission_pct}%"))
                    self.table.setItem(row_idx, 3, QTableWidgetItem(f"$ {comm_usd:,.2f}"))
                    self.table.setItem(row_idx, 4, QTableWidgetItem(f"Bs {comm_bs:,.2f}"))
                    
                    btn_pay = QPushButton("Pagar")
                    btn_pay.setProperty("accent", "primary")
                    # Pass the specific sales list for this batch
                    btn_pay.clicked.connect(lambda _, w=worker, cu=comm_usd, cb=comm_bs, s=sales_in_batch: self.pay_commission(w, cu, cb, s))
                    self.table.setCellWidget(row_idx, 5, btn_pay)
                    
                    row_idx += 1

    def pay_commission(self, worker, comm_usd, comm_bs, sales_list):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Pago Comisión - {worker.full_name}")
        l = QFormLayout(dlg)
        
        l.addRow("Monto USD:", QLineEdit(f"{comm_usd:.2f}"))
        l.addRow("Monto Bs:", QLineEdit(f"{comm_bs:.2f}"))
        l.addRow(QLabel("Seleccione cuenta para registrar el egreso:"))
        
        cb_account = QComboBox()
        with self.session_factory() as session:
            accounts = session.query(Account).filter(Account.is_active==True).all()
            for a in accounts:
                cb_account.addItem(f"{a.name} ({a.currency})", a.id)
        l.addRow("Cuenta:", cb_account)
        l.addRow(QLabel("NOTA: Se creará un egreso por el total convertido si la cuenta es mono-moneda."))
        
        btn = QPushButton("Registrar Pago")
        btn.clicked.connect(dlg.accept)
        l.addRow(btn)
        
        if dlg.exec():
            # Create transaction logic
            acc_id = cb_account.currentData()
            with self.session_factory() as session:
                 acc = session.query(Account).get(acc_id)
                 
                 worker = session.merge(worker)
                 
                 # Simplification: Convert everything to account currency and charge
                 # Real world: Split payment.
                 
                 total_charge = 0
                 
                 # Get Rate
                 try: 
                     rate = get_bcv_rate()
                     if not rate or rate <= 0: rate = 1.0
                 except: rate = 1.0

                 if acc.currency == 'USD':
                     total_charge = comm_usd + (comm_bs / rate)
                 else:
                     # BS Account
                     total_charge = comm_bs + (comm_usd * rate)
                 
                 acc.balance -= total_charge
                 
                 cat = session.query(TransactionCategory).filter(TransactionCategory.name == "Comisiones").first()
                 if not cat:
                     cat = TransactionCategory(name="Comisiones", type="EXPENSE")
                     session.add(cat)
                     session.flush()
                 cat_id = cat.id
                 
                 txn = Transaction(
                     date=datetime.now(),
                     amount=total_charge,
                     transaction_type="EXPENSE",
                     description=f"Pago Comisiones {worker.full_name}",
                     account_id=acc.id,
                     category_id=cat_id,
                     related_table="workers",
                     related_id=worker.id
                 )
                 session.add(txn)
                 
                 # Mark sales as commission paid
                 if sales_list:
                     for s_obj in sales_list:
                         # Re-fetch or merge to ensure attachment to current session
                         # s_obj comes from calculate_commissions query which closed its session
                         # But objects are detached. merge() is safer.
                         s_persistent = session.merge(s_obj)
                         s_persistent.commission_paid = True
                 
                 session.commit()
            
            QMessageBox.information(self, "Registrado", "Pago de comisión registrado.")
            self.calculate_commissions() # refresh

# --- TAB 5: BONUSES ---
class BonusesManager(QWidget):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        layout = QVBoxLayout(self)
        
        top = QHBoxLayout()
        btn_load = QPushButton("Cargar Bonos Configurados")
        btn_load.clicked.connect(self.load_data)
        top.addWidget(btn_load)
        top.addStretch()
        layout.addLayout(top)
        
        self.table = QTableWidget()
        headers = ["Trabajador", "Asistencia ($)", "Alimentación ($)", "Responsabilidad ($)", "Total ($)", "Total (Bs)", "Acción"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        # Load data delayed
        
    def load_data(self):
        # ... logic ...

        try:
            rate = get_bcv_rate()
            if not rate: rate = 1.0
        except: rate = 1.0
        
        with self.session_factory() as session:
            workers = session.query(Worker).filter(Worker.is_active == True).all()
            
            row_idx = 0
            for worker in workers:
                b_att = worker.bonus_attendance or 0
                b_food = worker.bonus_food or 0
                b_role = worker.bonus_role or 0
                
                if b_att == 0 and b_food == 0 and b_role == 0:
                    continue
                    
                total_usd = b_att + b_food + b_role
                total_bs = total_usd * rate
                
                self.table.insertRow(row_idx)
                self.table.setItem(row_idx, 0, QTableWidgetItem(worker.full_name))
                self.table.setItem(row_idx, 1, QTableWidgetItem(f"{b_att}"))
                self.table.setItem(row_idx, 2, QTableWidgetItem(f"{b_food}"))
                self.table.setItem(row_idx, 3, QTableWidgetItem(f"{b_role}"))
                self.table.setItem(row_idx, 4, QTableWidgetItem(f"$ {total_usd:.2f}"))
                self.table.setItem(row_idx, 5, QTableWidgetItem(f"Bs {total_bs:,.2f}"))
                
                btn_pay = QPushButton("Pagar Bonos")
                btn_pay.clicked.connect(lambda _, w=worker, t=total_usd: self.pay_bonus(w, t))
                self.table.setCellWidget(row_idx, 6, btn_pay)
                
                row_idx += 1

    def pay_bonus(self, worker, amount_usd):
        # Dialog to confirm checks (Validation)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Pago Bonos - {worker.full_name}")
        l = QFormLayout(dlg)
        
        l.addRow(QLabel("Verifique los bonos a pagar:"))
        chk_att = QCheckBox(f"Asistencia (${worker.bonus_attendance or 0})")
        chk_att.setChecked(True)
        chk_food = QCheckBox(f"Alimentación (${worker.bonus_food or 0})")
        chk_food.setChecked(True)
        chk_role = QCheckBox(f"Responsabilidad (${worker.bonus_role or 0})")
        chk_role.setChecked(True)
        
        l.addRow(chk_att)
        l.addRow(chk_food)
        l.addRow(chk_role)
        
        cb_account = QComboBox()
        with self.session_factory() as session:
            accounts = session.query(Account).filter(Account.is_active==True).all()
            for a in accounts:
                cb_account.addItem(f"{a.name} ({a.currency})", a.id)
        l.addRow("Cuenta Egreso:", cb_account)
        
        btn = QPushButton("Pagar Selección")
        btn.clicked.connect(dlg.accept)
        l.addRow(btn)
        
        if dlg.exec():
            # Calculate total based on checks
            final_usd = 0
            if chk_att.isChecked(): final_usd += (worker.bonus_attendance or 0)
            if chk_food.isChecked(): final_usd += (worker.bonus_food or 0)
            if chk_role.isChecked(): final_usd += (worker.bonus_role or 0)
            
            if final_usd <= 0: return
            
            acc_id = cb_account.currentData()
            with self.session_factory() as session:
                acc = session.query(Account).get(acc_id)
                worker = session.merge(worker)

                # Convert to account currency
                amt_deduct = final_usd
                try: rate = get_bcv_rate() 
                except: rate = 1.0
                if not rate: rate = 1.0

                if acc.currency == 'VES':
                    amt_deduct = final_usd * rate
                
                acc.balance -= amt_deduct
                
                cat = session.query(TransactionCategory).filter(TransactionCategory.name == "Bonos").first()
                if not cat:
                    cat = TransactionCategory(name="Bonos", type="EXPENSE")
                    session.add(cat)
                    session.flush()
                cat_id = cat.id
                
                txn = Transaction(
                     date=datetime.now(),
                     amount=amt_deduct,
                     transaction_type="EXPENSE",
                     description=f"Pago Bonos {worker.full_name}",
                     account_id=acc.id,
                     category_id=cat_id,
                     related_table="workers",
                     related_id=worker.id
                )
                session.add(txn)
                session.commit()
            
            QMessageBox.information(self, "Listo", "Pago de bonos registrado.")
            self.load_data()


class PayrollHistoryDialog(QDialog):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.setWindowTitle("Historial de Pagos (Nómina)")
        self.resize(1000, 600)
        
        layout = QVBoxLayout(self)
        
        # Filters (Optional, maybe Month/Year later, for now just a list)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Fecha", "Descripción", "Monto", "Cuenta", "Referencia", "ID Transacción"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)
        
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        
        self.load_data()
        
    def load_data(self):
        self.table.setRowCount(0)
        with self.session_factory() as session:
            # Query Transactions with category "Nómina"
            txs = (session.query(Transaction)
                   .join(TransactionCategory)
                   .filter(TransactionCategory.name == "Nómina")
                   .order_by(Transaction.date.desc())
                   .limit(100) # Limit to last 100 for now
                   .all())
            
            self.table.setRowCount(len(txs))
            for i, t in enumerate(txs):
                self.table.setItem(i, 0, QTableWidgetItem(t.date.strftime("%d/%m/%Y %H:%M")))
                self.table.setItem(i, 1, QTableWidgetItem(t.description))
                
                amount_str = f"{t.amount:,.2f}"
                currency = t.account.currency if t.account else ""
                self.table.setItem(i, 2, QTableWidgetItem(f"{currency} {amount_str}"))
                
                self.table.setItem(i, 3, QTableWidgetItem(t.account.name if t.account else "N/A"))
                self.table.setItem(i, 4, QTableWidgetItem(t.reference or ""))
                self.table.setItem(i, 5, QTableWidgetItem(str(t.id)))

