from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QMessageBox, QLabel, QLineEdit,
    QComboBox, QDateEdit, QDoubleSpinBox, QTextEdit, QDialog,
    QFormLayout, QDialogButtonBox, QGroupBox, QGridLayout, QSpacerItem,
    QSizePolicy, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate, QEvent
from PySide6.QtGui import QFont, QColor
from datetime import datetime
from sqlalchemy.orm import sessionmaker, joinedload
import json

from ..models import Sale
from ..repository import (
    list_sales,
    add_sale,
    update_sale,
    delete_sale_by_id,
    get_sale_by_id,
    get_customer_by_id,
    add_corporeo_payload,
    add_corporeo_config,
)
from .sale_dialog import SaleDialog as InvoiceSaleDialog


class SalesView(QWidget):
    def __init__(self, session_factory: sessionmaker, parent=None):
        super().__init__(parent)
        self._session_factory = session_factory
        self._setup_ui()
        self._load_sales()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Título
        title = QLabel("Gestión de Ventas")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Búsqueda
        search_layout = QHBoxLayout()
        search_label = QLabel("Búsqueda:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Buscar por número de orden, artículo, asesor...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit, 2)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # Botones de acción
        button_layout = QHBoxLayout()

        self.btn_add = QPushButton("➕ Nueva Venta")
        # Mantener verde para acción positiva
        self.btn_add.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 16px; }")
        self.btn_add.clicked.connect(self._on_add_sale)
        button_layout.addWidget(self.btn_add)

        self.btn_edit = QPushButton("✏️ Editar")
        self.btn_edit.clicked.connect(self._on_edit_sale)
        self.btn_edit.setEnabled(False)
        button_layout.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("🗑️ Eliminar")
        # Mantener rojo para acción destructiva
        self.btn_delete.setStyleSheet("QPushButton { background-color: #f44336; color: white; padding: 8px 16px; }")
        self.btn_delete.clicked.connect(self._on_delete_sale)
        self.btn_delete.setEnabled(False)
        button_layout.addWidget(self.btn_delete)

        self.btn_refresh = QPushButton("🔄 Actualizar")
        self.btn_refresh.clicked.connect(self._load_sales)
        button_layout.addWidget(self.btn_refresh)

        button_layout.addStretch()

        # Estado
        self._status_label = QLabel("Listo", self)
        self._status_label.setStyleSheet("color: #666; font-style: italic; padding: 4px;")
        button_layout.addWidget(self._status_label)

        layout.addLayout(button_layout)

        # Tabla de ventas
        self.table = QTableWidget()
        self._setup_table()
        layout.addWidget(self.table)
        
    def _setup_table(self):
        # Configurar columnas de la tabla
        columns = [
            "ID", "Fecha", "Núm. Orden", "Artículo", "Descripción", "Asesor", "Cliente", "Venta $", 
            "Forma Pago", "Serial Billete", "Banco", "Referencia", "Fecha Pago",
            "Monto Bs.D", "Monto $ Calc.", "Tasa BCV", "Abono $", "Restante $", "IVA", "Por Cobrar $",
            "Diseño $", "Ingresos $"
        ]
        
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # Configurar tabla con el mismo estilo que otros módulos
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        
        # Ajustar el ancho de las columnas
        header = self.table.horizontalHeader()
        # Ajustar todas las columnas al contenido automáticamente
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        
        # Conectar selección
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        
        # Instalar filtro de eventos para detectar clics en espacio vacío
        self.table.viewport().installEventFilter(self)

    def eventFilter(self, source, event):
        if source == self.table.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            index = self.table.indexAt(event.pos())
            if not index.isValid():
                self.table.clearSelection()
        return super().eventFilter(source, event)
        
    def _load_sales(self):
        """Cargar todas las ventas en la tabla."""
        self._status_label.setText("Cargando ventas...")
        try:
            with self._session_factory() as session:
                # Cargar ventas con relaciones (items y payments) para visualización correcta
                sales = session.query(Sale).options(
                    joinedload(Sale.items),
                    joinedload(Sale.payments)
                ).order_by(Sale.id.desc()).all()
            
                self.table.setRowCount(len(sales))
                
                for row, sale in enumerate(sales):
                    # Llenar cada columna
                    # Determinar nombre de cliente preferido
                    client_name = ''
                    try:
                        if getattr(sale, 'cliente', None):
                            client_name = getattr(sale, 'cliente')
                        elif getattr(sale, 'cliente_id', None):
                            try:
                                cust = get_customer_by_id(session, int(getattr(sale, 'cliente_id')))
                                if cust:
                                    client_name = getattr(cust, 'name', '')
                            except Exception:
                                client_name = ''
                    except Exception:
                        client_name = ''

                    # Formatear Artículo (Productos)
                    articulo_display = sale.articulo or ""
                    try:
                        if hasattr(sale, 'items') and sale.items:
                            product_counts = {}
                            for item in sale.items:
                                name = item.product_name
                                qty = item.quantity
                                if name in product_counts:
                                    product_counts[name] += qty
                                else:
                                    product_counts[name] = qty
                            
                            parts = []
                            for name, total_qty in product_counts.items():
                                if total_qty > 1:
                                    if total_qty % 1 == 0:
                                        parts.append(f"{name} x{int(total_qty)}")
                                    else:
                                        parts.append(f"{name} x{total_qty:.2f}")
                                else:
                                    parts.append(name)
                            if parts:
                                articulo_display = ", ".join(parts)
                    except Exception:
                        pass

                    # Formatear Forma de Pago y Calcular Ingresos USD reales
                    pago_display = sale.forma_pago or ""
                    real_ingresos_usd = 0.0
                    
                    try:
                        if hasattr(sale, 'payments') and sale.payments:
                            methods = []
                            for p in sale.payments:
                                if p.payment_method:
                                    methods.append(p.payment_method)
                                    
                                    # Lógica para Ingresos $: Sumar solo si el método es en divisas
                                    # Métodos considerados divisas: Efectivo USD, Zelle, Banesco Panamá, Binance, PayPal
                                    # O cualquier otro que no sea Bs.
                                    bs_methods = ["Efectivo Bs.D", "Pago móvil", "Transferencia Bs.D", "Punto de Venta"]
                                    if p.payment_method not in bs_methods:
                                        real_ingresos_usd += (p.amount_usd or 0.0)
                                        
                            if methods:
                                pago_display = ", ".join(methods)
                    except Exception:
                        pass

                    # Construct description from details_json if sale.descripcion is empty or generic
                    description_text = sale.descripcion or ""
                    if (not description_text or description_text.strip().lower() == "producto") and sale.details_json:
                        try:
                            details = json.loads(sale.details_json)
                            items_list = details.get('items', [])
                            parts = []
                            for i in items_list:
                                p_name = i.get('product_name', '')
                                p_details = i.get('details', {})
                                extra = ""
                                if isinstance(p_details, dict):
                                    # Corporeo check
                                    if 'alto' in p_details and 'ancho' in p_details:
                                        alto = p_details.get('alto')
                                        ancho = p_details.get('ancho')
                                        mat = p_details.get('material_text') or ""
                                        extra = f"{alto}x{ancho}cm {mat}".strip()
                                    # ProductConfigDialog check
                                    elif 'summary' in p_details:
                                        desc = p_details.get('summary', {}).get('descripcion', '')
                                        if desc:
                                            extra = desc
                                
                                # Si tenemos detalles extra, usarlos como descripción principal
                                # Esto evita mostrar "Producto" o "Sello" cuando tenemos "SELLO AUTOMATICO..."
                                if extra:
                                    full_desc = extra
                                else:
                                    full_desc = p_name or "Producto"
                                
                                parts.append(full_desc)
                            
                            if parts:
                                description_text = "; ".join(parts)
                        except Exception:
                            pass

                    items = [
                        str(sale.id),
                        sale.fecha.strftime("%d/%m/%Y %H:%M") if sale.fecha else "",
                        sale.numero_orden or "",
                        articulo_display,
                        description_text,
                        sale.asesor or "",
                        client_name or "",
                        f"${sale.venta_usd:,.2f}" if sale.venta_usd else "$0.00",
                        pago_display,
                        sale.serial_billete or "",
                        sale.banco or "",
                        sale.referencia or "",
                        sale.fecha_pago.strftime("%d/%m/%Y") if sale.fecha_pago else "",
                        f"Bs. {sale.monto_bs:,.2f}" if sale.monto_bs else "",
                        f"${sale.monto_usd_calculado:,.2f}" if sale.monto_usd_calculado else "",
                        f"{sale.tasa_bcv:,.2f}" if sale.tasa_bcv else "",
                        f"${sale.abono_usd:,.2f}" if sale.abono_usd else "",
                        "",
                        f"${sale.iva:,.2f}" if sale.iva else "",
                        f"${sale.restante:,.2f}" if sale.restante else "",
                        f"${sale.diseno_usd:,.2f}" if sale.diseno_usd else "",
                        f"${real_ingresos_usd:,.2f}" if real_ingresos_usd > 0 else "",
                    ]
                    
                    for col, text in enumerate(items):
                        item = QTableWidgetItem(text)
                        item.setData(Qt.ItemDataRole.UserRole, sale.id)  # Guardar ID para referencia
                        
                        # Colorear Número de Orden (col 2) según deuda
                        if col == 2:
                            # Si hay deuda (restante > 0.01), Naranja. Si no, Verde.
                            restante = sale.restante if sale.restante is not None else 0.0
                            if restante > 0.01:
                                item.setForeground(QColor("orange"))
                            else:
                                item.setForeground(QColor("green"))
                            # Hacerlo negrita para que resalte más
                            font = item.font()
                            font.setBold(True)
                            item.setFont(font)

                        self.table.setItem(row, col, item)
                    
            self._status_label.setText(f"✅ {len(sales)} ventas cargadas")
        except Exception as e:
            self._status_label.setText(f"❌ Error al cargar ventas: {str(e)}")
            print(f"Error cargando ventas: {e}")
            
    def _apply_filter(self):
        """Aplicar filtro de búsqueda a la tabla."""
        search_text = self.search_edit.text().lower()
        
        for row in range(self.table.rowCount()):
            should_show = True
            
            if search_text:
                # Buscar en columnas relevantes: número orden, artículo, descripción, asesor, cliente
                match_found = False
                for col in [2, 3, 4, 5, 6]:  # núm_orden, artículo, descripción, asesor, cliente
                    item = self.table.item(row, col)
                    if item and search_text in item.text().lower():
                        match_found = True
                        break
                should_show = match_found
                
            self.table.setRowHidden(row, not should_show)
                
    def _on_selection_changed(self):
        """Habilitar/deshabilitar botones según la selección."""
        has_selection = len(self.table.selectedItems()) > 0
        self.btn_edit.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)
        
    def _get_selected_sale_id(self) -> int | None:
        """Obtener el ID de la venta seleccionada."""
        selected_items = self.table.selectedItems()
        if selected_items:
            return selected_items[0].data(Qt.ItemDataRole.UserRole)
        return None
        
    def _on_add_sale(self):
        """Abrir diálogo para agregar nueva venta con el nuevo formulario estilo factura."""
        dialog = InvoiceSaleDialog(parent=self, session_factory=self._session_factory)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Mapear datos del nuevo diálogo hacia el repositorio
            try:
                data = dialog.get_data() or {}
                if not data.get('articulo'):
                    QMessageBox.warning(self, "Error", "El artículo es requerido.")
                    return
                if not data.get('asesor'):
                    QMessageBox.warning(self, "Error", "El asesor es requerido.")
                    return
                # Parseos seguros
                def f(key: str) -> float | None:
                    try:
                        v = data.get(key)
                        if v is None or v == "":
                            return None
                        return float(v)
                    except Exception:
                        return None

                venta_usd = f('venta_usd') or 0.0
                if venta_usd <= 0:
                    QMessageBox.warning(self, "Error", "El monto de venta debe ser mayor a cero.")
                    return

                # Fecha de pago
                fecha_pago_str = data.get('fecha_pago')
                fecha_pago_dt = None
                try:
                    if fecha_pago_str:
                        fecha_pago_dt = datetime.strptime(fecha_pago_str, "%Y-%m-%d")
                except Exception:
                    fecha_pago_dt = None

                add_sale_kwargs = {
                    'articulo': data.get('articulo', ''),
                    'asesor': data.get('asesor', ''),
                    'venta_usd': venta_usd,
                    'forma_pago': data.get('forma_pago') or None,
                    'serial_billete': data.get('serial_billete') or None,
                    'banco': data.get('banco') or None,
                    'referencia': data.get('referencia') or None,
                    'fecha_pago': fecha_pago_dt,
                    'monto_bs': f('monto_bs'),
                    'monto_usd_calculado': f('monto_usd'),
                    'abono_usd': f('abono_usd'),
                    'iva': f('iva'),
                    'diseno_usd': f('diseno_usd'),
                    'ingresos_usd': f('ingresos_usd'),
                    'notes': data.get('notas') or None,
                    # Campos para creación automática de pedido
                    'descripcion': data.get('descripcion') or None,
                    'cantidad': f('cantidad'),
                    'precio_unitario': f('precio_unitario'),
                    'total_bs': f('total_bs'),
                    # Campos extra: incluir indicador de diseño, subtotales y cliente legible
                    'incluye_diseno': (str(data.get('incluye_diseno') or '').strip() in ("1", "true", "True")),
                    'subtotal_usd': f('subtotal_usd'),
                    'total_usd': f('total_usd'),
                    'notas': data.get('notas') or None,
                    'cliente': data.get('cliente') or None,
                    'tasa_bcv': f('tasa_bcv'),
                    'precio_unitario': f('precio_unitario'),
                    'cliente_id': (int(str(data.get('cliente_id')).strip()) if data.get('cliente_id') is not None and str(data.get('cliente_id')).strip().isdigit() else None),
                    'items': data.get('items'),
                    'payments': data.get('payments'),
                }

                # Include corporeo payload if dialog had it
                try:
                    if hasattr(dialog, '_corporeo_payload') and dialog._corporeo_payload:
                        add_sale_kwargs['corporeo_payload'] = dialog._corporeo_payload
                except Exception:
                    pass

                created_sale = None
                try:
                    with self._session_factory() as session:
                        # Normalizar cliente_id a int|None
                        cid_raw = add_sale_kwargs.get('cliente_id')
                        if cid_raw is not None and isinstance(cid_raw, str) and cid_raw.isdigit():
                            add_sale_kwargs['cliente_id'] = int(cid_raw)
                        # Añadir nombre del usuario que creó la venta (si lo conoce el diálogo)
                        try:
                            creator = dialog._resolve_current_user() if hasattr(dialog, '_resolve_current_user') else None
                        except Exception:
                            creator = None
                        if creator:
                            add_sale_kwargs['created_by'] = creator
                        # Mapear nombres de parámetros para repository.add_sale
                        if 'incluye_diseno' in add_sale_kwargs:
                            add_sale_kwargs['incluye_diseno'] = bool(add_sale_kwargs.get('incluye_diseno'))
                        # Renombrar claves para coincidir con la firma de add_sale
                        add_sale_kwargs['subtotal_usd'] = add_sale_kwargs.pop('subtotal_usd', None)
                        add_sale_kwargs['total_usd'] = add_sale_kwargs.pop('total_usd', None)
                        add_sale_kwargs['notas'] = add_sale_kwargs.pop('notas', None)
                        add_sale_kwargs['cliente'] = add_sale_kwargs.pop('cliente', None)
                        add_sale_kwargs['tasa_bcv_input'] = add_sale_kwargs.pop('tasa_bcv', None)
                        add_sale_kwargs['precio_unitario_input'] = add_sale_kwargs.pop('precio_unitario', None)

                        created_sale = add_sale(session, **add_sale_kwargs)

                        # Persistir payload corpóreo (si se configuró) ahora que tenemos sale_id definitivo
                        try:
                            payload_for_sale = getattr(dialog, '_corporeo_payload', None)
                            if created_sale and isinstance(payload_for_sale, dict) and payload_for_sale:
                                # Resolver product_id desde el payload si está disponible
                                product_id = None
                                try:
                                    product_id = payload_for_sale.get('product_id')
                                    if not product_id and isinstance(payload_for_sale.get('meta'), dict):
                                        product_id = payload_for_sale['meta'].get('product_id')
                                    if product_id is not None:
                                        product_id = int(product_id)
                                except Exception:
                                    product_id = None

                                try:
                                    add_corporeo_payload(
                                        session,
                                        sale_id=int(created_sale.id),
                                        order_id=getattr(created_sale, 'created_order_id', None),
                                        order_number=getattr(created_sale, 'numero_orden', None),
                                        product_id=product_id,
                                        payload=payload_for_sale,
                                    )
                                except Exception:
                                    pass

                                try:
                                    computed = InvoiceSaleDialog.build_corporeo_computed(
                                        payload_for_sale,
                                        summary=None,
                                        total_bs=add_sale_kwargs.get('total_bs'),
                                    )
                                    order_number = getattr(created_sale, 'numero_orden', None)
                                    if order_number and not computed.get('order_number'):
                                        computed['order_number'] = order_number

                                    add_corporeo_config(
                                        session,
                                        sale_id=int(created_sale.id),
                                        order_id=getattr(created_sale, 'created_order_id', None),
                                        product_id=product_id,
                                        payload=payload_for_sale,
                                        computed=computed,
                                    )
                                except Exception:
                                    pass
                        except Exception:
                            pass
                finally:
                    # Recargar la lista de ventas
                    self._load_sales()

                # Si la venta devolvió un pedido creado, mostrar notificación
                try:
                    if created_sale and getattr(created_sale, 'created_order_id', None):
                        order_id = int(getattr(created_sale, 'created_order_id'))
                        from ..repository import get_order_by_id
                        with self._session_factory() as session:
                            order = get_order_by_id(session, order_id)
                        if order:
                            QMessageBox.information(self, "Pedido creado", f"Se creó el pedido {order.order_number} para la venta.")
                except Exception:
                    pass
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al guardar la venta: {str(e)}")
            
    def _on_edit_sale(self):
        """Abrir diálogo para editar venta seleccionada (usa diálogo legado)."""
        sale_id = self._get_selected_sale_id()
        if not sale_id:
            return

        # Cargar venta desde la base y abrir el diálogo de factura (nuevo) prellenado
        data: dict = {}
        sale = None
        
        try:
            with self._session_factory() as session:
                sale = get_sale_by_id(session, sale_id)
                if not sale:
                    QMessageBox.warning(self, "Editar", "No se encontró la venta seleccionada.")
                    return

                # Mapear campos de modelo Sale hacia los nombres esperados por SaleDialog.set_data
                # Cargar items si existen (dentro de la sesión)
                items_data = []
                if hasattr(sale, 'items') and sale.items:
                    for item in sale.items:
                        try:
                            details = {}
                            if item.details_json:
                                details = json.loads(item.details_json)
                        except:
                            details = {}
                        
                        items_data.append({
                            'product_name': item.product_name,
                            'quantity': item.quantity,
                            'unit_price': item.unit_price,
                            'total_price': item.total_price,
                            'total_bs': 0.0, # No guardado explícitamente en item, se recalculará o ignorará
                            'details': details
                        })
                data["items"] = items_data

                # Cargar pagos si existen (dentro de la sesión)
                payments_data = []
                if hasattr(sale, 'payments') and sale.payments:
                    for pay in sale.payments:
                        payments_data.append({
                            'payment_method': pay.payment_method,
                            'amount_usd': pay.amount_usd,
                            'amount_bs': pay.amount_bs,
                            'exchange_rate': pay.exchange_rate,
                            'reference': pay.reference,
                            'bank': pay.bank,
                            'payment_date': pay.payment_date.strftime("%Y-%m-%d") if pay.payment_date else ""
                        })
                data["payments"] = payments_data

                data["articulo"] = getattr(sale, 'articulo', '') or ''
                data["asesor"] = getattr(sale, 'asesor', '') or ''
                data["cliente"] = getattr(sale, 'cliente', '') or ''
                # Sale stores total in venta_usd; SaleDialog expects precio_unitario + cantidad
                venta_total = float(getattr(sale, 'venta_usd', 0.0) or 0.0)
                data["venta_usd"] = f"{venta_total:.2f}"
                # Preferir precio_unitario guardado; si no existe, calcularlo desde el total y la cantidad
                stored_unit = getattr(sale, 'precio_unitario', None)
                cantidad_stored = float(getattr(sale, 'cantidad', 1.0) or 1.0)
                if stored_unit and float(stored_unit) > 0:
                    data["precio_unitario"] = f"{float(stored_unit):.2f}"
                else:
                    # evitar dividir por cero
                    try:
                        unit = (venta_total / cantidad_stored) if cantidad_stored and cantidad_stored > 0 else venta_total
                    except Exception:
                        unit = venta_total
                    data["precio_unitario"] = f"{unit:.2f}"
                data["cantidad"] = f"{cantidad_stored:.2f}"
                data["forma_pago"] = getattr(sale, 'forma_pago', '') or ''
                data["serial_billete"] = getattr(sale, 'serial_billete', '') or ''
                data["banco"] = getattr(sale, 'banco', '') or ''
                data["referencia"] = getattr(sale, 'referencia', '') or ''
                if getattr(sale, 'fecha_pago', None):
                    try:
                        data["fecha_pago"] = getattr(sale, 'fecha_pago').strftime("%Y-%m-%d")
                    except Exception:
                        data["fecha_pago"] = ""
                data["monto_bs"] = f"{(getattr(sale, 'monto_bs', 0.0) or 0.0):.2f}"
                data["monto_usd"] = f"{(getattr(sale, 'monto_usd_calculado', 0.0) or 0.0):.2f}"
                data["abono_usd"] = f"{(getattr(sale, 'abono_usd', 0.0) or 0.0):.2f}"
                data["iva"] = f"{(getattr(sale, 'iva', 0.0) or 0.0):.2f}"
                data["diseno_usd"] = f"{(getattr(sale, 'diseno_usd', 0.0) or 0.0):.2f}"
                # Reflejar si la venta ya incluye diseño para preseleccionar la casilla.
                # Compatibilidad: si el flag `incluye_diseno` no existe, marcar la casilla
                # cuando `diseno_usd` > 0 (ventas antiguas).
                try:
                    inc_flag = getattr(sale, 'incluye_diseno', None)
                    if inc_flag is None:
                        try:
                            dis_val = float(getattr(sale, 'diseno_usd', 0.0) or 0.0)
                        except Exception:
                            dis_val = 0.0
                        data['incluye_diseno'] = "1" if dis_val > 0.0 else "0"
                    else:
                        data['incluye_diseno'] = "1" if bool(inc_flag) else "0"
                except Exception:
                    data['incluye_diseno'] = "0"
                data["ingresos_usd"] = f"{(getattr(sale, 'ingresos_usd', 0.0) or 0.0):.2f}"
                # Preferir campo de descripción específico, si existe, o las notas
                data["descripcion"] = (getattr(sale, 'descripcion', None) or getattr(sale, 'notes', '') or '')
                data["notas"] = getattr(sale, 'notes', '') or ''
                # If the sale has a stored tasa_bcv use it; otherwise try to fetch rate for the payment date
                stored_rate = getattr(sale, 'tasa_bcv', None)
                if stored_rate and float(stored_rate) > 0:
                    data["tasa_bcv"] = f"{float(stored_rate):.2f}"
                else:
                    # attempt to resolve rate for the payment date
                    try:
                        from ..exchange import get_rate_for_date
                        if getattr(sale, 'fecha_pago', None):
                            dt = getattr(sale, 'fecha_pago')
                            rate_for_date = get_rate_for_date(dt, timeout=1.0)
                            if rate_for_date and float(rate_for_date) > 0:
                                data["tasa_bcv"] = f"{float(rate_for_date):.2f}"
                            else:
                                data["tasa_bcv"] = f"{36.0:.2f}"
                        else:
                            data["tasa_bcv"] = f"{36.0:.2f}"
                    except Exception:
                        data["tasa_bcv"] = f"{36.0:.2f}"
                # Evitar sobrescribir valores que ya pudieron ser extraídos del payload
                try:
                    if not data.get('precio_unitario') or float(str(data.get('precio_unitario') or '0').strip()) == 0.0:
                        data['precio_unitario'] = f"{(getattr(sale, 'precio_unitario', 0.0) or 0.0):.2f}"
                except Exception:
                    data['precio_unitario'] = f"{(getattr(sale, 'precio_unitario', 0.0) or 0.0):.2f}"
                try:
                    if not data.get('precio_unitario_bs') or float(str(data.get('precio_unitario_bs') or '0').strip()) == 0.0:
                        data['precio_unitario_bs'] = f"{(getattr(sale, 'precio_unitario_bs', 0.0) or 0.0):.2f}"
                except Exception:
                    data['precio_unitario_bs'] = f"{(getattr(sale, 'precio_unitario_bs', 0.0) or 0.0):.2f}"
                try:
                    if not data.get('cantidad') or float(str(data.get('cantidad') or '0').strip()) == 0.0:
                        data['cantidad'] = f"{(getattr(sale, 'cantidad', 1.0) or 1.0):.2f}"
                except Exception:
                    data['cantidad'] = f"{(getattr(sale, 'cantidad', 1.0) or 1.0):.2f}"
                try:
                    if not data.get('total_bs') or float(str(data.get('total_bs') or '0').strip()) == 0.0:
                        data['total_bs'] = f"{(getattr(sale, 'total_bs', 0.0) or 0.0):.2f}"
                except Exception:
                    data['total_bs'] = f"{(getattr(sale, 'total_bs', 0.0) or 0.0):.2f}"
                # Cliente ID (para seleccionar el cliente en el diálogo)
                try:
                    if getattr(sale, 'cliente_id', None) is not None:
                        data['cliente_id'] = str(int(getattr(sale, 'cliente_id')))
                except Exception:
                    pass

                # Intentar cargar payload de pedido asociado (si existe) y extraer valores clave
                try:
                    from ..repository import get_order_for_sale
                    from ..repository import get_corporeo_payload_by_sale, get_corporeo_by_sale
                    
                    order = get_order_for_sale(session, sale_id)
                    
                    # Extract order number if available
                    if order and getattr(order, 'order_number', None):
                        data['numero_orden'] = str(order.order_number)
                    elif getattr(sale, 'numero_orden', None):
                        data['numero_orden'] = str(sale.numero_orden)
                        
                    # prefer payload saved in corporeo_payloads (new table)
                    try:
                        cp = get_corporeo_payload_by_sale(session, sale_id)
                        if cp and getattr(cp, 'payload_json', None):
                            try:
                                payload = json.loads(cp.payload_json)
                                # We can't set attr on dlg yet as it's not created, store in data
                                data['_corporeo_payload'] = payload
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # second fallback: corporeo_configs (legacy detailed payloads)
                    if not data.get('_corporeo_payload'):
                        try:
                            cfg = get_corporeo_by_sale(session, sale_id)
                            if cfg and getattr(cfg, 'payload_json', None):
                                payload = json.loads(cfg.payload_json)
                                data['_corporeo_payload'] = payload
                        except Exception:
                            pass
                    if order and getattr(order, 'details_json', None) and not data.get('_corporeo_payload'):
                        try:
                            payload = json.loads(order.details_json)
                            data['_corporeo_payload'] = payload
                            # Extraer descripción y totales del payload para prellenar el diálogo
                            try:
                                meta = payload.get('meta', {}) if isinstance(payload, dict) else {}
                                # Descripción preferida desde payload
                                descr_text = None
                                if isinstance(payload, dict):
                                    descr_text = payload.get('descripcion_text') or meta.get('descripcion') or meta.get('descripcion_text')
                                data['descripcion'] = (descr_text or getattr(sale, 'notes', '') or '')

                                # Determinar precio unitario: preferir meta.precio_unitario o item.precio_unitario.
                                # Si sólo hay totals.total_usd, ese valor es el total de la configuración; calcular unitario dividiendo por cantidad.
                                precio = None
                                if isinstance(meta, dict):
                                    meta_precio = meta.get('precio_unitario')
                                    if meta_precio is not None:
                                        try:
                                            precio = float(meta_precio)
                                        except Exception:
                                            precio = None
                                if precio is None and isinstance(payload, dict):
                                    items = payload.get('items') or []
                                    if items and isinstance(items, list) and items[0].get('precio_unitario') is not None:
                                        try:
                                            precio = float(items[0].get('precio_unitario'))
                                        except Exception:
                                            precio = None
                                # Si sólo tenemos totals.total_usd, calcular unitario = total_usd / cantidad
                                if precio is None and isinstance(payload, dict):
                                    try:
                                        totals = payload.get('totals') or {}
                                        total_usd = totals.get('total_usd') if isinstance(totals, dict) else None
                                        if total_usd is not None:
                                            # determinar cantidad desde items si existe
                                            qty = 1.0
                                            items = payload.get('items')
                                            if isinstance(items, list) and len(items) > 0:
                                                try:
                                                    item0 = items[0] or {}
                                                    qty = float(item0.get('cantidad') or 1.0)
                                                except Exception:
                                                    qty = 1.0
                                            precio = float(total_usd) / (qty if qty and qty > 0 else 1.0)
                                    except Exception:
                                        precio = None
                                if precio is None:
                                    # Evitar usar el total de la venta como precio unitario.
                                    # Como último recurso, dividir venta_total por la cantidad almacenada
                                    # para obtener un unitario aproximado. Si falla, usar venta_usd entero.
                                    try:
                                        venta_total_val = float(getattr(sale, 'venta_usd', 0.0) or 0.0)
                                        qty_fallback = 1.0
                                        try:
                                            qty_fallback = float(getattr(sale, 'cantidad', 1.0) or 1.0)
                                        except Exception:
                                            qty_fallback = 1.0
                                        precio = (venta_total_val / (qty_fallback if qty_fallback and qty_fallback > 0 else 1.0))
                                    except Exception:
                                        precio = float(getattr(sale, 'venta_usd', 0.0) or 0.0)
                                data['precio_unitario'] = f"{precio:.2f}"

                                # Cantidad: items[0].cantidad or sale cantidad fallback 1
                                cantidad_val = 1.0
                                try:
                                    items = payload.get('items') if isinstance(payload, dict) else None
                                    if isinstance(items, list) and len(items) > 0:
                                        try:
                                            item0 = items[0] or {}
                                            cantidad_val = float(item0.get('cantidad') or 1.0)
                                        except Exception:
                                            cantidad_val = 1.0
                                except Exception:
                                    cantidad_val = 1.0
                                data['cantidad'] = f"{cantidad_val:.2f}"

                                # Total Bs: desde payload.totals.total_bs o sale.monto_bs
                                try:
                                    totals = payload.get('totals') or {}
                                    total_bs_raw = totals.get('total_bs') if isinstance(totals, dict) else None
                                    if total_bs_raw is not None:
                                        total_bs_val = float(total_bs_raw)
                                    else:
                                        total_bs_val = float(getattr(sale, 'monto_bs', 0.0) or 0.0)
                                except Exception:
                                    total_bs_val = float(getattr(sale, 'monto_bs', 0.0) or 0.0)
                                data['total_bs'] = f"{total_bs_val:.2f}"

                                # Cliente: preferir meta.cliente o meta.cliente_id
                                try:
                                    cliente_meta = meta.get('cliente') if isinstance(meta, dict) else None
                                    cliente_id_meta = meta.get('cliente_id') if isinstance(meta, dict) else None
                                    if cliente_meta:
                                        data['cliente'] = cliente_meta
                                    elif cliente_id_meta:
                                        # try to set by id; SaleDialog.set_data only sets by text, so try to find label
                                        data['cliente_id'] = str(cliente_id_meta)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    pass

                # Si no tenemos cliente_id explícito en sale, intentar extraerlo desde sale.details_json
                try:
                    if 'cliente_id' not in data or not data.get('cliente_id'):
                        if getattr(sale, 'details_json', None):
                            try:
                                parsed = json.loads(getattr(sale, 'details_json'))
                                meta = parsed.get('meta') if isinstance(parsed, dict) else {}
                                if isinstance(meta, dict):
                                    cid = meta.get('cliente_id') or meta.get('clienteId')
                                    cname = meta.get('cliente')
                                    if cid:
                                        data['cliente_id'] = str(int(cid))
                                    elif cname and not data.get('cliente'):
                                        data['cliente'] = str(cname)
                            except Exception:
                                pass
                except Exception:
                    pass

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar la venta: {str(e)}")
            return

        dlg = InvoiceSaleDialog(parent=self, session_factory=self._session_factory)
        # expose editing context so downstream code can know the sale being edited
        try:
            setattr(dlg, '_editing_sale_id', int(sale_id))
            if data.get('_corporeo_payload'):
                setattr(dlg, '_corporeo_payload', data.pop('_corporeo_payload'))
        except Exception:
            pass

        # Establecer datos en el diálogo y ejecutarlo
        try:
            dlg.set_data(data)
        except Exception:
            pass

        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                new_data = dlg.get_data()
                if new_data:
                    # Preparar datos para update_sale
                    update_kwargs = {
                        'articulo': new_data.get('articulo'),
                        'asesor': new_data.get('asesor'),
                        'venta_usd': float(new_data.get('venta_usd') or 0.0),
                        'forma_pago': new_data.get('forma_pago'),
                        'serial_billete': new_data.get('serial_billete'),
                        'banco': new_data.get('banco'),
                        'referencia': new_data.get('referencia'),
                        'monto_bs': float(new_data.get('monto_bs') or 0.0),
                        'monto_usd_calculado': float(new_data.get('monto_usd') or 0.0),
                        'abono_usd': float(new_data.get('abono_usd') or 0.0),
                        'iva': float(new_data.get('iva') or 0.0),
                        'diseno_usd': float(new_data.get('diseno_usd') or 0.0),
                        'ingresos_usd': float(new_data.get('ingresos_usd') or 0.0),
                        'notes': new_data.get('notas'),
                        'descripcion': new_data.get('descripcion'),
                        'cantidad': float(new_data.get('cantidad') or 1.0),
                        'precio_unitario': float(new_data.get('precio_unitario') or 0.0),
                        'total_bs': float(new_data.get('total_bs') or 0.0),
                        'incluye_diseno': (str(new_data.get('incluye_diseno') or '').strip() in ("1", "true", "True")),
                        'subtotal_usd': float(new_data.get('subtotal_usd') or 0.0),
                        'total_usd': float(new_data.get('total_usd') or 0.0),
                        'tasa_bcv': float(new_data.get('tasa_bcv') or 0.0),
                        'items': new_data.get('items'),
                        'payments': new_data.get('payments'),
                    }
                    
                    # Fecha pago
                    fp_str = new_data.get('fecha_pago')
                    if fp_str:
                        try:
                            update_kwargs['fecha_pago'] = datetime.strptime(fp_str, "%Y-%m-%d")
                        except: pass

                    # Cliente
                    if new_data.get('cliente_id'):
                        update_kwargs['cliente_id'] = int(new_data.get('cliente_id'))
                    if new_data.get('cliente'):
                        update_kwargs['cliente'] = new_data.get('cliente')

                    with self._session_factory() as session:
                        if update_sale(session, int(sale_id), **update_kwargs):
                            # Si el diálogo actualizó o creó un payload en dlg._corporeo_payload, intentar persistirlo
                            try:
                                if getattr(dlg, '_corporeo_payload', None):
                                    from ..repository import get_order_for_sale, update_order
                                    existing = get_order_for_sale(session, sale_id)
                                    if existing:
                                        try:
                                            update_order(session, int(existing.id), details_json=json.dumps(dlg._corporeo_payload, ensure_ascii=False))
                                        except Exception:
                                            pass
                                    else:
                                        # crear pedido asociado
                                        try:
                                            from ..repository import add_order
                                            order_num = getattr(sale, 'numero_orden', None)
                                            add_order(session, sale_id=sale_id, product_name=(getattr(sale, 'articulo', '') or ''), details_json=json.dumps(dlg._corporeo_payload, ensure_ascii=False), status='NUEVO', order_number=order_num)
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                            
                            QMessageBox.information(self, "Éxito", "Venta actualizada correctamente.")
                        else:
                            QMessageBox.warning(self, "Error", "No se pudo actualizar la venta.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al guardar cambios: {str(e)}")

            self._load_sales()
                
    def _on_delete_sale(self):
        """Eliminar venta seleccionada."""
        sale_id = self._get_selected_sale_id()
        if not sale_id:
            return
            
        reply = QMessageBox.question(
            self, 
            "Confirmar Eliminación",
            "¿Está seguro de que desea eliminar esta venta?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            with self._session_factory() as session:
                if delete_sale_by_id(session, sale_id):
                    self._load_sales()
                    QMessageBox.information(self, "Éxito", "Venta eliminada correctamente.")
                else:
                    QMessageBox.warning(self, "Error", "No se pudo eliminar la venta.")


class LegacySaleDialog(QDialog):
    """Diálogo LEGADO para crear o editar una venta (se mantiene para edición)."""
    
    def __init__(self, session_factory: sessionmaker, sale_id: int | None = None, parent=None):
        super().__init__(parent)
        self._session_factory = session_factory
        self._sale_id = sale_id
        self._sale = None
        
        if sale_id:
            self.setWindowTitle("Editar Venta")
            self._load_sale()
        else:
            self.setWindowTitle("Nueva Venta")
            
        self._setup_ui()
        self._populate_form()
        
    def _load_sale(self):
        """Cargar la venta para edición."""
        if self._sale_id is not None:
            with self._session_factory() as session:
                self._sale = get_sale_by_id(session, self._sale_id)
            
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Crear formulario
        form_layout = QFormLayout()
        
        # Campos básicos
        basic_group = QGroupBox("Información Básica")
        basic_layout = QFormLayout(basic_group)
        
        self.articulo_edit = QLineEdit()
        basic_layout.addRow("Artículo:", self.articulo_edit)
        
        self.asesor_edit = QLineEdit()
        basic_layout.addRow("Asesor:", self.asesor_edit)
        
        self.venta_usd_spin = QDoubleSpinBox()
        self.venta_usd_spin.setRange(0, 999999)
        self.venta_usd_spin.setDecimals(2)
        self.venta_usd_spin.setPrefix("$ ")
        basic_layout.addRow("Venta $ (Total):", self.venta_usd_spin)
        
        layout.addWidget(basic_group)
        
        # Campos de pago
        payment_group = QGroupBox("Información de Pago")
        payment_layout = QFormLayout(payment_group)
        
        self.forma_pago_combo = QComboBox()
        self.forma_pago_combo.addItems([
            "", "Efectivo $", "Zelle", "Efectivo Bs", "Pago Móvil", "Transferencia Bs", "Transferencia $"
        ])
        payment_layout.addRow("Forma de Pago:", self.forma_pago_combo)
        
        self.serial_billete_edit = QLineEdit()
        payment_layout.addRow("Serial Billete:", self.serial_billete_edit)
        
        self.banco_edit = QLineEdit()
        payment_layout.addRow("Banco:", self.banco_edit)
        
        self.referencia_edit = QLineEdit()
        payment_layout.addRow("Referencia:", self.referencia_edit)
        
        self.fecha_pago_edit = QDateEdit()
        self.fecha_pago_edit.setDate(QDate.currentDate())
        self.fecha_pago_edit.setCalendarPopup(True)
        payment_layout.addRow("Fecha de Pago:", self.fecha_pago_edit)
        
        layout.addWidget(payment_group)
        
        # Campos de montos
        amounts_group = QGroupBox("Montos y Cálculos")
        amounts_layout = QFormLayout(amounts_group)
        
        self.monto_bs_spin = QDoubleSpinBox()
        self.monto_bs_spin.setRange(0, 999999999)
        self.monto_bs_spin.setDecimals(2)
        self.monto_bs_spin.setPrefix("Bs. ")
        amounts_layout.addRow("Monto Bs.D:", self.monto_bs_spin)
        
        self.monto_usd_calculado_spin = QDoubleSpinBox()
        self.monto_usd_calculado_spin.setRange(0, 999999)
        self.monto_usd_calculado_spin.setDecimals(2)
        self.monto_usd_calculado_spin.setPrefix("$ ")
        self.monto_usd_calculado_spin.setReadOnly(True)  # Campo calculado automáticamente
        amounts_layout.addRow("Monto $ Calculado:", self.monto_usd_calculado_spin)
        
        self.abono_usd_spin = QDoubleSpinBox()
        self.abono_usd_spin.setRange(0, 999999)
        self.abono_usd_spin.setDecimals(2)
        self.abono_usd_spin.setPrefix("$ ")
        amounts_layout.addRow("Abono $:", self.abono_usd_spin)
        
        self.iva_spin = QDoubleSpinBox()
        self.iva_spin.setRange(0, 999999)
        self.iva_spin.setDecimals(2)
        self.iva_spin.setPrefix("$ ")
        amounts_layout.addRow("IVA:", self.iva_spin)
        
        self.diseno_usd_spin = QDoubleSpinBox()
        self.diseno_usd_spin.setRange(0, 999999)
        self.diseno_usd_spin.setDecimals(2)
        self.diseno_usd_spin.setPrefix("$ ")
        amounts_layout.addRow("Diseño $:", self.diseno_usd_spin)
        
        self.ingresos_usd_spin = QDoubleSpinBox()
        self.ingresos_usd_spin.setRange(0, 999999)
        self.ingresos_usd_spin.setDecimals(2)
        self.ingresos_usd_spin.setPrefix("$ ")
        amounts_layout.addRow("Ingresos $:", self.ingresos_usd_spin)
        
        layout.addWidget(amounts_group)
        
        # Notas
        notes_group = QGroupBox("Notas")
        notes_layout = QVBoxLayout(notes_group)
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        notes_layout.addWidget(self.notes_edit)
        layout.addWidget(notes_group)
        
        # Botones
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_sale)
        button_box.rejected.connect(self.reject)
        # Add a Configure button for corpóreo editing when editing existing sales
        try:
            self.btn_configurar = QPushButton("Configurar Corpóreo...", self)
            self.btn_configurar.clicked.connect(self._on_configurar_corporeo_for_edit)
            button_box.addButton(self.btn_configurar, QDialogButtonBox.ButtonRole.ActionRole)
        except Exception:
            pass
        layout.addWidget(button_box)
        
        # Variables para controlar cálculos automáticos
        self._last_monto_usd_calculado = 0.0
        
        # Conectar señales para cálculos automáticos
        self.forma_pago_combo.currentTextChanged.connect(self._calculate_ingresos)
        self.abono_usd_spin.valueChanged.connect(self._calculate_ingresos)
        self.monto_bs_spin.valueChanged.connect(self._calculate_monto_usd_and_abono)
        
    def _calculate_ingresos(self):
        """Calcular automáticamente los ingresos $ basado en la forma de pago y el abono."""
        forma_pago = self.forma_pago_combo.currentText()
        abono_usd = self.abono_usd_spin.value()
        
        if forma_pago in ["Efectivo $", "Zelle"]:
            # Solo para efectivo $ o Zelle, los ingresos son igual al abono
            self.ingresos_usd_spin.setValue(abono_usd)
        else:
            # Para todas las demás formas de pago, limpiar el campo
            # El usuario puede llenarlo manualmente si aplica
            if not self._sale:  # Solo limpiar si es venta nueva
                self.ingresos_usd_spin.setValue(0.0)
        
    def _calculate_monto_usd_and_abono(self):
        """Calcular el monto en USD basado en el monto en Bs y agregarlo al abono."""
        monto_bs = self.monto_bs_spin.value()
        
        if monto_bs > 0:
            # Obtener la tasa BCV actual
            from ..exchange import get_bcv_rate
            try:
                tasa_bcv = get_bcv_rate()
                if tasa_bcv and tasa_bcv > 0:
                    # Calcular monto en USD
                    monto_usd_calculado = monto_bs / tasa_bcv
                    self.monto_usd_calculado_spin.setValue(monto_usd_calculado)
                    
                    # Restar el valor anterior y sumar el nuevo al abono
                    abono_actual = self.abono_usd_spin.value()
                    nuevo_abono = abono_actual - self._last_monto_usd_calculado + monto_usd_calculado
                    self.abono_usd_spin.setValue(nuevo_abono)
                    
                    # Actualizar el valor anterior
                    self._last_monto_usd_calculado = monto_usd_calculado
                    
                    # Recalcular ingresos (solo si aplica según forma de pago)
                    self._calculate_ingresos()
                else:
                    self.monto_usd_calculado_spin.setValue(0.0)
                    # Restar el valor anterior si no se puede calcular
                    abono_actual = self.abono_usd_spin.value()
                    self.abono_usd_spin.setValue(abono_actual - self._last_monto_usd_calculado)
                    self._last_monto_usd_calculado = 0.0
            except Exception:
                self.monto_usd_calculado_spin.setValue(0.0)
                # Restar el valor anterior si hay error
                abono_actual = self.abono_usd_spin.value()
                self.abono_usd_spin.setValue(abono_actual - self._last_monto_usd_calculado)
                self._last_monto_usd_calculado = 0.0
        else:
            # Si no hay monto en Bs, limpiar el campo calculado y restar del abono
            self.monto_usd_calculado_spin.setValue(0.0)
            abono_actual = self.abono_usd_spin.value()
            self.abono_usd_spin.setValue(abono_actual - self._last_monto_usd_calculado)
            self._last_monto_usd_calculado = 0.0
        
    def _populate_form(self):
        """Poblar el formulario con los datos de la venta (si estamos editando)."""
        if self._sale:
            self.articulo_edit.setText(self._sale.articulo or "")
            self.asesor_edit.setText(self._sale.asesor or "")
            self.venta_usd_spin.setValue(self._sale.venta_usd or 0.0)
            
            if self._sale.forma_pago:
                index = self.forma_pago_combo.findText(self._sale.forma_pago)
                if index >= 0:
                    self.forma_pago_combo.setCurrentIndex(index)
                    
            self.serial_billete_edit.setText(self._sale.serial_billete or "")
            self.banco_edit.setText(self._sale.banco or "")
            self.referencia_edit.setText(self._sale.referencia or "")
            
            if self._sale.fecha_pago:
                self.fecha_pago_edit.setDate(QDate.fromString(
                    self._sale.fecha_pago.strftime("%Y-%m-%d"), "yyyy-MM-dd"
                ))
                
            self.monto_bs_spin.setValue(self._sale.monto_bs or 0.0)
            monto_usd_calc = self._sale.monto_usd_calculado or 0.0
            self.monto_usd_calculado_spin.setValue(monto_usd_calc)
            self._last_monto_usd_calculado = monto_usd_calc  # Inicializar con valor existente
            self.abono_usd_spin.setValue(self._sale.abono_usd or 0.0)
            self.iva_spin.setValue(self._sale.iva or 0.0)
            self.diseno_usd_spin.setValue(self._sale.diseno_usd or 0.0)
            self.ingresos_usd_spin.setValue(self._sale.ingresos_usd or 0.0)
            self.notes_edit.setPlainText(self._sale.notes or "")
        else:
            # Para nueva venta, establecer el asesor como usuario actual
            try:
                main_window = self.parent()
                while main_window and not hasattr(main_window, '_current_user'):
                    main_window = main_window.parent()
                if main_window and hasattr(main_window, '_current_user'):
                    current_user = getattr(main_window, '_current_user', '')
                    self.asesor_edit.setText(current_user)
            except:
                pass
                
    def _save_sale(self):
        """Guardar la venta."""
        # Validar campos requeridos
        if not self.articulo_edit.text().strip():
            QMessageBox.warning(self, "Error", "El artículo es requerido.")
            return
            
        if not self.asesor_edit.text().strip():
            QMessageBox.warning(self, "Error", "El asesor es requerido.")
            return
            
        if self.venta_usd_spin.value() <= 0:
            QMessageBox.warning(self, "Error", "El monto de venta debe ser mayor a cero.")
            return
            
        try:
            # Preparar datos
            data = {
                'articulo': self.articulo_edit.text().strip(),
                'asesor': self.asesor_edit.text().strip(),
                'venta_usd': self.venta_usd_spin.value(),
                'forma_pago': self.forma_pago_combo.currentText() or None,
                'serial_billete': self.serial_billete_edit.text().strip() or None,
                'banco': self.banco_edit.text().strip() or None,
                'referencia': self.referencia_edit.text().strip() or None,
                'fecha_pago': self.fecha_pago_edit.date().toPython() if self.fecha_pago_edit.date().isValid() else None,
                'monto_bs': self.monto_bs_spin.value() or None,
                'monto_usd_calculado': self.monto_usd_calculado_spin.value() or None,
                'abono_usd': self.abono_usd_spin.value() or None,
                'iva': self.iva_spin.value() or None,
                'diseno_usd': self.diseno_usd_spin.value() or None,
                'ingresos_usd': self.ingresos_usd_spin.value() or None,
                'notes': self.notes_edit.toPlainText().strip() or None,
            }
            
            with self._session_factory() as session:
                if self._sale_id:
                    # Actualizar venta existente
                    if update_sale(session, self._sale_id, **data):
                        self.accept()
                    else:
                        QMessageBox.warning(self, "Error", "No se pudo actualizar la venta.")
                else:
                    # Crear nueva venta
                    created = add_sale(session, **data)
                    # If there is a pending corporeo payload attached to this dialog, persist it as an Order
                    try:
                        payload = getattr(self, '_corporeo_payload', None)
                        if payload and created is not None:
                            # create order using repository.add_order helper
                            from ..repository import add_order
                            details_json = json.dumps(payload, ensure_ascii=False)
                            order_num = getattr(created, 'numero_orden', None)
                            add_order(session, sale_id=int(created.id), product_name=(getattr(created, 'articulo', '') or ''), details_json=details_json, status='NUEVO', order_number=order_num)
                    except Exception:
                        pass
                    self.accept()
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar la venta: {str(e)}")

    def _on_configurar_corporeo_for_edit(self) -> None:
        """Abrir el configurador Corpóreo para la venta en edición y persistir payload en orders."""
        # Only available when editing an existing sale
        if not getattr(self, '_sale_id', None):
            QMessageBox.information(self, "Configurar", "Edite la venta primero o cree la venta antes de configurar el corpóreo.")
            return
        try:
            from .corporeo_dialog import CorporeoDialog
            from ..repository import get_order_for_sale, update_order

            # Load existing order payload if any; reserve a draft order if none exists
            sale_id_val = int(self._sale_id) if self._sale_id is not None else None
            initial_payload = None
            order_id = None
            with self._session_factory() as session:
                if sale_id_val is not None:
                    order = get_order_for_sale(session, sale_id_val)
                    if order and order.details_json:
                        try:
                            initial_payload = json.loads(order.details_json)
                            order_id = int(order.id)
                        except Exception:
                            initial_payload = None
                    # Do NOT create a draft order automatically. Leave order_id as None
                    # if there is no existing order. Orders should be created explicitly
                    # when the sale is saved so they share the official sale order_number.
                    if order is None:
                        order_id = None
                # try to resolve corpóreo type_id from EAV types (reuse same session)
                type_id = None
                try:
                    from ..repository import eav_list_types, ensure_corporeo_eav
                    types = eav_list_types(session)
                    for t in types:
                        key = (getattr(t, 'key', '') or '').lower()
                        name = (getattr(t, 'name', '') or '').lower()
                        if 'corp' in key or 'corp' in name:
                            type_id = int(getattr(t, 'id'))
                            break
                    if not isinstance(type_id, int):
                        try:
                            type_id = ensure_corporeo_eav(session)
                        except Exception:
                            type_id = None
                except Exception:
                    type_id = None

            # Open dialog with payload if present
            sf = self._session_factory
            dlg = CorporeoDialog(sf, type_id=(type_id or 0), product_id=None, initial_payload=initial_payload)
            if dlg.exec():
                # Get accepted payload and persist it into order (create order if missing)
                payload = getattr(dlg, 'accepted_data', None) or getattr(dlg, '_corporeo_payload', None)
                if not payload:
                    return
                # Save into DB: update existing order or create a new one
                with self._session_factory() as session:
                    if order_id:
                        # update existing order
                        try:
                            update_order(session, order_id, details_json=json.dumps(payload, ensure_ascii=False))
                        except Exception:
                            pass
                    else:
                        # create new order only if we have a valid sale_id_val
                        try:
                            if sale_id_val is not None:
                                from ..repository import add_order
                                sale_art = (getattr(self._sale, 'articulo', '') or '')
                                order_num = getattr(self._sale, 'numero_orden', None)
                                add_order(session, sale_id=sale_id_val, product_name=sale_art, details_json=json.dumps(payload, ensure_ascii=False), status='NUEVO', order_number=order_num)
                        except Exception:
                            pass
                # Keep a copy in the dialog instance for later use
                try:
                    self._corporeo_payload = payload
                except Exception:
                    pass
                QMessageBox.information(self, "Configurar", "Configuración del corpóreo guardada.")
        except Exception as e:
            QMessageBox.critical(self, "Configurar", f"Error al abrir el configurador:\n{e}")
