
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QSpinBox, QLabel, QPushButton, QHeaderView, QMessageBox, QDialogButtonBox
)
from PySide6.QtCore import Qt
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from ..repository import get_worker, get_worker_goals_by_year, set_worker_goal

class WorkerGoalsDialog(QDialog):
    def __init__(self, session_factory: sessionmaker, worker_id: int, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.worker_id = worker_id
        self.setWindowTitle("Metas Mensuales")
        self.resize(500, 400)
        
        self.layout = QVBoxLayout(self)
        
        # Header: Worker Name and Year Selector
        header_layout = QHBoxLayout()
        self.lbl_worker = QLabel("Trabajador: ...")
        self.spin_year = QSpinBox()
        self.spin_year.setRange(2000, 2100)
        self.spin_year.setValue(datetime.now().year)
        self.spin_year.valueChanged.connect(self._load_goals)
        
        header_layout.addWidget(self.lbl_worker)
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Año:"))
        header_layout.addWidget(self.spin_year)
        self.layout.addLayout(header_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Mes", "Meta ($)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.layout.addWidget(self.table)
        
        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.buttons.rejected.connect(self.reject)
        
        self.btn_save = QPushButton("Guardar Cambios")
        self.btn_save.clicked.connect(self._save_changes)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.buttons)
        self.layout.addLayout(btn_layout)
        
        self._load_worker_info()
        self._load_goals()
        
    def _load_worker_info(self):
        with self.session_factory() as session:
            worker = get_worker(session, self.worker_id)
            if worker:
                info = worker.full_name
                if worker.job_title:
                    info += f" ({worker.job_title})"
                self.lbl_worker.setText(f"Trabajador: {info}")
                
    def _load_goals(self):
        year = self.spin_year.value()
        self.table.setRowCount(12)
        
        goals_map = {}
        with self.session_factory() as session:
            goals = get_worker_goals_by_year(session, self.worker_id, year)
            for g in goals:
                goals_map[g.month] = g.target_amount
                
        months = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        
        for i in range(12):
            month_num = i + 1
            month_name = months[i]
            goal_val = goals_map.get(month_num, 0.0)
            
            item_month = QTableWidgetItem(month_name)
            item_month.setFlags(Qt.ItemFlag.ItemIsEnabled)
            
            item_goal = QTableWidgetItem(f"{goal_val:.2f}")
            
            self.table.setItem(i, 0, item_month)
            self.table.setItem(i, 1, item_goal)
            
    def _save_changes(self):
        year = self.spin_year.value()
        try:
            with self.session_factory() as session:
                for i in range(12):
                    month_num = i + 1
                    item_goal = self.table.item(i, 1)
                    try:
                        val = float(item_goal.text())
                    except ValueError:
                        val = 0.0
                    
                    set_worker_goal(session, self.worker_id, year, month_num, val)
            
            QMessageBox.information(self, "Éxito", "Metas actualizadas correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar metas: {e}")
