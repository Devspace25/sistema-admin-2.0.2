
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QLabel, QLineEdit
)
from PySide6.QtCore import Qt
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from ..repository import list_workers, get_worker_goal, delete_worker
from .worker_dialog import WorkerDialog
from .worker_goals_dialog import WorkerGoalsDialog

class WorkersView(QWidget):
    def __init__(self, session_factory: sessionmaker, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self._can_edit = True  # Default to true, updated by set_permissions
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Top Bar (Search Left, Buttons Right)
        top_bar = QHBoxLayout()
        
        # Search
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)
        
        lbl_search = QLabel("Buscar:")
        # lbl_search.setStyleSheet("font-weight: bold; color: #bdc3c7;") 
        self.edt_search = QLineEdit()
        self.edt_search.setPlaceholderText("Buscar por nombre, cédula o cargo...")
        # self.edt_search.setFixedWidth(300) # Removed fixed width
        self.edt_search.textChanged.connect(self.refresh)
        
        search_layout.addWidget(lbl_search)
        search_layout.addWidget(self.edt_search)
        
        top_bar.addWidget(search_container, 1) # Expand search container
        # top_bar.addStretch() # Removed stretch to let search fill space
        
        # Buttons
        self.btn_add = QPushButton("➕ Nuevo Trabajador")
        self.btn_add.clicked.connect(self._add_worker)
        
        self.btn_edit = QPushButton("✏️ Editar")
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self._edit_selected)
        
        self.btn_delete = QPushButton("🗑️ Eliminar")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_selected)
        
        self.btn_goals = QPushButton("🎯 Metas")
        self.btn_goals.setEnabled(False)
        self.btn_goals.clicked.connect(self._goals_selected)
        
        # Style buttons
        for btn in [self.btn_add, self.btn_edit, self.btn_delete, self.btn_goals]:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f8f9fa;
                    border: 1px solid #e0e0e0;
                    border-radius: 6px;
                    padding: 6px 12px;
                    color: #2c3e50;
                }
                QPushButton:hover {
                    background-color: #eef2f7;
                }
                QPushButton:disabled {
                    background-color: #f0f0f0;
                    color: #bdc3c7;
                }
            """)
            top_bar.addWidget(btn)
            
        layout.addLayout(top_bar)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "Cargo", "Teléfono", "Meta (Mes)", "Activo"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)
        
        self.refresh()
        
    def set_permissions(self, permissions: set[str]):
        """Configurar permisos de edición."""
        self._can_edit = "edit_workers" in permissions
        self.btn_add.setVisible(self._can_edit)
        self._on_selection_changed()  # Re-evaluar estado de botones
        
    def refresh(self):
        search_text = self.edt_search.text().strip()
        self.table.setRowCount(0)
        now = datetime.now()
        
        with self.session_factory() as session:
            workers = list_workers(session, active_only=False, search_query=search_text)
            self.table.setRowCount(len(workers))
            for i, w in enumerate(workers):
                self.table.setItem(i, 0, QTableWidgetItem(str(w.id)))
                self.table.setItem(i, 1, QTableWidgetItem(w.full_name))
                self.table.setItem(i, 2, QTableWidgetItem(w.job_title or ""))
                self.table.setItem(i, 3, QTableWidgetItem(w.phone or ""))
                
                # Fetch current month goal
                goal = get_worker_goal(session, w.id, now.year, now.month)
                goal_val = goal.target_amount if goal else 0.0
                self.table.setItem(i, 4, QTableWidgetItem(f"$ {goal_val:.2f}"))
                
                status_item = QTableWidgetItem("Sí" if w.is_active else "No")
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if not w.is_active:
                    status_item.setForeground(Qt.GlobalColor.red)
                else:
                    status_item.setForeground(Qt.GlobalColor.darkGreen)
                self.table.setItem(i, 5, status_item)
        
        self._on_selection_changed()

    def _on_selection_changed(self):
        has_selection = len(self.table.selectedItems()) > 0
        self.btn_edit.setEnabled(has_selection and self._can_edit)
        self.btn_delete.setEnabled(has_selection and self._can_edit)
        self.btn_goals.setEnabled(has_selection and self._can_edit)

    def _get_selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row >= 0:
            item_id = self.table.item(row, 0)
            if item_id:
                return int(item_id.text())
        return None

    def _delete_selected(self):
        worker_id = self._get_selected_id()
        if not worker_id:
            return
            
        reply = QMessageBox.question(
            self, 
            "Confirmar eliminación",
            "¿Está seguro de que desea eliminar este trabajador?\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with self.session_factory() as session:
                    if delete_worker(session, worker_id):
                        QMessageBox.information(self, "Éxito", "Trabajador eliminado correctamente.")
                        self.refresh()
                    else:
                        QMessageBox.warning(self, "Error", "No se pudo encontrar el trabajador.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar trabajador: {e}")

    def _edit_selected(self):
        worker_id = self._get_selected_id()
        if worker_id:
            self._edit_worker(worker_id)

    def _goals_selected(self):
        worker_id = self._get_selected_id()
        if worker_id:
            self._open_goals(worker_id)
                
    def _add_worker(self):
        dlg = WorkerDialog(self.session_factory, parent=self)
        if dlg.exec():
            self.refresh()
            
    def _edit_worker(self, worker_id: int):
        dlg = WorkerDialog(self.session_factory, worker_id=worker_id, parent=self)
        if dlg.exec():
            self.refresh()
            
    def _on_double_click(self, row, col):
        if not self._can_edit:
            return
        item_id = self.table.item(row, 0)
        if item_id:
            self._edit_worker(int(item_id.text()))
            
    def _open_goals(self, worker_id: int):
        dlg = WorkerGoalsDialog(self.session_factory, worker_id=worker_id, parent=self)
        dlg.exec()
