from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QAbstractItemView, QDialog, QFormLayout,
    QLineEdit, QDoubleSpinBox, QDialogButtonBox, QMessageBox, QLabel, QGroupBox
)
from PySide6.QtCore import Qt
from sqlalchemy.orm import sessionmaker
from ..models import DeliveryZone

class ZoneDialog(QDialog):
    def __init__(self, parent=None, zone: DeliveryZone | None = None):
        super().__init__(parent)
        self.setWindowTitle("Zona de Delivery")
        self.setFixedWidth(400) # Slightly wider
        # Eliminar background-color explícito del QDialog para evitar el "azul" (#111827).
        # Se usará herencia o un gris muy neutro si es necesario.
        # Si el usuario NO quiere azul, usamos #1f2937 (Panel) o vacío.
        # Probemos eliminando la propiedad background-color del QDialog principal y dejando solo los controles.
        # O usar un gris oscuro estándar de Material Design: #303030 o #202020 if global is problematic.
        # Pero mejor aún: NO definir background-color en el Dialog y dejar que el estilo global actúe.
        # Sin embargo, si el global es azul, eso no ayuda.
        # User said: "Aun se muestra el color azul".
        # So I will force a NEUTRAL DARK GRAY #222222.
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; color: #e5e7eb; }
            QLabel { color: #e5e7eb; }
            QGroupBox {
                border: 1px solid #374151;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
                color: #e5e7eb;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
                background-color: #1a1a1a;
            }
            QLineEdit, QDoubleSpinBox {
                background-color: #2b2b2b;
                color: #e5e7eb;
                border: 1px solid #374151;
                padding: 6px;
                border-radius: 4px;
            }
            QLineEdit:focus, QDoubleSpinBox:focus {
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
        
        self.zone = zone
        
        layout = QVBoxLayout(self)
        
        grp = QGroupBox("Datos de la Zona")
        form = QFormLayout()
        
        self.edt_name = QLineEdit()
        self.edt_name.setPlaceholderText("Ej. Zona Norte")
        
        self.spn_price = QDoubleSpinBox()
        self.spn_price.setRange(0, 1000)
        self.spn_price.setPrefix("$")
        
        if zone:
            self.edt_name.setText(zone.name)
            self.spn_price.setValue(zone.price)
            
        form.addRow("Nombre:", self.edt_name)
        form.addRow("Precio:", self.spn_price)
        
        grp.setLayout(form)
        layout.addWidget(grp)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        return {
            "name": self.edt_name.text().strip(),
            "price": self.spn_price.value()
        }

class DeliveryZonesView(QWidget):
    def __init__(self, session_factory: sessionmaker, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        
        layout = QVBoxLayout(self)
        
        header = QHBoxLayout()
        title = QLabel("Zonas de Delivery")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #e5e7eb;")
        header.addWidget(title)
        header.addStretch()
        
        # Action Buttons Style
        btn_style = """
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 6px 12px;
                color: #2c3e50;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #eef2f7; }
            QPushButton:disabled { background-color: #4b5563; color: #9ca3af; border: 1px solid #374151; }
        """

        self.btn_add = QPushButton("➕ Nueva Zona")
        self.btn_add.setStyleSheet(btn_style)
        self.btn_add.clicked.connect(self.add_zone)
        header.addWidget(self.btn_add)
        
        self.btn_edit = QPushButton("✏️ Editar")
        self.btn_edit.setStyleSheet(btn_style)
        self.btn_edit.clicked.connect(self.edit_selected_zone)
        self.btn_edit.setEnabled(False)
        header.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("🗑️ Eliminar")
        self.btn_delete.setStyleSheet(btn_style)
        self.btn_delete.clicked.connect(self.delete_zone)
        self.btn_delete.setEnabled(False)
        header.addWidget(self.btn_delete)

        layout.addLayout(header)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "Precio"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self.edit_zone)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        
        # Table Style - Removing explicit Blue #0b1220 to avoid "Blue Dialog" issue
        # Using a more neutral dark style or inheriting if global exists.
        # But to ensure it's not "Blue", we explicitly use darker grays.
        self.table.setStyleSheet("""
             QTableWidget { background-color: #1a1a1a; color: #e5e7eb; gridline-color: #374151; border: none; }
             QHeaderView::section { background-color: #2b2b2b; color: #e5e7eb; border: 1px solid #374151; padding: 6px; font-weight: bold; }
             QTableWidget::item:selected { background-color: #333333; color: white; }
             QTableWidget::item { padding: 4px; }
        """)
        self.table.verticalHeader().setVisible(False)
        
        layout.addWidget(self.table)
        
        self.refresh()
        
    def refresh(self):
        self.table.setRowCount(0)
        with self.session_factory() as session:
            zones = session.query(DeliveryZone).all()
            self.table.setRowCount(len(zones))
            for i, z in enumerate(zones):
                self.table.setItem(i, 0, QTableWidgetItem(str(z.id)))
                self.table.setItem(i, 1, QTableWidgetItem(z.name))
                price_item = QTableWidgetItem(f"${z.price:.2f}")
                price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i, 2, price_item)
                
                # Store ID in first item
                self.table.item(i, 0).setData(Qt.UserRole, z.id)

    def _on_selection_changed(self):
        has_selection = bool(self.table.selectedItems())
        self.btn_edit.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)

    def add_zone(self):
        dlg = ZoneDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if not data["name"]:
                return
            
            with self.session_factory() as session:
                z = DeliveryZone(name=data["name"], price=data["price"])
                session.add(z)
                session.commit()
            self.refresh()
    
    def edit_selected_zone(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            # Create a fake item to reuse existing logic or just call edit_zone logic directly
            # Easier to pass a dummy item with row info since edit_zone expects an item
            # Or better: refactor edit_zone to take row index
            self._edit_zone_by_row(current_row)

    def edit_zone(self, item):
        self._edit_zone_by_row(item.row())

    def _edit_zone_by_row(self, row):
        zid = self.table.item(row, 0).data(Qt.UserRole)
        
        with self.session_factory() as session:
            z = session.get(DeliveryZone, zid)
            if not z:
                return
                
            dlg = ZoneDialog(self, zone=z)
            if dlg.exec():
                data = dlg.get_data()
                z.name = data["name"]
                z.price = data["price"]
                session.commit()
                self.refresh()

    def delete_zone(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            return
            
        zid = self.table.item(current_row, 0).data(Qt.UserRole)
        zone_name = self.table.item(current_row, 1).text()
        
        reply = QMessageBox.question(
            self, 
            "Confirmar Eliminación",
            f"¿Estás seguro de que deseas eliminar la zona '{zone_name}'?\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            with self.session_factory() as session:
                z = session.get(DeliveryZone, zid)
                if z:
                    session.delete(z)
                    session.commit()
            self.refresh()


    def edit_zone(self, item):
        row = item.row()
        zid = self.table.item(row, 0).data(Qt.UserRole)
        
        with self.session_factory() as session:
            z = session.get(DeliveryZone, zid)
            if not z:
                return
                
            dlg = ZoneDialog(self, zone=z)
            if dlg.exec():
                data = dlg.get_data()
                z.name = data["name"]
                z.price = data["price"]
                session.commit()
                self.refresh()
