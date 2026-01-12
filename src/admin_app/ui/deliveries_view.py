from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QAbstractItemView, QDialog, QFormLayout,
    QComboBox, QDateEdit, QDateTimeEdit, QDialogButtonBox, QMessageBox, QLabel, QTextEdit,
    QGroupBox, QLineEdit, QDoubleSpinBox, QMenu, QCheckBox
)
from PySide6.QtCore import Qt, QDate, QDateTime
from sqlalchemy.orm import sessionmaker, joinedload, contains_eager
from datetime import datetime, time

from ..models import Delivery, DeliveryZone, Order, User, Sale, Customer, DeliveryPayment, Account, Transaction, TransactionCategory
from .delivery_zones_view import DeliveryZonesView
from sqlalchemy import func

class PaymentDialog(QDialog):
    def __init__(self, session_factory, start_date, end_date, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.start_date = start_date
        self.end_date = end_date
        self.setWindowTitle(f"Procesar Pagos ({start_date.toString('dd/MM')} - {end_date.toString('dd/MM')})")
        self.resize(700, 450)
        
        self.layout = QVBoxLayout(self)
        
        # Account Selector
        hb_acc = QHBoxLayout()
        hb_acc.addWidget(QLabel("Cuenta a Debitar (Bs):"))
        self.cb_account = QComboBox()
        self.cb_account.setMinimumWidth(200)
        self._load_accounts()
        hb_acc.addWidget(self.cb_account)
        hb_acc.addStretch()
        self.layout.addLayout(hb_acc)
        
        # Table of riders to pay
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Motorizado", "Carreras Pendientes", "Monto (Bs)", "Estado", "Acción"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        
        self.layout.addWidget(self.table)
        
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.accept)
        self.layout.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignRight)
        
        self.load_data()
        
    def load_data(self):
        self.table.setRowCount(0)
        
        # Convert QDate to datetime for query
        dt_start = datetime.combine(self.start_date.toPython(), time.min)
        dt_end = datetime.combine(self.end_date.toPython(), time.max)
        
        with self.session_factory() as session:
            # Query grouped by user
            # Filter: Date range, Payment Source=EMPRESA, Not Paid (payment_id IS NULL)
            # We assume 'status'='ENTREGADO' or maybe all statuses? 
            # Usually only delivered ones are paid. Let's filter by status='ENTREGADO' for safety?
            # Or maybe PENDIENTE/ENTREGADO? User didn't specify, but usually paid after done.
            # Let's count all that are 'EMPRESA' and payment_id is Null.
            
            results = session.query(
                User.id, 
                User.username, 
                func.count(Delivery.id), 
                func.sum(Delivery.amount_bs)
            ).join(Delivery.delivery_user)\
             .filter(Delivery.sent_at >= dt_start, Delivery.sent_at <= dt_end)\
             .filter(Delivery.payment_source == 'EMPRESA')\
             .filter(Delivery.payment_id == None)\
             .group_by(User.id, User.username).all()
            
            self.table.setRowCount(len(results))
            for i, row in enumerate(results):
                user_id, username, count, total_bs = row
                total_bs = total_bs or 0.0
                
                self.table.setItem(i, 0, QTableWidgetItem(username))
                self.table.setItem(i, 1, QTableWidgetItem(str(count)))
                self.table.setItem(i, 2, QTableWidgetItem(f"Bs. {total_bs:,.2f}"))
                self.table.setItem(i, 3, QTableWidgetItem("Pendiente"))
                
                # Pay Button
                btn_pay = QPushButton("Pagar")
                btn_pay.setStyleSheet("background-color: #2ecc71; color: white;")
                btn_pay.clicked.connect(lambda _, uid=user_id, uname=username, c=count, amt=total_bs: self.process_payment(uid, uname, c, amt))
                self.table.setCellWidget(i, 4, btn_pay)

    def _load_accounts(self):
        with self.session_factory() as session:
            # Load active VES accounts (since logic is in Bs)
            accounts = session.query(Account).filter(
                Account.is_active == True, 
                Account.currency == 'VES'
            ).all()
            
            for acc in accounts:
                self.cb_account.addItem(f"{acc.name} (Saldo: {acc.balance:,.2f})", acc.id)
                
            if not accounts:
                self.cb_account.addItem("Sin cuentas en Bs configuradas", None)
                self.btn_close.setFocus()

    def process_payment(self, user_id, username, count, amount):
        acc_id = self.cb_account.currentData()
        if acc_id is None:
            QMessageBox.warning(self, "Atención", "Seleccione una cuenta para debitar el pago.")
            return

        reply = QMessageBox.question(
            self, 
            "Confirmar Pago", 
            f"¿Registrar pago a {username}?\n\nCarreras: {count}\nMonto: Bs. {amount:,.2f}\n\nSe debitará de la cuenta seleccionada.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            dt_start = datetime.combine(self.start_date.toPython(), time.min)
            dt_end = datetime.combine(self.end_date.toPython(), time.max)
            
            with self.session_factory() as session:
                # 1. Create Payment Record
                payment = DeliveryPayment(
                    rider_id=user_id,
                    amount_bs=amount,
                    quantity=count,
                    start_date=dt_start,
                    end_date=dt_end,
                    created_at=datetime.now(),
                    notes=f"Pago semana {self.start_date.toString('dd/MM')} al {self.end_date.toString('dd/MM')}"
                )
                session.add(payment)
                session.flush() # Get ID
                
                # 2. Update Deliveries
                deliveries = session.query(Delivery).filter(
                    Delivery.delivery_user_id == user_id,
                    Delivery.sent_at >= dt_start, 
                    Delivery.sent_at <= dt_end,
                    Delivery.payment_source == 'EMPRESA',
                    Delivery.payment_id == None
                ).all()
                
                for d in deliveries:
                    d.payment_id = payment.id

                # 3. Create Accounting Transaction
                cat = session.query(TransactionCategory).filter(TransactionCategory.name == "Delivery").first()
                cat_id = cat.id if cat else None
                
                txn = Transaction(
                    date=datetime.now(),
                    amount=amount,
                    transaction_type="EXPENSE",
                    description=f"Pago Semanal Delivery: {username} ({count} envíos)",
                    account_id=acc_id,
                    category_id=cat_id,
                    related_table="delivery_payments",
                    related_id=payment.id
                )
                session.add(txn)
                
                # Debit Account
                acc = session.get(Account, acc_id)
                if acc:
                    acc.balance -= amount

                session.commit()
                QMessageBox.information(self, "Éxito", "Pago registrado y contabilidad actualizada.")
                self.load_data() # Refresh table
                self._load_accounts() # Update balance display (simple reload: clears combo)
                # Ideally refresh combo properly, but clearing dupes is needed
                self.cb_account.clear()
                self._load_accounts()



class PaymentHistoryDialog(QDialog):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.setWindowTitle("Historial de Pagos a Delivery")
        self.resize(700, 500)
        self.setStyleSheet("""
             QDialog { background-color: #1e1e1e; color: white; }
             QTableWidget { background-color: #2b2b2b; color: white; gridline-color: #555; }
             QHeaderView::section { background-color: #333; color: white; padding: 4px; }
             QLabel { color: white; }
        """)
        
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7) # ID, Rider, Fecha Pago, Cantidad, Monto, Notas, Ver
        self.table.setHorizontalHeaderLabels(["ID", "Motorizado", "Fecha Pago", "Carreras", "Monto", "Notas", "Detalles"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        
        layout.addWidget(self.table)
        
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        
        self.load_data()
        
    def load_data(self):
        with self.session_factory() as session:
            payments = session.query(DeliveryPayment).options(
                joinedload(DeliveryPayment.rider)
            ).order_by(DeliveryPayment.created_at.desc()).limit(100).all()
            
            self.table.setRowCount(len(payments))
            for i, p in enumerate(payments):
                self.table.setItem(i, 0, QTableWidgetItem(str(p.id)))
                rider_name = p.rider.username if p.rider else "Unknown"
                self.table.setItem(i, 1, QTableWidgetItem(rider_name))
                self.table.setItem(i, 2, QTableWidgetItem(p.created_at.strftime("%d/%m/%Y %I:%M %p")))
                self.table.setItem(i, 3, QTableWidgetItem(str(p.quantity)))
                self.table.setItem(i, 4, QTableWidgetItem(f"Bs. {p.amount_bs:,.2f}"))
                self.table.setItem(i, 5, QTableWidgetItem(p.notes or ""))
                
                btn_view = QPushButton("Ver")
                btn_view.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_view.setStyleSheet("background-color: #3498db; color: white; border: none; padding: 4px; border-radius: 4px;")
                btn_view.clicked.connect(lambda _, pid=p.id: self.show_details(pid))
                self.table.setCellWidget(i, 6, btn_view)
                
    def show_details(self, payment_id):
        dlg = PaymentDetailsDialog(payment_id, self.session_factory, self)
        dlg.exec()

class PaymentDetailsDialog(QDialog):
    def __init__(self, payment_id, session_factory, parent=None):
        super().__init__(parent)
        self.payment_id = payment_id
        self.session_factory = session_factory
        self.setWindowTitle(f"Detalles de Pago #{payment_id}")
        self.resize(800, 500)
        self.setStyleSheet("QDialog { background-color: #1e1e1e; color: white; }")
        
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Fecha Envio", "Orden", "Zona", "Monto (Bs)", "Dirección"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("QTableWidget { background-color: #2b2b2b; color: white; alternate-background-color: #333; }")
        layout.addWidget(self.table)
        
        btn_ok = QPushButton("Cerrar")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)
        
        self._load()
        
    def _load(self):
        with self.session_factory() as session:
            # Import Order inside method to avoid circular imports if any, though not expected here
            from ..models import Delivery, Order
            
            deliveries = session.query(Delivery).options(joinedload(Delivery.order)).filter(Delivery.payment_id == self.payment_id).all()
            
            self.table.setRowCount(len(deliveries))
            for i, d in enumerate(deliveries):
                sent_str = d.sent_at.strftime("%d/%m/%Y %I:%M %p") if d.sent_at else "-"
                self.table.setItem(i, 0, QTableWidgetItem(sent_str))
                
                order_txt = d.order.order_number if d.order else str(d.order_id)
                self.table.setItem(i, 1, QTableWidgetItem(order_txt))
                
                # Zone name not easily available without join, assuming we might need to join or fetch.
                # Delivery model has relation 'zone'
                zone_name = d.zone.name if d.zone else "-"
                self.table.setItem(i, 2, QTableWidgetItem(zone_name))
                
                self.table.setItem(i, 3, QTableWidgetItem(f"Bs. {d.amount_bs:,.2f}"))
                
                # Address from order? Order has no address directly usually, it's on customer, or notes
                # Let's check model. Order probably has client info or description
                # Checking Delivery model.. delivery.notes might be useful, or checking context
                
                # Using delivery notes or order details
                address_guess = d.notes or "-"
                self.table.setItem(i, 4, QTableWidgetItem(address_guess))

class CreateDeliveryDialog(QDialog):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.setWindowTitle("Nuevo Despacho / Delivery")
        self.resize(500, 500)
        
        # Style Refined to remove Blue Tint (#0b1220 -> #1a1a1a)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; color: #e5e7eb; }
            QLabel { color: #e5e7eb; font-weight: normal; }
            QGroupBox {
                border: 1px solid #374151;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                font-weight: bold;
                color: #e5e7eb;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                left: 10px;
                background-color: #1a1a1a; /* Hide border behind title */
            }
            QComboBox, QDateEdit, QDateTimeEdit, QTextEdit, QLineEdit {
                background-color: #2b2b2b;
                color: #e5e7eb;
                border: 1px solid #374151;
                padding: 5px;
                border-radius: 4px;
            }
            QComboBox:focus, QDateEdit:focus, QDateTimeEdit:focus, QTextEdit:focus {
                border: 1px solid #FF6900;
            }
            QPushButton {
                background-color: #2b2b2b;
                color: #e5e7eb;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #333333; }
        """)

        layout = QVBoxLayout(self)
        
        # --- Group 1: Asignación ---
        grp_assign = QGroupBox("Asignación de Envío")
        form_assign = QFormLayout()
        form_assign.setContentsMargins(10, 15, 10, 10)
        form_assign.setSpacing(10)

        self.cb_orders = QComboBox()
        self.cb_zones = QComboBox()
        self.cb_users = QComboBox()

        # Checkbox para mandados
        self.chk_errand = QCheckBox("Es Mandado/Diligencia (Sin Orden)")
        self.chk_errand.toggled.connect(self._toggle_errand)
        form_assign.addRow("", self.chk_errand)
        
        form_assign.addRow("Orden:", self.cb_orders)
        form_assign.addRow("Zona Destino:", self.cb_zones)
        form_assign.addRow("Motorizado:", self.cb_users)
        
        # --- Payment Source ---
        self.cb_payment = QComboBox()
        self.cb_payment.addItem("Empresa (Semanal)", "EMPRESA")
        self.cb_payment.addItem("Cliente (Directo)", "CLIENTE")
        self.cb_payment.currentIndexChanged.connect(self._toggle_amount_bs)
        form_assign.addRow("¿Quién paga?:", self.cb_payment)
        
        # --- Amount BS ---
        self.spin_amount_bs = QDoubleSpinBox()
        self.spin_amount_bs.setRange(0, 1000000)
        self.spin_amount_bs.setPrefix("Bs. ")
        self.spin_amount_bs.setDecimals(2)
        # Style override for spinbox
        self.spin_amount_bs.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #2b2b2b;
                color: #e5e7eb;
                border: 1px solid #374151;
                padding: 5px;
                border-radius: 4px;
            }
        """)
        self.form_assign = form_assign # Reference to show/hide row if needed, but we can just toggle Enabled
        form_assign.addRow("Monto Acordado (Bs):", self.spin_amount_bs)
        
        grp_assign.setLayout(form_assign)
        layout.addWidget(grp_assign)

        # --- Group 2: Detalles ---
        grp_details = QGroupBox("Detalles de Salida")
        form_details = QFormLayout()
        form_details.setContentsMargins(10, 15, 10, 10)
        form_details.setSpacing(10)

        self.dt_sent = QDateTimeEdit()
        self.dt_sent.setCalendarPopup(True)
        self.dt_sent.setDateTime(QDateTime.currentDateTime())
        self.dt_sent.setDisplayFormat("dd/MM/yyyy hh:mm AP")
        
        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Instrucciones...")
        self.txt_notes.setMaximumHeight(60)
        
        form_details.addRow("Fecha Salida:", self.dt_sent)
        form_details.addRow("Notas:", self.txt_notes)
        
        grp_details.setLayout(form_details)
        layout.addWidget(grp_details)

        # Load data
        self.load_data()

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.validate_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def load_data(self):
        with self.session_factory() as session:
            # Load Zones (active only ideally)
            zones = session.query(DeliveryZone).all()
            for z in zones:
                self.cb_zones.addItem(f"{z.name} - ${z.price:.2f}", z.id)

            # Load Users (Active)
            users = session.query(User).filter(User.is_active == True).all()
            for u in users:
                self.cb_users.addItem(u.username, u.id)

            # Load Orders in production or ready
            orders = session.query(Order).filter(
                Order.status.in_(['LISTO', 'EN_PRODUCCION', 'PRODUCCION', 'POR_PRODUCIR'])
            ).order_by(Order.id.desc()).limit(100).all()
            
            for o in orders:
                # Mostrar solo numero de orden si el usuario no quiere cliente
                label = f"{o.order_number}"
                self.cb_orders.addItem(label, o.id)

    def _toggle_amount_bs(self):
        # Enable Amount BS only if EMPRESA pays? Or both?
        # User said: "cuando la empresa paga se fija un monto en bs". 
        # Usually if client pays, the rider just keeps the money, maybe we don't track the exact BS amount, or maybe we do.
        # Let's keep it enabled but maybe highlight it when EMPRESA is selected.
        method = self.cb_payment.currentData()
        # self.spin_amount_bs.setEnabled(method == 'EMPRESA') 
        # I'll enable it always just in case they want to record it
        pass
    
    def _toggle_errand(self, checked):
        self.cb_orders.setEnabled(not checked)
        if checked:
            self.cb_orders.setCurrentIndex(-1)
        # If unchecked, we might want to restore selection or just leave it blank

    def validate_and_accept(self):
        if not self.chk_errand.isChecked() and self.cb_orders.currentIndex() == -1:
            QMessageBox.warning(self, "Error", "Debe seleccionar una orden o marcar 'Es Mandado'.")
            return
        if self.cb_zones.currentIndex() == -1:
            QMessageBox.warning(self, "Error", "Debe seleccionar una zona.")
            return
        self.accept()

    def get_data(self):
        order_id = self.cb_orders.currentData()
        if self.chk_errand.isChecked():
            order_id = None
            
        return {
            "order_id": order_id,
            "zone_id": self.cb_zones.currentData(),
            "user_id": self.cb_users.currentData(),
            "payment_source": self.cb_payment.currentData(),
            "amount_bs": self.spin_amount_bs.value(),
            "date": self.dt_sent.dateTime(),
            "notes": self.txt_notes.toPlainText()
        }

class EditDeliveryDialog(QDialog):
    def __init__(self, session_factory, delivery_id, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.delivery_id = delivery_id
        self.setWindowTitle(f"Editar Delivery #{delivery_id}")
        self.resize(500, 600)
        
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; color: #e5e7eb; }
            QLabel { color: #e5e7eb; font-weight: normal; }
            QGroupBox {
                border: 1px solid #374151;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                font-weight: bold;
                color: #e5e7eb;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                padding: 0 3px;
                left: 10px;
                background-color: #1a1a1a; 
            }
            QComboBox, QDateEdit, QDateTimeEdit, QTextEdit, QLineEdit, QDoubleSpinBox {
                background-color: #2b2b2b;
                color: #e5e7eb;
                border: 1px solid #374151;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #2b2b2b;
                color: #e5e7eb;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #333333; }
        """)

        layout = QVBoxLayout(self)
        
        grp = QGroupBox("Editar Datos")
        form = QFormLayout()
        form.setSpacing(12)
        
        self.cb_orders = QComboBox()
        self.cb_zones = QComboBox()
        self.cb_users = QComboBox()
        self.cb_payment = QComboBox()
        self.cb_payment.addItems(["EMPRESA", "CLIENTE"])
        self.cb_payment.setItemData(0, "EMPRESA")
        self.cb_payment.setItemData(1, "CLIENTE")
        
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0, 1000000)
        self.spin_amount.setPrefix("Bs. ")
        self.spin_amount.setDecimals(2)
        
        self.dt_sent = QDateTimeEdit()
        self.dt_sent.setCalendarPopup(True)
        self.dt_sent.setDisplayFormat("dd/MM/yyyy hh:mm AP")
        
        self.cb_status = QComboBox()
        self.cb_status.addItems(["PENDIENTE", "ENTREGADO"])
        
        self.txt_notes = QTextEdit()
        self.txt_notes.setMaximumHeight(60)

        form.addRow("Orden:", self.cb_orders)
        form.addRow("Zona:", self.cb_zones)
        form.addRow("Logística (Motorizado):", self.cb_users)
        form.addRow("Pago Vía:", self.cb_payment)
        form.addRow("Monto Bs:", self.spin_amount)
        form.addRow("Fecha Salida:", self.dt_sent)
        form.addRow("Estado:", self.cb_status)
        form.addRow("Notas:", self.txt_notes)
        
        grp.setLayout(form)
        layout.addWidget(grp)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
        self._load_data()

    def _load_data(self):
        with self.session_factory() as session:
            d = session.get(Delivery, self.delivery_id)
            if not d:
                self.reject()
                return

            # Zones
            for z in session.query(DeliveryZone).all():
                self.cb_zones.addItem(f"{z.name} - ${z.price:.2f}", z.id)
            idx = self.cb_zones.findData(d.zone_id)
            if idx >= 0: self.cb_zones.setCurrentIndex(idx)
            
            # Users
            for u in session.query(User).filter(User.is_active == True).all():
                self.cb_users.addItem(u.username, u.id)
            idx = self.cb_users.findData(d.delivery_user_id)
            if idx >= 0: self.cb_users.setCurrentIndex(idx)
            
            # Orders
            current_order = session.get(Order, d.order_id)
            if current_order:
                self.cb_orders.addItem(f"{current_order.order_number}", current_order.id)
            
            others = session.query(Order).filter(Order.status.in_(['LISTO','EN_PRODUCCION'])).order_by(Order.id.desc()).limit(20).all()
            for o in others:
                if current_order and o.id != current_order.id:
                     self.cb_orders.addItem(f"{o.order_number}", o.id)
                elif not current_order:
                     self.cb_orders.addItem(f"{o.order_number}", o.id)
            
            # Fields
            idx_pay = self.cb_payment.findText(d.payment_source or "EMPRESA")
            if idx_pay >= 0: self.cb_payment.setCurrentIndex(idx_pay)
            
            self.spin_amount.setValue(d.amount_bs or 0.0)
            
            if d.sent_at:
                self.dt_sent.setDateTime(QDateTime(d.sent_at))
            
            st_idx = self.cb_status.findText(d.status)
            if st_idx >= 0: self.cb_status.setCurrentIndex(st_idx)
            
            self.txt_notes.setPlainText(d.notes or "")

    def get_data(self):
        return {
            "order_id": self.cb_orders.currentData(),
            "zone_id": self.cb_zones.currentData(),
            "user_id": self.cb_users.currentData(),
            "payment_source": self.cb_payment.currentText(),
            "amount_bs": self.spin_amount.value(),
            "sent_at": self.dt_sent.dateTime().toPython(),
            "status": self.cb_status.currentText(),
            "notes": self.txt_notes.toPlainText()
        }


class DeliveriesView(QWidget):
    def __init__(self, session_factory: sessionmaker, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.all_deliveries = [] # Store for filtering
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # --- Top Bar (Search + Buttons) ---
        top_bar = QHBoxLayout()
        
        # Search Container
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)
        
        lbl_search = QLabel("Buscar:")
        # Font matching UI generally
        lbl_search.setStyleSheet("color: white; font-weight: bold;") 
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Buscar por número de orden, zona, motorizado...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b2b;
                color: #e5e7eb;
                border: 1px solid #555;
                padding: 5px;
                border-radius: 4px;
            }
        """)
        
        search_layout.addWidget(lbl_search)
        search_layout.addWidget(self.search_edit)
        
        top_bar.addWidget(search_container, 1) # Expand search
        
        # Action Buttons
        button_style = """
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 6px 12px;
                color: #2c3e50;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #eef2f7;
            }
            QPushButton:disabled {
                background-color: #f0f0f0;
                color: #bdc3c7;
            }
        """
        
        self.btn_add = QPushButton("🆕 Asignar Delivery")
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.setStyleSheet(button_style)
        self.btn_add.clicked.connect(self.add_delivery)
        top_bar.addWidget(self.btn_add)

        self.btn_zones = QPushButton("📍 Zonas de Entrega")
        self.btn_zones.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_zones.setStyleSheet(button_style)
        self.btn_zones.clicked.connect(self.open_zones_dialog)
        top_bar.addWidget(self.btn_zones)

        self.btn_refresh = QPushButton("🔄 Actualizar")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.setStyleSheet(button_style)
        self.btn_refresh.clicked.connect(self.refresh)
        top_bar.addWidget(self.btn_refresh)
        
        self.btn_history = QPushButton("📜 Historial Pagos")
        self.btn_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_history.setStyleSheet(button_style)
        self.btn_history.clicked.connect(self.open_history)
        top_bar.addWidget(self.btn_history)
        
        layout.addLayout(top_bar)
        
        # --- Table ---
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "ID", "Fecha Salida", "Orden", "Zona", "Dirección", "Precio ($)", "Monto (Bs)", "Pago Vía", "Motorizado", "Estado", "Pago Rider"
        ])
        
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeToContents) # ID
        header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Date
        header_view.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Order
        header_view.setSectionResizeMode(3, QHeaderView.Stretch)          # Zone
        header_view.setSectionResizeMode(4, QHeaderView.Stretch)          # Address
        header_view.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Price $
        header_view.setSectionResizeMode(6, QHeaderView.ResizeToContents) # Amount Bs
        header_view.setSectionResizeMode(7, QHeaderView.ResizeToContents) # Payment Source
        header_view.setSectionResizeMode(8, QHeaderView.Stretch)          # User
        header_view.setSectionResizeMode(9, QHeaderView.ResizeToContents) # Status (Delivery)
        header_view.setSectionResizeMode(10, QHeaderView.ResizeToContents) # Status (Payment)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_context_menu)
        self.table.itemDoubleClicked.connect(self.change_status)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnHidden(0, True) # Ocultar ID

        # IMPORTANT: Removing explicit table stylesheet to inherit global styles
        # or minimal tweaks. SalesView does NOT have explicit background color set.
        # It relies on 'styles-dark.qss'.
        # However, if 'styles-dark.qss' sets #111827 and user dislikes it, 
        # but SalesView looks fine, then SalesView might be transparent?
        # Actually in SalesView.py no setStyleSheet is called on table.
        # But here to be safe and "not blue", let's use a very neutral dark grey which is standard for modern dark themes 
        # if the global one is indeed #111827 (Navy).
        # Wait, user said SalesView (Image 1) is correct. If SalesView uses global, and global is #111827, 
        # then maybe my manual override was the issue. 
        # I will REMOVE the explicit styles completely to match SalesView 100%.
        
        layout.addWidget(self.table, stretch=2) # Give table weight 2
        
        # Status Label
        self._status_label = QLabel(f"0 entregas cargadas", self)
        self._status_label.setStyleSheet("color: #666; font-style: italic; padding: 4px;")
        layout.addWidget(self._status_label)
        
        # --- Bottom Summary ---
        self.grp_summary = QGroupBox("Resumen Semanal de Pagos a Delivery")
        # Bigger header, more margin/padding
        self.grp_summary.setStyleSheet("""
            QGroupBox { 
                border: 1px solid #555; 
                border-radius: 6px; 
                margin-top: 10px; 
                color: white; 
                font-weight: bold; 
                font-size: 14px;
                background-color: #1e1e1e;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout_summary = QHBoxLayout()
        layout_summary.setContentsMargins(15, 25, 15, 15) # Add top margin for title space
        layout_summary.setSpacing(20)
        
        # Date Range inputs styler
        date_style = """
            QDateEdit { 
                padding: 5px; 
                font-size: 13px; 
                border: 1px solid #555; 
                border-radius: 4px;
                background-color: #2b2b2b;
                color: white;
            }
        """
        
        # Date Range
        lbl_sem = QLabel("Semana:")
        lbl_sem.setStyleSheet("font-size: 14px;")
        layout_summary.addWidget(lbl_sem)
        
        self.dt_start = QDateEdit()
        self.dt_start.setCalendarPopup(True)
        self.dt_start.setDisplayFormat("dd/MM/yyyy")
        self.dt_start.setStyleSheet(date_style)
        self.dt_start.setMinimumWidth(110)
        
        self.dt_end = QDateEdit()
        self.dt_end.setCalendarPopup(True)
        self.dt_end.setDisplayFormat("dd/MM/yyyy")
        self.dt_end.setStyleSheet(date_style)
        self.dt_end.setMinimumWidth(110)
        
        # Defaults (Monday to Friday)
        today = QDate.currentDate()
        # dayOfWeek: Mon=1 ... Sun=7
        monday = today.addDays(-(today.dayOfWeek() - 1))
        friday = monday.addDays(4)
        self.dt_start.setDate(monday)
        self.dt_end.setDate(friday)
        
        layout_summary.addWidget(self.dt_start)
        layout_summary.addWidget(QLabel("-"))
        layout_summary.addWidget(self.dt_end)
        
        btn_calc = QPushButton(" 🔄 Calcular ")
        btn_calc.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_calc.setStyleSheet(button_style)
        btn_calc.clicked.connect(self.calculate_weekly_summary)
        layout_summary.addWidget(btn_calc)
        
        layout_summary.addSpacing(30)
        
        # Labels - Much Bigger
        self.lbl_week_count = QLabel("Carreras Empresa: 0")
        self.lbl_week_count.setStyleSheet("font-size: 18px; font-weight: bold; color: #3498db;")
        layout_summary.addWidget(self.lbl_week_count)
        
        layout_summary.addSpacing(20)
        
        self.lbl_week_amount = QLabel("Monto Pendiente: Bs. 0.00")
        self.lbl_week_amount.setStyleSheet("font-size: 18px; font-weight: bold; color: #2ecc71;")
        layout_summary.addWidget(self.lbl_week_amount)
        
        layout_summary.addStretch()
        
        # Pay Button - Prominent
        btn_pay_week = QPushButton(" 💳 Pagar / Cierre Semanal ")
        btn_pay_week.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pay_week.setStyleSheet(button_style)
        btn_pay_week.clicked.connect(self.open_payment_dialog)
        layout_summary.addWidget(btn_pay_week)
        
        self.grp_summary.setLayout(layout_summary)
        # Add summary with stretch 0 (auto height based on content), but content is now bigger
        layout.addWidget(self.grp_summary)
        
        self.refresh()
        self.calculate_weekly_summary()
        
    def calculate_weekly_summary(self):
        start = datetime.combine(self.dt_start.date().toPython(), time.min)
        end = datetime.combine(self.dt_end.date().toPython(), time.max)
        
        with self.session_factory() as session:
            # Query sum of amount_bs for EMPRESA payments within range and NOT PAID
            result = session.query(
                func.count(Delivery.id),
                func.sum(Delivery.amount_bs)
            ).filter(
                Delivery.sent_at >= start,
                Delivery.sent_at <= end,
                Delivery.payment_source == 'EMPRESA',
                Delivery.payment_id == None
            ).first()
            
            count = result[0] if result[0] else 0
            amount = result[1] if result[1] else 0.0
            
            self.lbl_week_count.setText(f"Carreras Empresa: {count}")
            self.lbl_week_amount.setText(f"Monto Pendiente: Bs. {amount:,.2f}")

    def open_payment_dialog(self):
        dlg = PaymentDialog(self.session_factory, self.dt_start.date(), self.dt_end.date(), self)
        if dlg.exec(): # If closed/accepted (though button handles logic)
            self.refresh()
            self.calculate_weekly_summary()

    def refresh(self):
        self.table.setRowCount(0)
        self.all_deliveries = []
        
        with self.session_factory() as session:
            # Query Delivery and Customer Address
            # Join Order -> Sale -> Customer (Outer Join for Customer in case not present)
            query = session.query(Delivery, Customer.short_address)\
                .select_from(Delivery)\
                .outerjoin(Order, Delivery.order_id == Order.id)\
                .outerjoin(Sale, Order.sale_id == Sale.id)\
                .outerjoin(Customer, Sale.cliente_id == Customer.id)\
                .options(
                    joinedload(Delivery.zone),
                    joinedload(Delivery.delivery_user),
                    contains_eager(Delivery.order)
                ).order_by(Delivery.sent_at.desc())

            results = query.all()
            
            # Cache for filtering
            for d, address in results:
                self.all_deliveries.append({
                    "id": d.id,
                    "date": d.sent_at,
                    "order_num": d.order.order_number if d.order else "DILIGENCIA",
                    "zone": d.zone.name if d.zone else "",
                    "address": address if address else (d.notes or ""),
                    "price": d.zone.price if d.zone else 0.0,
                    "amount_bs": d.amount_bs if hasattr(d, 'amount_bs') else 0.0,
                    "payment_source": d.payment_source if hasattr(d, 'payment_source') and d.payment_source else "EMPRESA",
                    "payment_id": d.payment_id,
                    "user": d.delivery_user.username if d.delivery_user else "Sin Asignar",
                    "status": d.status,
                    "obj_id": d.id
                })
                
        self._populate_table(self.all_deliveries)

    def open_history(self):
        dlg = PaymentHistoryDialog(self.session_factory, self)
        dlg.exec()

    def _apply_filter(self):
        text = self.search_edit.text().strip().lower()
        if not text:
            self._populate_table(self.all_deliveries)
            return
            
        filtered = []
        for item in self.all_deliveries:
            # Search in order, zone, address, user
            if (text in item["order_num"].lower() or 
                text in item["zone"].lower() or 
                text in item["address"].lower() or
                text in item["user"].lower()):
                filtered.append(item)
        
        self._populate_table(filtered)

    def _populate_table(self, data):
        self.table.setRowCount(len(data))
        for i, item in enumerate(data):
            self.table.setItem(i, 0, QTableWidgetItem(str(item["id"])))
            
            date_str = item["date"].strftime("%d/%m/%Y %I:%M %p") if item["date"] else "-"
            self.table.setItem(i, 1, QTableWidgetItem(date_str))
            
            self.table.setItem(i, 2, QTableWidgetItem(f"{item['order_num']}"))
            self.table.setItem(i, 3, QTableWidgetItem(item["zone"]))
            self.table.setItem(i, 4, QTableWidgetItem(item["address"]))
            
            self.table.setItem(i, 5, QTableWidgetItem(f"${item['price']:.2f}"))
            self.table.setItem(i, 6, QTableWidgetItem(f"Bs. {item['amount_bs']:,.2f}"))
            
            # Payment Source column
            payment_item = QTableWidgetItem(item["payment_source"])
            if item["payment_source"] == "CLIENTE":
                payment_item.setForeground(Qt.GlobalColor.cyan)
            self.table.setItem(i, 7, QTableWidgetItem(payment_item))
            
            self.table.setItem(i, 8, QTableWidgetItem(item["user"]))
            
            status_item = QTableWidgetItem(item["status"])
            if item["status"] == "ENTREGADO":
                status_item.setForeground(Qt.GlobalColor.green)
            else:
                status_item.setForeground(Qt.GlobalColor.yellow)
            status_item.setTextAlignment(Qt.AlignCenter)
                
            self.table.setItem(i, 9, status_item)
            
            # Payment Status Column
            paid_status = "PENDIENTE"
            if item["payment_source"] == "CLIENTE":
                paid_status = "N/A (Cliente)"
                item_pay = QTableWidgetItem(paid_status)
                item_pay.setForeground(Qt.GlobalColor.gray)
            elif item["payment_id"]:
                paid_status = "PAGADO"
                item_pay = QTableWidgetItem(paid_status)
                item_pay.setForeground(Qt.GlobalColor.green)
                item_pay.setFont(status_item.font()) # Bold maybe?
            else:
                item_pay = QTableWidgetItem("PENDIENTE")
                item_pay.setForeground(Qt.GlobalColor.red)
            
            item_pay.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 10, item_pay)
            
            self.table.item(i, 0).setData(Qt.UserRole, item["obj_id"])
            
        self._status_label.setText(f"✅ {len(data)} entregas cargadas")

    def add_delivery(self):
        dlg = CreateDeliveryDialog(self.session_factory, self)
        if dlg.exec():
            data = dlg.get_data()
            
            # Format date correctly
            sent_date = data['date']
            # If QDateTime, convert
            if hasattr(sent_date, 'toPython'): 
                 sent_date = sent_date.toPython() # Returns datetime
            
            sent_dt = sent_date # Already datetime

            with self.session_factory() as session:
                new_delivery = Delivery(
                    order_id=data['order_id'],
                    zone_id=data['zone_id'],
                    delivery_user_id=data['user_id'],
                    sent_at=sent_dt, 
                    notes=data['notes'],
                    status="PENDIENTE",
                    payment_source=data['payment_source'],
                    amount_bs=data['amount_bs']
                )
                session.add(new_delivery)
                session.commit()
            self.refresh()

    def open_zones_dialog(self):
        # Create a Dialog to wrap the zones view
        dlg = QDialog(self)
        dlg.setWindowTitle("Zonas de Delivery")
        dlg.resize(650, 500)
        # Fix: Use Neutral Dark #1a1a1a instead of Blue #111827
        dlg.setStyleSheet("QDialog { background-color: #1a1a1a; color: #e5e7eb; }")
        
        layout = QVBoxLayout(dlg)
        
        # Instantiate the view
        view = DeliveryZonesView(self.session_factory, parent=dlg)
        layout.addWidget(view)
        
        # Close button at the bottom
        btn_close = QPushButton("Cerrar")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton { 
                background-color: #1f2937; 
                color: white; 
                border: 1px solid #374151; 
                padding: 6px 12px; 
                border-radius: 4px; 
            }
            QPushButton:hover { background-color: #374151; }
        """)
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignRight)
        
        dlg.exec()
        # Refresh main table in case zones info (names) changed
        self.refresh()

    def change_status(self, item):
        row = item.row()
        did = self.table.item(row, 0).data(Qt.UserRole)
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Actualizar Estado")
        msg.setText("¿Cambiar estado del delivery?")
        # Match Dialog Style for consistency
        msg.setStyleSheet("QMessageBox { background-color: #0b1220; color: #e5e7eb; } QPushButton { background-color: #1f2937; color: white; border: 1px solid #374151; padding: 5px 15px; border-radius: 4px; }")
        
        btn_completed = msg.addButton("Marcar ENTREGADO", QMessageBox.ButtonRole.AcceptRole)
        btn_pending = msg.addButton("Marcar PENDIENTE", QMessageBox.ButtonRole.ActionRole)
        btn_cancel = msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        
        new_status = None
        if msg.clickedButton() == btn_completed:
            new_status = "ENTREGADO"
        elif msg.clickedButton() == btn_pending:
            new_status = "PENDIENTE"
            
        if new_status:
            with self.session_factory() as session:
                d = session.get(Delivery, did)
                if d:
                    d.status = new_status
                    session.commit()
            self.refresh()

    def open_context_menu(self, position):
        menu = QMenu()
        edit_action = menu.addAction("✏️ Editar Detalles")
        delete_action = menu.addAction("🗑️ Eliminar")
        
        action = menu.exec(self.table.viewport().mapToGlobal(position))
        
        item = self.table.itemAt(position)
        if not item: return
        
        row = item.row()
        delivery_id = self.table.item(row, 0).data(Qt.UserRole)
        
        if action == edit_action:
            self.edit_delivery(delivery_id)
        elif action == delete_action:
            self.delete_delivery(delivery_id)

    def edit_delivery(self, delivery_id):
        dlg = EditDeliveryDialog(self.session_factory, delivery_id, self)
        if dlg.exec():
            data = dlg.get_data()
            with self.session_factory() as session:
                d = session.get(Delivery, delivery_id)
                if d:
                    d.order_id = data['order_id']
                    d.zone_id = data['zone_id']
                    d.delivery_user_id = data['user_id']
                    d.payment_source = data['payment_source']
                    d.amount_bs = data['amount_bs']
                    d.sent_at = data['sent_at']
                    d.status = data['status']
                    d.notes = data['notes']
                    session.commit()
            self.refresh()
            self.calculate_weekly_summary()

    def delete_delivery(self, delivery_id):
        with self.session_factory() as session:
            d = session.get(Delivery, delivery_id)
            if not d: return
            
            if d.payment_id:
                QMessageBox.warning(self, "Error", "No se puede eliminar un delivery que ya ha sido pagado (tiene lote de pago asociado).")
                return
                
            reply = QMessageBox.question(
                self, "Confirmar Eliminación", 
                "¿Seguro que desea eliminar este envío?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                session.delete(d)
                session.commit()
                
        self.refresh()
        self.calculate_weekly_summary()
