from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QAbstractItemView, QLineEdit, QSizePolicy, QSpacerItem, QMessageBox, QComboBox,
    QLabel
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from sqlalchemy.orm import sessionmaker
import json
from pathlib import Path

from ..repository import list_orders, get_order_by_id, update_order, delete_order_by_id
from ..events import events

COLUMNS = [
    "N° Orden",      # order_number
    "Venta #",       # sale_id
    "Producto",      # product_name
    "Estado",        # status
    "Creado",        # created_at
]


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
                    'order_number': getattr(o, 'order_number', f"ORD-{o.id:03d}"),
                    'sale_id': int(o.sale_id or 0),
                    'product_name': o.product_name or '',
                    'status': o.status or '',
                    'created_at': o.created_at.strftime('%Y-%m-%d %H:%M') if getattr(o, 'created_at', None) else '',
                })
            self.loaded.emit(rows)
        except Exception:
            pass


class OrdersView(QWidget):
    def __init__(self, session_factory: sessionmaker, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._loading = False

        # Layout del encabezado con dos filas
        header = QVBoxLayout()
        
        # Primera fila: búsqueda y filtros
        search_row = QHBoxLayout()
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Buscar… (ID, Venta, Producto, Estado)")
        self.search.setClearButtonEnabled(True)
        
        self.cmb_state = QComboBox(self)
        self.cmb_state.addItems(["Todos", "NUEVO", "EN PROCESO", "LISTO", "ENTREGADO"]) 
        
        search_row.addWidget(QLabel("Búsqueda:"))
        search_row.addWidget(self.search, 2)
        search_row.addWidget(QLabel("Estado:"))
        search_row.addWidget(self.cmb_state)
        search_row.addStretch()
        
        # Segunda fila: acciones
        actions_row = QHBoxLayout()
        self.btn_status = QPushButton("🔄 Cambiar estado", self)
        self.btn_view = QPushButton("👁️ Ver detalles", self)
        self.btn_delete = QPushButton("🗑️ Eliminar", self)
        self.btn_print = QPushButton("🖨️ Imprimir", self)
        self.btn_refresh = QPushButton("🔄 Actualizar", self)
        
        # Estilos: neutro por defecto. Usar acento primario solo en acciones clave.
        # Marcar "Cambiar estado" como acción primaria del flujo.
        self.btn_status.setProperty("accent", "primary")
        # Eliminar estilos inline de eliminar/imprimir para mantener consistencia de tema.
        # Si se requiere un estilo especial (p. ej. danger), podemos añadirlo vía QSS en el futuro.
        
        actions_row.addWidget(self.btn_status)
        actions_row.addWidget(self.btn_view)
        actions_row.addWidget(self.btn_delete)
        actions_row.addWidget(self.btn_print)
        actions_row.addStretch()
        actions_row.addWidget(self.btn_refresh)
        
        header.addLayout(search_row)
        header.addLayout(actions_row)

        self._table = QTableWidget(0, len(COLUMNS), self)
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self._table)

        # Eventos
        self.search.textChanged.connect(self._apply_filter)
        self.cmb_state.currentIndexChanged.connect(self._apply_filter)
        self.btn_refresh.clicked.connect(self.reload)
        self.btn_status.clicked.connect(self._on_change_status)
        self.btn_view.clicked.connect(self._on_view)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_print.clicked.connect(self._on_print)

        self.reload()
        # Conectar evento global para recargar cuando se cree un pedido
        try:
            events.order_created.connect(lambda order_id: self.reload())
        except Exception:
            pass

    def _selected_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        try:
            # Obtener el ID real desde UserRole
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
            return None
        except Exception:
            return None

    def reload(self) -> None:
        try:
            with self._session_factory() as session:
                orders = list_orders(session)
            rows = []
            for o in orders:
                rows.append({
                    'id': int(o.id),
                    'order_number': getattr(o, 'order_number', f"ORD-{o.id:03d}"),
                    'sale_id': int(o.sale_id or 0),
                    'product_name': o.product_name or '',
                    'status': o.status or '',
                    'created_at': o.created_at.strftime('%Y-%m-%d %H:%M') if getattr(o, 'created_at', None) else '',
                })
            self._populate(rows)
        except Exception:
            pass

    def _populate(self, rows: list[dict]) -> None:
        sort_enabled = self._table.isSortingEnabled()
        if sort_enabled:
            self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))
        for r, d in enumerate(rows):
            # Crear item para el número de orden y guardar el ID real para selección
            order_item = QTableWidgetItem(d.get('order_number') or f"ORD-{d.get('id') or 0:03d}")
            order_item.setData(Qt.ItemDataRole.UserRole, int(d.get('id') or 0))
            self._table.setItem(r, 0, order_item)
            self._table.setItem(r, 1, QTableWidgetItem(str(d.get('sale_id') or '')))
            self._table.setItem(r, 2, QTableWidgetItem(d.get('product_name') or ''))
            self._table.setItem(r, 3, QTableWidgetItem(d.get('status') or ''))
            self._table.setItem(r, 4, QTableWidgetItem(d.get('created_at') or ''))
        self._table.resizeColumnsToContents()
        if sort_enabled:
            self._table.setSortingEnabled(True)

    def _apply_filter(self) -> None:
        text = (self.search.text() or '').lower().strip()
        state = self.cmb_state.currentText()
        rows = self._table.rowCount()
        # Aplicar filtro por estado y texto (si hay)
        for r in range(rows):
            vis = True
            # filtrar por estado
            if state and state != "Todos":
                item_state = self._table.item(r, 3)
                val_state = (item_state.text() if item_state else '')
                if val_state.strip().upper() != state.strip().upper():
                    vis = False
            # filtrar por texto
            if vis and text:
                vis = False
                for c in range(self._table.columnCount()):
                    item = self._table.item(r, c)
                    val = ((item.text() if item else '') or '').lower()
                    if text in val:
                        vis = True
                        break
            self._table.setRowHidden(r, not vis)

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
                from PySide6.QtWidgets import QFileDialog
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

    def _on_change_status(self) -> None:
        sid = self._selected_id()
        if sid is None:
            return
        from PySide6.QtWidgets import QInputDialog
        new_status, ok = QInputDialog.getText(self, "Cambiar estado", "Nuevo estado:")
        if not ok:
            return
        try:
            with self._session_factory() as session:
                update_order(session, sid, status=new_status.strip())
            self.reload()
        except Exception:
            QMessageBox.warning(self, "Pedidos", "No se pudo actualizar el estado.")

    def _on_view(self) -> None:
        sid = self._selected_id()
        if sid is None:
            return
        try:
            with self._session_factory() as session:
                order = get_order_by_id(session, sid)
            if not order:
                return
            details = {}
            try:
                details = json.loads(order.details_json or "{}")
            except Exception:
                pass
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox
            dlg = QDialog(self)
            dlg.setWindowTitle(f"Pedido #{sid}")
            lay = QVBoxLayout(dlg)
            txt = QTextEdit(dlg)
            txt.setReadOnly(True)
            txt.setPlainText(json.dumps(details, ensure_ascii=False, indent=2))
            lay.addWidget(txt)
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, dlg)
            btns.accepted.connect(dlg.accept)
            lay.addWidget(btns)
            dlg.resize(520, 400)
            dlg.exec()
        except Exception:
            QMessageBox.information(self, "Pedidos", "No se pudo abrir el detalle.")

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
            self.reload()
        except Exception:
            QMessageBox.warning(self, "Pedidos", "No se pudo eliminar el pedido.")
