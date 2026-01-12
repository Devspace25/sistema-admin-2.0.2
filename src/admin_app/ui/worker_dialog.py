
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox,
    QDialogButtonBox, QMessageBox, QComboBox, QDateEdit, QDoubleSpinBox, QTextEdit,
    QTabWidget, QWidget, QGroupBox
)
from PySide6.QtCore import QDate
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from ..repository import create_worker, update_worker, get_worker, get_worker_goal, set_worker_goal

class WorkerDialog(QDialog):
    def __init__(self, session_factory: sessionmaker, worker_id: int | None = None, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.worker_id = worker_id
        self.setWindowTitle("Gestión de Trabajador")
        self.resize(600, 480)
        
        self.layout = QVBoxLayout(self)
        
        # Tabs
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # Tab 1: General Info
        self.tab_general = QWidget()
        self.tabs.addTab(self.tab_general, "Información Personal")
        self._init_general_tab()
        
        # Tab 2: Job Info
        self.tab_job = QWidget()
        self.tabs.addTab(self.tab_job, "Información Laboral")
        self._init_job_tab()
        
        # Tab 3: Banking Info
        self.tab_bank = QWidget()
        self.tabs.addTab(self.tab_bank, "Información Bancaria")
        self._init_bank_tab()
        
        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
        
        if self.worker_id:
            self._load_data()

    def _init_general_tab(self):
        layout = QVBoxLayout(self.tab_general)
        form = QFormLayout()
        
        self.edt_name = QLineEdit()
        self.edt_name.setPlaceholderText("Ej. Juan Pérez")
        
        self.edt_cedula = QLineEdit()
        self.edt_cedula.setPlaceholderText("Ej. V-12345678")
        
        self.edt_phone = QLineEdit()
        self.edt_phone.setPlaceholderText("Ej. 0414-1234567")
        
        self.edt_email = QLineEdit()
        self.edt_email.setPlaceholderText("Ej. juan@correo.com")
        
        self.edt_address = QTextEdit()
        self.edt_address.setMaximumHeight(80)
        
        form.addRow("Nombre Completo (*):", self.edt_name)
        form.addRow("Cédula / DNI:", self.edt_cedula)
        form.addRow("Teléfono:", self.edt_phone)
        form.addRow("Correo Electrónico:", self.edt_email)
        form.addRow("Dirección:", self.edt_address)
        
        layout.addLayout(form)
        layout.addStretch()

    def _init_job_tab(self):
        layout = QVBoxLayout(self.tab_job)
        form = QFormLayout()
        
        self.edt_job_title = QLineEdit()
        self.edt_job_title.setPlaceholderText("Ej. Vendedor, Gerente...")
        
        self.edt_start_date = QDateEdit()
        self.edt_start_date.setCalendarPopup(True)
        self.edt_start_date.setDate(QDate.currentDate())
        self.edt_start_date.setDisplayFormat("dd/MM/yyyy")
        
        self.chk_weekly_payment = QCheckBox("Pago Semanal (Diseñadores, Obreros)")
        self.chk_weekly_payment.setToolTip("Si se activa, el trabajador aparecerá en la pestaña Semanal.")
        
        self.spin_salary = QDoubleSpinBox()
        self.spin_salary.setRange(0, 1000000)
        self.spin_salary.setPrefix("$ ")
        self.spin_salary.setDecimals(2)
        
        self.spin_commission_pct = QDoubleSpinBox()
        self.spin_commission_pct.setRange(0, 100)
        self.spin_commission_pct.setSuffix(" %")
        self.spin_commission_pct.setDecimals(2)
        
        self.spin_bonus_attendance = QDoubleSpinBox()
        self.spin_bonus_attendance.setRange(0, 10000)
        self.spin_bonus_attendance.setPrefix("$ ")
        self.spin_bonus_attendance.setDecimals(2)
        
        self.spin_bonus_food = QDoubleSpinBox()
        self.spin_bonus_food.setRange(0, 10000)
        self.spin_bonus_food.setPrefix("$ ")
        self.spin_bonus_food.setDecimals(2)
        
        self.spin_bonus_role = QDoubleSpinBox()
        self.spin_bonus_role.setRange(0, 10000)
        self.spin_bonus_role.setPrefix("$ ")
        self.spin_bonus_role.setDecimals(2)
        
        self.spin_monthly_goal = QDoubleSpinBox()
        self.spin_monthly_goal.setRange(0, 10000000)
        self.spin_monthly_goal.setPrefix("$ ")
        self.spin_monthly_goal.setDecimals(2)
        self.spin_monthly_goal.setToolTip("Meta de ventas para el mes actual")
        
        self.chk_active = QCheckBox("Trabajador Activo")
        self.chk_active.setChecked(True)
        
        self.edt_assigned_user = QLineEdit()
        self.edt_assigned_user.setReadOnly(True)
        self.edt_assigned_user.setPlaceholderText("Sin usuario asignado")
        
        form.addRow("Cargo / Puesto:", self.edt_job_title)
        form.addRow("Frecuencia de Pago:", self.chk_weekly_payment)
        form.addRow("Fecha de Ingreso:", self.edt_start_date)
        form.addRow("Salario Base (USD):", self.spin_salary)
        form.addRow("Comisión Ventas (%):", self.spin_commission_pct)
        form.addRow("Bono Asistencia (USD):", self.spin_bonus_attendance)
        form.addRow("Bono Alimentación (USD):", self.spin_bonus_food)
        form.addRow("Bono Responsabilidad (USD):", self.spin_bonus_role)
        form.addRow(f"Meta ({datetime.now().strftime('%B')}):", self.spin_monthly_goal)
        form.addRow("Usuario Asignado:", self.edt_assigned_user)
        form.addRow("", self.chk_active)
        
        layout.addLayout(form)
        layout.addStretch()
            
    def _init_bank_tab(self):
        layout = QVBoxLayout(self.tab_bank)
        
        # 1. Datos de Transferencias
        grp_trans = QGroupBox("Datos de Transferencias")
        form_trans = QFormLayout()
        
        self.edt_bank_account = QLineEdit()
        self.edt_bank_account.setPlaceholderText("Nro. de Cuenta (20 dígitos)")
        form_trans.addRow("Nro. de Cuenta:", self.edt_bank_account)
        
        grp_trans.setLayout(form_trans)
        layout.addWidget(grp_trans)
        
        # 2. Datos Pago Móvil
        grp_pm = QGroupBox("Datos Pago Móvil")
        form_pm = QFormLayout()
        
        self.edt_pm_cedula = QLineEdit()
        self.edt_pm_cedula.setPlaceholderText("Ej. V-12345678")
        
        self.edt_pm_phone = QLineEdit()
        self.edt_pm_phone.setPlaceholderText("Ej. 0414-0000000")
        
        self.edt_pm_bank = QComboBox()
        self.edt_pm_bank.setEditable(True)
        # Listado básico de bancos en Vzla
        banks = [
            "Banco de Venezuela", "Banesco", "Mercantil", "Provincial", "Bancamiga", 
            "BNC", "Banplus", "Tesoro", "Bicentenario", "Exterior", "Plaza", "Fondo Común"
        ]
        self.edt_pm_bank.addItems(sorted(banks))
        self.edt_pm_bank.setCurrentIndex(-1)
        self.edt_pm_bank.setPlaceholderText("Seleccione o escriba el banco")
        
        form_pm.addRow("Cédula:", self.edt_pm_cedula)
        form_pm.addRow("Teléfono:", self.edt_pm_phone)
        form_pm.addRow("Banco:", self.edt_pm_bank)
        
        grp_pm.setLayout(form_pm)
        layout.addWidget(grp_pm)
        
        # 3. Datos Cripto (Binance / Zelle)
        grp_crypto = QGroupBox("Cuentas Cripto / USD")
        form_crypto = QFormLayout()

        self.edt_binance = QLineEdit()
        self.edt_binance.setPlaceholderText("Correo Pay / ID")

        self.edt_zelle = QLineEdit()
        self.edt_zelle.setPlaceholderText("Correo Zelle")

        form_crypto.addRow("Binance Email/ID:", self.edt_binance)
        form_crypto.addRow("Zelle Email:", self.edt_zelle)

        grp_crypto.setLayout(form_crypto)
        layout.addWidget(grp_crypto)
        
        layout.addStretch()

    def _load_data(self):
        with self.session_factory() as session:
            worker = get_worker(session, self.worker_id)
            if worker:
                self.edt_name.setText(worker.full_name)
                self.edt_cedula.setText(worker.cedula or "")
                self.edt_phone.setText(worker.phone or "")
                self.edt_email.setText(worker.email or "")
                self.edt_address.setText(worker.address or "")
                self.edt_job_title.setText(worker.job_title or "")
                
                # Frequency
                freq = getattr(worker, 'payment_frequency', 'QUINCENAL')
                self.chk_weekly_payment.setChecked(freq == "SEMANAL")
                
                if worker.start_date:
                    self.edt_start_date.setDate(worker.start_date.date())
                if worker.salary:
                    self.spin_salary.setValue(worker.salary)
                
                if hasattr(worker, 'commission_pct') and worker.commission_pct:
                    self.spin_commission_pct.setValue(worker.commission_pct)
                if hasattr(worker, 'bonus_attendance') and worker.bonus_attendance:
                    self.spin_bonus_attendance.setValue(worker.bonus_attendance)
                if hasattr(worker, 'bonus_food') and worker.bonus_food:
                    self.spin_bonus_food.setValue(worker.bonus_food)
                if hasattr(worker, 'bonus_role') and worker.bonus_role:
                    self.spin_bonus_role.setValue(worker.bonus_role)
                    
                # Load Banking Info
                if hasattr(worker, 'bank_account'):
                    self.edt_bank_account.setText(worker.bank_account or "")
                if hasattr(worker, 'pago_movil_cedula'):
                    self.edt_pm_cedula.setText(worker.pago_movil_cedula or "")
                if hasattr(worker, 'pago_movil_phone'):
                    self.edt_pm_phone.setText(worker.pago_movil_phone or "")
                if hasattr(worker, 'pago_movil_bank'):
                    self.edt_pm_bank.setEditText(worker.pago_movil_bank or "")

                if hasattr(worker, 'binance_email'):
                    self.edt_binance.setText(worker.binance_email or "")
                if hasattr(worker, 'zelle_email'):
                    self.edt_zelle.setText(worker.zelle_email or "")

                self.chk_active.setChecked(worker.is_active)
                
                # Show assigned user if any
                if worker.user:
                    status = " (Activo)" if worker.user.is_active else " (Inactivo)"
                    self.edt_assigned_user.setText(f"{worker.user.username}{status}")
                else:
                    self.edt_assigned_user.setText("Sin usuario asignado")
                
                # Load current month goal
                now = datetime.now()
                goal = get_worker_goal(session, self.worker_id, now.year, now.month)
                if goal:
                    self.spin_monthly_goal.setValue(goal.target_amount)
                        
    def accept(self):
        name = self.edt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "El nombre es obligatorio.")
            self.tabs.setCurrentIndex(0)
            self.edt_name.setFocus()
            return

        # ... (rest of simple fields) ...
            
        is_active = self.chk_active.isChecked()
        
        cedula = self.edt_cedula.text().strip() or None
        phone = self.edt_phone.text().strip() or None
        email = self.edt_email.text().strip() or None
        address = self.edt_address.toPlainText().strip() or None
        job_title = self.edt_job_title.text().strip() or None
        
        # Convert QDate to datetime
        qdate = self.edt_start_date.date()
        start_date = datetime(qdate.year(), qdate.month(), qdate.day())
        
        frequency = "SEMANAL" if self.chk_weekly_payment.isChecked() else "QUINCENAL"
        
        salary = self.spin_salary.value()
        commission_pct = self.spin_commission_pct.value()
        bonus_attendance = self.spin_bonus_attendance.value()
        bonus_food = self.spin_bonus_food.value()
        bonus_role = self.spin_bonus_role.value()
        
        monthly_goal = self.spin_monthly_goal.value()
        
        # Banking Info
        bank_account = self.edt_bank_account.text().strip() or None
        pm_cedula = self.edt_pm_cedula.text().strip() or None
        pm_phone = self.edt_pm_phone.text().strip() or None
        pm_bank = self.edt_pm_bank.currentText().strip() or None
        
        binance_email = self.edt_binance.text().strip() or None
        zelle_email = self.edt_zelle.text().strip() or None

        try:
            with self.session_factory() as session:
                if self.worker_id:
                    worker = update_worker(session, self.worker_id, full_name=name, is_active=is_active,
                                  cedula=cedula, phone=phone, email=email, address=address, job_title=job_title,
                                  start_date=start_date, salary=salary, payment_frequency=frequency,
                                  commission_pct=commission_pct, bonus_attendance=bonus_attendance,
                                  bonus_food=bonus_food, bonus_role=bonus_role,
                                  bank_account=bank_account, pago_movil_cedula=pm_cedula,
                                  pago_movil_phone=pm_phone, pago_movil_bank=pm_bank,
                                  binance_email=binance_email, zelle_email=zelle_email)
                else:
                    worker = create_worker(session, full_name=name,
                                  cedula=cedula, phone=phone, email=email, address=address, job_title=job_title,
                                  start_date=start_date, salary=salary, payment_frequency=frequency,
                                  commission_pct=commission_pct, bonus_attendance=bonus_attendance,
                                  bonus_food=bonus_food, bonus_role=bonus_role,
                                  bank_account=bank_account, pago_movil_cedula=pm_cedula,
                                  pago_movil_phone=pm_phone, pago_movil_bank=pm_bank,
                                  binance_email=binance_email, zelle_email=zelle_email)
                
                # Save monthly goal
                if worker:
                    now = datetime.now()
                    set_worker_goal(session, worker.id, now.year, now.month, monthly_goal)
                    
            super().accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar: {e}")
