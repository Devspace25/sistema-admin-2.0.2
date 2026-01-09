from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QAbstractItemView, QLineEdit, QHeaderView, QMessageBox, QComboBox,
    QLabel, QDialog, QTextEdit, QDialogButtonBox, QFileDialog, QProgressBar
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from sqlalchemy.orm import sessionmaker
import json
import os
from pathlib import Path

from ..repository import (
    list_orders, get_order_by_id, update_order, delete_order_by_id, 
    list_users, get_order_full, user_has_role
)
from ..models import User
from ..permissions import is_admin_user
from ..events import events
from .order_details_dialog import OrderDetailsDialog
from zoneinfo import ZoneInfo
from datetime import timezone

COLUMNS = [
    "Fecha",         # created_at
    "N° Orden",      # order_number
    "Asesor",        # sale.asesor
    "Diseñador",     # designer (Button or Name)
    "Estado",        # status (Label)
    "Entregado El",  # delivered_at
    "Entrega",       # delivery_method
    "Producto",      # product_name
    "Descripción",   # sale.descripcion
]

def format_date_caracas(dt):
    if not dt:
        return "-"
    # Si es naive, asumimos que ya está en hora correcta (local) o UTC.
    # Ante la duda de migraciones mixtas, lo convertimos explícitamente si tiene tz.
    # Para cumplir requerimiento "Zona horaria Caracas":
    utc = ZoneInfo("UTC")
    caracas = ZoneInfo("America/Caracas")
    
    if dt.tzinfo is None:
        # Asumir que lo guardado está en UTC (práctica recomendada) para poder convertir
        # Si resulta que se guardó en local, esto restará 4h.
        # Ajuste: Si se usó datetime.now() local, no deberíamos convertir.
        # Pero para estandarizar, lo trataremos.
        # Al no tener certeza del origen (legacy vs nuevo), aplicamos solo formato español
        # para visualización limpia, y conversión si viene aware.
        pass
    else:
        dt = dt.astimezone(caracas)
        
    return dt.strftime('%d/%m/%Y %I:%M %p')

class OrderStatusWidget(QWidget):
    def __init__(self, current_status: str, order_id: int, callback=None, parent=None):
        super().__init__(parent)
        self.order_id = order_id
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        # Label instead of Combo
        self.lbl_status = QLabel(current_status or "NUEVO")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("font-weight: bold; font-size: 11px;")
        
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setRange(0, 100)
        
        self._update_visuals(current_status)
        
        layout.addWidget(self.lbl_status)
        layout.addWidget(self.progress)
            
    def _update_visuals(self, status):
        mapping = {
            "NUEVO": 5,
            "DISEÑO": 25,
            "POR_PRODUCIR": 40,
            "PRODUCCION": 45,
            "EN_PRODUCCION": 60,
            "LISTO": 85,
            "ENTREGADO": 100
        }
        status_norm = status.replace(" ", "_") # Handle "EN PROCESO" legacy
        val = mapping.get(status, mapping.get(status_norm, 0))
        self.progress.setValue(val)
        
        # Colors
        colors = {
            "NUEVO": "#9E9E9E",      # Grey
            "DISEÑO": "#9C27B0",     # Purple
            "POR_PRODUCIR": "#E91E63", # Pink
            "PRODUCCION": "#E91E63",   # Pink
            "EN_PRODUCCION": "#2196F3", # Blue
            "LISTO": "#FF9800",      # Orange
            "ENTREGADO": "#4CAF50"   # Green
        }
        col = colors.get(status, colors.get(status_norm, "#2196F3"))
        
        self.lbl_status.setStyleSheet(f"color: {col}; font-weight: bold;")
        self.progress.setStyleSheet(f"QProgressBar::chunk {{ background-color: {col}; border-radius: 2px; }} QProgressBar {{ border: none; background: #e0e0e0; height: 4px; }}")

class _LoadOrdersThread(QThread):
    loaded = Signal(list)

    def __init__(self, session_factory: sessionmaker, filter_user: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self.filter_user = filter_user

    def run(self) -> None:
        try:
            with self._session_factory() as session:
                orders = list_orders(session, filter_user=self.filter_user)
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
                        'requires_design': (o.sale.diseno_usd or 0) > 0 if o.sale else False,
                        'delivered_at': format_date_caracas(getattr(o, 'delivered_at', None)),
                        'delivery_method': o.delivery_method or '-'
                    })
                self.loaded.emit(rows)
        except Exception as e:
            print(f"Error loading orders: {e}")
            pass

class OrdersView(QWidget):
    def __init__(self, session_factory: sessionmaker, current_user: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._current_user = current_user
        self._loading = False
        self._orders_data = [] # Store data for filtering
        self._can_edit = False  # ediciones de flujo (estado/asignación)
        self._can_delete = False  # eliminación (solo ADMIN)

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
        self.btn_delete.setVisible(False)
        
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
        
        # 'Descripción' is the last column (index 8), so let it stretch
        header.setSectionResizeMode(8, QHeaderView.Stretch)
        
        # Specific tuning
        # Column 6 'Método' doesn't need to be huge
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        # Set minimum width for columns generally
        header.setMinimumSectionSize(90)
        
        # Set default row height to accommodate the status widget
        self._table.verticalHeader().setDefaultSectionSize(50)
        
        layout.addWidget(self._table)
        
        # Initial load
        QTimer.singleShot(100, self.refresh)
        
        # Events
        try:
            # Usar una referencia débil o verificar isVisible/isValid antes de llamar
            # Para simplificar, capturamos RuntimeError dentro de la lambda
            def safe_refresh(oid):
                try:
                    if self.isVisible():
                        self.refresh()
                except RuntimeError:
                    pass
            events.order_created.connect(safe_refresh)
        except Exception:
            pass

    def set_permissions(self, permissions: set[str]):
        """Configurar permisos de edición y eliminación."""
        is_admin = is_admin_user(self._session_factory, self._current_user)

        # Permite editar flujo (estado/asignación) por permiso.
        self._can_edit = "edit_orders" in permissions
        # Eliminar solo para ADMIN (aunque tenga edit_orders).
        self._can_delete = is_admin and ("edit_orders" in permissions)
        
        self.btn_delete.setVisible(self._can_delete)
        # Refrescar tabla para actualizar widgets de estado y diseñador
        self._apply_filter()

    def refresh(self) -> None:
        if self._loading:
            return
        self._loading = True
        self.btn_refresh.setEnabled(False)
        self._table.setRowCount(0)
        
        filter_user = None
        if self._current_user:
            try:
                with self._session_factory() as session:
                    user = session.query(User).filter(User.username == self._current_user).first()
                    if user:
                        is_admin = user_has_role(session, user_id=user.id, role_name="ADMIN")
                        is_administracion = user_has_role(session, user_id=user.id, role_name="ADMINISTRACION")
                        is_designer = user_has_role(session, user_id=user.id, role_name="DISEÑADOR")
                        is_taller = user_has_role(session, user_id=user.id, role_name="TALLER")
                        
                        if not (is_admin or is_administracion or is_designer or is_taller):
                            filter_user = self._current_user
            except Exception as e:
                print(f"Error checking permissions in OrdersView: {e}")
        
        self._thread = _LoadOrdersThread(self._session_factory, filter_user=filter_user, parent=self)
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
                    btn_designer.setEnabled(self._can_edit)
                    self._table.setCellWidget(i, 3, btn_designer)
                else:
                    btn_assign = QPushButton("➕ Asignar")
                    btn_assign.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold;")
                    btn_assign.clicked.connect(lambda _, oid=row['id']: self._assign_designer(oid))
                    btn_assign.setEnabled(self._can_edit)
                    self._table.setCellWidget(i, 3, btn_assign)
            else:
                item_na = QTableWidgetItem("N/A")
                item_na.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(i, 3, item_na)
            
            # Status (Widget with Progress - Automatic, ReadOnly)
            status_widget = OrderStatusWidget(row['status'], row['id'])
            self._table.setCellWidget(i, 4, status_widget)
            
            # Delivered At
            item_del_at = QTableWidgetItem(row['delivered_at'])
            item_del_at.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(i, 5, item_del_at)
            
            # Delivery Method
            item_del_meth = QTableWidgetItem(row['delivery_method'])
            item_del_meth.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(i, 6, item_del_meth)
            
            # Product
            item_prod = QTableWidgetItem(row['product_name'])
            self._table.setItem(i, 7, item_prod)

            # Description
            item_desc = QTableWidgetItem(row['description'])
            item_desc.setToolTip(row['description'])  # Show full text on hover
            self._table.setItem(i, 8, item_desc)
            
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
        if not self._can_delete:
            QMessageBox.information(self, "Pedidos", "No tienes permisos para eliminar pedidos.")
            return
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
                
                # Obtener venta asociada para items y cliente
                from ..models import Sale, Customer
                sale = session.get(Sale, order.sale_id) if order.sale_id else None
                
                # Preparar datos para el ticket Excel
                order_info = {
                    'order_number': order.order_number,
                    'date': order.created_at.strftime('%Y-%m-%d'),
                    'items': [],
                    'advisor': getattr(sale, 'asesor', '') if sale else '',
                    'payment_method': getattr(sale, 'forma_pago', '') if sale else '',
                }
                
                # Cliente
                if sale:
                    order_info['customer_name'] = sale.cliente
                    if sale.cliente_id:
                        cust_obj = session.get(Customer, sale.cliente_id)
                        if cust_obj:
                            order_info['customer_name'] = cust_obj.name
                            order_info['customer_address'] = cust_obj.short_address or ""
                            order_info['customer_rif'] = cust_obj.document or ""
                            order_info['customer_phone'] = cust_obj.phone or ""
                
                # Fallback cliente desde details
                if not order_info.get('customer_name'):
                     try:
                        details = json.loads(order.details_json or '{}')
                        meta = details.get('meta') or {}
                        cliente_meta = meta.get('cliente') or meta.get('cliente_id') or meta.get('cliente_meta')
                        if isinstance(cliente_meta, dict):
                            order_info['customer_name'] = cliente_meta.get('name') or cliente_meta.get('nombre')
                            order_info['customer_address'] = cliente_meta.get('direccion_corta') or cliente_meta.get('direccion')
                            order_info['customer_rif'] = cliente_meta.get('documento') or cliente_meta.get('rif')
                            order_info['customer_phone'] = cliente_meta.get('telefono') or cliente_meta.get('telefono_movil')
                     except:
                        pass

                # Items
                tasa = getattr(sale, 'tasa_bcv', 0.0) or 0.0
                
                # Extras (Diseño, Instalación, IVA) en Bs
                if sale:
                    order_info['design_bs'] = (sale.diseno_usd or 0.0) * tasa
                    # Instalación se mapea desde ingresos_usd según convención
                    order_info['installation_bs'] = (sale.ingresos_usd or 0.0) * tasa
                    order_info['iva_bs'] = (sale.iva or 0.0) * tasa
                    
                    # Lógica de estado de pago (A24)
                    restante_usd = sale.restante or 0.0
                    if restante_usd <= 0.01:
                        order_info['payment_status_text'] = "PAGO TOTAL"
                    else:
                        abono_usd = sale.abono_usd or 0.0
                        order_info['payment_status_text'] = f"ABONO $ {abono_usd:,.2f} POR COBRAR $ {restante_usd:,.2f}"
                
                if sale and sale.items:
                    for item in sale.items:
                        # Calcular total en Bs si hay tasa, sino usar 0 o el valor en USD si se prefiere (aquí asumimos Bs)
                        total_bs = (item.total_price or 0.0) * tasa
                        
                        # Intentar obtener descripción específica del item desde details_json
                        item_desc = None
                        if item.details_json:
                            try:
                                details = json.loads(item.details_json)
                                if isinstance(details, dict):
                                    item_desc = details.get('description')
                            except Exception:
                                pass
                        
                        # Usar descripción específica del item, o fallback al nombre del producto
                        # Evitar usar sale.descripcion para items individuales para prevenir duplicidad
                        description_text = item_desc if item_desc else item.product_name
                        
                        order_info['items'].append({
                            'qty': item.quantity,
                            'desc': description_text,
                            'total': total_bs
                        })
                else:
                    # Fallback si no hay items
                    desc_fallback = sale.descripcion if (sale and sale.descripcion) else order.product_name
                    order_info['items'].append({
                        'qty': 1,
                        'desc': desc_fallback,
                        'total': 0.0
                    })

            # Preguntar dónde guardar
            default_name = f"{(order.order_number or f'ORD-{int(order.id):03d}')}.pdf"
            start_dir = str(Path.home())
            save_path, _ = QFileDialog.getSaveFileName(self, "Guardar ticket como", str(Path(start_dir) / default_name), "PDF Files (*.pdf)")
            if not save_path:
                return

            from ..receipts import print_ticket_excel_pdf
            path = print_ticket_excel_pdf(order_info, Path(save_path))
            
            QMessageBox.information(self, "Pedidos", f"Ticket generado en:\n{path}")
            
            # Abrir automáticamente
            try:
                os.startfile(path)
            except Exception as e:
                print(f"No se pudo abrir el archivo automáticamente: {e}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo imprimir el ticket: {e}")
            import traceback
            traceback.print_exc()
