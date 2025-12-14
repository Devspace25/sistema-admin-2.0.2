
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox,
    QDialogButtonBox, QMessageBox, QComboBox, QDateEdit, QDoubleSpinBox, QTextEdit,
    QTabWidget, QWidget
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
        
        self.spin_salary = QDoubleSpinBox()
        self.spin_salary.setRange(0, 1000000)
        self.spin_salary.setPrefix("$ ")
        self.spin_salary.setDecimals(2)
        
        self.spin_monthly_goal = QDoubleSpinBox()
        self.spin_monthly_goal.setRange(0, 10000000)
        self.spin_monthly_goal.setPrefix("$ ")
        self.spin_monthly_goal.setDecimals(2)
        self.spin_monthly_goal.setToolTip("Meta de ventas para el mes actual")
        
        self.chk_active = QCheckBox("Trabajador Activo")
        self.chk_active.setChecked(True)
        
        form.addRow("Cargo / Puesto:", self.edt_job_title)
        form.addRow("Fecha de Ingreso:", self.edt_start_date)
        form.addRow("Salario Base:", self.spin_salary)
        form.addRow(f"Meta ({datetime.now().strftime('%B')}):", self.spin_monthly_goal)
        form.addRow("", self.chk_active)
        
        layout.addLayout(form)
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
                if worker.start_date:
                    self.edt_start_date.setDate(worker.start_date.date())
                if worker.salary:
                    self.spin_salary.setValue(worker.salary)
                    
                self.chk_active.setChecked(worker.is_active)
                
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
            
        is_active = self.chk_active.isChecked()
        
        cedula = self.edt_cedula.text().strip() or None
        phone = self.edt_phone.text().strip() or None
        email = self.edt_email.text().strip() or None
        address = self.edt_address.toPlainText().strip() or None
        job_title = self.edt_job_title.text().strip() or None
        
        # Convert QDate to datetime
        qdate = self.edt_start_date.date()
        start_date = datetime(qdate.year(), qdate.month(), qdate.day())
        
        salary = self.spin_salary.value()
        monthly_goal = self.spin_monthly_goal.value()
        
        try:
            with self.session_factory() as session:
                if self.worker_id:
                    worker = update_worker(session, self.worker_id, full_name=name, is_active=is_active,
                                  cedula=cedula, phone=phone, email=email, address=address, job_title=job_title,
                                  start_date=start_date, salary=salary)
                else:
                    worker = create_worker(session, full_name=name,
                                  cedula=cedula, phone=phone, email=email, address=address, job_title=job_title,
                                  start_date=start_date, salary=salary)
                
                # Save monthly goal
                if worker:
                    now = datetime.now()
                    set_worker_goal(session, worker.id, now.year, now.month, monthly_goal)
                    
            super().accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar: {e}")
