from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, 
    QPushButton, QTableWidget, QHeaderView, QTableWidgetItem,
    QMessageBox, QDialog, QFormLayout, QComboBox, QDoubleSpinBox,
    QLineEdit, QDateEdit, QTextEdit, QCheckBox, QFrame
)
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QColor
from datetime import datetime
from sqlalchemy import not_, func
from ..models import (
    AccountsPayable, Supplier, Worker, Transaction, 
    TransactionCategory, Account, Delivery, DeliveryPayment, User
)

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
        
        self.tabs.addTab(self.suppliers_tab, "Proveedores (Facturas)")
        self.tabs.addTab(self.payroll_tab, "Empleados (Nómina)")
        self.tabs.addTab(self.delivery_tab, "Delivery (Motorizados)")
        
        layout.addWidget(self.tabs)
        
    def refresh_all(self):
        self.suppliers_tab.load_data()
        self.payroll_tab.refresh()
        self.delivery_tab.load_data()


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
        
        self.load_data()

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
        self.designers_tab = PayrollList(session_factory, "designers", self)
        self.general_tab = PayrollList(session_factory, "general", self)

        self.tabs.addTab(self.designers_tab, "Diseñadores (Semanal)")
        self.tabs.addTab(self.general_tab, "General (Quincenal)")
        layout.addWidget(self.tabs)

    def refresh(self):
        self.designers_tab.load_data()
        self.general_tab.load_data()


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
        self._load_accounts()
        top.addWidget(self.cb_account)
        top.addStretch()
        layout.addLayout(top)

        self.table = QTableWidget()
        headers = ["ID", "Nombre", "Cargo", "Salario Mensual", "Pago Est.", "Acción"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        self.load_data()

    def _load_accounts(self):
        self.cb_account.clear()
        with self.session_factory() as session:
            accounts = session.query(Account).filter(Account.is_active == True).all()
            for a in accounts:
                self.cb_account.addItem(f"{a.name} ({a.currency})", a.id)

    def load_data(self):
        self.table.setRowCount(0)
        with self.session_factory() as session:
            query = session.query(Worker).filter(Worker.is_active == True)
            if self.worker_type == "designers":
                query = query.filter(Worker.job_title.ilike("%diseñad%"))
            else:
                query = query.filter(not_(Worker.job_title.ilike("%diseñad%")))

            workers = query.all()
            self.table.setRowCount(len(workers))

            for i, w in enumerate(workers):
                self.table.setItem(i, 0, QTableWidgetItem(str(w.id)))
                self.table.setItem(i, 1, QTableWidgetItem(w.full_name))
                self.table.setItem(i, 2, QTableWidgetItem(w.job_title or ""))
                
                salary = w.salary or 0.0
                self.table.setItem(i, 3, QTableWidgetItem(f"$ {salary:,.2f}"))
                
                est_pay = salary / 4.0 if self.worker_type == "designers" else salary / 2.0
                self.table.setItem(i, 4, QTableWidgetItem(f"$ {est_pay:,.2f}"))

                btn_pay = QPushButton("Pagar")
                btn_pay.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_pay.setStyleSheet("background-color: #27ae60; color: white; border-radius: 4px; padding: 4px;")
                btn_pay.clicked.connect(lambda _, wid=w.id, name=w.full_name, amount=est_pay: self.pay_worker(wid, name, amount)) 
                self.table.setCellWidget(i, 5, btn_pay)

    def pay_worker(self, worker_id, name, estimated_amount):
        acc_id = self.cb_account.currentData()
        if acc_id is None:
            QMessageBox.warning(self, "Error", "Seleccione una cuenta de origen.")
            return

        period = "Semanal" if self.worker_type == "designers" else "Quincenal"
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Procesar Pago {period}")
        l = QFormLayout(dlg)

        lbl_info = QLabel(f"Trabajador: {name}\nCuenta: {self.cb_account.currentText()}")
        spin_amt = QDoubleSpinBox()
        spin_amt.setRange(0, 100000.0)
        spin_amt.setValue(estimated_amount)
        spin_amt.setPrefix("$ ")

        txt_note = QLineEdit()
        txt_note.setText(f"Pago de Nómina {period} - {datetime.now().strftime('%d/%m')}")

        l.addRow(lbl_info)
        l.addRow("Monto a Pagar:", spin_amt)
        l.addRow("Nota:", txt_note)

        btn_ok = QPushButton("Confirmar")
        btn_ok.setProperty("accent", "primary")
        btn_ok.clicked.connect(dlg.accept)
        l.addRow(btn_ok)
        
        if dlg.exec():
            with self.session_factory() as session:
                acc = session.query(Account).get(acc_id)
                acc.balance -= spin_amt.value()
                
                cat = session.query(TransactionCategory).filter(TransactionCategory.name == "Nómina").first()
                cat_id = cat.id if cat else None
                
                txn = Transaction(
                    date=datetime.now(),
                    amount=spin_amt.value(),
                    transaction_type="EXPENSE",
                    description=f"{txt_note.text()} (Trabajador ID: {worker_id})",
                    account_id=acc_id,
                    category_id=cat_id,
                    related_table="workers",
                    related_id=worker_id
                )
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
        
        self.load_data()
        
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
                # Logic to pay specific user not implemented in UI button click yet
                # We can just use the "Pagar Todo" for now or implement user specific payment later
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
