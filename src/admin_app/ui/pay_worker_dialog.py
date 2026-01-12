from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QDoubleSpinBox, 
    QLineEdit, QPushButton, QRadioButton, QButtonGroup, QGroupBox, 
    QMessageBox, QComboBox, QWidget, QSpinBox, QHBoxLayout, QScrollArea
)
from PySide6.QtCore import Qt
from datetime import datetime
from ..repository import get_worker, get_bcv_rate

class CashDenominationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.denominations = [1, 5, 10, 20, 50, 100]
        self.rows = []
        
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Billete</b>"), 1)
        header.addWidget(QLabel("<b>Cant.</b>"), 1)
        header.addWidget(QLabel("<b>Seriales (sep. por coma)</b>"), 3)
        layout.addLayout(header)
        
        for denom in self.denominations:
            row_layout = QHBoxLayout()
            lbl = QLabel(f"$ {denom}")
            spin = QSpinBox()
            spin.setRange(0, 500)
            txt_serial = QLineEdit()
            txt_serial.setPlaceholderText("Ej: A12345678, B87654321")
            
            row_layout.addWidget(lbl, 1)
            row_layout.addWidget(spin, 1)
            row_layout.addWidget(txt_serial, 3)
            
            layout.addLayout(row_layout)
            self.rows.append({
                "denom": denom,
                "spin": spin,
                "serial": txt_serial
            })
            
    def get_details(self):
        data = []
        for r in self.rows:
            qty = r["spin"].value()
            if qty > 0:
                data.append({
                    "denomination": r["denom"],
                    "quantity": qty,
                    "serials": r["serial"].text()
                })
        return data

class PayWorkerDialog(QDialog):
    def __init__(self, session_factory, worker_id: int, account_text: str, period: str, estimated_usd: float, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.worker_id = worker_id
        self.account_text = account_text
        self.setWindowTitle(f"Procesar Pago {period}")
        self.resize(550, 650)
        
        self.rate = get_bcv_rate()
        
        # Load Worker Data safely
        self.worker_data = {}
        with self.session_factory() as session:
            worker = get_worker(session, self.worker_id)
            if worker:
                self.worker_data = {
                    "full_name": worker.full_name,
                    "cedula": worker.cedula,
                    "bank_account": worker.bank_account,
                    "pago_movil_cedula": worker.pago_movil_cedula,
                    "pago_movil_phone": worker.pago_movil_phone,
                    "pago_movil_bank": worker.pago_movil_bank
                }
            
        if not self.worker_data:
            QMessageBox.critical(self, "Error", "Trabajador no encontrado")
            self.reject()
            return
            
        layout = QVBoxLayout(self)
        
        # --- Worker Info Block ---
        grp_info = QGroupBox("Datos del Trabajador")
        l_info = QFormLayout(grp_info)
        l_info.addRow("Nombre:", QLabel(self.worker_data["full_name"]))
        l_info.addRow("Cédula:", QLabel(self.worker_data["cedula"] or "N/A"))
        layout.addWidget(grp_info)

        # --- Payment Source ---
        layout.addWidget(QLabel(f"<b>Cuenta origen:</b> {account_text}"))
        
        # --- Payment Method ---
        grp_method = QGroupBox("Método de Pago")
        v_method = QVBoxLayout(grp_method)
        
        self.cb_method = QComboBox()
        self.cb_method.addItems([
            "Transferencia Bs", 
            "Pago Móvil", 
            "Efectivo USD", 
            "Efectivo Bs", 
            "Binance", 
            "Zelle"
        ])
        
        # Signals
        self.cb_method.currentIndexChanged.connect(self._update_bank_details)
        
        v_method.addWidget(self.cb_method)
        layout.addWidget(grp_method)
        
        # --- Dynamic Banking Details ---
        self.grp_details = QGroupBox("Datos Bancarios / Detalles")
        self.layout_details = QFormLayout(self.grp_details)
        layout.addWidget(self.grp_details)
        
        # Reference Field (Dynamic)
        self.w_ref_container = QWidget()
        l_ref = QFormLayout(self.w_ref_container)
        l_ref.setContentsMargins(0,0,0,0)
        self.txt_reference = QLineEdit()
        self.txt_reference.setPlaceholderText("Mínimo 4 dígitos")
        l_ref.addRow("Referencia / Comprobante:", self.txt_reference)
        layout.addWidget(self.w_ref_container)

        # Cash USD Details (Hidden by default)
        self.cash_widget = CashDenominationWidget()
        self.cash_widget.setVisible(False)
        layout.addWidget(self.cash_widget)
        
        # --- Amounts ---
        grp_amount = QGroupBox("Monto")
        l_amount = QFormLayout(grp_amount)
        
        self.spin_usd = QDoubleSpinBox()
        self.spin_usd.setRange(0, 100000.0)
        self.spin_usd.setPrefix("$ ")
        self.spin_usd.setValue(estimated_usd)
        self.spin_usd.valueChanged.connect(self._recalc_bs)
        
        self.lbl_rate = QLabel(f"{self.rate:.2f} Bs/$")
        
        self.spin_bs = QDoubleSpinBox()
        self.spin_bs.setRange(0, 100000000.0)
        self.spin_bs.setPrefix("Bs. ")
        self.spin_bs.setReadOnly(True)
        self.spin_bs.setButtonSymbols(QDoubleSpinBox.NoButtons)
        
        l_amount.addRow("Monto (USD):", self.spin_usd)
        l_amount.addRow("Tasa BCV:", self.lbl_rate)
        l_amount.addRow("Equivalente (Bs):", self.spin_bs)
        
        layout.addWidget(grp_amount)
        
        # --- Note ---
        layout.addWidget(QLabel("Nota / Concepto:"))
        self.txt_note = QLineEdit()
        self.txt_note.setText(f"Pago de Nómina {period} - {datetime.now().strftime('%d/%m')}")
        layout.addWidget(self.txt_note)
        
        # --- Buttons ---
        btn_confirm = QPushButton("Confirmar Pago")
        btn_confirm.setProperty("accent", "primary")
        btn_confirm.clicked.connect(self.accept)
        btn_confirm.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        
        layout.addWidget(btn_confirm)
        
        # Init state
        self._update_bank_details()
        self._recalc_bs()

    def _update_bank_details(self):
        method = self.cb_method.currentText()
        
        # Reset visibility
        self.w_ref_container.setVisible(True)
        self.cash_widget.setVisible(False)
        self.grp_details.setVisible(True)
        
        # Clear previous layout rows
        while self.layout_details.rowCount() > 0:
            self.layout_details.removeRow(0)
            
        if method == "Transferencia Bs":
            self.grp_details.setTitle("Datos Transferencia Bancaria")
            acc = self.worker_data.get("bank_account") or "No registrado"
            self.layout_details.addRow("Nro. Cuenta:", QLabel(acc))
            
        elif method == "Pago Móvil":
            self.grp_details.setTitle("Datos Pago Móvil")
            pm_cedula = self.worker_data.get("pago_movil_cedula") or "N/A"
            pm_phone = self.worker_data.get("pago_movil_phone") or "N/A"
            pm_bank = self.worker_data.get("pago_movil_bank") or "N/A"
            
            self.layout_details.addRow("Banco:", QLabel(pm_bank))
            self.layout_details.addRow("Cédula:", QLabel(pm_cedula))
            self.layout_details.addRow("Teléfono:", QLabel(pm_phone))
            
        elif method == "Efectivo USD":
            self.grp_details.setVisible(False)
            self.w_ref_container.setVisible(False) # No reference needed for cash usually, but serials are in the widget
            self.cash_widget.setVisible(True)
            
        elif method == "Efectivo Bs":
            self.grp_details.setTitle("Datos Efectivo Bs")
            self.w_ref_container.setVisible(False)
            self.layout_details.addRow(QLabel("Pago en efectivo (Bolívares)"))
            
        elif method in ["Binance", "Zelle"]:
            self.grp_details.setTitle(f"Datos {method}")
            # Assuming we don't store Binance/Zelle address for worker yet, or use Email/Phone
            # For now just show a label
            self.layout_details.addRow(QLabel(f"Realizar pago vía {method}"))

    def _recalc_bs(self):
        usd = self.spin_usd.value()
        bs = usd * self.rate
        self.spin_bs.setValue(bs)
        
    def accept(self):
        method = self.cb_method.currentText()
        
        # Validation
        if self.w_ref_container.isVisible():
            ref = self.txt_reference.text().strip()
            if len(ref) < 4:
                QMessageBox.warning(self, "Validación", "El número de referencia debe tener al menos 4 dígitos.")
                return

        # Consistency Validation (Account vs Method)
        acc_str = self.account_text.lower()
        met_str = method.lower()
        
        # 1. Cash vs Non-Cash
        is_acc_cash = "efectivo" in acc_str or "caja" in acc_str
        is_met_cash = "efectivo" in met_str
        
        if is_acc_cash and not is_met_cash:
            QMessageBox.critical(self, "Error de Consistencia", 
                f"Estás pagando desde una cuenta de <b>Efectivo</b>, pero seleccionaste <b>{method}</b>.<br>"
                "Por favor selecciona un método de Efectivo o cambia la cuenta origen.")
            return

        if not is_acc_cash and is_met_cash:
             QMessageBox.critical(self, "Error de Consistencia", 
                f"Estás pagando con <b>Efectivo</b>, pero la cuenta origen es <b>{self.account_text}</b>.<br>"
                "Si retiraste el dinero del banco, primero registra una transferencia a la Caja/Efectivo.")
             return

        # 2. Crypto / Zelle Specifics
        if "binance" in acc_str and "binance" not in met_str:
            QMessageBox.critical(self, "Error", "Si la cuenta es Binance, el método debe ser Binance.")
            return
            
        if "zelle" in acc_str and "zelle" not in met_str:
            QMessageBox.critical(self, "Error", "Si la cuenta es Zelle, el método debe ser Zelle.")
            return
                
        super().accept()

    def get_data(self):
        method = self.cb_method.currentText()
        ref = self.txt_reference.text().strip() if self.w_ref_container.isVisible() else ""
        
        cash_details = []
        if method == "Efectivo USD":
            cash_details = self.cash_widget.get_details()
            # If serial reference is needed in main description, we can format it
            if cash_details:
                ref = "Efectivo" # Or detailed summary
        
        return {
            "amount_usd": self.spin_usd.value(),
            "amount_bs": self.spin_bs.value(),
            "note": self.txt_note.text(),
            "method": method,
            "reference": ref,
            "cash_details": cash_details
        }
