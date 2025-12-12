from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, 
    QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem, QDialogButtonBox,
    QHeaderView, QWidget, QScrollArea, QAbstractItemView
)
from PySide6.QtCore import Qt
import json

class OrderDetailsDialog(QDialog):
    def __init__(self, order, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Detalles del Pedido - {order.order_number}")
        self.resize(700, 600)
        
        self.order = order
        self.details = {}
        try:
            self.details = json.loads(order.details_json or "{}")
        except:
            pass
            
        self._init_ui()
        
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        # --- General Info ---
        grp_general = QGroupBox("Información General")
        form_general = QFormLayout()
        
        self.lbl_order_number = QLineEdit(self.order.order_number)
        self.lbl_order_number.setReadOnly(True)
        form_general.addRow("N° Orden:", self.lbl_order_number)
        
        self.lbl_date = QLineEdit(self.order.created_at.strftime('%Y-%m-%d %H:%M'))
        self.lbl_date.setReadOnly(True)
        form_general.addRow("Fecha:", self.lbl_date)
        
        self.lbl_status = QLineEdit(self.order.status or "NUEVO")
        self.lbl_status.setReadOnly(True)
        form_general.addRow("Estado:", self.lbl_status)
        
        designer_name = "N/A"
        if self.order.designer:
            designer_name = self.order.designer.username
        self.lbl_designer = QLineEdit(designer_name)
        self.lbl_designer.setReadOnly(True)
        form_general.addRow("Diseñador:", self.lbl_designer)

        grp_general.setLayout(form_general)
        layout.addWidget(grp_general)
        
        # --- Customer & Product ---
        grp_product = QGroupBox("Producto y Cliente")
        form_product = QFormLayout()
        
        meta = self.details.get('meta', {})
        
        customer_name = meta.get('cliente') or "N/A"
        self.lbl_customer = QLineEdit(str(customer_name))
        self.lbl_customer.setReadOnly(True)
        form_product.addRow("Cliente:", self.lbl_customer)
        
        self.lbl_product = QLineEdit(self.order.product_name)
        self.lbl_product.setReadOnly(True)
        form_product.addRow("Producto:", self.lbl_product)
        
        desc_text = self.details.get('descripcion_text', '')
        if desc_text:
            self.txt_desc = QTextEdit()
            self.txt_desc.setPlainText(desc_text)
            self.txt_desc.setReadOnly(True)
            self.txt_desc.setMaximumHeight(80)
            form_product.addRow("Descripción:", self.txt_desc)
            
        grp_product.setLayout(form_product)
        layout.addWidget(grp_product)
        
        # --- Items ---
        items = self.details.get('items', [])
        if items:
            grp_items = QGroupBox(f"Items ({len(items)})")
            layout_items = QVBoxLayout()
            
            table = QTableWidget(len(items), 3)
            table.setHorizontalHeaderLabels(["Cant.", "Descripción", "Precio Unit."])
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            
            for i, item in enumerate(items):
                qty = item.get('cantidad', 1)
                name = item.get('product_name', 'Item')
                price = item.get('precio_unitario', 0.0)
                
                table.setItem(i, 0, QTableWidgetItem(str(qty)))
                table.setItem(i, 1, QTableWidgetItem(str(name)))
                table.setItem(i, 2, QTableWidgetItem(f"${price:.2f}"))
                
            table.setFixedHeight(100 + (len(items) * 30))
            table.setMaximumHeight(200)
            
            layout_items.addWidget(table)
            grp_items.setLayout(layout_items)
            layout.addWidget(grp_items)
            
        # --- Totals ---
        totals = self.details.get('totals', {})
        if totals:
            grp_totals = QGroupBox("Totales")
            form_totals = QFormLayout()
            
            total_usd = totals.get('total_usd', 0.0)
            total_bs = totals.get('total_bs', 0.0)
            
            self.lbl_total_usd = QLineEdit(f"${total_usd:.2f}")
            self.lbl_total_usd.setReadOnly(True)
            form_totals.addRow("Total USD:", self.lbl_total_usd)
            
            self.lbl_total_bs = QLineEdit(f"Bs. {total_bs:.2f}")
            self.lbl_total_bs.setReadOnly(True)
            form_totals.addRow("Total Bs:", self.lbl_total_bs)
            
            grp_totals.setLayout(form_totals)
            layout.addWidget(grp_totals)
            
        # --- Notes ---
        notes = meta.get('notas')
        if notes:
            grp_notes = QGroupBox("Notas")
            layout_notes = QVBoxLayout()
            txt_notes = QTextEdit()
            txt_notes.setPlainText(str(notes))
            txt_notes.setReadOnly(True)
            txt_notes.setMaximumHeight(60)
            layout_notes.addWidget(txt_notes)
            grp_notes.setLayout(layout_notes)
            layout.addWidget(grp_notes)

        # Add spacer
        layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(self.accept)
        main_layout.addWidget(btns)
