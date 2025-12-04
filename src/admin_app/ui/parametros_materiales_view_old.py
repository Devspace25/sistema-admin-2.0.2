from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox
)

from ..repository import list_corporeo_products


class ParametrosMaterialesView(QWidget):
    """Módulo de Dashboard: muestra tabla producto_corporeo y botón 'Parámetros…'."""

    def __init__(self, session_factory, parent=None) -> None:
        super().__init__(parent)
        self.session_factory = session_factory
        self.setObjectName("ParametrosMaterialesView")
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        # Botonera superior
        bar = QHBoxLayout()
        self.btn_parameters = QPushButton("Parámetros…", self)
        self.btn_refresh = QPushButton("Refrescar", self)
        bar.addWidget(self.btn_parameters)
        bar.addStretch(1)
        bar.addWidget(self.btn_refresh)
        layout.addLayout(bar)

        # Tabla producto_corporeo (ORM principal CorporeoProducto)
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Alto (mm)", "Ancho (mm)", "Material ID", "Espesor ID"
        ])
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(self.table.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        # Wiring
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_parameters.clicked.connect(self.on_open_parameters)

    def refresh(self) -> None:
        try:
            with self.session_factory() as s:
                items = list_corporeo_products(s)
        except Exception as e:
            QMessageBox.warning(self, "Cargar productos", f"No fue posible cargar productos corpóreos: {e}")
            items = []
        t = self.table
        t.setRowCount(len(items))
        for i, p in enumerate(items):
            t.setItem(i, 0, QTableWidgetItem(str(getattr(p, 'id', ''))))
            t.setItem(i, 1, QTableWidgetItem(str(getattr(p, 'name', '') or '')))
            t.setItem(i, 2, QTableWidgetItem(str(getattr(p, 'alto_mm', '') or '')))
            t.setItem(i, 3, QTableWidgetItem(str(getattr(p, 'ancho_mm', '') or '')))
            t.setItem(i, 4, QTableWidgetItem(str(getattr(p, 'material_id', '') or '')))
            t.setItem(i, 5, QTableWidgetItem(str(getattr(p, 'espesor_id', '') or '')))
        t.resizeColumnsToContents()

    def on_open_parameters(self) -> None:
        try:
            from .corporeo_catalogs_dialog import CorporeoCatalogsDialog
            dlg = CorporeoCatalogsDialog(self)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Parámetros", f"No fue posible abrir parámetros: {e}")
