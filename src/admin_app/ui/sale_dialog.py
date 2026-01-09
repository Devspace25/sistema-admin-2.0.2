from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QVBoxLayout, QHBoxLayout, QWidget,
    QLineEdit, QComboBox, QDateEdit, QLabel, QGroupBox, QGridLayout, QDoubleSpinBox, QCheckBox,
    QScrollArea, QFrame, QAbstractSpinBox, QPushButton, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QGuiApplication, QPixmap, QDoubleValidator
from datetime import date as Date
from sqlalchemy.orm import sessionmaker
import unicodedata

from ..exchange import get_bcv_rate, get_rate_for_date
from ..repository import list_customers, add_customers, list_configurable_products, eav_list_types, generate_order_number
from ..db import make_engine, make_session_factory
from ..models import Customer, User, Role, UserRole
from .customer_dialog import CustomerDialog
from .login_dialog import LoginDialog
import json


class MoneySpinBox(QDoubleSpinBox):
    """SpinBox que permite borrar todo el contenido y lo interpreta como 0.00 al perder el foco."""
    def validate(self, text: str, pos: int) -> object:
        if not text:
            return QDoubleValidator.State.Intermediate, text, pos
        return super().validate(text, pos)

    def valueFromText(self, text: str) -> float:
        if not text:
            return 0.0
        return super().valueFromText(text)

    def fixup(self, input: str) -> str:
        if not input:
            return ""
        return super().fixup(input)


class SaleDialog(QDialog):
    """Diálogo de Nueva Venta con formato de factura y campos decimales (2 cifras)."""

    def __init__(self, parent=None, session_factory: sessionmaker | None = None, current_user: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Factura de Venta")
        self._current_user_override = current_user
        # Tamaño inicial adaptado a la pantalla
        try:
            screen = QGuiApplication.primaryScreen()
            if screen:
                avail = screen.availableGeometry()
                w = max(640, int(avail.width() * 0.55))
                h = max(540, int(avail.height() * 0.7))
                self.resize(w, h)
            else:
                self.resize(900, 780)
        except Exception:
            self.resize(900, 780)
        self.setSizeGripEnabled(True)
        self._session_factory = session_factory
        self.discount_authorized = False # Estado de autorización de descuento
        
        # Atributos para productos corpóreos
        self._precio_corporeo_tasa_bcv = 0.0  # Precio en Bs para métodos de pago en Bs
        self._is_corporeo_product = False  # Flag para identificar si es producto corpóreo

        # Aplicar estilo: dejamos que el tema global (QSS) maneje colores; evitamos estilos inline fuertes
        self._apply_invoice_style()

        # Usuario/asesor
        self._seller: str | None = self._resolve_current_user() or "admin"

        # Layout raíz
        root = QVBoxLayout(self)

        # Encabezado tipo factura
        self._create_invoice_header(root)

        # Cuerpo en contenedor con scroll y diseño adaptable
        self._create_invoice_body(root)

        # Poblar listas de clientes y productos
        try:
            self._populate_lookups()
            self._load_order_number()
        except Exception:
            pass

        # Botonera
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        try:
            ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
            if ok_btn:
                ok_btn.setProperty("accent", "primary")
        except Exception:
            pass
        root.addWidget(btns)

        # Señales y datos iniciales
        self._setup_signals()
        self._load_bcv_rate()
        self._update_totals()

    def accept(self) -> None:
        """Validar antes de guardar."""
        # 1. Validar Cliente
        client_val = ""
        if hasattr(self, 'edt_cliente'):
            # edt_cliente is a QComboBox, use currentText()
            client_val = self.edt_cliente.currentText().strip()
        
        if not client_val or client_val.startswith("----"):
            QMessageBox.warning(self, "Validación", "El campo Cliente es requerido para procesar la venta.")
            if hasattr(self, 'edt_cliente'): self.edt_cliente.setFocus()
            return

        # 2. Validar Productos
        has_products = False
        if hasattr(self, 'tbl_product_lines') and self.tbl_product_lines.rowCount() > 0:
            has_products = True
        elif hasattr(self, 'tbl_items') and self.tbl_items.rowCount() > 0:
            has_products = True
            
        if not has_products:
            QMessageBox.warning(self, "Validación", "Debe agregar al menos un producto a la venta.")
            return

        # 3. Validar Pagos
        if hasattr(self, 'tbl_payments'):
            if self.tbl_payments.rowCount() == 0:
                QMessageBox.warning(self, "Validación", "Debe agregar al menos un método de pago.")
                return

            for r in range(self.tbl_payments.rowCount()):
                cmb_method = self.tbl_payments.cellWidget(r, 0)
                if not cmb_method: continue
                
                method = cmb_method.currentText()
                if not method or method.startswith('----'):
                    continue # Ignore empty lines or force selection? Usually ignore or warn.
                             # If lines exist but nothing selected, maybe warn?
                             # Let's assume ignore empty selection rows usually.
                
                # Retrieve Widgets
                w_bank = self.tbl_payments.cellWidget(r, 3) 
                w_ref = self.tbl_payments.cellWidget(r, 4)
                
                # A. Efectivo USD -> Serial Requerido
                if method == "Efectivo USD":
                    serial = ""
                    if isinstance(w_bank, QLineEdit): serial = w_bank.text().strip()
                    elif isinstance(w_bank, QComboBox): serial = w_bank.currentText().strip()
                    
                    if not serial:
                        QMessageBox.warning(self, "Validación", "El Serial del billete es requerido para pagos en Efectivo USD.")
                        w_bank.setFocus()
                        return

                # B. Pago Móvil / Transferencia -> Banco y Referencia Requeridos
                # Assuming this applies to the methods we converted to ComboBox logic
                is_bank_method = method in ["Pago móvil", "Transferencia Bs.D", "Zelle", "Banesco Panamá", "Punto de Venta"]
                
                if is_bank_method:
                    # Validate Bank Selection
                    bank_val = ""
                    if isinstance(w_bank, QComboBox):
                        bank_val = w_bank.currentText()
                        if bank_val.startswith("----"): bank_val = ""
                    elif isinstance(w_bank, QLineEdit):
                        bank_val = w_bank.text().strip()
                        
                    if not bank_val:
                        QMessageBox.warning(self, "Validación", f"Debe seleccionar un Banco para el método '{method}'.")
                        if isinstance(w_bank, QComboBox): w_bank.showPopup()
                        w_bank.setFocus()
                        return

                    # Validate Reference Length
                    ref_val = w_ref.text().strip() if w_ref else ""
                    if len(ref_val) < 4:
                        QMessageBox.warning(self, "Validación", f"La Referencia para '{method}' debe tener al menos 4 dígitos.")
                        if w_ref: w_ref.setFocus()
                        return

        super().accept()

    # --- Construcción de UI ---
    def _create_invoice_header(self, layout: QVBoxLayout) -> None:
        from datetime import datetime

        header = QWidget(self)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 10, 12, 6)
        hl.setSpacing(8)

        # Logo Centrado
        logo_lbl = QLabel(self)
        try:
            pix = QPixmap("assets/img/logo.png")
            if not pix.isNull():
                # Logo un poco más grande si va solo
                logo_lbl.setPixmap(pix.scaledToHeight(48, Qt.TransformationMode.SmoothTransformation))
        except Exception:
            pass
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Fecha y Orden a la derecha
        right = QVBoxLayout()
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        # Etiquetas eliminadas a petición del usuario
        # today = datetime.now().strftime("%d/%m/%Y")
        # lbl_date = QLabel(f"Fecha: {today}", self)
        # lbl_date.setAlignment(Qt.AlignmentFlag.AlignRight)
        # lbl_order = QLabel("Orden: Auto", self)
        # lbl_order.setAlignment(Qt.AlignmentFlag.AlignRight)
        # right.addWidget(lbl_date)
        # right.addWidget(lbl_order)

        # Layout: [Spacer] [Logo] [Spacer] [Right Info]
        # Para que el logo quede realmente centrado en la ventana, es difícil si hay contenido a la derecha.
        # Usaremos un layout distribuido:
        
        # Opción A: Logo en el centro del layout, info a la derecha.
        hl.addStretch(1)
        hl.addWidget(logo_lbl)
        hl.addStretch(1)
        hl.addLayout(right)

        layout.addWidget(header)

        sep = QWidget(self)
        sep.setFixedHeight(1)
        layout.addWidget(sep)

    def _create_invoice_body(self, layout: QVBoxLayout) -> None:
        # Widgets base
        self._create_widgets()

        # Contenedor principal con scroll
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._body_container = QWidget(self)
        self._scroll.setWidget(self._body_container)
        layout.addWidget(self._scroll)
        # Layout principal (columna única)
        main_col = QVBoxLayout(self._body_container)
        main_col.setContentsMargins(15, 10, 15, 10)
        main_col.setSpacing(14)

        # === 1. Top Section (Datos Venta + Datos Cliente) ===
        top_container = QWidget(self)
        top_layout = QHBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        # 1.1 Datos de la Venta
        self.grp_datos_venta = QGroupBox("Datos de la Venta", self)
        grid_venta = QGridLayout()
        
        # Row 0
        grid_venta.addWidget(QLabel("Fecha:", self), 0, 0)
        from datetime import datetime
        today = datetime.now().strftime("%d/%m/%Y")
        grid_venta.addWidget(QLabel(today, self), 0, 1)
        
        grid_venta.addWidget(QLabel("Orden:", self), 0, 2)
        self.lbl_orden = QLabel("...", self)
        self.lbl_orden.setStyleSheet("font-weight: bold; color: #2196F3;")
        grid_venta.addWidget(self.lbl_orden, 0, 3)
        
        # Row 1
        grid_venta.addWidget(QLabel("Fecha Pago:", self), 1, 0)
        grid_venta.addWidget(self.edt_fecha_pago, 1, 1)
        
        grid_venta.addWidget(QLabel("Asesor:", self), 1, 2)
        grid_venta.addWidget(self.lbl_asesor, 1, 3)
        
        self.grp_datos_venta.setLayout(grid_venta)
        top_layout.addWidget(self.grp_datos_venta, 1)

        # 1.2 Datos del Cliente
        self.grp_datos_cliente = QGroupBox("Datos del Cliente", self)
        grid_cliente = QGridLayout()
        
        # Row 0
        grid_cliente.addWidget(QLabel("Cliente:", self), 0, 0)
        grid_cliente.addWidget(self.edt_cliente, 0, 1)
        self.btn_nuevo_cliente = QPushButton("Nuevo", self)
        self.btn_nuevo_cliente.setMaximumWidth(60)
        grid_cliente.addWidget(self.btn_nuevo_cliente, 0, 2)
        
        # Row 1 (Details)
        self._customer_details_widget = QWidget(self)
        details_grid = QGridLayout(self._customer_details_widget)
        details_grid.setContentsMargins(0, 0, 0, 0)
        
        details_grid.addWidget(QLabel("Doc:", self), 0, 0)
        self.lbl_cli_doc = QLabel("—", self)
        details_grid.addWidget(self.lbl_cli_doc, 0, 1)
        
        details_grid.addWidget(QLabel("Tel:", self), 0, 2)
        self.lbl_cli_phone = QLabel("—", self)
        details_grid.addWidget(self.lbl_cli_phone, 0, 3)
        
        details_grid.addWidget(QLabel("Dir:", self), 1, 0)
        self.lbl_cli_addr = QLabel("—", self)
        details_grid.addWidget(self.lbl_cli_addr, 1, 1, 1, 3)
        
        details_grid.addWidget(QLabel("Email:", self), 2, 0)
        self.lbl_cli_email = QLabel("—", self)
        details_grid.addWidget(self.lbl_cli_email, 2, 1, 1, 3)
        
        grid_cliente.addWidget(self._customer_details_widget, 1, 0, 1, 3)
        
        self.grp_datos_cliente.setLayout(grid_cliente)
        top_layout.addWidget(self.grp_datos_cliente, 1)
        
        main_col.addWidget(top_container)

        # === 2. Líneas de Productos ===
        self._create_product_lines_section(main_col)

        # === 3. Extras (MOVIDO AQUÍ) ===
        self.grp_extras = QGroupBox("Extras", self)
        grid_extras = QGridLayout()
        
        # Row 0: Diseño
        grid_extras.addWidget(QLabel("Diseño USD:", self), 0, 0)
        self.chk_incluye_diseno = QCheckBox("Incluir", self)
        grid_extras.addWidget(self.chk_incluye_diseno, 0, 1)
        grid_extras.addWidget(QLabel("Precio $:", self), 0, 2)
        grid_extras.addWidget(self.edt_diseno, 0, 3)
        
        # Row 1: Instalación (New)
        grid_extras.addWidget(QLabel("INST. $:", self), 1, 0)
        self.chk_incluye_inst = QCheckBox("Incluir", self)
        grid_extras.addWidget(self.chk_incluye_inst, 1, 1)
        grid_extras.addWidget(QLabel("Precio $:", self), 1, 2)
        # self.edt_inst creation
        self.edt_inst = MoneySpinBox(self)
        self._conf_money(self.edt_inst, prefix="", maxv=999999.99)
        self.edt_inst.setEnabled(False)
        grid_extras.addWidget(self.edt_inst, 1, 3)
        
        # Row 2: Descripción
        grid_extras.addWidget(QLabel("Descripción:", self), 2, 0)
        self.edt_descripcion.setPlaceholderText("Descripción adicional...")
        grid_extras.addWidget(self.edt_descripcion, 2, 1, 1, 3)
        
        self.grp_extras.setLayout(grid_extras)
        main_col.addWidget(self.grp_extras)

        # === 4. Métodos de Pago ===
        self._create_payment_methods_section(main_col)

        # === 5. Resumen (Totales) ===
        self.grp_resumen = QGroupBox("Resumen", self)
        # Usar QHBoxLayout para empujar todo a la derecha
        layout_resumen = QHBoxLayout(self.grp_resumen)
        layout_resumen.addStretch() # Empujar contenido a la derecha
        
        # Contenedor para el formulario
        form_widget = QWidget()
        form_resumen = QFormLayout(form_widget)
        form_resumen.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_resumen.setFormAlignment(Qt.AlignmentFlag.AlignRight)
        form_resumen.setContentsMargins(0, 0, 0, 0)
        form_resumen.setSpacing(8)
        
        # Subtotal
        # self.out_subtotal ya creado en _create_widgets
        self._conf_money(self.out_subtotal, prefix="", maxv=99999999.99)
        self.out_subtotal.setReadOnly(True)
        self.out_subtotal.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.out_subtotal.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.out_subtotal.setStyleSheet("background: transparent; border: none; font-weight: bold;")
        form_resumen.addRow("Subtotal:", self.out_subtotal)
        
        # IVA
        # self.chk_iva ya creado en _create_widgets
        self._conf_money(self.out_iva, prefix="", maxv=99999999.99)
        self.out_iva.setReadOnly(True)
        self.out_iva.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.out_iva.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.out_iva.setStyleSheet("background: transparent; border: none;")
        
        # Usamos el checkbox como widget de etiqueta (izquierda) y el monto como campo (derecha)
        # Al tener setLabelAlignment(AlignRight), el checkbox se alineará a la derecha
        form_resumen.addRow(self.chk_iva, self.out_iva)
        
        # Descuento
        hbox_desc = QHBoxLayout()
        hbox_desc.setContentsMargins(0, 0, 0, 0)
        hbox_desc.setAlignment(Qt.AlignmentFlag.AlignRight) # Alinear contenido del hbox a la derecha
        hbox_desc.addWidget(self.btn_unlock_discount)
        
        self.out_descuento.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.out_descuento.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.out_descuento.setFixedWidth(70) # Hacer más pequeño
        hbox_desc.addWidget(self.out_descuento)
        
        form_resumen.addRow("Descuento:", hbox_desc)
        
        # Subtotal Descuento (Monto)
        self.out_descuento_monto.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.out_descuento_monto.setAlignment(Qt.AlignmentFlag.AlignRight)
        form_resumen.addRow("", self.out_descuento_monto)

        # Total
        # self.out_total ya creado en _create_widgets
        self._conf_money(self.out_total, prefix="", maxv=99999999.99)
        self.out_total.setReadOnly(True)
        self.out_total.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.out_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.out_total.setStyleSheet("background: transparent; border: none; font-weight: bold; font-size: 14px;")
        form_resumen.addRow("Total a Pagar:", self.out_total)
        
        layout_resumen.addWidget(form_widget)
        main_col.addWidget(self.grp_resumen)

    def _create_product_lines_section(self, parent_layout: QVBoxLayout) -> None:
        self.grp_lineas_productos = QGroupBox("Líneas de Productos", self)
        layout = QVBoxLayout(self.grp_lineas_productos)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_add_product_line = QPushButton("+ Agregar Producto", self)
        self.btn_remove_product_line = QPushButton("Eliminar Línea", self)
        toolbar.addWidget(self.btn_add_product_line)
        toolbar.addWidget(self.btn_remove_product_line)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Table
        self.tbl_product_lines = QTableWidget(self)
        self.tbl_product_lines.setColumnCount(8)
        self.tbl_product_lines.setHorizontalHeaderLabels([
            "Producto", "Descripción", "Cant.", "Precio $ Unit.", "Precio Bs Unit.", "Total Bs", "", ""
        ])
        # Adjust column widths
        header = self.tbl_product_lines.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Product
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Description
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Cant
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Price $
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Price Bs
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # Total Bs
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed) # Settings
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed) # Delete
        self.tbl_product_lines.setColumnWidth(6, 30)
        self.tbl_product_lines.setColumnWidth(7, 30)
        
        self.tbl_product_lines.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_product_lines.setMinimumHeight(150)
        
        layout.addWidget(self.tbl_product_lines)
        
        parent_layout.addWidget(self.grp_lineas_productos)
        
        # Connect signals
        self.btn_add_product_line.clicked.connect(self._on_add_product_line)
        self.btn_remove_product_line.clicked.connect(self._on_remove_selected_product_line)

    def _on_add_product_line(self) -> None:
        row = self.tbl_product_lines.rowCount()
        self.tbl_product_lines.insertRow(row)
        
        # 0. Product ComboBox
        cmb_product = QComboBox(self)
        cmb_product.addItem("----Seleccione----", None)
        if hasattr(self, '_cached_products'):
            for p in self._cached_products:
                cmb_product.addItem(p.get('name'), int(p.get('id')))
        self.tbl_product_lines.setCellWidget(row, 0, cmb_product)

        # 1. Descripción (QLineEdit)
        edt_desc = QLineEdit(self)
        edt_desc.setPlaceholderText("Detalles...")
        self.tbl_product_lines.setCellWidget(row, 1, edt_desc)
        
        # 2. Cantidad
        edt_cant = MoneySpinBox(self)
        self._conf_money(edt_cant, prefix="", maxv=9999.0)
        edt_cant.setDecimals(2)
        edt_cant.setValue(1.00)
        self.tbl_product_lines.setCellWidget(row, 2, edt_cant)
        
        # 3. Precio $ Unit
        edt_price_usd = MoneySpinBox(self)
        self._conf_money(edt_price_usd, prefix="", maxv=999999.99)
        self.tbl_product_lines.setCellWidget(row, 3, edt_price_usd)
        
        # 4. Precio Bs Unit
        edt_price_bs = MoneySpinBox(self)
        self._conf_money(edt_price_bs, prefix="", maxv=999999999.99)
        self.tbl_product_lines.setCellWidget(row, 4, edt_price_bs)
        
        # 5. Total Bs
        edt_total_bs = QDoubleSpinBox(self)
        self._conf_money(edt_total_bs, prefix="", maxv=999999999.99)
        edt_total_bs.setReadOnly(True)
        edt_total_bs.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.tbl_product_lines.setCellWidget(row, 5, edt_total_bs)
        
        # 6. Settings Button
        btn_settings = QPushButton("⚙", self)
        btn_settings.setFixedSize(24, 24)
        self.tbl_product_lines.setCellWidget(row, 6, btn_settings)
        
        # 7. Delete Button
        btn_delete = QPushButton("❌", self)
        btn_delete.setFixedSize(24, 24)
        btn_delete.setStyleSheet("color: red;")
        self.tbl_product_lines.setCellWidget(row, 7, btn_delete)
        
        # Ensure there is an item in col 0 to store payload data
        if not self.tbl_product_lines.item(row, 0):
            self.tbl_product_lines.setItem(row, 0, QTableWidgetItem(""))

        # Connect row signals
        cmb_product.currentIndexChanged.connect(lambda: self._on_line_product_changed(cmb_product))
        edt_cant.valueChanged.connect(lambda: self._recalc_line_total(edt_cant))
        edt_price_usd.valueChanged.connect(lambda: self._recalc_line_total(edt_price_usd))
        edt_price_bs.valueChanged.connect(lambda: self._recalc_line_total(edt_price_bs))
        
        btn_settings.clicked.connect(lambda: self._on_configure_line_product(btn_settings))
        btn_delete.clicked.connect(lambda: self._on_delete_line_row(btn_delete))
        
    def _on_remove_selected_product_line(self) -> None:
        row = self.tbl_product_lines.currentRow()
        if row >= 0:
            self.tbl_product_lines.removeRow(row)
            self._update_totals()
            self._rebuild_main_description()
            
    def _on_delete_line_row(self, btn: QPushButton) -> None:
        # Find the row containing this button
        for r in range(self.tbl_product_lines.rowCount()):
            if self.tbl_product_lines.cellWidget(r, 7) == btn:
                self.tbl_product_lines.removeRow(r)
                self._update_totals()
                self._rebuild_main_description()
                break

    def _on_line_product_changed(self, cmb: QComboBox) -> None:
        # Find row
        row = -1
        for r in range(self.tbl_product_lines.rowCount()):
            if self.tbl_product_lines.cellWidget(r, 0) == cmb:
                row = r
                break
        
        if row == -1:
            return

        # Get product ID
        prod_id = cmb.currentData()
        
        # Find product in cache
        desc_text = ""
        if isinstance(prod_id, int) and hasattr(self, '_cached_products'):
            for p in self._cached_products:
                if p.get('id') == prod_id:
                    # Prefer description, fallback to name
                    desc_text = p.get('description') or p.get('name') or ""
                    break
        
        # Fallback to current text if no ID (shouldn't happen for valid products)
        if not desc_text:
            txt = cmb.currentText()
            if txt and not txt.startswith('----'):
                desc_text = txt

        # Update description widget (col 1)
        edt_desc = self.tbl_product_lines.cellWidget(row, 1)
        if edt_desc:
             edt_desc.setText(desc_text)

        self._rebuild_main_description()

    def _rebuild_main_description(self) -> None:
        descriptions = []
        for r in range(self.tbl_product_lines.rowCount()):
            # Get item data
            item = self.tbl_product_lines.item(r, 0)
            data = item.data(Qt.UserRole) if item else None
            
            desc = ""
            # Try to get from data
            if isinstance(data, dict):
                # Generic
                if 'summary' in data and isinstance(data['summary'], dict):
                    desc = data['summary'].get('descripcion', '')
                # Talonario / Corporeo (stored manually)
                if not desc and 'description_summary' in data:
                     desc = data['description_summary']
                
            # Fallback to product name
            if not desc:
                cmb = self.tbl_product_lines.cellWidget(r, 0)
                if cmb:
                    txt = cmb.currentText()
                    if txt and not txt.startswith('----'):
                        desc = txt
            
            if desc:
                descriptions.append(desc)
        
        full_desc = " + ".join(descriptions)
        self.edt_descripcion.setText(full_desc)

    def _on_configure_line_product(self, btn: QPushButton) -> None:
        # Find row
        row = -1
        for r in range(self.tbl_product_lines.rowCount()):
            if self.tbl_product_lines.cellWidget(r, 6) == btn:
                row = r
                break
        if row == -1:
            return

        cmb_product = self.tbl_product_lines.cellWidget(row, 0)
        prod_name = (cmb_product.currentText() or '').strip()
        if not prod_name or prod_name.startswith('----'):
            QMessageBox.information(self, "Configurar", "Seleccione un producto primero.")
            return
        
        name_l_pre = self._norm_text(prod_name)
        
        # 1. Corpóreo
        if 'corp' in name_l_pre:
            self._configure_corporeo_line(row)
            return
            
        # 2. Talonario
        if 'talonario' in name_l_pre or 'talon' in name_l_pre:
            self._configure_talonario_line(row)
            return
            
        # 3. Dinámico (Generic)
        prod_id = None
        try:
            prod_id = cmb_product.currentData()
            if not isinstance(prod_id, int):
                prod_id = None
        except Exception:
            prod_id = None
            
        if prod_id is not None:
            try:
                from .. import repository as _repo
                sf = self._ensure_session_factory()
                if sf is not None:
                    with sf() as s:
                        tables = _repo.get_product_parameter_tables(s, prod_id)
                    if tables:
                        from .product_config_dialog import ProductConfigDialog
                        
                        # Retrieve previous payload
                        prev_data = None
                        item = self.tbl_product_lines.item(row, 0)
                        if item:
                            prev_data = item.data(Qt.UserRole)

                        dlg = ProductConfigDialog(sf, product_id=prod_id, initial_data=prev_data)
                        if dlg.exec():
                            summary = dlg.get_pricing_summary() or {}
                            total_usd = float(summary.get('total', 0.0) or 0.0)
                            config_data = dlg.get_config_data()
                            
                            # Update row fields
                            edt_price_usd = self.tbl_product_lines.cellWidget(row, 3)
                            # edt_cant = self.tbl_product_lines.cellWidget(row, 2) # Not used here
                            
                            if total_usd > 0.0:
                                edt_price_usd.setValue(total_usd)
                            
                            # Update main description
                            desc = summary.get('descripcion', '')
                            
                            # Update row description
                            edt_desc = self.tbl_product_lines.cellWidget(row, 1)
                            if edt_desc and desc:
                                edt_desc.setText(desc)
                            
                            # Store payload
                            payload = {'selections': config_data, 'summary': summary}
                            if item:
                                item.setData(Qt.UserRole, payload)
                            
                            self._rebuild_main_description()
                        return
            except Exception:
                pass
        
        QMessageBox.information(
            self,
            "Configurar",
            f"El producto '{prod_name}' no tiene configuración disponible."
        )

    def _configure_corporeo_line(self, row: int) -> None:
        sf = self._ensure_session_factory()
        if sf is None:
            return
            
        # Resolver type_id
        type_id = None
        try:
            with sf() as s:
                types = eav_list_types(s)
                for t in types:
                    key = self._norm_text(getattr(t, 'key', '') or '')
                    name = self._norm_text(getattr(t, 'name', '') or '')
                    if 'corp' in key or 'corp' in name:
                        type_id = int(getattr(t, 'id'))
                        break
        except Exception:
            pass
            
        if not isinstance(type_id, int):
            QMessageBox.warning(self, "Configurar", "No se encontró el tipo de producto 'Corpóreo'.")
            return

        cmb_product = self.tbl_product_lines.cellWidget(row, 0)
        prod_id = cmb_product.currentData()
        if not isinstance(prod_id, int):
            prod_id = None
            
        # Retrieve previous payload from item data
        prev = None
        item = self.tbl_product_lines.item(row, 0)
        if item:
            prev = item.data(Qt.UserRole)
            
        try:
            from .corporeo_dialog import CorporeoDialog
            dlg = CorporeoDialog(sf, type_id=type_id, product_id=prod_id, initial_payload=prev)
            # Disable draft order logic
            try:
                setattr(dlg, '_draft_order_id', None)
            except Exception:
                pass
                
            if dlg.exec():
                summary = dlg.get_pricing_summary()
                # Use precio_final_usd if available (calculated with corporeo rate), else fallback to total
                final_price = float(summary.get('precio_final_usd', 0.0)) if isinstance(summary, dict) else 0.0
                if final_price <= 0:
                    final_price = float(summary.get('total', 0.0)) if isinstance(summary, dict) else 0.0
                
                payload = dlg.get_full_payload()
                
                # Update row
                edt_price_usd = self.tbl_product_lines.cellWidget(row, 3)
                if final_price > 0.0:
                    edt_price_usd.setValue(final_price)
                    
                # Update main description
                desc_summary = ""
                if hasattr(dlg, 'build_config_summary'):
                    desc_summary = dlg.build_config_summary()
                    # self.edt_descripcion.setText(desc_summary)
                
                # Update row description
                edt_desc = self.tbl_product_lines.cellWidget(row, 1)
                if edt_desc and desc_summary:
                    edt_desc.setText(desc_summary)
                    
                # Store payload
                if isinstance(payload, dict):
                    payload['description_summary'] = desc_summary
                
                if item:
                    item.setData(Qt.UserRole, payload)
                
                self._rebuild_main_description()
                    
        except Exception as e:
            QMessageBox.critical(self, "Configurar", f"Error: {e}")

    def _configure_talonario_line(self, row: int) -> None:
        sf = self._ensure_session_factory()
        if sf is None:
            return
            
        cmb_product = self.tbl_product_lines.cellWidget(row, 0)
        prod_id = cmb_product.currentData()
        if not isinstance(prod_id, int):
            prod_id = None
            
        initial_data = {}
        if prod_id:
            initial_data['product_id'] = prod_id
            
        # Retrieve previous payload
        item = self.tbl_product_lines.item(row, 0)
        if item:
            prev_data = item.data(Qt.UserRole)
            if isinstance(prev_data, dict):
                initial_data.update(prev_data)
        
        try:
            from .talonario_dialog import TalonarioDialog
            dlg = TalonarioDialog(sf, parent=self, initial_data=initial_data)
            
            if dlg.exec():
                data = dlg.accepted_data
                if data:
                    total = float(data.get('precio_total', 0.0))
                    edt_price_usd = self.tbl_product_lines.cellWidget(row, 3)
                    edt_cant = self.tbl_product_lines.cellWidget(row, 2)
                    
                    if total > 0.0:
                        edt_price_usd.setValue(total)
                        
                    # Update main description
                    desc_summary = ""
                    if hasattr(dlg, 'build_config_summary'):
                        desc_summary = dlg.build_config_summary()
                        # self.edt_descripcion.setText(desc_summary)
                    
                    # Update row description
                    edt_desc = self.tbl_product_lines.cellWidget(row, 1)
                    if edt_desc and desc_summary:
                        edt_desc.setText(desc_summary)
                        
                    # Store payload
                    if isinstance(data, dict):
                        data['description_summary'] = desc_summary

                    item = self.tbl_product_lines.item(row, 0)
                    if item:
                        item.setData(Qt.UserRole, data)
                    
                    self._rebuild_main_description()
                        
        except Exception as e:
            QMessageBox.critical(self, "Configurar", f"Error: {e}")

    def _recalc_line_total(self, sender_widget: QWidget) -> None:
        # Find row
        row = -1
        for r in range(self.tbl_product_lines.rowCount()):
            if (self.tbl_product_lines.cellWidget(r, 2) == sender_widget or
                self.tbl_product_lines.cellWidget(r, 3) == sender_widget or
                self.tbl_product_lines.cellWidget(r, 4) == sender_widget):
                row = r
                break
        
        if row == -1:
            return
            
        edt_cant = self.tbl_product_lines.cellWidget(row, 2)
        edt_price_usd = self.tbl_product_lines.cellWidget(row, 3)
        edt_price_bs = self.tbl_product_lines.cellWidget(row, 4)
        edt_total_bs = self.tbl_product_lines.cellWidget(row, 5)
        
        if not (edt_cant and edt_price_usd and edt_price_bs and edt_total_bs):
            return
            
        cant = edt_cant.value()
        price_usd = edt_price_usd.value()
        price_bs = edt_price_bs.value()
        
        rate = self.edt_tasa_bcv.value()
        
        # Avoid infinite recursion if we update the other field
        sender_widget.blockSignals(True)
        try:
            if sender_widget == edt_price_usd:
                price_bs = price_usd * rate
                edt_price_bs.blockSignals(True)
                edt_price_bs.setValue(price_bs)
                edt_price_bs.blockSignals(False)
            elif sender_widget == edt_price_bs:
                if rate > 0:
                    price_usd = price_bs / rate
                    edt_price_usd.blockSignals(True)
                    edt_price_usd.setValue(price_usd)
                    edt_price_usd.blockSignals(False)
        finally:
            sender_widget.blockSignals(False)
        
        # Recalc Total Bs
        total_bs = edt_price_bs.value() * cant
        edt_total_bs.setValue(total_bs)
        
        # Update global totals
        self._update_totals()

    def _create_payment_methods_section(self, parent_layout: QVBoxLayout) -> None:
        self.grp_metodos_pago = QGroupBox("Métodos de Pago", self)
        layout = QVBoxLayout(self.grp_metodos_pago)
        
        # Table
        self.tbl_payments = QTableWidget(self)
        self.tbl_payments.setColumnCount(6)
        self.tbl_payments.setHorizontalHeaderLabels([
            "Forma de Pago", "Monto Bs", "Monto $", "Banco/Serial", "Referencia", ""
        ])
        header = self.tbl_payments.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # Forma de Pago
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # Monto Bs
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Monto $
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch) # Banco
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Referencia
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed) # Delete
        self.tbl_payments.setColumnWidth(5, 30)
        
        self.tbl_payments.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_payments.setMinimumHeight(150)
        layout.addWidget(self.tbl_payments)
        
        # Add Button
        self.btn_add_payment = QPushButton("+ Agregar Método de Pago", self)
        self.btn_add_payment.setStyleSheet("background-color: #e0e0e0; padding: 6px; font-weight: bold;")
        layout.addWidget(self.btn_add_payment)
        
        # Footer
        footer_layout = QGridLayout()
        
        # Totals Labels
        self.lbl_total_bs_payments = QLabel("Total Bs: 0.00", self)
        self.lbl_total_bs_payments.setStyleSheet("color: #00aaff; font-weight: bold;")
        self.lbl_total_usd_payments = QLabel("Total $: 0.00", self)
        self.lbl_total_usd_payments.setStyleSheet("color: #28a745; font-weight: bold;")
        
        totals_box = QHBoxLayout()
        totals_box.addWidget(self.lbl_total_bs_payments)
        totals_box.addWidget(self.lbl_total_usd_payments)
        totals_box.addStretch()
        footer_layout.addLayout(totals_box, 0, 0, 1, 4)
        
        # Fields
        footer_layout.addWidget(QLabel("Tasa BCV (Bs/$):", self), 1, 0)
        self.edt_tasa_bcv_payments = QDoubleSpinBox(self)
        self._conf_money(self.edt_tasa_bcv_payments, prefix="", maxv=999.99)
        self.edt_tasa_bcv_payments.setValue(self.edt_tasa_bcv.value()) # Sync initial
        footer_layout.addWidget(self.edt_tasa_bcv_payments, 1, 1)
        
        footer_layout.addWidget(QLabel("Abono $:", self), 2, 0)
        self.edt_abono_payments = QDoubleSpinBox(self)
        self._conf_money(self.edt_abono_payments, prefix="", maxv=999999.99)
        self.edt_abono_payments.setReadOnly(True) # Calculated from table
        footer_layout.addWidget(self.edt_abono_payments, 2, 1)
        
        footer_layout.addWidget(QLabel("Por Cobrar $:", self), 2, 2)
        self.out_restante_payments = QDoubleSpinBox(self)
        self._conf_money(self.out_restante_payments, prefix="", maxv=999999.99)
        self.out_restante_payments.setReadOnly(True)
        footer_layout.addWidget(self.out_restante_payments, 2, 3)
        
        layout.addLayout(footer_layout)
        parent_layout.addWidget(self.grp_metodos_pago)
        
        # Signals
        self.btn_add_payment.clicked.connect(self._on_add_payment_row)
        self.edt_tasa_bcv_payments.valueChanged.connect(self._recalc_all_payments)
        
        # Sync main rate to this rate
        self.edt_tasa_bcv.valueChanged.connect(lambda: self.edt_tasa_bcv_payments.setValue(self.edt_tasa_bcv.value()))
        
    def _on_add_payment_row(self) -> None:
        row = self.tbl_payments.rowCount()
        self.tbl_payments.insertRow(row)
        
        # 0. Forma de Pago
        cmb_method = QComboBox(self)
        cmb_method.addItems([
            "---- Seleccione ----",
            "Efectivo USD", "Zelle", "Banesco Panamá", "Binance", "PayPal",
            "Efectivo Bs.D", "Pago móvil", "Transferencia Bs.D", "Punto de Venta"
        ])
        self.tbl_payments.setCellWidget(row, 0, cmb_method)
        
        # 1. Monto Bs
        edt_monto_bs = MoneySpinBox(self)
        self._conf_money(edt_monto_bs, prefix="Bs ", maxv=999999999.99)
        self.tbl_payments.setCellWidget(row, 1, edt_monto_bs)
        
        # 2. Monto $
        edt_monto_usd = MoneySpinBox(self)
        self._conf_money(edt_monto_usd, prefix="$ ", maxv=999999.99)
        self.tbl_payments.setCellWidget(row, 2, edt_monto_usd)
        
        # 3. Banco/Serial
        edt_banco = QLineEdit(self)
        edt_banco.setPlaceholderText("Banco o Serial...")
        self.tbl_payments.setCellWidget(row, 3, edt_banco)
        
        # 4. Referencia
        edt_ref = QLineEdit(self)
        edt_ref.setPlaceholderText("Referencia...")
        self.tbl_payments.setCellWidget(row, 4, edt_ref)
        
        # 5. Delete
        btn_delete = QPushButton("🗑️", self)
        btn_delete.setFixedSize(24, 24)
        self.tbl_payments.setCellWidget(row, 5, btn_delete)
        
        # Signals
        edt_monto_bs.valueChanged.connect(lambda: self._recalc_payment_row(edt_monto_bs))
        edt_monto_usd.valueChanged.connect(lambda: self._recalc_payment_row(edt_monto_usd))
        btn_delete.clicked.connect(lambda: self._on_delete_payment_row(btn_delete))
        
        # Connect method change to auto-fill logic
        cmb_method.currentIndexChanged.connect(lambda: self._on_payment_method_changed(cmb_method))
        
        # Trigger update to get current remaining
        self._update_payment_totals()
        
        # Auto-fill remaining balance (always try, logic inside handles method type)
        self._apply_payment_autofill(row)

    def _is_bs_method(self, method_name: str) -> bool:
        # Define methods that are in Bolívares
        bs_methods = [
            "Efectivo Bs.D", "Pago móvil", "Transferencia Bs.D", "Punto de Venta"
        ]
        return method_name in bs_methods

    def _apply_payment_autofill(self, row: int) -> None:
        cmb = self.tbl_payments.cellWidget(row, 0)
        if not cmb: return
        method = cmb.currentText()
        
        # Rule: "si es en divisas no se va a llenar"
        if not self._is_bs_method(method):
            # Rule: "si se vuelve a selecionar un metodo en divisas se borra el campo monto en vs"
            edt_bs = self.tbl_payments.cellWidget(row, 1)
            if edt_bs:
                edt_bs.setValue(0.0)
            return
            
        # Calculate remaining excluding this row
        total_sale = self.out_total.value()
        current_paid = 0.0
        for r in range(self.tbl_payments.rowCount()):
            if r == row: continue
            w_usd = self.tbl_payments.cellWidget(r, 2)
            if w_usd:
                current_paid += w_usd.value()
        
        remaining = max(0.0, total_sale - current_paid)
        
        if remaining > 0:
            edt_usd = self.tbl_payments.cellWidget(row, 2)
            if edt_usd:
                edt_usd.setValue(remaining)
                # This triggers _recalc_payment_row(edt_monto_usd) which updates Bs

    def _on_payment_method_changed(self, cmb: QComboBox) -> None:
        # Find row
        row = -1
        for r in range(self.tbl_payments.rowCount()):
            if self.tbl_payments.cellWidget(r, 0) == cmb:
                row = r
                break
        if row == -1:
            return

        # -----------------------------------------------------------
        # NEW LOGIC: Switch Banco/Serial widget type depending on Method
        # -----------------------------------------------------------
        method = cmb.currentText().lower()
        w_bank_current = self.tbl_payments.cellWidget(row, 3)
        current_text = ""
        if isinstance(w_bank_current, QLineEdit):
            current_text = w_bank_current.text()
        elif isinstance(w_bank_current, QComboBox):
             current_text = w_bank_current.currentText()

        # Keywords that imply a BANK selection
        bs_bank_methods = ["pago móvil", "transferencia", "punto", "biopago", "deposito", "zelle", "panama", "mony"]
        
        should_be_combo = any(m in method for m in bs_bank_methods)
        
        if should_be_combo:
            if not isinstance(w_bank_current, QComboBox):
                # Replace with ComboBox
                new_cmb = QComboBox(self)
                new_cmb.setEditable(True) 
                
                # Define banks based on likely currency
                banks = []
                if "zelle" in method or "panama" in method or "mony" in method:
                     banks = ["Zelle", "Banesco Panamá", "Mercantil Panamá", "Facebank", "PayPal", "Binance"]
                else:
                     # VES Banks (Company specific first)
                     banks = ["Banesco", "Banco de Venezuela", "Bancamiga", "Mercantil", "Provincial", "BNC", "Tesoro", "Bicentenario"]

                new_cmb.addItems(["---- Seleccione ----"] + banks)
                
                # Try to restore text if matches
                if current_text:
                    idx = new_cmb.findText(current_text)
                    if idx >= 0:
                        new_cmb.setCurrentIndex(idx)
                    else:
                        new_cmb.setEditText(current_text)
                    
                self.tbl_payments.setCellWidget(row, 3, new_cmb)
        else:
            if not isinstance(w_bank_current, QLineEdit):
                # Replace with LineEdit (for Efectivo / Notes)
                new_edt = QLineEdit(self)
                new_edt.setPlaceholderText("Serial Billete / Nota...")
                new_edt.setText(current_text)
                self.tbl_payments.setCellWidget(row, 3, new_edt)
        # -----------------------------------------------------------
            
        # Apply auto-fill logic (always, logic inside handles method type)
        self._apply_payment_autofill(row)

    def _on_delete_payment_row(self, btn: QPushButton) -> None:
        for r in range(self.tbl_payments.rowCount()):
            if self.tbl_payments.cellWidget(r, 5) == btn:
                self.tbl_payments.removeRow(r)
                self._update_payment_totals()
                break

    def _recalc_payment_row(self, sender_widget: QWidget) -> None:
        row = -1
        for r in range(self.tbl_payments.rowCount()):
            if (self.tbl_payments.cellWidget(r, 1) == sender_widget or
                self.tbl_payments.cellWidget(r, 2) == sender_widget):
                row = r
                break
        
        if row == -1:
            return
            
        edt_bs = self.tbl_payments.cellWidget(row, 1)
        edt_usd = self.tbl_payments.cellWidget(row, 2)
        rate = self.edt_tasa_bcv_payments.value()
        
        sender_widget.blockSignals(True)
        try:
            if sender_widget == edt_bs:
                if rate > 0:
                    val_usd = edt_bs.value() / rate
                    edt_usd.blockSignals(True)
                    edt_usd.setValue(val_usd)
                    edt_usd.blockSignals(False)
            elif sender_widget == edt_usd:
                val_bs = edt_usd.value() * rate
                edt_bs.blockSignals(True)
                edt_bs.setValue(val_bs)
                edt_bs.blockSignals(False)
        finally:
            sender_widget.blockSignals(False)
            
        self._update_payment_totals()

    def _recalc_all_payments(self) -> None:
        rate = self.edt_tasa_bcv_payments.value()
        for r in range(self.tbl_payments.rowCount()):
            edt_bs = self.tbl_payments.cellWidget(r, 1)
            edt_usd = self.tbl_payments.cellWidget(r, 2)
            if edt_usd and edt_bs:
                # Assume USD is master if rate changes? Or keep Bs fixed?
                # Usually if rate changes, we might want to update Bs based on USD or vice versa.
                # Let's assume USD is the "value" and Bs updates.
                val_bs = edt_usd.value() * rate
                edt_bs.blockSignals(True)
                edt_bs.setValue(val_bs)
                edt_bs.blockSignals(False)
        self._update_payment_totals()

    def _update_payment_totals(self) -> None:
        total_bs = 0.0
        total_usd = 0.0
        
        for r in range(self.tbl_payments.rowCount()):
            edt_bs = self.tbl_payments.cellWidget(r, 1)
            edt_usd = self.tbl_payments.cellWidget(r, 2)
            if edt_bs: total_bs += edt_bs.value()
            if edt_usd: total_usd += edt_usd.value()
            
        self.lbl_total_bs_payments.setText(f"Total Bs: {total_bs:,.2f}")
        self.lbl_total_usd_payments.setText(f"Total $: {total_usd:,.2f}")
        
        self.edt_abono_payments.setValue(total_usd)
        
        # Calculate remaining
        # We need the sale total. We can get it from self.out_total
        sale_total = self.out_total.value()
        remaining = sale_total - total_usd
        if remaining < 0: remaining = 0.0
        self.out_restante_payments.setValue(remaining)

    def _init_layout(self) -> None:
        pass

    def _apply_body_layout(self, mode: str) -> None:
        # El layout ya está definido en _create_invoice_body como grid fijo
        # No necesita cambios dinámicos, solo guardamos el modo por compatibilidad
        self._layout_mode = mode

    def resizeEvent(self, event) -> None:
        try:
            mode = 'one' if self.width() < 750 else 'two'
            self._apply_body_layout(mode)
        except Exception:
            pass
        super().resizeEvent(event)

    def _create_widgets(self) -> None:
        # Datos básicos
        self.lbl_asesor = QLabel(self._seller or "admin", self)
        self.edt_fecha_pago = QDateEdit(self)
        self.edt_fecha_pago.setCalendarPopup(True)
        self.edt_fecha_pago.setDate(QDate.currentDate())
        self.edt_fecha_pago_2 = QDateEdit(self)  # Segunda fecha de pago
        self.edt_fecha_pago_2.setCalendarPopup(True)
        self.edt_fecha_pago_2.setDate(QDate.currentDate())
        # Cliente como lista editable (con búsqueda)
        self.edt_cliente = QComboBox(self)
        self.edt_cliente.setEditable(True)
        # Caché para clientes: id -> objeto
        self._customers_by_id = {}

        # Items de la venta
        self._items_data = []
        self.tbl_items = QTableWidget(self)
        self.tbl_items.setColumnCount(5)
        self.tbl_items.setHorizontalHeaderLabels(["Producto", "Cant", "P.Unit ($)", "Total ($)", ""])
        self.tbl_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_items.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_items.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_items.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_items.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_items.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_items.setMinimumHeight(150)

        self.btn_add_item = QPushButton("Agregar Item", self)
        self.btn_add_item.setStyleSheet("background-color: #e0e0e0; padding: 4px;")

        # Pagos (Legacy Single Payment)
        self.cmb_forma_pago = QComboBox(self)
        self.cmb_forma_pago.addItems([
            "Efectivo USD", "Zelle", "Banesco Panamá", "Binance", "PayPal",
            "Efectivo Bs.D", "Pago móvil", "Transferencia Bs.D", "Punto de Venta"
        ])
        
        # Detalle del producto (Input area)
        self.edt_articulo = QComboBox(self)
        self.edt_articulo.setObjectName("edt_articulo")
        self.edt_articulo.setEditable(True)
        self.edt_precio_unitario = QDoubleSpinBox(self)
        self._conf_money(self.edt_precio_unitario, prefix="", maxv=999999.99)
        self.edt_precio_unitario_bs = QDoubleSpinBox(self)  # Nuevo precio en Bs
        self._conf_money(self.edt_precio_unitario_bs, prefix="", maxv=999999999.99)
        # Label para mostrar precio final corpóreo (solo visible cuando es producto corpóreo)
        self.lbl_precio_final_corporeo = QLabel("$0.00", self)
        self.lbl_precio_final_corporeo.setStyleSheet("color: #28a745; font-weight: bold;")
        self.lbl_precio_final_corporeo.setVisible(False)  # Oculto por defecto
        # Cantidad como texto con validador decimal (2)
        self.edt_cantidad = QLineEdit(self)
        self.edt_cantidad.setObjectName("edt_cantidad")
        dv = QDoubleValidator(0.0, 9999.0, 2, self)
        dv.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.edt_cantidad.setValidator(dv)
        self.edt_cantidad.setText("1.00")
        self.edt_total_bs = QDoubleSpinBox(self)
        self._conf_money(self.edt_total_bs, prefix="", maxv=999999999.99)

        # Tasa BCV (Global para la venta, aunque cada pago puede tener la suya)
        self.edt_tasa_bcv = QDoubleSpinBox(self)
        self._conf_money(self.edt_tasa_bcv, prefix="", maxv=999.99)
        # La tasa BCV es sólo informativa: impedir modificaciones manuales.
        try:
            self.edt_tasa_bcv.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            self.edt_tasa_bcv.setReadOnly(True)
        except Exception:
            pass
        # Set a sensible default, then attempt to override with live rate from API (dolarapi/pydolar)
        self.edt_tasa_bcv.setValue(36.0)  # Default BCV rate
        # Permitimos que el usuario habilite/deshabilite la edición manual del precio unitario
        self.chk_edit_price = QCheckBox("Editar", self)
        try:
            self.chk_edit_price.setChecked(True)
        except Exception:
            pass
        # Conectar la casilla para activar/desactivar el spinbox
        try:
            self.chk_edit_price.toggled.connect(lambda v: self.edt_precio_unitario.setEnabled(bool(v)))
        except Exception:
            pass
        try:
            # get_bcv_rate may block; call it with a small timeout and ignore failures
            rate = get_bcv_rate(timeout=3.0)
            if rate and float(rate) > 0:
                try:
                    self.edt_tasa_bcv.setValue(float(rate))
                except Exception:
                    pass
        except Exception:
            # ignore network errors and keep default
            pass
        
        # Campos de totales de pago (reutilizados o nuevos)
        self.edt_monto_bs = QDoubleSpinBox(self)
        self._conf_money(self.edt_monto_bs, prefix="", maxv=99999999.99)
        self.edt_monto_calculado = QDoubleSpinBox(self)
        self._conf_money(self.edt_monto_calculado, prefix="")
        self.edt_monto_calculado.setReadOnly(True)
        self.edt_abono = QDoubleSpinBox(self)
        self._conf_money(self.edt_abono, prefix="")
        self.out_restante = QDoubleSpinBox(self)
        self._conf_money(self.out_restante, prefix="")
        self.out_restante.setReadOnly(True)
        self.edt_banco = QLineEdit(self)
        self.edt_referencia = QLineEdit(self)
        self.edt_serial = QLineEdit(self)

        # IVA
        self.chk_iva = QCheckBox("Cobrar IVA (16%)", self)
        self.chk_iva.setChecked(False)
        self.out_iva = QDoubleSpinBox(self)
        self._conf_money(self.out_iva, prefix="", maxv=999999.99)
        self.out_iva.setReadOnly(True)

        # Extras
        self.edt_diseno = MoneySpinBox(self)
        self._conf_money(self.edt_diseno, prefix="")
        self.edt_ingresos = MoneySpinBox(self)
        self._conf_money(self.edt_ingresos, prefix="")
        self.edt_descripcion = QLineEdit(self)  # Nueva descripción
        self.edt_descripcion.setPlaceholderText("Descripción adicional...")

        # Totales
        self.out_subtotal = QDoubleSpinBox(self)
        self._conf_money(self.out_subtotal, prefix="")
        self.out_subtotal.setReadOnly(True)
        
        # Descuento
        self.out_descuento = MoneySpinBox(self)
        self._conf_money(self.out_descuento, prefix="", maxv=100.00) # Max 100%
        self.out_descuento.setSuffix("%")
        self.out_descuento.setReadOnly(True) # Bloqueado por defecto
        self.out_descuento.setStyleSheet("color: #d9534f; font-weight: bold;")
        
        self.btn_unlock_discount = QPushButton("🔓", self)
        self.btn_unlock_discount.setToolTip("Autorizar Descuento (Admin)")
        self.btn_unlock_discount.setFixedWidth(30)
        self.btn_unlock_discount.setStyleSheet("background-color: #f0ad4e; border: none; border-radius: 4px;")

        # Monto calculado del descuento
        self.out_descuento_monto = QDoubleSpinBox(self)
        self._conf_money(self.out_descuento_monto, prefix="-", maxv=99999999.99)
        self.out_descuento_monto.setReadOnly(True)
        self.out_descuento_monto.setStyleSheet("color: #d9534f; font-weight: bold; background: transparent; border: none;")

        self.out_iva_subtotal = QDoubleSpinBox(self)
        self._conf_money(self.out_iva_subtotal, prefix="")
        self.out_iva_subtotal.setReadOnly(True)
        self.out_total = QDoubleSpinBox(self)
        self._conf_money(self.out_total, prefix="")
        self.out_total.setReadOnly(True)

        # Notas
        self.edt_notas = QLineEdit(self)
        self.edt_notas.setObjectName("edt_notas")
        self.edt_notas.setPlaceholderText("Notas adicionales...")
        # Este campo fue retirado del diseño visual. Como el widget se creaba con parent=self
        # y no se añadía a ningún layout, Qt lo mostraba en (0,0) superpuesto al logo.
        # Lo mantenemos por compatibilidad con get_data/set_data pero lo ocultamos explícitamente.
        self.edt_notas.hide()

        # Ocultar widgets legacy que ya no se usan en el layout pero se mantienen por compatibilidad
        for w in [
            self.edt_articulo, self.edt_precio_unitario, self.edt_precio_unitario_bs,
            self.lbl_precio_final_corporeo, self.edt_cantidad, self.edt_total_bs,
            self.cmb_forma_pago, self.edt_monto_bs, self.edt_monto_calculado,
            self.edt_abono, self.out_restante, self.edt_banco, self.edt_referencia,
            self.edt_serial, self.btn_add_item, self.chk_edit_price,
            # Widgets adicionales que quedaron flotando
            self.edt_tasa_bcv, self.out_iva_subtotal, self.tbl_items,
            self.edt_ingresos, self.edt_fecha_pago_2
        ]:
            try:
                w.hide()
            except Exception:
                pass

    def _conf_money(self, sp: QDoubleSpinBox, prefix: str = "", maxv: float = 9999999.99) -> None:
        sp.setDecimals(2)
        sp.setRange(0.00, maxv)
        if prefix:
            sp.setPrefix(prefix)
        sp.setValue(0.00)
        sp.setSingleStep(1.00)
        try:
            sp.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        except Exception:
            pass

    def _populate_lookups(self) -> None:
        """Cargar clientes y productos en los combos."""
        sf = self._ensure_session_factory()
        if sf is None:
            return
        try:
            with sf() as session:
                # Clientes: usar name si existe, o nombre+apellido como fallback
                customers = list_customers(session)
                self._customers_by_id = {}
                self.edt_cliente.clear()
                # Placeholder
                self.edt_cliente.addItem("----Selecione----", None)
                for c in customers:
                    label = (getattr(c, 'name', None) or '').strip()
                    if not label:
                        first = getattr(c, 'first_name', '') or ''
                        last = getattr(c, 'last_name', '') or ''
                        label = f"{first} {last}".strip()
                    if not label:
                        label = f"Cliente #{getattr(c, 'id', '')}".strip()
                    cid = getattr(c, 'id', None)
                    if cid is not None:
                        self._customers_by_id[int(cid)] = c
                        self.edt_cliente.addItem(label, int(cid))
                    else:
                        self.edt_cliente.addItem(label)
                # Limpiar detalles al inicio
                self._clear_customer_details()

                # Productos desde Configurables (Parámetros y materiales)
                conf_products = list_configurable_products(session)
                self._cached_products = conf_products
                self.edt_articulo.clear()
                # Placeholder
                self.edt_articulo.addItem("----Selecione----", None)
                for p in conf_products:
                    self.edt_articulo.addItem(p.get('name'), int(p.get('id')))
        except Exception:
            pass

    def _load_order_number(self) -> None:
        """Cargar el siguiente número de orden."""
        sf = self._ensure_session_factory()
        if sf is None:
            return
        try:
            with sf() as session:
                next_order = generate_order_number(session)
                if hasattr(self, 'lbl_orden'):
                    self.lbl_orden.setText(next_order)
        except Exception:
            pass

    # --- Estilo ---
    def _apply_invoice_style(self) -> None:
        # Dejar que el QSS global maneje colores/estados. Solo asignamos objectNames útiles.
        try:
            self.setObjectName("invoiceDialog")
        except Exception:
            pass

    # --- Lógica ---
    def _norm_text(self, s: str) -> str:
        try:
            if not s:
                return ""
            # Quitar acentos y pasar a minúsculas
            nfkd = unicodedata.normalize("NFKD", s)
            return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()
        except Exception:
            try:
                return s.lower()
            except Exception:
                return ""

    def _setup_signals(self) -> None:
        # Conectar cálculos automáticos
        self.edt_precio_unitario.valueChanged.connect(self._calc_total_bs)
        self.edt_cantidad.textChanged.connect(self._calc_total_bs)
        self.edt_tasa_bcv.valueChanged.connect(self._recalc_monto_usd)
        self.edt_monto_bs.valueChanged.connect(self._recalc_monto_usd)
        self.edt_fecha_pago.dateChanged.connect(self._on_payment_date_changed)
        # Cliente: crear nuevo y cambios de selección
        self.btn_nuevo_cliente.clicked.connect(self._on_new_customer)
        # Cliente seleccionado
        self.edt_cliente.currentIndexChanged.connect(self._on_customer_changed)
        # Configurar producto
        try:
            if hasattr(self, 'btn_configurar'):
                self.btn_configurar.clicked.connect(self._on_configurar_producto)
        except Exception:
            pass
        try:
            if hasattr(self, 'btn_edit_corporeo'):
                self.btn_edit_corporeo.clicked.connect(self._on_edit_corporeo)
        except Exception:
            pass
        
        # Agregar item
        self.btn_add_item.clicked.connect(self._on_add_item)
        
        # Descuento
        self.btn_unlock_discount.clicked.connect(self._request_admin_auth)
        self.out_descuento.valueChanged.connect(self._update_totals)
        
        # Conectar actualizaciones de totales
        for sp in (self.edt_total_bs, self.edt_abono, self.edt_diseno, self.edt_ingresos):
            sp.valueChanged.connect(self._update_totals)
        self.chk_iva.toggled.connect(self._update_totals)
        # Checkbox de diseño: habilita el campo de diseño y fuerza recálculo
        try:
            self.chk_incluye_diseno.toggled.connect(lambda v: (self.edt_diseno.setEnabled(bool(v)), self._update_totals()))
        except Exception:
            pass
        # Checkbox de instalación: habilita el campo de instalación y fuerza recálculo
        try:
            self.chk_incluye_inst.toggled.connect(lambda v: (self.edt_inst.setEnabled(bool(v)), self._update_totals()))
            self.edt_inst.valueChanged.connect(self._update_totals)
        except Exception:
            pass
        
        # Conectar cálculo de precio en Bs cuando cambie precio USD o tasa
        self.edt_precio_unitario.valueChanged.connect(self._calc_precio_unitario_bs)
        self.edt_tasa_bcv.valueChanged.connect(self._calc_precio_unitario_bs)
        # Recalcular precio en Bs cuando cambia forma de pago (importante para corpóreos)
        self.cmb_forma_pago.currentIndexChanged.connect(self._calc_precio_unitario_bs)
    
    def _calc_total_bs(self) -> None:
        """Calcular Total Bs = Precio Unitario (Bs) * Cantidad"""
        try:
            precio_bs = self.edt_precio_unitario_bs.value()
            try:
                cantidad = float((self.edt_cantidad.text() or "0").replace(",", "."))
            except Exception:
                cantidad = 0.0
            total = precio_bs * cantidad
            self.edt_total_bs.setValue(total)
        except Exception:
            pass

    def _calc_precio_unitario_bs(self) -> None:
        """Calcular Precio Unitario en Bs = Precio Unitario ($) * Tasa"""
        try:
            # Verificar si es producto corpóreo
            if self._is_corporeo_product:
                precio_usd = self.edt_precio_unitario.value()
                tasa = self.edt_tasa_bcv.value() or 0.0
                label_bs = self._precio_corporeo_tasa_bcv if self._precio_corporeo_tasa_bcv > 0 else (precio_usd * tasa)
                # Mostrar siempre el precio final corpóreo en Bs y tooltip con el USD equivalente
                self.lbl_precio_final_corporeo.setText(f"Bs {label_bs:,.2f}")
                self.lbl_precio_final_corporeo.setToolTip(f"Equivalente USD: ${precio_usd:.2f}")
                self.lbl_precio_final_corporeo.setVisible(True)

                forma_pago = self.cmb_forma_pago.currentText().strip()
                # Métodos de pago en Bs: Efectivo Bs.D, Transferencia Bs.D, Pago móvil
                es_pago_bs = any(metodo in forma_pago for metodo in ['Bs.D', 'Bs.', 'móvil', 'movil'])

                if es_pago_bs and label_bs > 0:
                    # Usar precio corpóreo tasa BCV para pagos en Bs
                    self.edt_precio_unitario_bs.setValue(self._precio_corporeo_tasa_bcv if self._precio_corporeo_tasa_bcv > 0 else label_bs)
                    # Actualizar label para indicar que se usa precio corpóreo
                    self.lbl_precio_final_corporeo.setStyleSheet("color: #dc3545; font-weight: bold;")  # Rojo
                    # Recalcular total después de actualizar precio en Bs
                    self._calc_total_bs()
                    return
                else:
                    # Pago en divisas: actualizar label a verde (precio normal)
                    self.lbl_precio_final_corporeo.setStyleSheet("color: #28a745; font-weight: bold;")  # Verde
            else:
                # Asegurar que el label quede oculto cuando no es corpóreo
                self.lbl_precio_final_corporeo.setVisible(False)

            # Cálculo normal para productos no corpóreos o pago en divisas
            precio_usd = self.edt_precio_unitario.value()
            tasa = self.edt_tasa_bcv.value() or 36.0
            precio_bs = precio_usd * tasa
            self.edt_precio_unitario_bs.setValue(precio_bs)
            # Recalcular total después de actualizar precio en Bs
            self._calc_total_bs()
        except Exception:
            pass

    def _load_bcv_rate(self) -> None:
        try:
            rate = get_bcv_rate(timeout=2.0)
            self._current_bcv_rate = rate if (rate and rate > 0) else 36.0
        except Exception:
            self._current_bcv_rate = 36.0

    def _on_payment_date_changed(self) -> None:
        try:
            qd = self.edt_fecha_pago.date()
            d = Date(qd.year(), qd.month(), qd.day())
            rate = get_rate_for_date(d, timeout=0.5)
            if rate and rate > 0:
                self._current_bcv_rate = rate
                # Opcional: actualizar el campo visual de tasa
                try:
                    self.edt_tasa_bcv.setValue(float(rate))
                except Exception:
                    pass
            self._recalc_monto_usd()
        except Exception:
            pass

    def _recalc_monto_usd(self) -> None:
        try:
            rate = self.edt_tasa_bcv.value() or 36.0
            monto_bs = self.edt_monto_bs.value()
            usd = (monto_bs / rate) if rate > 0 else 0.0
            self.edt_monto_calculado.setValue(usd)
        except Exception:
            pass

    def _on_add_item(self) -> None:
        """Agregar el item actual a la lista."""
        try:
            # Validar
            prod_text = self.edt_articulo.currentText()
            if not prod_text or prod_text == "----Selecione----":
                QMessageBox.warning(self, "Error", "Seleccione un producto")
                return
            
            try:
                qty = float(self.edt_cantidad.text().replace(",", "."))
            except:
                qty = 1.0
            
            price_usd = self.edt_precio_unitario.value()
            total_bs = self.edt_total_bs.value()
            
            # Calcular total USD para el item
            total_usd = price_usd * qty
            
            # Datos del item
            item = {
                'product_name': prod_text,
                'quantity': qty,
                'unit_price': price_usd,
                'total_price': total_usd,
                'total_bs': total_bs,
                'details': {
                    'corporeo_payload': getattr(self, '_corporeo_payload', None),
                    'is_corporeo': getattr(self, '_is_corporeo_product', False),
                    'description': self.edt_descripcion.text()
                }
            }
            
            self._items_data.append(item)
            self._render_items_table()
            self._update_totals()
            
            # Limpiar campos
            self.edt_articulo.setCurrentIndex(0)
            self.edt_cantidad.setText("1.00")
            self.edt_precio_unitario.setValue(0.0)
            self.edt_total_bs.setValue(0.0)
            self.edt_descripcion.clear()
            self._corporeo_payload = None
            self._is_corporeo_product = False
            self.lbl_precio_final_corporeo.setVisible(False)
            self.lbl_precio_final_corporeo_label.setVisible(False)
            if hasattr(self, 'btn_edit_corporeo'):
                self.btn_edit_corporeo.setEnabled(False)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al agregar item: {e}")

    def _render_items_table(self) -> None:
        self.tbl_items.setRowCount(0)
        for i, item in enumerate(self._items_data):
            self.tbl_items.insertRow(i)
            self.tbl_items.setItem(i, 0, QTableWidgetItem(str(item['product_name'])))
            self.tbl_items.setItem(i, 1, QTableWidgetItem(f"{item['quantity']:.2f}"))
            self.tbl_items.setItem(i, 2, QTableWidgetItem(f"{item['unit_price']:.2f}"))
            self.tbl_items.setItem(i, 3, QTableWidgetItem(f"{item['total_price']:.2f}"))
            
            btn_del = QPushButton("❌")
            btn_del.setFixedSize(24, 24)
            btn_del.setFlat(True)
            btn_del.clicked.connect(lambda checked, idx=i: self._remove_item(idx))
            self.tbl_items.setCellWidget(i, 4, btn_del)

    def _remove_item(self, index: int) -> None:
        if 0 <= index < len(self._items_data):
            self._items_data.pop(index)
            self._render_items_table()
            self._update_totals()

    def _request_admin_auth(self) -> None:
        """Solicita autorización de administrador para desbloquear el descuento."""
        if self.discount_authorized:
            return

        dlg = LoginDialog(self, self._session_factory)
        dlg.setWindowTitle("Autorización Requerida")
        if dlg.exec():
            username, _ = dlg.get_credentials()
            
            try:
                with self._session_factory() as session:
                    user = session.query(User).filter(User.username == username).first()
                    is_admin = False
                    
                    if user:
                        # Check default role
                        if user.default_role_id:
                            role = session.get(Role, user.default_role_id)
                            if role and role.name == "ADMIN":
                                is_admin = True
                                
                        # Check user_roles
                        if not is_admin:
                            user_roles = session.query(UserRole).filter_by(user_id=user.id).all()
                            for ur in user_roles:
                                r = session.get(Role, ur.role_id)
                                if r and r.name == "ADMIN":
                                    is_admin = True
                                    break
                    else:
                         # Fallback
                         if username == "admin":
                             is_admin = True

                    if is_admin:
                        self.discount_authorized = True
                        self.out_descuento.setReadOnly(False)
                        self.out_descuento.setStyleSheet("color: #000000; font-weight: bold;")
                        self.btn_unlock_discount.setVisible(False)
                        self.out_descuento.setFocus()
                        QMessageBox.information(self, "Autorizado", "Descuento habilitado.")
                    else:
                        QMessageBox.warning(self, "Acceso Denegado", "El usuario no tiene permisos de administrador.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error verificando permisos: {e}")

    def _update_totals(self) -> None:
        """Recalcular totales generales sumando los items."""
        try:
            # Sumar items (Legacy table)
            subtotal_usd = sum(item['total_price'] for item in self._items_data)
            
            # Sumar items (New Product Lines table)
            if hasattr(self, 'tbl_product_lines'):
                for r in range(self.tbl_product_lines.rowCount()):
                    w_cant = self.tbl_product_lines.cellWidget(r, 2)
                    w_price = self.tbl_product_lines.cellWidget(r, 3)
                    if w_cant and w_price:
                        subtotal_usd += w_cant.value() * w_price.value()

            # Si no hay items en ninguna tabla, usar los campos de entrada (comportamiento legacy/edición simple)
            # Solo si subtotal es 0 y no hay items en la lista legacy.
            # (Si hay items en la nueva tabla, subtotal_usd > 0 o al menos se intentó sumar)
            # Ajuste: Si la tabla nueva tiene filas, NO usar el fallback.
            has_new_items = hasattr(self, 'tbl_product_lines') and self.tbl_product_lines.rowCount() > 0
            
            if not self._items_data and not has_new_items:
                try:
                    qty = float(self.edt_cantidad.text().replace(",", "."))
                except:
                    qty = 0.0
                subtotal_usd = self.edt_precio_unitario.value() * qty

            # Extras
            diseno = self.edt_diseno.value() if self.chk_incluye_diseno.isChecked() else 0.0
            inst = self.edt_inst.value() if hasattr(self, 'edt_inst') and self.chk_incluye_inst.isChecked() else 0.0
            
            # Subtotal base antes de descuento
            subtotal_bruto = subtotal_usd + diseno + inst
            
            # Descuento (Porcentaje)
            porcentaje_desc = self.out_descuento.value()
            monto_descuento = subtotal_bruto * (porcentaje_desc / 100.0)
            
            # Base imponible
            base_imponible = max(0.0, subtotal_bruto - monto_descuento)
            
            # IVA
            iva = 0.0
            if self.chk_iva.isChecked():
                iva = base_imponible * 0.16
            
            total_usd = base_imponible + iva
            
            # Actualizar campos de salida
            self.out_subtotal.setValue(subtotal_usd)
            self.out_descuento_monto.setValue(monto_descuento)
            self.out_iva.setValue(iva)
            if hasattr(self, 'out_iva_subtotal'): self.out_iva_subtotal.setValue(iva)
            self.out_total.setValue(total_usd)
            
            # Calcular restante
            abono = self.edt_abono.value()
            restante = max(0.0, total_usd - abono)
            self.out_restante.setValue(restante)
            
            # Update new payment section totals if it exists
            if hasattr(self, '_update_payment_totals'):
                self._update_payment_totals()
                
        except Exception:
            pass

    # --- Data binding ---
    def get_data(self) -> dict:
        try:
            # 1. Gather Items from tbl_product_lines
            items = []
            if hasattr(self, 'tbl_product_lines'):
                for r in range(self.tbl_product_lines.rowCount()):
                    cmb_prod = self.tbl_product_lines.cellWidget(r, 0)
                    w_desc = self.tbl_product_lines.cellWidget(r, 1)
                    w_cant = self.tbl_product_lines.cellWidget(r, 2)
                    w_price_usd = self.tbl_product_lines.cellWidget(r, 3)
                    w_price_bs = self.tbl_product_lines.cellWidget(r, 4)
                    w_total_bs = self.tbl_product_lines.cellWidget(r, 5)
                    
                    if not (cmb_prod and w_cant and w_price_usd):
                        continue
                        
                    prod_name = cmb_prod.currentText()
                    if not prod_name or prod_name.startswith('----'):
                        continue
                        
                    qty = w_cant.value()
                    price_usd = w_price_usd.value()
                    total_usd = qty * price_usd
                    
                    # Retrieve payload from item data (col 0)
                    item_widget = self.tbl_product_lines.item(r, 0)
                    payload = item_widget.data(Qt.UserRole) if item_widget else None
                    
                    items.append({
                        'product_name': prod_name,
                        'quantity': qty,
                        'unit_price': price_usd,
                        'total_price': total_usd,
                        'total_bs': w_total_bs.value() if w_total_bs else 0.0,
                        'details': payload or {},
                        'description': w_desc.text() if w_desc else ""  # Use 'description' key to match repository expectation
                    })
            
            # Fallback to legacy _items_data if new table is empty (just in case)
            if not items and self._items_data:
                items = list(self._items_data)

            # 2. Gather Payments from tbl_payments
            payments = []
            if hasattr(self, 'tbl_payments'):
                for r in range(self.tbl_payments.rowCount()):
                    cmb_method = self.tbl_payments.cellWidget(r, 0)
                    w_bs = self.tbl_payments.cellWidget(r, 1)
                    w_usd = self.tbl_payments.cellWidget(r, 2)
                    w_bank = self.tbl_payments.cellWidget(r, 3)
                    w_ref = self.tbl_payments.cellWidget(r, 4)
                    
                    if not cmb_method: continue
                    method = cmb_method.currentText()
                    if not method or method.startswith('----'): continue
                    
                    # Extract Bank / Serial info safely from LineEdit or ComboBox
                    bank_info = ""
                    if isinstance(w_bank, QLineEdit):
                        bank_info = w_bank.text()
                    elif isinstance(w_bank, QComboBox):
                        bank_info = w_bank.currentText()

                    payments.append({
                        'payment_method': method,
                        'amount_bs': w_bs.value() if w_bs else 0.0,
                        'amount_usd': w_usd.value() if w_usd else 0.0,
                        'bank': bank_info,
                        'reference': w_ref.text() if w_ref else "",
                        'serial_billete': bank_info, # Legacy support
                        'exchange_rate': self.edt_tasa_bcv_payments.value() if hasattr(self, 'edt_tasa_bcv_payments') else 0.0
                    })

            # 3. Determine main article name
            if len(items) > 1:
                # Join names, truncate if too long
                names = [i['product_name'] for i in items]
                articulo = ", ".join(names)
                if len(articulo) > 190: # Limit for DB column
                    articulo = articulo[:187] + "..."
            elif items:
                articulo = items[0]['product_name']
            else:
                articulo = "Venta General"

            # 4. Calculate Totals from Payments
            total_monto_bs = sum(p.get('amount_bs', 0.0) for p in payments)
            total_abono_usd = sum(p.get('amount_usd', 0.0) for p in payments)
            
            # Legacy Payment Fields (take first payment or defaults for display, but totals for amounts)
            first_pay = payments[0] if payments else {}
            forma_pago = first_pay.get('payment_method', "")
            # If multiple payments, maybe indicate mixed? For now, just first method is fine as legacy fallback.
            if len(payments) > 1:
                forma_pago = "Múltiples"
            
            banco = first_pay.get('bank', "")
            referencia = first_pay.get('reference', "")
            
            # 5. Construct Result
            return {
                "articulo": articulo,
                "items": items,
                "payments": payments, # New field
                "asesor": self.lbl_asesor.text(),
                "venta_usd": f"{self.out_total.value():.2f}",
                "forma_pago": forma_pago,
                "serial_billete": "",
                "banco": banco,
                "referencia": referencia,
                "fecha_pago": self.edt_fecha_pago.date().toString("yyyy-MM-dd"),
                "fecha_pago_2": self.edt_fecha_pago_2.date().toString("yyyy-MM-dd"),
                "monto_bs": f"{total_monto_bs:.2f}", # Sum of all Bs payments
                "monto_usd": f"{total_abono_usd:.2f}", # Sum of all USD payments (legacy field name often used for abono)
                "abono_usd": f"{total_abono_usd:.2f}", # Sum of all USD payments
                "iva": f"{self.out_iva.value():.2f}",
                "iva_aplicado": self.chk_iva.isChecked(),
                "diseno_usd": f"{self.edt_diseno.value():.2f}",
                "incluye_diseno": self.chk_incluye_diseno.isChecked(),
                "ingresos_usd": f"{self.edt_inst.value():.2f}" if hasattr(self, 'edt_inst') else "0.00", # Map INST to ingresos_usd
                "descripcion": self.edt_descripcion.text(),
                "subtotal_usd": f"{self.out_subtotal.value():.2f}",
                "total_usd": f"{self.out_total.value():.2f}",
                "restante_usd": f"{self.out_restante_payments.value():.2f}" if hasattr(self, 'out_restante_payments') else "0.00",
                "notas": self.edt_notas.text(),
                "cliente": self.edt_cliente.currentText(),
                "cliente_id": str(self.edt_cliente.currentData() or ""),
                "tasa_bcv": f"{self.edt_tasa_bcv.value():.2f}",
                # Legacy fields
                "precio_unitario": "0.00",
                "precio_unitario_bs": "0.00",
                "cantidad": "0.00",
                "total_bs": "0.00",
            }
        except Exception as e:
            print(f"Error in get_data: {e}")
            return {}

    @staticmethod
    def build_corporeo_computed(payload: dict | None, summary: dict | None = None, *, total_bs: float | None = None) -> dict:
        """Construir el diccionario `computed` para persistir configuraciones corpóreas.

        Extrae campos útiles desde el payload aceptado por `CorporeoDialog` y
        complementa valores con el resumen calculado por el diálogo (si se
        proporciona). Cualquier conversión que falle se ignora de forma segura.
        """
        computed: dict = {}
        if not isinstance(payload, dict):
            return computed

        meta = payload.get('meta') if isinstance(payload.get('meta'), dict) else {}
        if meta:
            try:
                if meta.get('cliente_id') is not None:
                    computed['cliente_id'] = int(meta.get('cliente_id'))
            except Exception:
                pass
            try:
                if meta.get('order_number'):
                    computed['order_number'] = str(meta.get('order_number'))
            except Exception:
                pass

        soporte = payload.get('soporte') if isinstance(payload.get('soporte'), dict) else {}
        if soporte:
            try:
                if soporte.get('qty') is not None:
                    computed['soporte_qty'] = int(soporte.get('qty'))
            except Exception:
                pass
            try:
                if soporte.get('model_id') is not None:
                    computed['soporte_model_id'] = int(soporte.get('model_id'))
            except Exception:
                pass
            try:
                if soporte.get('price') is not None:
                    computed['soporte_price'] = float(soporte.get('price'))
            except Exception:
                pass

        luces = payload.get('luces') if isinstance(payload.get('luces'), dict) else {}
        if luces:
            try:
                if luces.get('posicion'):
                    computed['posicion_luz'] = str(luces.get('posicion'))
            except Exception:
                pass
            selected = luces.get('selected') if isinstance(luces.get('selected'), list) else []
            if selected:
                first = selected[0] or {}
                try:
                    if first.get('pv_id') is not None:
                        computed['luz_pv_id'] = int(first.get('pv_id'))
                except Exception:
                    pass
                try:
                    if first.get('price') is not None:
                        computed['luz_price'] = float(first.get('price'))
                except Exception:
                    pass

        totals = payload.get('totals') if isinstance(payload.get('totals'), dict) else {}
        try:
            total_usd = totals.get('total_usd')
            if total_usd is None and isinstance(summary, dict):
                total_usd = summary.get('total')
            if total_usd is not None:
                computed['precio_total_usd'] = float(total_usd)
        except Exception:
            pass
        try:
            total_bs_val = totals.get('total_bs')
            if total_bs_val is None:
                total_bs_val = total_bs
            if total_bs_val is not None:
                computed['precio_total_bs'] = float(total_bs_val)
        except Exception:
            pass

        # Persistir precios finales y tasas para futuras ediciones
        try:
            precio_final_usd = None
            if isinstance(summary, dict) and summary.get('precio_final_usd') is not None:
                precio_final_usd = float(summary.get('precio_final_usd'))
            elif payload.get('precio_final_usd') is not None:
                precio_final_usd = float(payload.get('precio_final_usd'))
            elif (payload.get('totals') or {}).get('total_usd') is not None:
                precio_final_usd = float(payload['totals']['total_usd'])
            if precio_final_usd is not None:
                computed['precio_final_usd'] = precio_final_usd
        except Exception:
            pass

        try:
            precio_final_bs = None
            if isinstance(summary, dict) and summary.get('precio_final_bs') is not None:
                precio_final_bs = float(summary.get('precio_final_bs'))
            elif payload.get('precio_final_bs') is not None:
                precio_final_bs = float(payload.get('precio_final_bs'))
            elif (payload.get('totals') or {}).get('total_bs') is not None:
                precio_final_bs = float(payload['totals']['total_bs'])
            if precio_final_bs is not None:
                computed['precio_final_bs'] = precio_final_bs
        except Exception:
            pass

        try:
            tasa_bcv_val = None
            if isinstance(summary, dict) and summary.get('tasa_bcv') is not None:
                tasa_bcv_val = float(summary.get('tasa_bcv'))
            elif payload.get('tasa_bcv') is not None:
                tasa_bcv_val = float(payload.get('tasa_bcv'))
            elif (payload.get('totals') or {}).get('tasa_bcv') is not None:
                tasa_bcv_val = float(payload['totals']['tasa_bcv'])
            if tasa_bcv_val is not None:
                computed['tasa_bcv'] = tasa_bcv_val
        except Exception:
            pass

        try:
            tasa_corp = None
            if isinstance(summary, dict) and summary.get('tasa_corporeo') is not None:
                tasa_corp = float(summary.get('tasa_corporeo'))
            elif payload.get('tasa_corporeo') is not None:
                tasa_corp = float(payload.get('tasa_corporeo'))
            elif (payload.get('totals') or {}).get('tasa_corporeo') is not None:
                tasa_corp = float(payload['totals']['tasa_corporeo'])
            if tasa_corp is not None:
                computed['tasa_corporeo'] = tasa_corp
        except Exception:
            pass

        return computed

    def set_data(self, data: dict) -> None:
        try:
            # 0. Orden (si existe)
            if v := data.get("numero_orden"):
                if hasattr(self, 'lbl_orden'):
                    self.lbl_orden.setText(v)

            # 1. Asesor
            if v := data.get("asesor"):
                if hasattr(self, 'lbl_asesor'):
                    self.lbl_asesor.setText(v)

            # 2. Cliente
            cid = data.get("cliente_id") or data.get("clienteId")
            cname = data.get("cliente")
            handled = False
            try:
                if cid is not None and str(cid).strip().isdigit():
                    target = int(str(cid).strip())
                    for i in range(self.edt_cliente.count()):
                        try:
                            if self.edt_cliente.itemData(i) == target:
                                self.edt_cliente.setCurrentIndex(i)
                                try:
                                    self._on_customer_changed(i)
                                except Exception:
                                    pass
                                handled = True
                                break
                        except Exception:
                            continue
            except Exception:
                pass
            if not handled and cname:
                try:
                    self.edt_cliente.setCurrentText(cname)
                    idx = self.edt_cliente.findText(cname)
                    if idx >= 0:
                        self.edt_cliente.setCurrentIndex(idx)
                        try:
                            self._on_customer_changed(idx)
                        except Exception:
                            pass
                except Exception:
                    try:
                        self.edt_cliente.setCurrentText(cname or '')
                    except Exception:
                        pass

            # 3. Tasa BCV
            if v := data.get("tasa_bcv"):
                try:
                    val = float(v)
                    self.edt_tasa_bcv.setValue(val)
                    if hasattr(self, 'edt_tasa_bcv_payments'):
                        self.edt_tasa_bcv_payments.setValue(val)
                except: pass

            # 4. Items (Product Lines)
            self.tbl_product_lines.setRowCount(0)
            items = data.get("items")
            if items and isinstance(items, list) and len(items) > 0:
                for item in items:
                    self._on_add_product_line()
                    row = self.tbl_product_lines.rowCount() - 1
                    
                    cmb_prod = self.tbl_product_lines.cellWidget(row, 0)
                    pname = item.get('product_name', '')
                    idx = cmb_prod.findText(pname)
                    if idx >= 0:
                        cmb_prod.setCurrentIndex(idx)
                    
                    # 1. Description
                    w_desc = self.tbl_product_lines.cellWidget(row, 1)
                    if w_desc:
                        w_desc.setText(item.get('description') or item.get('descripcion') or '')

                    # 2. Quantity
                    w_cant = self.tbl_product_lines.cellWidget(row, 2)
                    try: w_cant.setValue(float(item.get('quantity', 1.0)))
                    except: pass
                    
                    # 3. Price USD
                    w_price_usd = self.tbl_product_lines.cellWidget(row, 3)
                    try: w_price_usd.setValue(float(item.get('unit_price', 0.0)))
                    except: pass
                    
                    if item.get('details'):
                        it = self.tbl_product_lines.item(row, 0)
                        if it:
                            it.setData(Qt.UserRole, item.get('details'))
            else:
                # Legacy fallback
                art = data.get("articulo")
                if art:
                    self._on_add_product_line()
                    row = self.tbl_product_lines.rowCount() - 1
                    cmb_prod = self.tbl_product_lines.cellWidget(row, 0)
                    idx = cmb_prod.findText(art)
                    if idx >= 0:
                        cmb_prod.setCurrentIndex(idx)
                    
                    # 1. Description (Legacy fallback usually doesn't have description, but we can try)
                    w_desc = self.tbl_product_lines.cellWidget(row, 1)
                    if w_desc:
                        w_desc.setText(data.get('descripcion') or '')

                    # 2. Quantity
                    w_cant = self.tbl_product_lines.cellWidget(row, 2)
                    try: w_cant.setValue(float(data.get("cantidad", 1.0)))
                    except: pass
                    
                    # 3. Price USD
                    w_price_usd = self.tbl_product_lines.cellWidget(row, 3)
                    try: w_price_usd.setValue(float(data.get("precio_unitario", 0.0)))
                    except: pass
                    
                    # Restore payload if available (from _corporeo_payload attribute set by caller)
                    if hasattr(self, '_corporeo_payload') and self._corporeo_payload:
                        it = self.tbl_product_lines.item(row, 0)
                        if it:
                            it.setData(Qt.UserRole, self._corporeo_payload)

            # 5. Payments
            if hasattr(self, 'tbl_payments'):
                self.tbl_payments.setRowCount(0)
                payments = data.get("payments")
                if payments and isinstance(payments, list) and len(payments) > 0:
                    for pay in payments:
                        self._on_add_payment_row()
                        row = self.tbl_payments.rowCount() - 1
                        
                        cmb_method = self.tbl_payments.cellWidget(row, 0)
                        idx = cmb_method.findText(pay.get('payment_method', ''))
                        if idx >= 0: cmb_method.setCurrentIndex(idx)
                        
                        w_bs = self.tbl_payments.cellWidget(row, 1)
                        try: w_bs.setValue(float(pay.get('amount_bs', 0.0)))
                        except: pass
                        
                        w_usd = self.tbl_payments.cellWidget(row, 2)
                        try: w_usd.setValue(float(pay.get('amount_usd', 0.0)))
                        except: pass
                        
                        w_bank = self.tbl_payments.cellWidget(row, 3)
                        w_bank.setText(pay.get('bank', '') or pay.get('serial_billete', '') or '')
                        
                        w_ref = self.tbl_payments.cellWidget(row, 4)
                        w_ref.setText(pay.get('reference', ''))
                else:
                    # Legacy fallback
                    forma = data.get("forma_pago")
                    if forma:
                        self._on_add_payment_row()
                        row = self.tbl_payments.rowCount() - 1
                        
                        cmb_method = self.tbl_payments.cellWidget(row, 0)
                        idx = cmb_method.findText(forma)
                        if idx >= 0: cmb_method.setCurrentIndex(idx)
                        
                        w_bs = self.tbl_payments.cellWidget(row, 1)
                        try: w_bs.setValue(float(data.get("monto_bs", 0.0)))
                        except: pass
                        
                        w_usd = self.tbl_payments.cellWidget(row, 2)
                        try: w_usd.setValue(float(data.get("abono_usd", 0.0)))
                        except: pass
                        
                        w_bank = self.tbl_payments.cellWidget(row, 3)
                        w_bank.setText(data.get("banco") or data.get("serial_billete") or "")
                        
                        w_ref = self.tbl_payments.cellWidget(row, 4)
                        w_ref.setText(data.get("referencia") or "")

            # 6. Extras
            if v := data.get("diseno_usd"):
                self.edt_diseno.setValue(float(v))
            if v := data.get("incluye_diseno"):
                self.chk_incluye_diseno.setChecked(str(v) in ("1", "true", "True"))
            if v := data.get("ingresos_usd"):
                self.edt_ingresos.setValue(float(v))
            if v := data.get("descripcion"):
                self.edt_descripcion.setText(v)
            if v := data.get("notas"):
                self.edt_notas.setText(v)
            
            # 7. Fechas
            if v := data.get("fecha_pago"):
                dt = QDate.fromString(v, "yyyy-MM-dd")
                if dt.isValid():
                    self.edt_fecha_pago.setDate(dt)

            # If we are provided with a flag that indicates we're editing an existing sale,
            # enable the 'Editar Corpóreo' button so the user can directly edit the stored
            # corpóreo configuration. SaleView sets dlg._editing_sale_id before calling set_data.
            try:
                editing = getattr(self, '_editing_sale_id', None)
                if editing:
                    try:
                        if hasattr(self, 'btn_edit_corporeo'):
                            self.btn_edit_corporeo.setEnabled(True)
                    except Exception:
                        pass
                    # disable the generic 'Configurar' to indicate we're in edit flow
                    try:
                        if hasattr(self, 'btn_configurar'):
                            self.btn_configurar.setEnabled(False)
                    except Exception:
                        pass
            except Exception:
                pass

            # Recalcular todo
            self._update_totals()
        except Exception as e:
            print(f"Error setting data: {e}")
            pass

    def _on_edit_corporeo(self) -> None:
        """Open the CorporeoDialog prefilled with the existing payload for editing.

        This handler expects that `self._corporeo_payload` was set by the caller
        (e.g., `SalesView._on_edit_sale`) when the dialog was created for editing.
        After the user accepts the Corporeo dialog, update the description/price fields
        accordingly and store the payload to `_corporeo_payload` so it will be persisted
        when the sale is saved.
        """
        try:
            prev = getattr(self, '_corporeo_payload', None)
            
            # Si no hay payload en memoria, intentar cargarlo de la BD
            if prev is None and getattr(self, '_editing_sale_id', None):
                try:
                    from ..repository import (
                        get_corporeo_payload_by_sale,
                        get_corporeo_by_sale,
                        get_order_for_sale,
                    )
                    sf_local = self._ensure_session_factory()
                    if sf_local is not None:
                        with sf_local() as s:
                            # Intentar cargar de corporeo_payloads
                            try:
                                cp = get_corporeo_payload_by_sale(s, int(getattr(self, '_editing_sale_id')))
                                if cp and getattr(cp, 'payload_json', None):
                                    import json as _json
                                    try:
                                        prev = _json.loads(cp.payload_json)
                                        print(f"[DEBUG] Payload cargado desde corporeo_payloads: {list(prev.keys()) if prev else None}")
                                        if isinstance(prev, dict):
                                            self._corporeo_payload = prev
                                    except Exception as e:
                                        print(f"[DEBUG] Error parseando payload_json: {e}")
                                        prev = None
                            except Exception as e:
                                print(f"[DEBUG] Error cargando corporeo_payload: {e}")
                                prev = None
                            
                            # Fallback a corporeo_configs si no hay corporeo_payloads
                            if prev is None:
                                try:
                                    cfg = get_corporeo_by_sale(s, int(getattr(self, '_editing_sale_id')))
                                    if cfg and getattr(cfg, 'payload_json', None):
                                        import json as _json
                                        prev = _json.loads(cfg.payload_json)
                                        print(f"[DEBUG] Payload cargado desde corporeo_configs: {list(prev.keys()) if prev else None}")
                                        if isinstance(prev, dict):
                                            self._corporeo_payload = prev
                                except Exception as e:
                                    print(f"[DEBUG] Error cargando corporeo_config: {e}")
                                    prev = None

                            # Fallback a order.details_json si no hay corporeo_payloads
                            if prev is None:
                                try:
                                    order = get_order_for_sale(s, int(getattr(self, '_editing_sale_id')))
                                    if order and getattr(order, 'details_json', None):
                                        try:
                                            import json as _json
                                            prev = _json.loads(order.details_json)
                                            print(f"[DEBUG] Payload cargado desde order.details_json: {list(prev.keys()) if prev else None}")
                                            if isinstance(prev, dict):
                                                self._corporeo_payload = prev
                                        except Exception as e:
                                            print(f"[DEBUG] Error parseando order details_json: {e}")
                                            prev = None
                                except Exception as e:
                                    print(f"[DEBUG] Error cargando order: {e}")
                                    pass
                except Exception as e:
                    print(f"[DEBUG] Error general cargando payload: {e}")
                    prev = getattr(self, '_corporeo_payload', None)
            
            if prev is None:
                QMessageBox.information(self, "Editar Corpóreo", "No hay configuración corpórea cargada para editar.")
                return
            
            # Log del payload para debugging
            print(f"[DEBUG] Payload a editar tiene claves: {list(prev.keys()) if isinstance(prev, dict) else 'No es dict'}")
            if isinstance(prev, dict):
                print(f"[DEBUG] product_id en payload: {prev.get('product_id')}")
                print(f"[DEBUG] cortes en payload: {prev.get('cortes')}")
            # Determine type_id and product_id as in _configure_corporeo
            sf = self._ensure_session_factory()
            if sf is None:
                QMessageBox.critical(self, "Editar Corpóreo", "No hay conexión a la base de datos.")
                return
            type_id = None
            try:
                with sf() as s:
                    types = eav_list_types(s)
                    for t in types:
                        key = self._norm_text(getattr(t, 'key', '') or '')
                        name = self._norm_text(getattr(t, 'name', '') or '')
                        if 'corp' in key or 'corp' in name:
                            type_id = int(getattr(t, 'id'))
                            break
            except Exception:
                type_id = None
            if not isinstance(type_id, int):
                QMessageBox.warning(self, "Editar Corpóreo", "No se encontró el tipo 'Corpóreo' para editar.")
                return
            # Obtener product_id: priorizar payload, luego combo
            prod_id = None
            
            # Prioridad 1: product_id del payload (más confiable cuando se edita)
            if isinstance(prev, dict) and prev.get('product_id'):
                try:
                    prod_id = int(prev.get('product_id'))
                    print(f"[DEBUG] product_id obtenido del payload: {prod_id}")
                except Exception:
                    prod_id = None
            
            # Prioridad 2: product_id del combo (si el usuario lo cambió)
            if prod_id is None:
                try:
                    prod_id = self.edt_articulo.currentData()
                    if not isinstance(prod_id, int):
                        prod_id = None
                    else:
                        print(f"[DEBUG] product_id obtenido del combo: {prod_id}")
                except Exception:
                    prod_id = None
            
            # Prioridad 3: intentar inferir de estructuras anidadas en payload
            if prod_id is None and isinstance(prev, dict):
                try:
                    pid = (prev.get('meta') or {}).get('product_id')
                    if pid is None and isinstance(prev.get('items'), list) and prev.get('items'):
                        pid = prev.get('items')[0].get('product_id')
                    if pid is not None:
                        try:
                            prod_id = int(pid)
                            print(f"[DEBUG] product_id inferido de estructuras anidadas: {prod_id}")
                        except Exception:
                            prod_id = None
                except Exception:
                    pass
            
            if prod_id:
                print(f"[DEBUG] Abriendo CorporeoDialog con product_id={prod_id}")
            else:
                print(f"[DEBUG] ⚠️ Abriendo CorporeoDialog SIN product_id")

            from .corporeo_dialog import CorporeoDialog
            dlg = CorporeoDialog(sf, type_id=type_id, product_id=prod_id, initial_payload=prev)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                # update description/price if configurator returned values
                try:
                    summary = dlg.get_pricing_summary() or {}
                    # Use los valores calculados por el dialogo corpóreo
                    precio_configurado = summary.get('precio_final_usd')
                    precio_corporeo_bs = summary.get('precio_final_bs')
                    tasa_bcv_config = summary.get('tasa_bcv')

                    # Fallback to find the precio_final_usd in the accepted_data payload if not in summary
                    if precio_configurado is None and hasattr(dlg, 'accepted_data'):
                        payload = getattr(dlg, 'accepted_data', {})
                        if isinstance(payload, dict):
                            if payload.get('precio_final_usd') is not None:
                                precio_configurado = float(payload.get('precio_final_usd'))
                            elif payload.get('total') is not None:
                                # Fallback legacy: use total if precio_final_usd not present
                                precio_configurado = float(payload.get('total'))
                            elif (payload.get('totals') or {}).get('total_usd') is not None:
                                precio_configurado = float(payload['totals']['total_usd'])
                            if precio_corporeo_bs is None and payload.get('precio_final_bs') is not None:
                                precio_corporeo_bs = float(payload.get('precio_final_bs'))
                            if tasa_bcv_config is None:
                                if payload.get('tasa_bcv') is not None:
                                    tasa_bcv_config = float(payload.get('tasa_bcv'))
                                elif (payload.get('totals') or {}).get('tasa_bcv') is not None:
                                    tasa_bcv_config = float(payload['totals']['tasa_bcv'])

                    # Determinar las tasas y montos finales
                    tasa_bcv_final = None
                    try:
                        tasa_bcv_final = float(tasa_bcv_config) if tasa_bcv_config is not None else None
                    except Exception:
                        tasa_bcv_final = None
                    if tasa_bcv_final is None or tasa_bcv_final <= 0:
                        tasa_bcv_final = self.edt_tasa_bcv.value() or 36.0

                    # Si no tenemos USD pero sí Bs, estimar el USD dividiendo por la tasa
                    if precio_configurado is None and precio_corporeo_bs is not None and tasa_bcv_final:
                        try:
                            precio_configurado = float(precio_corporeo_bs) / float(tasa_bcv_final)
                        except Exception:
                            precio_configurado = None

                    if precio_configurado is not None:
                        self.edt_precio_unitario.setValue(float(precio_configurado))

                    if precio_corporeo_bs is None and precio_configurado is not None:
                        try:
                            precio_corporeo_bs = float(precio_configurado) * float(tasa_bcv_final)
                        except Exception:
                            precio_corporeo_bs = None

                    if precio_corporeo_bs is not None:
                        self._precio_corporeo_tasa_bcv = float(precio_corporeo_bs)
                        self._is_corporeo_product = True  # Marcar que es producto corpóreo

                        # Mostrar el precio final corpóreo en Bs (con tooltip del equivalente USD)
                        tooltip_usd = f"${float(precio_configurado):.2f}" if precio_configurado is not None else "N/D"
                        self.lbl_precio_final_corporeo.setText(f"Bs {self._precio_corporeo_tasa_bcv:,.2f}")
                        self.lbl_precio_final_corporeo.setToolTip(f"Equivalente USD: {tooltip_usd}")
                        self.lbl_precio_final_corporeo.setVisible(True)
                        self.lbl_precio_final_corporeo_label.setVisible(True)
                    else:
                        self._precio_corporeo_tasa_bcv = 0.0
                        self._is_corporeo_product = False
                        self.lbl_precio_final_corporeo.setVisible(False)
                        self.lbl_precio_final_corporeo_label.setVisible(False)
                except Exception:
                    pass
                # update description
                try:
                    if hasattr(dlg, 'build_config_summary'):
                        self.edt_descripcion.setText(dlg.build_config_summary())
                    else:
                        self.edt_descripcion.setText(summary.get('descripcion', ''))
                except Exception:
                    pass
                # store payload for later persistence
                try:
                    if getattr(dlg, 'accepted_data', None):
                        self._corporeo_payload = dlg.accepted_data
                except Exception:
                    pass
                # Persist the accepted payload into DB similar to new-sale flow
                try:
                    if getattr(dlg, 'accepted_data', None):
                        from ..repository import add_corporeo_payload, add_corporeo_config
                        sf_local = self._ensure_session_factory()
                        if sf_local is not None:
                            with sf_local() as s:
                                try:
                                    add_corporeo_payload(s, sale_id=getattr(self, '_editing_sale_id', None), order_id=getattr(dlg, '_draft_order_id', None), order_number=None, product_id=prod_id, payload=dlg.accepted_data)
                                except Exception:
                                    pass
                                try:
                                    # computed fields for add_corporeo_config
                                    computed = {}
                                    comp = getattr(dlg, 'accepted_data', {}) or {}
                                    try:
                                        computed['soporte_qty'] = int((comp.get('soporte') or {}).get('qty') or 0)
                                    except Exception:
                                        pass
                                    try:
                                        luz = (comp.get('luces') or {}).get('selected')
                                        if isinstance(luz, list) and luz:
                                            first = luz[0]
                                            computed['luz_pv_id'] = int(first.get('pv_id')) if first.get('pv_id') is not None else None
                                            computed['luz_price'] = float(first.get('price')) if first.get('price') is not None else None
                                    except Exception:
                                        pass
                                    try:
                                        computed['posicion_luz'] = (comp.get('luces') or {}).get('posicion')
                                    except Exception:
                                        pass
                                    try:
                                        computed['precio_total_usd'] = float((comp.get('totals') or {}).get('total_usd') or 0.0)
                                    except Exception:
                                        computed['precio_total_usd'] = None
                                    try:
                                        computed['precio_total_bs'] = float((comp.get('totals') or {}).get('total_bs') or 0.0)
                                    except Exception:
                                        computed['precio_total_bs'] = None
                                    try:
                                        add_corporeo_config(s, sale_id=getattr(self, '_editing_sale_id', None), order_id=getattr(dlg, '_draft_order_id', None), product_id=prod_id, payload=dlg.accepted_data, computed=computed)
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                except Exception:
                    pass
        except Exception as e:
            QMessageBox.critical(self, "Editar Corpóreo", f"Error abriendo el editor corpóreo:\n{e}")

    def _resolve_current_user(self) -> str | None:
        if hasattr(self, '_current_user_override') and self._current_user_override:
            return self._current_user_override
        return "admin"

    def _ensure_session_factory(self) -> sessionmaker | None:
        """Garantiza que exista un session_factory reutilizable."""
        if self._session_factory is not None:
            return self._session_factory
        try:
            engine = make_engine()
            self._session_factory = make_session_factory(engine)
            return self._session_factory
        except Exception:
            return None

    # --- Cliente: helpers ---
    def _on_customer_changed(self, index: int) -> None:
        try:
            cid = self.edt_cliente.itemData(index)
            if cid is None:
                self._clear_customer_details()
                return
            c = self._customers_by_id.get(int(cid)) if hasattr(self, "_customers_by_id") else None
            if not c:
                self._clear_customer_details()
                return
            doc = (getattr(c, 'document', None) or '').strip() or '—'
            phone = (getattr(c, 'phone', None) or '').strip() or '—'
            addr = (getattr(c, 'short_address', None) or '').strip() or '—'
            email = (getattr(c, 'email', None) or '').strip() or '—'
            self._set_customer_details(doc, phone, addr, email)
        except Exception:
            self._clear_customer_details()

    def _on_new_customer(self) -> None:
        """Abre el diálogo para crear un cliente y lo agrega a la lista si se guarda."""
        dlg = CustomerDialog(self)
        dlg.setWindowTitle("Nuevo cliente")
        if not dlg.exec():
            return
        data = dlg.get_data()
        sf = self._ensure_session_factory()
        if sf is None:
            QMessageBox.critical(self, "Error", "No hay conexión a la base de datos para crear el cliente.")
            return
        try:
            with sf() as session:
                cust = Customer(
                    name=(data.get("first_name") or ""),
                    first_name=data.get("first_name"),
                    last_name=data.get("last_name"),
                    document=data.get("document"),
                    short_address=data.get("short_address"),
                    phone=data.get("phone"),
                    email=data.get("email"),
                )
                add_customers(session, [cust])
                # Ahora en memoria tenemos 'cust' con ID si la sesión lo refresca; add_customers hace commit.
                # Recuperar ID desde la base por si acaso
                session.refresh(cust)
                cid = int(getattr(cust, 'id'))
                # Preparar etiqueta
                label = (cust.name or "").strip() or f"{(cust.first_name or '').strip()} {(cust.last_name or '').strip()}".strip()
                if not label:
                    label = f"Cliente #{cid}"
                # Registrar en caché y combo
                self._customers_by_id[cid] = cust
                self.edt_cliente.addItem(label, cid)
                self.edt_cliente.setCurrentIndex(self.edt_cliente.count() - 1)
                # Actualizar panel de detalles
                self._set_customer_details(
                    document=(cust.document or ""),
                    phone=(cust.phone or ""),
                    address=(cust.short_address or ""),
                    email=(cust.email or ""),
                )
                QMessageBox.information(self, "Cliente", "Cliente creado correctamente")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo crear el cliente:\n{e}")

    def _clear_customer_details(self) -> None:
        try:
            if hasattr(self, 'lbl_cli_doc'):
                self.lbl_cli_doc.setText('—')
            if hasattr(self, 'lbl_cli_phone'):
                self.lbl_cli_phone.setText('—')
            if hasattr(self, 'lbl_cli_addr'):
                self.lbl_cli_addr.setText('—')
            if hasattr(self, 'lbl_cli_email'):
                self.lbl_cli_email.setText('—')
        except Exception:
            pass

    def _set_customer_details(self, document: str, phone: str, address: str, email: str) -> None:
        try:
            self.lbl_cli_doc.setText(document or '—')
            self.lbl_cli_phone.setText(phone or '—')
            self.lbl_cli_addr.setText(address or '—')
            self.lbl_cli_email.setText(email or '—')
        except Exception:
            pass

    # --- Configuración de producto ---
    def _on_configurar_producto(self) -> None:
        try:
            prod_name = (self.edt_articulo.currentText() or '').strip()
            if not prod_name or prod_name.startswith('----'):
                QMessageBox.information(self, "Configurar", "Seleccione un producto primero.")
                return
            # Normalizar nombre para detectar tipo de producto
            name_l_pre = self._norm_text(prod_name)
            
            # Priorizar formulario especializado de Corpóreo si el nombre lo indica
            if 'corp' in name_l_pre:
                self._configure_corporeo()
                return
            
            # Detectar Talonario
            if 'talonario' in name_l_pre or 'talon' in name_l_pre:
                self._configure_talonario()
                return
            
            # Intentar configurador dinámico basado en tablas del módulo de productos
            prod_id = None
            try:
                prod_id = self.edt_articulo.currentData()
                if not isinstance(prod_id, int):
                    prod_id = None
            except Exception:
                prod_id = None
            if prod_id is not None:
                try:
                    from .. import repository as _repo
                    sf = self._ensure_session_factory()
                    if sf is not None:
                        with sf() as s:
                            tables = _repo.get_product_parameter_tables(s, prod_id)
                        if tables:
                            from .product_config_dialog import ProductConfigDialog
                            dlg = ProductConfigDialog(sf, product_id=prod_id)
                            dlg_result = dlg.exec()
                            if dlg_result:
                                summary = dlg.get_pricing_summary() or {}
                                total_usd = float(summary.get('total', 0.0) or 0.0)
                                if total_usd > 0.0:
                                    self.edt_precio_unitario.setValue(total_usd)
                                if not (self.edt_cantidad.text() or '').strip():
                                    self.edt_cantidad.setText('1.00')
                                # Descripción del configurador dinámico
                                if desc := summary.get('descripcion'):
                                    self.edt_descripcion.setText(str(desc))
                                self._calc_total_bs(); self._update_totals()
                            # Siempre retornar si se mostró el formulario dinámico,
                            # incluso si fue Cancelar, para no abrir el fallback
                            return
                except Exception:
                    # Continuar con fallback si falla el dinámico
                    pass
            # Fallback: mensaje orientativo si no hay formulario
            QMessageBox.information(
                self,
                "Configurar",
                f"El producto '{prod_name}' aún no tiene formulario dinámico.\n"
                "Abre el módulo de Productos → Parámetros para definir tablas/relaciones y habilitarlo."
            )
        except Exception as e:
            QMessageBox.critical(self, "Configurar", f"No se pudo abrir el configurador:\n{e}")
    
    def _configure_talonario(self) -> None:
        """Abrir diálogo de configuración de Talonario."""
        try:
            sf = self._ensure_session_factory()
            if sf is None:
                QMessageBox.critical(self, "Configurar", "No hay conexión a la base de datos.")
                return
            
            # Obtener product_id del combo
            prod_id = None
            try:
                prod_id = self.edt_articulo.currentData()
                if not isinstance(prod_id, int):
                    prod_id = None
            except Exception:
                prod_id = None
            
            # Preparar datos iniciales si estamos editando
            initial_data = {}
            if prod_id:
                initial_data['product_id'] = prod_id
            
            # Abrir diálogo
            from .talonario_dialog import TalonarioDialog
            dlg = TalonarioDialog(sf, parent=self, initial_data=initial_data)
            
            if dlg.exec():
                # Recuperar datos aceptados
                data = dlg.accepted_data
                if data:
                    # Actualizar precio unitario con el total calculado
                    total = float(data.get('precio_total', 0.0))
                    if total > 0.0:
                        self.edt_precio_unitario.setValue(total)
                    
                    # Actualizar cantidad si no está configurada
                    if not (self.edt_cantidad.text() or '').strip():
                        self.edt_cantidad.setText('1.00')
                    
                    # Crear descripción resumida
                    desc_parts = [
                        f"Tipo: {data.get('tipo_talonario_nombre', 'N/A')}",
                        f"Impresión: {data.get('impresion_nombre', 'N/A')}",
                        f"Cantidad: {data.get('cantidad', 1)}"
                    ]
                    descripcion = " | ".join(desc_parts)
                    self.edt_descripcion.setText(descripcion)
                    
                    # Recalcular totales
                    self._calc_total_bs()
                    self._update_totals()
        except Exception as e:
            QMessageBox.critical(self, "Configurar Talonario", f"Error al configurar talonario:\n{e}")


    def _configure_corporeo(self) -> None:
        # Resolver type_id para corpóreo (EAV)
        sf = self._ensure_session_factory()
        if sf is None:
            QMessageBox.critical(self, "Configurar", "No hay conexión a la base de datos.")
            return
        type_id = None
        try:
            with sf() as s:
                types = eav_list_types(s)
                for t in types:
                    key = self._norm_text(getattr(t, 'key', '') or '')
                    name = self._norm_text(getattr(t, 'name', '') or '')
                    if 'corp' in key or 'corp' in name:
                        type_id = int(getattr(t, 'id'))
                        break
                # Si no existe, intentar crearlo automáticamente
                if not isinstance(type_id, int):
                    try:
                        from ..repository import ensure_corporeo_eav
                        type_id = ensure_corporeo_eav(s)
                    except Exception:
                        type_id = None
        except Exception:
            type_id = None
        if not isinstance(type_id, int):
            QMessageBox.warning(self, "Configurar", "No se encontró el tipo de producto 'Corpóreo' y no se pudo crear automáticamente.")
            return
        # Pasar el ID del producto configurable seleccionado (si existe)
        try:
            prod_id = self.edt_articulo.currentData()
            if not isinstance(prod_id, int):
                prod_id = None
        except Exception:
            prod_id = None
        # No reintentar el dinámico aquí: este método es el fallback específico de Corpóreo
        try:
            from .corporeo_dialog import CorporeoDialog
            # pass previous payload if exists so the user can edit
            prev = getattr(self, '_corporeo_payload', None)
            
            # Log para debugging
            if prev:
                print(f"[DEBUG _configure_corporeo] Payload previo encontrado con claves: {list(prev.keys()) if isinstance(prev, dict) else 'No es dict'}")
                if isinstance(prev, dict):
                    print(f"[DEBUG _configure_corporeo] product_id en payload: {prev.get('product_id')}")
                    print(f"[DEBUG _configure_corporeo] cortes en payload: {prev.get('cortes')}")
            else:
                print(f"[DEBUG _configure_corporeo] ⚠️ NO HAY payload previo (_corporeo_payload es None)")
            
            # If no product id was found in the combo, try to infer it from a previously
            # attached payload (when opening from edit). Many payloads include a
            # 'product_id' or a nested 'meta' with product identifiers.
            try:
                if prod_id is None and isinstance(prev, dict):
                    pid = None
                    if prev.get('product_id'):
                        pid = prev.get('product_id')
                    else:
                        meta = prev.get('meta') if isinstance(prev.get('meta'), dict) else {}
                        if meta:
                            pid = meta.get('product_id') or meta.get('productId') or meta.get('product_id')
                        # fallback to items[0].product_id
                        if pid is None:
                            items = prev.get('items') if isinstance(prev.get('items'), list) else None
                            if items and isinstance(items[0], dict):
                                pid = items[0].get('product_id') or items[0].get('productId')
                    try:
                        if pid is not None:
                            # normalize to int when possible
                            prod_id = int(pid)
                    except Exception:
                        pass
            except Exception:
                pass
            # If no prev and we are editing a sale, try to load from corporeo_payloads
            try:
                if prev is None and getattr(self, '_editing_sale_id', None):
                    from ..repository import get_corporeo_payload_by_sale
                    with sf() as s:
                        cp = get_corporeo_payload_by_sale(s, int(getattr(self, '_editing_sale_id')))
                        if cp and getattr(cp, 'payload_json', None):
                            try:
                                import json as _json
                                prev = _json.loads(cp.payload_json)
                                if isinstance(prev, dict):
                                    self._corporeo_payload = prev
                            except Exception:
                                prev = None
            except Exception:
                pass
            try:
                if prev is None and getattr(self, '_editing_sale_id', None):
                    from ..repository import get_order_for_sale
                    with sf() as s:
                        order = get_order_for_sale(s, int(getattr(self, '_editing_sale_id')))
                        if order and getattr(order, 'details_json', None):
                            try:
                                import json as _json
                                prev = _json.loads(order.details_json)
                                if isinstance(prev, dict):
                                    self._corporeo_payload = prev
                            except Exception:
                                prev = None
            except Exception:
                pass
            # Do not reserve a draft order. The configurator will return payload
            # to the caller and the order should be created at sale save time so it
            # shares the definitive sale order_number.
            draft_order_id = None
            print(f"[DEBUG _configure_corporeo] Creando CorporeoDialog con:")
            print(f"  - product_id: {prod_id}")
            print(f"  - initial_payload: {'Sí' if prev else 'No'}")
            dlg = CorporeoDialog(sf, type_id=type_id, product_id=prod_id, initial_payload=prev)
            # Do not attach a draft order id.
            try:
                setattr(dlg, '_draft_order_id', None)
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, "Configurar", f"No se pudo cargar el configurador:\n{e}")
            return
        if dlg.exec():
            # Recuperar totales calculados y aplicar al precio unitario
            try:
                summary = dlg.get_pricing_summary()
                total_usd = float(summary.get('total', 0.0)) if isinstance(summary, dict) else 0.0
            except Exception:
                summary = {}
                total_usd = 0.0
            if total_usd <= 0.0:
                # Como fallback, tratar de leer desde labels
                try:
                    txt = getattr(dlg, 'lbl_total').text()
                    total_usd = float(str(txt).replace(',', '').strip())
                except Exception:
                    total_usd = 0.0
            # Establecer precio unitario y descripción detallada
            try:
                if total_usd > 0.0:
                    self.edt_precio_unitario.setValue(total_usd)
                if not (self.edt_cantidad.text() or '').strip():
                    self.edt_cantidad.setText('1.00')
                # Usar resumen detallado tipo lista
                if hasattr(dlg, 'build_config_summary'):
                    resumen = dlg.build_config_summary()
                    self.edt_descripcion.setText(resumen)
                else:
                    # Fallback a descripción compacta
                    desc = summary.get('descripcion', '')
                    self.edt_descripcion.setText(desc)
            except Exception:
                pass
            # Store the full payload returned by the configurator so subsequent edits keep values
            try:
                payload_dict = getattr(dlg, 'accepted_data', None)
                if payload_dict:
                    print(f"[DEBUG _configure_corporeo] Guardando payload en _corporeo_payload")
                    print(f"  Claves: {list(payload_dict.keys()) if isinstance(payload_dict, dict) else 'No es dict'}")
                    self._corporeo_payload = payload_dict
                    try:
                        import json as _json
                        print(f"  Payload completo: {_json.dumps(self._corporeo_payload, ensure_ascii=False)}")
                    except Exception:
                        print("  (No se pudo serializar el payload para debug)")

                    # habilitar el botón de edición para que el usuario pueda reabrir
                    # el configurador reutilizando el payload recién generado
                    try:
                        if hasattr(self, 'btn_edit_corporeo'):
                            self.btn_edit_corporeo.setEnabled(True)
                    except Exception:
                        pass

                    # Persist payload/config únicamente cuando estamos editando una venta existente
                    sale_id_ctx = getattr(self, '_editing_sale_id', None) if hasattr(self, '_editing_sale_id') else None
                    order_id_ctx = getattr(dlg, '_draft_order_id', None)
                    if sale_id_ctx is not None:
                        try:
                            from ..repository import add_corporeo_payload
                            sf_local = self._ensure_session_factory()
                            if sf_local is not None:
                                with sf_local() as s:
                                    product_for_payload = None
                                    try:
                                        if isinstance(payload_dict, dict):
                                            product_for_payload = payload_dict.get('product_id')
                                            if not product_for_payload and isinstance(payload_dict.get('meta'), dict):
                                                product_for_payload = payload_dict['meta'].get('product_id')
                                            if product_for_payload is not None:
                                                product_for_payload = int(product_for_payload)
                                    except Exception:
                                        product_for_payload = None
                                    add_corporeo_payload(
                                        s,
                                        sale_id=int(sale_id_ctx),
                                        order_id=order_id_ctx,
                                        order_number=None,
                                        product_id=product_for_payload,
                                        payload=payload_dict,
                                    )
                        except Exception:
                            pass

                        try:
                            from ..repository import add_corporeo_config, get_order_for_sale
                            sf_local = self._ensure_session_factory()
                            if sf_local is not None:
                                with sf_local() as s:
                                    # Intentar recuperar número de orden existente para enriquecer el computed
                                    order_number_ctx = None
                                    try:
                                        existing_order = get_order_for_sale(s, int(sale_id_ctx))
                                        if existing_order:
                                            order_number_ctx = getattr(existing_order, 'order_number', None)
                                            if order_id_ctx is None:
                                                order_id_ctx = int(getattr(existing_order, 'id'))
                                    except Exception:
                                        order_number_ctx = None

                                    computed = self.build_corporeo_computed(payload_dict, summary=summary, total_bs=self.edt_total_bs.value())
                                    if order_number_ctx and not computed.get('order_number'):
                                        computed['order_number'] = order_number_ctx

                                    product_for_config = None
                                    try:
                                        product_for_config = payload_dict.get('product_id')
                                        if not product_for_config and isinstance(payload_dict.get('meta'), dict):
                                            product_for_config = payload_dict['meta'].get('product_id')
                                        if product_for_config is not None:
                                            product_for_config = int(product_for_config)
                                    except Exception:
                                        product_for_config = None

                                    add_corporeo_config(
                                        s,
                                        sale_id=int(sale_id_ctx),
                                        order_id=order_id_ctx,
                                        product_id=product_for_config,
                                        payload=payload_dict,
                                        computed=computed,
                                    )
                        except Exception:
                            pass

                # if we reserved a draft order earlier, persist payload into it now
                try:
                    d_id = getattr(dlg, '_draft_order_id', None)
                    if d_id is not None:
                        from ..repository import update_order
                        sf_local = self._ensure_session_factory()
                        if sf_local is not None:
                            with sf_local() as s:
                                update_order(s, int(d_id), details_json=json.dumps(dlg.accepted_data, ensure_ascii=False))
                except Exception:
                    # ignore failure to persist draft
                    pass
                # Also persist a CorporeoConfig record for easier reloading
                try:
                    from ..repository import add_corporeo_config
                    sf_local = self._ensure_session_factory()
                    if sf_local is not None:
                        with sf_local() as s:
                            # Prepare computed fields safely usando helper reutilizable
                            computed = self.build_corporeo_computed(payload_dict, summary=summary, total_bs=self.edt_total_bs.value())
                            sale_id_ctx = getattr(self, '_editing_sale_id', None) if hasattr(self, '_editing_sale_id') else None
                            order_id_ctx = d_id
                            try:
                                add_corporeo_config(s, sale_id=sale_id_ctx, order_id=order_id_ctx, product_id=prod_id, payload=payload_dict, computed=computed)
                            except Exception:
                                pass
                except Exception:
                    pass
                # Do NOT write the raw JSON payload into the description field; keep the human-readable
                # summary already placed above (resumen or desc). The payload will be persisted separately
                # when the sale is created.
            except Exception:
                pass
            # Recalcular montos
            self._calc_total_bs()
            self._update_totals()
