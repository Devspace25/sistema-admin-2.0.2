from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QAbstractItemView, QLineEdit, QHeaderView, QMessageBox, QComboBox,
    QLabel, QDialog, QTextEdit, QDialogButtonBox, QFileDialog, QProgressBar
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from sqlalchemy.orm import sessionmaker
import json
from pathlib import Path

from ..repository import list_orders, get_order_by_id, update_order, delete_order_by_id, list_users, get_order_full
from ..events import events
from .order_details_dialog import OrderDetailsDialog

COLUMNS = [
    "Fecha",         # created_at
    "N° Orden",      # order_number
    "Asesor",        # sale.asesor
    "Diseñador",     # designer (Button or Name)
    "Estado",        # status (ComboBox)
    "Producto",      # product_name
    "Descripción",   # sale.descripcion
]

class OrderStatusWidget(QWidget):
    def __init__(self, current_status: str, order_id: int, callback, parent=None):
        super().__init__(parent)
        self.order_id = order_id
        self.callback = callback
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        self.combo = QComboBox()
        self.combo.addItems(["NUEVO", "DISEÑO", "EN PROCESO", "LISTO", "ENTREGADO"])
        self.combo.setCurrentText(current_status)
        self.combo.currentTextChanged.connect(self._on_change)
        
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setRange(0, 100)
        
        self._update_visuals(current_status)
        
        layout.addWidget(self.combo)
        layout.addWidget(self.progress)
        
    def _on_change(self, text):
        self._update_visuals(text)
        if self.callback:
            self.callback(self.order_id, text)
            
    def _update_visuals(self, status):
        mapping = {
            "NUEVO": 5,
            "DISEÑO": 25,
            "EN PROCESO": 50,
            "LISTO": 85,
            "ENTREGADO": 100
        }
        val = mapping.get(status, 0)
        self.progress.setValue(val)
        
        # Colors
        colors = {
            "NUEVO": "#9E9E9E",      # Grey
            "DISEÑO": "#9C27B0",     # Purple
            "EN PROCESO": "#2196F3", # Blue
            "LISTO": "#FF9800",      # Orange
            "ENTREGADO": "#4CAF50"   # Green
        }
        col = colors.get(status, "#2196F3")
        self.progress.setStyleSheet(f"QProgressBar::chunk {{ background-color: {col}; border-radius: 3px; }} QProgressBar {{ border: 1px solid #ddd; border-radius: 3px; background: #f0f0f0; }}")

class _LoadOrdersThread(QThread):
    loaded = Signal(list)

    def __init__(self, session_factory: sessionmaker, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory

    def run(self) -> None:
        try:
            with self._session_factory() as session:
                orders = list_orders(session)
                rows = []
                for o in orders:
                    rows.append({
                        'id': int(o.id),
                        'created_at': o.created_at.strftime('%Y-%m-%d %H:%M') if getattr(o, 'created_at', None) else '',
                        'order_number': getattr(o, 'order_number', f"ORD-{o.id:03d}"),
                        'advisor': o.sale.asesor if o.sale else 'N/A',
                        'status': o.status or 'NUEVO',
                        'product_name': o.product_name or '',
                        'description': o.sale.descripcion if o.sale else '',
                        'sale_id': int(o.sale_id or 0),
                        'details_json': o.details_json,
                        'designer_id': o.designer_id,
                        'designer_name': o.designer.username if o.designer else None,
                        'requires_design': (o.sale.diseno_usd or 0) > 0 if o.sale else False
                    })
                self.loaded.emit(rows)
        except Exception as e:
            print(f"Error loading orders: {e}")
            pass

class OrdersView(QWidget):
    def __init__(self, session_factory: sessionmaker, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._loading = False
        self._orders_data = [] # Store data for filtering

        # Layout
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Buscar por Orden, Asesor o Producto...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        
        self.btn_refresh = QPushButton("🔄 Actualizar", self)
        self.btn_refresh.clicked.connect(self.refresh)
        
        self.btn_view = QPushButton("👁️ Ver detalles", self)
        self.btn_view.clicked.connect(self._on_view)
        
        self.btn_print = QPushButton("🖨️ Imprimir", self)
        self.btn_print.clicked.connect(self._on_print)
        
        self.btn_delete = QPushButton("🗑️ Eliminar", self)
        self.btn_delete.clicked.connect(self._on_delete)
        
        header_layout.addWidget(QLabel("Buscar:"))
        header_layout.addWidget(self.search, 1)
        header_layout.addWidget(self.btn_view)
        header_layout.addWidget(self.btn_print)
        header_layout.addWidget(self.btn_delete)
        header_layout.addWidget(self.btn_refresh)
        
        layout.addLayout(header_layout)

        # Table
        self._table = QTableWidget(0, len(COLUMNS), self)
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # Resize columns
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch) # Description stretches
        # Set minimum width for columns to avoid being too narrow
        header.setMinimumSectionSize(120)
        
        # Set default row height to accommodate the status widget
        self._table.verticalHeader().setDefaultSectionSize(50)
        
        layout.addWidget(self._table)
        
        # Initial load
        QTimer.singleShot(100, self.refresh)
        
        # Events
        try:
            events.order_created.connect(lambda order_id: self.refresh())
        except Exception:
            pass

    def refresh(self) -> None:
        if self._loading:
            return
        self._loading = True
        self.btn_refresh.setEnabled(False)
        self._table.setRowCount(0)
        
        self._thread = _LoadOrdersThread(self._session_factory, self)
        self._thread.loaded.connect(self._on_loaded)
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _on_loaded(self, rows: list) -> None:
        self._orders_data = rows
        self._apply_filter()

    def _on_finished(self) -> None:
        self._loading = False
        self.btn_refresh.setEnabled(True)

    def _apply_filter(self) -> None:
        text = self.search.text().lower().strip()
        filtered = []
        for row in self._orders_data:
            if not text:
                filtered.append(row)
                continue
            
            # Search in relevant fields
            if (text in str(row['order_number']).lower() or 
                text in str(row['advisor']).lower() or 
                text in str(row['product_name']).lower() or
                text in str(row['description']).lower() or
                text in str(row['status']).lower()):
                filtered.append(row)
        
        self._populate_table(filtered)

    def _populate_table(self, rows: list) -> None:
        self._table.setRowCount(0)
        self._table.setRowCount(len(rows))
        self._table.setSortingEnabled(False) # Disable sorting while populating
        
        for i, row in enumerate(rows):
            # Date
            item_date = QTableWidgetItem(row['created_at'])
            item_date.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(i, 0, item_date)
            
            # Order Number
            item_ord = QTableWidgetItem(str(row['order_number']))
            item_ord.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(i, 1, item_ord)
            
            # Advisor
            item_adv = QTableWidgetItem(row['advisor'])
            item_adv.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(i, 2, item_adv)

            # Designer
            if row.get('requires_design'):
                if row.get('designer_name'):
                    btn_designer = QPushButton(f"👤 {row['designer_name']}")
                    btn_designer.setToolTip("Click para cambiar diseñador")
                    btn_designer.clicked.connect(lambda _, oid=row['id']: self._assign_designer(oid))
                    self._table.setCellWidget(i, 3, btn_designer)
                else:
                    btn_assign = QPushButton("➕ Asignar")
                    btn_assign.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold;")
                    btn_assign.clicked.connect(lambda _, oid=row['id']: self._assign_designer(oid))
                    self._table.setCellWidget(i, 3, btn_assign)
            else:
                item_na = QTableWidgetItem("N/A")
                item_na.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(i, 3, item_na)
            
            # Status (Widget with Progress)
            status_widget = OrderStatusWidget(row['status'], row['id'], self._update_status)
            self._table.setCellWidget(i, 4, status_widget)
            
            # Product
            item_prod = QTableWidgetItem(row['product_name'])
            self._table.setItem(i, 5, item_prod)

            # Description
            item_desc = QTableWidgetItem(row['description'])
            item_desc.setToolTip(row['description'])  # Show full text on hover
            self._table.setItem(i, 6, item_desc)
            
            # Store ID in the first item
            item_date.setData(Qt.UserRole, row['id'])

    def _assign_designer(self, order_id: int) -> None:
        try:
            with self._session_factory() as session:
                users = list_users(session)
                user_items = [(u.username, u.id) for u in users]
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error cargando usuarios: {e}")
            return

        if not user_items:
            QMessageBox.warning(self, "Aviso", "No hay usuarios disponibles.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Asignar Diseñador")
        lay = QVBoxLayout(dlg)
        
        combo = QComboBox()
        for name, uid in user_items:
            combo.addItem(name, uid)
            
        lay.addWidget(QLabel("Seleccione el diseñador:"))
        lay.addWidget(combo)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected_uid = combo.currentData()
            try:
                with self._session_factory() as session:
                    update_order(session, order_id, designer_id=selected_uid)
                    # Auto update status to DISEÑO if it was NUEVO
                    order = get_order_by_id(session, order_id)
                    if order and order.status == 'NUEVO':
                        update_order(session, order_id, status='DISEÑO')
                
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo asignar: {e}")

    def _update_status(self, order_id: int, new_status: str) -> None:
        try:
            with self._session_factory() as session:
                update_order(session, order_id, status=new_status)
            # Update local data to reflect change if we filter again
            for row in self._orders_data:
                if row['id'] == order_id:
                    row['status'] = new_status
                    break
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo actualizar el estado: {e}")

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item:
            return item.data(Qt.UserRole)
        return None

    def _on_view(self) -> None:
        sid = self._selected_id()
        if sid is None:
            return
        try:
            with self._session_factory() as session:
                order = get_order_full(session, sid)
                if order:
                    session.expunge(order)
            
            if not order:
                return
            
            dlg = OrderDetailsDialog(order, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.information(self, "Pedidos", f"No se pudo abrir el detalle: {e}")

    def _on_delete(self) -> None:
        sid = self._selected_id()
        if sid is None:
            return
        m = QMessageBox(self)
        m.setWindowTitle("Eliminar pedido")
        m.setIcon(QMessageBox.Icon.Warning)
        m.setText(f"¿Seguro que deseas eliminar el pedido #{sid}?")
        m.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        m.setDefaultButton(QMessageBox.StandardButton.No)
        if m.exec() != QMessageBox.StandardButton.Yes:
            return
        try:
            with self._session_factory() as session:
                delete_order_by_id(session, sid)
            self.refresh()
        except Exception:
            QMessageBox.warning(self, "Pedidos", "No se pudo eliminar el pedido.")

    def _on_print(self) -> None:
        sid = self._selected_id()
        if sid is None:
            return
        try:
            with self._session_factory() as session:
                order = get_order_by_id(session, sid)
            if not order:
                return
            from ..receipts import print_order_pdf, print_order_80mm
            # extraer customer info desde details_json.meta.cliente si existe
            customer = None
            try:
                details = json.loads(order.details_json or '{}')
                meta = details.get('meta') or {}
                cliente_meta = meta.get('cliente') or meta.get('cliente_id') or meta.get('cliente_meta')
                if isinstance(cliente_meta, dict):
                    customer = {
                        'name': cliente_meta.get('name') or cliente_meta.get('nombre') or '',
                        'short_address': cliente_meta.get('direccion_corta') or cliente_meta.get('direccion') or '',
                        'document': cliente_meta.get('documento') or cliente_meta.get('rif') or '',
                        'phone': cliente_meta.get('telefono') or cliente_meta.get('telefono_movil') or '',
                    }
            except Exception:
                customer = None

            # Preguntar al usuario dónde guardar el ticket (PDF)
            try:
                default_name = f"{(order.order_number or f'ORD-{int(order.id):03d}')}.pdf"
                start_dir = str(Path.home())
                save_path, _ = QFileDialog.getSaveFileName(self, "Guardar ticket como", str(Path(start_dir) / default_name), "PDF Files (*.pdf)")
                if not save_path:
                    # Usuario canceló
                    return
            except Exception:
                save_path = None

            # Preferir PDF si reportlab está disponible
            try:
                if save_path:
                    path = print_order_pdf(
                        order_id=int(order.id),
                        sale_id=int(order.sale_id or 0),
                        product_name=(order.product_name or ''),
                        status=(order.status or ''),
                        details_json=(order.details_json or '{}'),
                        customer=customer,
                        out_path=Path(save_path),
                    )
                else:
                    path = print_order_pdf(
                        order_id=int(order.id),
                        sale_id=int(order.sale_id or 0),
                        product_name=(order.product_name or ''),
                        status=(order.status or ''),
                        details_json=(order.details_json or '{}'),
                        customer=customer,
                    )
            except Exception:
                # Fallback: usar el generador 80mm que también devuelve Path; si acepta out_path lo usará, si no, guardará en default receipts folder
                try:
                    if save_path:
                        path = print_order_80mm(
                            order_id=int(order.id), sale_id=int(order.sale_id or 0), product_name=(order.product_name or ''), status=(order.status or ''), details_json=(order.details_json or '{}')
                        )
                        # Si el fallback no soporta out_path, intentar mover/renombrar al destino elegido
                        try:
                            p = Path(path)
                            dest = Path(save_path)
                            p.replace(dest)
                            path = dest
                        except Exception:
                            pass
                    else:
                        path = print_order_80mm(order_id=int(order.id), sale_id=int(order.sale_id or 0), product_name=(order.product_name or ''), status=(order.status or ''), details_json=(order.details_json or '{}'))
                except Exception as e:
                    QMessageBox.critical(self, 'Imprimir', f'Error al generar el ticket: {e}')
                    return

            QMessageBox.information(self, "Pedidos", f"Orden guardada en:\n{path}")
        except Exception:
            QMessageBox.warning(self, "Pedidos", "No se pudo imprimir la orden.")
