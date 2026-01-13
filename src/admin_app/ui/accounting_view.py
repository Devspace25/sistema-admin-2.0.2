from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QDateEdit, QComboBox, QLineEdit, 
    QDialog, QFormLayout, QMessageBox, QTabWidget, QGroupBox, QDoubleSpinBox,
    QFrame
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont
from datetime import datetime

from ..models import Account, Transaction, TransactionCategory, Worker, AccountsPayable, Supplier
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QDateEdit, QComboBox, QLineEdit, 
    QDialog, QFormLayout, QMessageBox, QTabWidget, QGroupBox, QDoubleSpinBox,
    QFrame, QCheckBox, QTextEdit, QGridLayout
)
from sqlalchemy import or_, not_

class AccountingView(QWidget):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        
        layout = QVBoxLayout(self)
        
        # Title
        header = QHBoxLayout()
        lbl_title = QLabel("Contabilidad y Finanzas")
        lbl_title.setObjectName("HeaderTitle")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 600; color: #e5e7eb; margin-bottom: 10px;")
        header.addWidget(lbl_title)
        
        # Refresh Dashboard Button
        btn_refresh = QPushButton("Actualizar")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self.refresh_dashboard)
        header.addStretch()
        header.addWidget(btn_refresh)
        
        layout.addLayout(header)
        
        # Dashboard Summary
        self.dashboard_layout = QHBoxLayout()
        self.dashboard_layout.setSpacing(15) # Better spacing between cards
        layout.addLayout(self.dashboard_layout)
        self.refresh_dashboard()

        # Tabs
        self.tabs = QTabWidget()
        # Remove manual stylesheet to let QSS handle it, or minimal adjustments
        self.tabs.setStyleSheet("QTabWidget::pane { border: 1px solid #243244; }")
        
        self.income_expenses_tab = IncomeExpensesManager(session_factory, self)
        self.transactions_tab = TransactionsManager(session_factory, self)
        self.accounts_tab = AccountsManager(session_factory, self)
        
        self.tabs.addTab(self.income_expenses_tab, "Ingresos vs Egresos")
        self.tabs.addTab(self.transactions_tab, "Movimientos (Log)")
        self.tabs.addTab(self.accounts_tab, "Cuentas")
        
        layout.addWidget(self.tabs)
        
        # Signals to refresh dashboard when data changes
        self.transactions_tab.data_changed.connect(self.refresh_dashboard)
        self.transactions_tab.data_changed.connect(self.accounts_tab.refresh)
        self.transactions_tab.data_changed.connect(self.income_expenses_tab.load_data)

    def refresh_dashboard(self):
        # Clear existing widgets in layout
        while self.dashboard_layout.count():
            item = self.dashboard_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        # Fetch accounts
        with self.session_factory() as session:
            accounts = session.query(Account).filter(Account.is_active == True).all()
            
            # Use a Horizontal Layout with a Scroll Area if needed, or just add them.
            # But QHBoxLayout doesn't wrap. 
            # We'll use a container widget with a Flow Layout logic simulation 
            # or just a Grid Layout wrapped in a widget.
            
            # Since we can't easily implement FlowLayout, let's use a nice ScrollArea 
            # with a horizontal layout of cards.
            
            from PySide6.QtWidgets import QScrollArea
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("background: transparent; border: none;")
            scroll.setFixedHeight(140) # Limit height for the dashboard strip
            
            container = QWidget()
            container.setStyleSheet("background: transparent;")
            # Use HBox for a horizontal strip of cards
            h_layout = QHBoxLayout(container)
            h_layout.setSpacing(15)
            h_layout.setContentsMargins(0, 0, 0, 0)
            
            # 1. Add Total Summaries (Optional, user liked them initially but asked for Bank Names)
            # User said "quiero son unas tarjeta... con los nombres de los banco"
            # Maybe we can have Totals as special cards at the start.
            
            total_usd = sum(a.balance for a in accounts if a.currency == 'USD')
            total_bs = sum(a.balance for a in accounts if a.currency == 'VES')
            
            h_layout.addWidget(self._create_simple_card("Total USD", f"${total_usd:,.2f}", "#2ecc71"))
            h_layout.addWidget(self._create_simple_card("Total Bs", f"Bs. {total_bs:,.2f}", "#3498db"))
            
            # Separator card or just space?
            line = QFrame()
            line.setFrameShape(QFrame.VLine)
            line.setStyleSheet("color: #444;")
            h_layout.addWidget(line)
            
            # 2. Add Individual Bank Cards
            # Sort: USD then VES
            sorted_accs = sorted(accounts, key=lambda x: (x.currency, x.name))
            
            for acc in sorted_accs:
                # Color code by currency
                color = "#2ecc71" if acc.currency == 'USD' else "#3498db"
                symbol = "$" if acc.currency == 'USD' else "Bs."
                
                val_str = f"{symbol} {acc.balance:,.2f}"
                
                # Create Card
                card = self._create_simple_card(acc.name, val_str, color)
                h_layout.addWidget(card)
                
            h_layout.addStretch()
            
            scroll.setWidget(container)
            self.dashboard_layout.addWidget(scroll)

    def _create_simple_card(self, title, value, color):
        card = QFrame()
        # Neutral Dark Background (matches Main Window usually)
        # Using #2b2b2b as standard neutral dark, removing blue tint.
        card.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border: 1px solid #3f3f46;
                border-radius: 8px;
            }
        """)
        card.setFixedSize(200, 100)
        
        l = QVBoxLayout(card)
        l.setSpacing(5)
        l.setContentsMargins(15, 15, 15, 15)
        
        lbl_t = QLabel(title)
        # Truncate title if too long
        font_t = QFont()
        font_t.setPointSize(10)
        lbl_t.setFont(font_t)
        lbl_t.setStyleSheet("color: #94a3b8; border: none; background: transparent;")
        
        lbl_v = QLabel(value)
        font_v = QFont()
        font_v.setPointSize(16)
        font_v.setBold(True)
        lbl_v.setFont(font_v)
        lbl_v.setStyleSheet(f"color: {color}; border: none; background: transparent;")
        
        l.addWidget(lbl_t)
        l.addWidget(lbl_v)
        return card


class IncomeExpensesManager(QWidget):
    """Gestor separado de ingresos y egresos."""
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        layout = QVBoxLayout(self)

        # Filters
        filter_layout = QHBoxLayout()
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate().addDays(-30))
        btn_refresh = QPushButton("Actualizar")
        btn_refresh.clicked.connect(self.load_data)
        
        filter_layout.addWidget(QLabel("Desde:"))
        filter_layout.addWidget(self.date_filter)
        filter_layout.addWidget(btn_refresh)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Layout Split: Left (Income), Right (Expenses)
        # Or Top (Income), Bottom (Expenses). User said "Una pestaña... ver los ingresos".
        # Side by side helps compare.
        split_layout = QHBoxLayout()
        
        # --- Income Section ---
        grp_inc = QGroupBox("Ingresos")
        grp_inc.setStyleSheet("QGroupBox { border: 1px solid #2ecc71; margin-top: 10px; } QGroupBox::title { color: #2ecc71; }")
        l_inc = QVBoxLayout(grp_inc)
        self.table_inc = QTableWidget()
        self.table_inc.setColumnCount(4)
        self.table_inc.setHorizontalHeaderLabels(["Fecha", "Descripción", "Monto", "Cuenta"])
        self.table_inc.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        l_inc.addWidget(self.table_inc)
        self.lbl_total_inc = QLabel("Total: 0.00")
        self.lbl_total_inc.setStyleSheet("font-weight: bold; color: #2ecc71; font-size: 14px;")
        l_inc.addWidget(self.lbl_total_inc, 0, Qt.AlignmentFlag.AlignRight)
        split_layout.addWidget(grp_inc)
        
        # --- Expense Section ---
        grp_exp = QGroupBox("Egresos")
        grp_exp.setStyleSheet("QGroupBox { border: 1px solid #e74c3c; margin-top: 10px; } QGroupBox::title { color: #e74c3c; }")
        l_exp = QVBoxLayout(grp_exp)
        self.table_exp = QTableWidget()
        self.table_exp.setColumnCount(4)
        self.table_exp.setHorizontalHeaderLabels(["Fecha", "Descripción", "Monto", "Cuenta"])
        self.table_exp.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        l_exp.addWidget(self.table_exp)
        self.lbl_total_exp = QLabel("Total: 0.00")
        self.lbl_total_exp.setStyleSheet("font-weight: bold; color: #e74c3c; font-size: 14px;")
        l_exp.addWidget(self.lbl_total_exp, 0, Qt.AlignmentFlag.AlignRight)
        split_layout.addWidget(grp_exp)
        
        layout.addLayout(split_layout)
        self.load_data()

    def load_data(self):
        start_date = datetime.combine(self.date_filter.date().toPython(), datetime.min.time())
        with self.session_factory() as session:
            # Fetch all transactons
            txns = session.query(Transaction).filter(Transaction.date >= start_date).order_by(Transaction.date.desc()).all()
            
            incomes = [t for t in txns if t.transaction_type == 'INCOME']
            expenses = [t for t in txns if t.transaction_type == 'EXPENSE']
            
            self._fill_table(self.table_inc, incomes, "#2ecc71")
            self._fill_table(self.table_exp, expenses, "#e74c3c")
            
            # Totals (approximate mixing currencies just for visuals or separate?)
            # Ideally separate totals by currency.
            # Let's show multiline label.
            self.lbl_total_inc.setText(self._calc_totals(incomes))
            self.lbl_total_exp.setText(self._calc_totals(expenses))

    def _fill_table(self, table, data, color_hex):
        table.setRowCount(len(data))
        for i, t in enumerate(data):
            table.setItem(i, 0, QTableWidgetItem(t.date.strftime("%d/%m")))
            table.setItem(i, 1, QTableWidgetItem(t.description))
            
            curr = t.account.currency if t.account else ""
            amt = QTableWidgetItem(f"{curr} {t.amount:,.2f}")
            amt.setForeground(QColor(color_hex))
            table.setItem(i, 2, amt)
            
            acc = t.account.name if t.account else ""
            table.setItem(i, 3, QTableWidgetItem(acc))

    def _calc_totals(self, data):
        sum_usd = sum(t.amount for t in data if t.account and t.account.currency == 'USD')
        sum_bs = sum(t.amount for t in data if t.account and t.account.currency == 'VES')
        return f"USD: {sum_usd:,.2f} | Bs: {sum_bs:,.2f}"


class Paragraph(QWidget): # Dummy filler if needed
    pass

class TransactionsManager(QWidget):
    from PySide6.QtCore import Signal
    data_changed = Signal()

    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        # Try to resolve current user. 
        # Since we are deep in widgets without direct passing, we might need a workaround 
        # or assume parent has it.
        # But 'parent' is AccountingView -> then App -> MainWindow (usually has user info).
        # For now, we'll try to get it from parent chain or default to non-admin safe.
        self._current_user_role = "user"
        self._resolve_user_role()
        
        layout = QVBoxLayout(self)
        
        # Filters & Actions
        # Top Bar Container
        top_container = QWidget()
        # Clean transparency to let buttons stand out on their own
        top_container.setStyleSheet(".QWidget { background-color: transparent; }")
        top_layout = QHBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        # Custom "Card-like" buttons style
        # White background, subtle border, specific text colors
        btn_bg = "#ffffff"
        btn_border = "#e2e8f0" 
        
        btn_style_base = f"""
            QPushButton {{
                background-color: {btn_bg};
                border: 1px solid {btn_border};
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
                padding: 6px 16px;
                text-align: center;
                color: #374151;
            }}
            QPushButton:hover {{
                background-color: #f8fafc;
                border-color: #cbd5e1;
            }}
            QPushButton:pressed {{
                background-color: #f1f5f9;
            }}
        """

        input_style = f"""
            QDateEdit {{
                background-color: {btn_bg};
                border: 1px solid {btn_border};
                border-radius: 6px;
                font-size: 13px;
                padding: 5px;
                color: #374151;
            }}
        """

        # Left: Date Filter
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate().addDays(-30)) # Last 30 days
        self.date_filter.setFixedWidth(120)
        self.date_filter.setStyleSheet(input_style)
        
        btn_filter = QPushButton("Filtrar")
        btn_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_filter.setStyleSheet(btn_style_base)
        btn_filter.clicked.connect(self.load_data)
        
        btn_update = QPushButton("Actualizar")
        btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_update.setStyleSheet(btn_style_base)
        btn_update.clicked.connect(self.refresh_view)
        
        top_layout.addWidget(QLabel("Desde:"))
        top_layout.addWidget(self.date_filter)
        top_layout.addWidget(btn_filter)
        top_layout.addWidget(btn_update)
        top_layout.addStretch()
        
        # 1. New
        btn_add = QPushButton("➕ Nuevo Movimiento") 
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(btn_style_base + "QPushButton { color: #374151; }") 
        btn_add.clicked.connect(self.open_add_dialog)
        
        # 2. Edit
        self.btn_edit = QPushButton("✏️ Editar") # Using Pencil emoji
        self.btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit.setStyleSheet(btn_style_base + "QPushButton { color: #4b5563; }") # Gray-600 to match image
        self.btn_edit.clicked.connect(self.edit_transaction)
        self.btn_edit.setVisible(False) # Default hidden, shown if admin

        # 3. Delete
        self.btn_delete = QPushButton("🗑️ Eliminar") # Using Trash emoji
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setStyleSheet(btn_style_base + "QPushButton { color: #4b5563; }") # Gray-600
        self.btn_delete.clicked.connect(self.delete_transaction)
        self.btn_delete.setVisible(False) # Default hidden, shown if admin

        # 4. Refresh (REMOVIDO: Actualización Automática)
        # btn_refresh = QPushButton("🔄 Actualizar")
        # btn_refresh.clicked.connect(self.load_data)
        
        top_layout.addWidget(btn_add)
        top_layout.addWidget(self.btn_edit)
        top_layout.addWidget(self.btn_delete)
        # top_layout.addWidget(btn_refresh)
        
        layout.addWidget(top_container)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8) # Added hidden column for flags
        self.table.setHorizontalHeaderLabels(["ID", "Fecha", "Descripción", "Categoría", "Monto", "Cuenta", "Origen", "raw_t"])
        self.table.setColumnHidden(6, True) # Origin hidden
        self.table.setColumnHidden(7, True) # raw hidden
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        # Connect double click to edit
        self.table.itemDoubleClicked.connect(self.edit_transaction)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)
        
        # Apply permissions
        if self._current_user_role == "admin":
             self.btn_edit.setVisible(True)
             self.btn_delete.setVisible(True)
        
        self.load_data()
        
    def _resolve_user_role(self):
        # Walk up the parent chain to find main window or similar where role might be stored
        # Or look for a global if available (though dirty).
        # In this project, MainWindow usually creates views.
        p = self.parent()
        while p:
            if hasattr(p, 'current_user_role'):
                self._current_user_role = p.current_user_role
                break
            # Also check if it has a 'user' object
            if hasattr(p, 'current_user') and hasattr(p.current_user, 'role'):
                 # It might be a string or object
                 r = p.current_user.role
                 if hasattr(r, 'name'):
                     self._current_user_role = r.name
                 else:
                     self._current_user_role = str(r)
                 break
            p = p.parent()
            
        # Fallback hack: check if running app has global (only for single user desktop apps)
        # If not successful, we might default to 'admin' for dev, or 'user' for safety.
        # Given snippet '...solo lo puede hacer el admin...', we default to restricted.
        # But if we can't find the user, we might lock ourselves out.
        # Let's inspect sys.modules['__main__']? No.
        # Let's check if the parent passed in context?
        pass

    def _on_selection_changed(self):
        if self._current_user_role != 'admin':
            return

        row = self.table.currentRow()
        if row < 0:
            self.btn_edit.setEnabled(False)
            self.btn_delete.setEnabled(False)
            return

        # Check origin
        origin_item = self.table.item(row, 6)
        origin = origin_item.text() if origin_item else ""
        
        # If origin is from Sale (Sales module), disable actions
        is_sale = (origin == "sale_payments") or ("Venta:" in self.table.item(row, 2).text())
        
        self.btn_edit.setEnabled(not is_sale)
        self.btn_delete.setEnabled(not is_sale)

    def edit_transaction(self):
        if self._current_user_role != 'admin':
            QMessageBox.warning(self, "Acceso Denegado", "Solo el administrador puede editar movimientos.")
            return

        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Aviso", "Seleccione un movimiento para editar.")
            return
            
        # Check permissions on specific row
        if not self.btn_edit.isEnabled():
            QMessageBox.warning(self, "Aviso", "Este movimiento proviene de una Venta y no se puede editar aquí.\nEdite la Venta original.")
            return

        tx_id = self.table.item(row, 0).text()
        
        # Open Dialog with existing data
        # We need to modify TransactionDialog to accept an ID or use a different method
        dlg = TransactionDialog(self.session_factory, self, transaction_id=tx_id)
        if dlg.exec():
            self.load_data()
            self.data_changed.emit()

    def delete_transaction(self):
        if self._current_user_role != 'admin':
            return

        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Aviso", "Seleccione un movimiento para eliminar.")
            return

        # Check permissions on specific row
        if not self.btn_delete.isEnabled():
            QMessageBox.warning(self, "Aviso", "Este movimiento proviene de una Venta y no se puede eliminar aquí.")
            return

        tx_id = self.table.item(row, 0).text()
        desc = self.table.item(row, 2).text()
        
        confirm = QMessageBox.question(
            self, 
            "Confirmar", 
            f"¿Está seguro de eliminar el movimiento:\n'{desc}'?\n\nEsto revertirá el saldo de la cuenta.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            with self.session_factory() as session:
                txn = session.get(Transaction, tx_id)
                if txn:
                    # Revert balance
                    if txn.account:
                        if txn.transaction_type == 'INCOME':
                            txn.account.balance -= txn.amount
                        else:
                            txn.account.balance += txn.amount
                            
                    session.delete(txn)
                    session.commit()
            
            self.load_data()
            self.data_changed.emit()

    def load_data(self):
        start_date = datetime.combine(self.date_filter.date().toPython(), datetime.min.time())
        
        self.table.setRowCount(0)
        with self.session_factory() as session:
            transactions = session.query(Transaction).filter(Transaction.date >= start_date).order_by(Transaction.date.desc()).all()
            
            self.table.setRowCount(len(transactions))
            for i, t in enumerate(transactions):
                self.table.setItem(i, 0, QTableWidgetItem(str(t.id)))
                self.table.setItem(i, 1, QTableWidgetItem(t.date.strftime("%d/%m/%Y %H:%M")))
                self.table.setItem(i, 2, QTableWidgetItem(t.description))
                
                cat_name = t.category.name if t.category else "General"
                self.table.setItem(i, 3, QTableWidgetItem(cat_name))
                
                amount_str = f"{t.amount:,.2f}"
                currency = t.account.currency if t.account else ""
                
                item_amt = QTableWidgetItem(f"{currency} {amount_str}")
                if t.transaction_type == 'INCOME':
                    item_amt.setForeground(QColor("#2ecc71"))
                else:
                    item_amt.setForeground(QColor("#e74c3c"))
                    
                self.table.setItem(i, 4, item_amt)
                
                acc_name = t.account.name if t.account else "Unknown"
                self.table.setItem(i, 5, QTableWidgetItem(acc_name))

                # Hidden columns for logic
                # col 6: origin
                self.table.setItem(i, 6, QTableWidgetItem(str(t.related_table or "")))
                # col 7: raw object (not safe in item, just skip)
                
        # Trigger selection change to update buttons for initial state
        self._on_selection_changed()

    def refresh_view(self):
        """Force reload of data and notify parent to update dashboard"""
        self.load_data()
        self.data_changed.emit()

    def open_add_dialog(self):
        dlg = TransactionDialog(self.session_factory, self)
        if dlg.exec():
            self.load_data()
            self.data_changed.emit()


class AccountsManager(QWidget):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Nombre", "Tipo", "Moneda", "Saldo Actual"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        self.refresh()
        
    def refresh(self):
        self.table.setRowCount(0)
        with self.session_factory() as session:
            accounts = session.query(Account).all()
            self.table.setRowCount(len(accounts))
            for i, a in enumerate(accounts):
                self.table.setItem(i, 0, QTableWidgetItem(a.name))
                self.table.setItem(i, 1, QTableWidgetItem(a.type))
                self.table.setItem(i, 2, QTableWidgetItem(a.currency))
                self.table.setItem(i, 3, QTableWidgetItem(f"{a.balance:,.2f}"))


class TransactionDialog(QDialog):
    def __init__(self, session_factory, parent=None, transaction_id=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.transaction_id = transaction_id
        
        # Cache for balances: id -> balance
        self._account_balances = {} 
        self._account_currencies = {}
        
        title = "Editar Movimiento" if transaction_id else "Registrar Movimiento"
        self.setWindowTitle(title)
        self.resize(850, 650)
        
        # Main Layout
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(10)

        # 1. Datos de la Operación
        self.grp_data = QGroupBox("Datos de la Operación")
        grid_data = QGridLayout(self.grp_data)
        grid_data.setContentsMargins(15, 15, 15, 15)
        grid_data.setVerticalSpacing(10)
        grid_data.setHorizontalSpacing(10)
        
        grid_data.addWidget(QLabel("Tipo:"), 0, 0)
        self.cb_type = QComboBox()
        self.cb_type.addItem("------- Seleccione --------", None)
        self.cb_type.addItems(["Ingreso (INCOME)", "Egreso (EXPENSE)"])
        self.cb_type.currentIndexChanged.connect(self._on_type_changed)
        grid_data.addWidget(self.cb_type, 0, 1)
        
        grid_data.addWidget(QLabel("Categoría:"), 0, 2)
        self.cb_category = QComboBox()
        grid_data.addWidget(self.cb_category, 0, 3)
        
        grid_data.addWidget(QLabel("Descripción:"), 1, 0)
        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("Ej. Pago de Alquiler y Servicios")
        grid_data.addWidget(self.txt_desc, 1, 1, 1, 3)
        
        root.addWidget(self.grp_data)
        
        # 2. Distribución Financiera
        self.grp_payments = QGroupBox("Distribución Financiera")
        layout_payments = QVBoxLayout(self.grp_payments)
        layout_payments.setContentsMargins(15, 15, 15, 15)
        
        # Toolbar
        bar = QHBoxLayout()
        self.btn_add_line = QPushButton(" + Agregar Cuenta")
        self.btn_add_line.setFixedWidth(140)
        self.btn_add_line.clicked.connect(self._add_payment_row)
        
        self.btn_del_line = QPushButton(" Eliminar Línea")
        self.btn_del_line.setFixedWidth(140)
        self.btn_del_line.clicked.connect(self._remove_payment_row)
        
        bar.addWidget(self.btn_add_line)
        bar.addWidget(self.btn_del_line)
        bar.addStretch()
        layout_payments.addLayout(bar)
        
        # Table
        self.tbl_payments = QTableWidget()
        self.tbl_payments.setColumnCount(3)
        self.tbl_payments.setHorizontalHeaderLabels(["Cuenta / Banco", "Saldo Disponible", "Monto a Usar"])
        self.tbl_payments.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl_payments.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl_payments.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.tbl_payments.setColumnWidth(2, 120)
        self.tbl_payments.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_payments.setAlternatingRowColors(True)
        layout_payments.addWidget(self.tbl_payments)
        
        root.addWidget(self.grp_payments)

        # 3. Resumen
        self.grp_summary = QGroupBox("Resumen")
        layout_sum = QHBoxLayout(self.grp_summary)
        layout_sum.setContentsMargins(15, 10, 25, 10)
        layout_sum.addStretch()
        
        form_sum = QFormLayout()
        form_sum.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.out_total = QDoubleSpinBox()
        self.out_total.setReadOnly(True)
        self.out_total.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.out_total.setRange(0, 9999999999.99)
        self.out_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        # self.out_total.setPrefix("$ ") # Simplificado, puede variar
        self.out_total.setStyleSheet("background: transparent; border: none; font-size: 16px; font-weight: bold; color: #3498db;")
        
        form_sum.addRow("Total Operación:", self.out_total)
        layout_sum.addLayout(form_sum)
        
        root.addWidget(self.grp_summary)
        
        # 4. Buttons
        btn_box = QHBoxLayout()
        btn_box.setContentsMargins(0, 10, 0, 0)
        btn_box.addStretch()
        
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setMinimumWidth(100)
        self.btn_cancel.setMinimumHeight(35)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_save = QPushButton("Guardar Operación")
        self.btn_save.setMinimumWidth(150)
        self.btn_save.setMinimumHeight(35)
        self.btn_save.clicked.connect(self.save)

        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_save)
        
        root.addLayout(btn_box)

        self._load_combos()
        
        # Add initial row if new
        if not self.transaction_id:
            self._add_payment_row()
        else:
            self.btn_add_line.setVisible(False) 
            self.btn_del_line.setVisible(False)
            self._load_data()
            
    def _on_type_changed(self):
        pass

    def _add_payment_row(self, account_id=None, amount=0.0):
        row = self.tbl_payments.rowCount()
        self.tbl_payments.insertRow(row)
        
        # Col 0: ComboBox Accounts
        cb = QComboBox()
        cb.addItem("--- Seleccionar ---", None)
        if hasattr(self, '_account_cache_list'):
            for name, aid in self._account_cache_list:
                cb.addItem(name, aid)
        
        if account_id:
            idx = cb.findData(account_id)
            if idx >= 0: cb.setCurrentIndex(idx)
            
        cb.currentIndexChanged.connect(lambda: self._update_row_balance(cb))
        self.tbl_payments.setCellWidget(row, 0, cb)
        
        # Col 1: Read-only Label
        lbl = QLabel("--")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #aaa;")
        self.tbl_payments.setCellWidget(row, 1, lbl)
        
        # Col 2: SpinBox Amount
        spin = QDoubleSpinBox()
        spin.setRange(0.00, 10000000.0)
        spin.setValue(amount)
        spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        spin.valueChanged.connect(self._update_total_label)
        self.tbl_payments.setCellWidget(row, 2, spin)
        
        self._update_row_balance(cb)
        
    def _remove_payment_row(self):
        curr = self.tbl_payments.currentRow()
        if curr >= 0:
            self.tbl_payments.removeRow(curr)
            self._update_total_label()
        
    def _update_row_balance(self, combo: QComboBox):
        row = -1
        for r in range(self.tbl_payments.rowCount()):
            if self.tbl_payments.cellWidget(r, 0) == combo:
                row = r
                break
        if row == -1: return
        
        acc_id = combo.currentData()
        lbl_bal = self.tbl_payments.cellWidget(row, 1) 
        
        if acc_id and acc_id in self._account_balances:
            bal = self._account_balances[acc_id]
            curr = self._account_currencies.get(acc_id, "")
            lbl_bal.setText(f"{curr} {bal:,.2f}")
        else:
            lbl_bal.setText("--")
            
        self._update_total_label()

    def _update_total_label(self):
        total = 0.0
        for r in range(self.tbl_payments.rowCount()):
            spin = self.tbl_payments.cellWidget(r, 2)
            if spin:
                total += spin.value()
        self.out_total.setValue(total)

    def _load_combos(self):
        self._account_cache_list = []
        with self.session_factory() as session:
            # Categories
            self.cb_category.addItem("------- Seleccione --------", None)
            cats = session.query(TransactionCategory).all()
            for c in cats:
                self.cb_category.addItem(c.name, c.id)
            
            # Accounts Cache
            accs = session.query(Account).filter(Account.is_active == True).order_by(Account.currency, Account.name).all()
            for a in accs:
                label = f"{a.name} ({a.currency})"
                self._account_cache_list.append((label, a.id))
                self._account_balances[a.id] = a.balance
                self._account_currencies[a.id] = a.currency
                
    def _load_data(self):
        # Only loads single transaction for now (Legacy edit support)
        # If we had master-detail transactions, we would load multiple rows.
        # For now, we load the single transaction as one row.
        with self.session_factory() as session:
            txn = session.get(Transaction, self.transaction_id)
            if not txn:
                self.reject()
                return
            
            # Set Type & Category
            idx = 1 if txn.transaction_type == 'INCOME' else 2
            self.cb_type.setCurrentIndex(idx)
            
            idx_cat = self.cb_category.findData(txn.category_id)
            if idx_cat >= 0: self.cb_category.setCurrentIndex(idx_cat)
            
            self.txt_desc.setText(txn.description)
            
            # Add the row
            self._add_payment_row(txn.account_id, txn.amount)

    def save(self):
        if not self.txt_desc.text():
            QMessageBox.warning(self, "Error", "Faltan campos requeridos: Descripción")
            return
        
        t_text = self.cb_type.currentText()
        if "Seleccione" in t_text:
             QMessageBox.warning(self, "Error", "Seleccione un tipo de transacción")
             return
             
        if self.cb_category.currentData() is None:
            QMessageBox.warning(self, "Error", "Seleccione una categoría")
            return

        t_type = "INCOME" if "INCOME" in t_text else "EXPENSE"
        cat_id = self.cb_category.currentData()
        desc = self.txt_desc.text()
        
        # Collect Rows
        rows_data = []
        if self.tbl_payments.rowCount() == 0:
            QMessageBox.warning(self, "Error", "Agregue al menos una cuenta afectada")
            return

        for r in range(self.tbl_payments.rowCount()):
            cb = self.tbl_payments.cellWidget(r, 0)
            spin = self.tbl_payments.cellWidget(r, 2)
            
            acc_id = cb.currentData()
            amount = spin.value()
            
            if not acc_id: continue # skip empty lines
            if amount <= 0: continue # skip zero amounts
            
            # Validate Balance for Expense
            if t_type == "EXPENSE":
                bal = self._account_balances.get(acc_id, 0.0)
                if amount > bal:
                    acc_name = cb.currentText()
                    QMessageBox.warning(self, "Saldo Insuficiente", f"La cuenta '{acc_name}' solo tiene {bal:,.2f}")
                    return
            
            rows_data.append((acc_id, amount))
            
        if not rows_data:
            QMessageBox.warning(self, "Error", "Ingreso montos válidos y seleccione cuentas.")
            return

        # EXECUTE SAVE
        with self.session_factory() as session:
            # EDIT MODE logic for table is tricky if splitting wasn't original.
            # Assuming simple edit = delete old + create new(s)
            if self.transaction_id:
                txn = session.get(Transaction, self.transaction_id)
                if txn:
                    # Revert
                    if txn.account:
                        if txn.transaction_type == 'INCOME':
                            txn.account.balance -= txn.amount
                        else:
                            txn.account.balance += txn.amount
                    session.delete(txn)
            
            # CREATE NEW TRANSACTIONS (One per row)
            for i, (acc_id, amount) in enumerate(rows_data):
                suffix = f" ({i+1}/{len(rows_data)})" if len(rows_data) > 1 else ""
                
                new_txn = Transaction(
                    transaction_type=t_type,
                    category_id=cat_id,
                    account_id=acc_id,
                    amount=amount,
                    description=desc + suffix,
                    date=datetime.now()
                )
                session.add(new_txn)
                
                # Update Balance
                acc = session.get(Account, acc_id)
                if t_type == "INCOME":
                    acc.balance += amount
                else:
                    acc.balance -= amount
                
            session.commit()
            
        self.accept()


class PayrollManager(QWidget):
    from PySide6.QtCore import Signal
    data_changed = Signal()

    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        layout = QVBoxLayout(self)
        
        # Tabs for Payroll Types
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { width: 150px; }
        """)
        
        self.designers_tab = PayrollList(session_factory, "designers", self)
        self.general_tab = PayrollList(session_factory, "general", self)
        
        self.tabs.addTab(self.designers_tab, "Diseñadores (Semanal)")
        self.tabs.addTab(self.general_tab, "General (Quincenal)")
        
        layout.addWidget(self.tabs)
        
        # Connect signals
        self.designers_tab.payment_made.connect(self.data_changed)
        self.general_tab.payment_made.connect(self.data_changed)


class PayrollList(QWidget):
    from PySide6.QtCore import Signal
    payment_made = Signal()

    def __init__(self, session_factory, worker_type, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.worker_type = worker_type # 'designers' | 'general'
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Top Actions
        top = QHBoxLayout()
        btn_refresh = QPushButton("Actualizar Lista")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self.load_data)
        top.addWidget(btn_refresh)
        top.addStretch()
        
        # Account Selection for Payments
        top.addWidget(QLabel("Pagar desde:"))
        self.cb_account = QComboBox()
        self.cb_account.setMinimumWidth(150)
        self.cb_account.setStyleSheet("padding: 4px; background: #333; color: white;")
        top.addWidget(self.cb_account)
        
        layout.addLayout(top)
        
        # Table
        self.table = QTableWidget()
        headers = ["ID", "Nombre", "Cargo", "Teléfono"]
        if self.worker_type == "designers":
            headers.extend(["Salario Mensual", "Pago Semanal (Est.)", "Acción"])
        else:
            headers.extend(["Salario Mensual", "Pago Quincenal (Est.)", "Acción"])
            
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        self.load_data()
        self.load_accounts()

    def load_accounts(self):
        self.cb_account.clear()
        with self.session_factory() as session:
            accounts = session.query(Account).filter(Account.is_active == True).all()
            for a in accounts:
                self.cb_account.addItem(f"{a.name} ({a.currency})", a.id)

    def load_data(self):
        self.table.setRowCount(0)
        with self.session_factory() as session:
            query = session.query(Worker).filter(Worker.is_active == True)
            
            if self.worker_type == "designers":
                # Filter by job title containing 'diseñador' or similar
                query = query.filter(Worker.job_title.ilike("%diseñad%"))
            else:
                # Exclude designers and maybe others?
                # Assuming 'General' means everyone else except Designers (Payment for Delivery handled separately)
                query = query.filter(not_(Worker.job_title.ilike("%diseñad%")))
                
            workers = query.all()
            self.table.setRowCount(len(workers))
            
            for i, w in enumerate(workers):
                self.table.setItem(i, 0, QTableWidgetItem(str(w.id)))
                self.table.setItem(i, 1, QTableWidgetItem(w.full_name))
                self.table.setItem(i, 2, QTableWidgetItem(w.job_title or ""))
                self.table.setItem(i, 3, QTableWidgetItem(w.phone or ""))
                
                salary = w.salary or 0.0
                self.table.setItem(i, 4, QTableWidgetItem(f"$ {salary:,.2f}"))
                
                # Estimated Payment
                if self.worker_type == "designers":
                    est_pay = salary / 4.0 # Weekly
                else:
                    est_pay = salary / 2.0 # Bi-weekly
                    
                self.table.setItem(i, 5, QTableWidgetItem(f"$ {est_pay:,.2f}"))
                
                # Pay Button
                btn_pay = QPushButton("Pagar")
                btn_pay.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_pay.setStyleSheet("background-color: #27ae60; color: white; border-radius: 4px; padding: 4px;")
                btn_pay.clicked.connect(lambda _, wid=w.id, name=w.full_name, amount=est_pay: self.pay_worker(wid, name, amount))
                self.table.setCellWidget(i, 6, btn_pay)

    def pay_worker(self, worker_id, name, estimated_amount):
        acc_id = self.cb_account.currentData()
        if acc_id is None:
            QMessageBox.warning(self, "Error", "Seleccione una cuenta de origen.")
            return

        # Confirm Dialog
        period = "Semanal" if self.worker_type == "designers" else "Quincenal"
        
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Procesar Pago {period}")
        dlg.setStyleSheet("background-color: #222; color: white;")
        l = QFormLayout(dlg)
        
        lbl_info = QLabel(f"Trabajador: {name}\nCuenta: {self.cb_account.currentText()}")
        spin_amt = QDoubleSpinBox()
        spin_amt.setRange(0, 100000.0)
        spin_amt.setValue(estimated_amount)
        spin_amt.setPrefix("$ ")
        spin_amt.setStyleSheet("background: #444; padding: 5px;")
        
        txt_note = QLineEdit()
        txt_note.setText(f"Pago de Nómina {period} - {datetime.now().strftime('%d/%m')}")
        txt_note.setStyleSheet("background: #444; padding: 5px;")
        
        l.addRow(lbl_info)
        l.addRow("Monto a Pagar:", spin_amt)
        l.addRow("Nota / Concepto:", txt_note)
        
        btn_ok = QPushButton("Confirmar Pago")
        btn_ok.setStyleSheet("background-color: #2980b9; color: white; padding: 8px;")
        btn_ok.clicked.connect(dlg.accept)
        l.addRow(btn_ok)
        
        if dlg.exec():
            final_amount = spin_amt.value()
            note = txt_note.text()
            self._execute_payment(acc_id, final_amount, note, worker_id)

    def _execute_payment(self, account_id, amount, note, worker_id):
        with self.session_factory() as session:
            # Check Account Balance
            acc = session.query(Account).get(account_id)
            
            # Simple debit
            acc.balance -= amount
            
            # Create Transaction
            cat = session.query(TransactionCategory).filter(TransactionCategory.name == "Nómina").first()
            cat_id = cat.id if cat else None
            
            txn = Transaction(
                date=datetime.now(),
                amount=amount,
                transaction_type="EXPENSE",
                description=f"{note} (Trabajador ID: {worker_id})",
                account_id=account_id,
                category_id=cat_id,
                related_table="workers",
                related_id=worker_id
            )
            session.add(txn)
            session.commit()
            
        QMessageBox.information(self, "Éxito", "Pago registrado correctamente.")
        self.payment_made.emit()

class AccountsPayableManager(QWidget):
    from PySide6.QtCore import Signal
    data_changed = Signal()

    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        layout = QVBoxLayout(self)
        
        # Tools bar
        bar = QHBoxLayout()
        self.btn_add = QPushButton("Registrar Factura")
        self.btn_add.setProperty("accent", "primary")
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.clicked.connect(self.on_add_bill)
        
        self.btn_pay = QPushButton("Pagar Seleccionada")
        self.btn_pay.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pay.clicked.connect(self.on_pay_bill)
        
        self.chk_show_paid = QCheckBox("Mostrar Pagadas")
        self.chk_show_paid.setChecked(False)
        self.chk_show_paid.stateChanged.connect(self.load_data)

        bar.addWidget(self.btn_add)
        bar.addWidget(self.btn_pay)
        bar.addStretch()
        bar.addWidget(self.chk_show_paid)
        layout.addLayout(bar)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Proveedor", "Fecha Emisión", "Vence", "Monto", "Estado", "Descripción"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        self.load_data()

    def load_data(self):
        show_paid = self.chk_show_paid.isChecked()
        self.table.setRowCount(0)
        
        with self.session_factory() as session:
            query = session.query(AccountsPayable)
            if not show_paid:
                query = query.filter(AccountsPayable.status != 'PAID')
                
            bills = query.order_by(AccountsPayable.issue_date.desc()).all()
            
            self.table.setRowCount(len(bills))
            for i, bill in enumerate(bills):
                self.table.setItem(i, 0, QTableWidgetItem(str(bill.id)))
                self.table.setItem(i, 1, QTableWidgetItem(bill.supplier_name))
                self.table.setItem(i, 2, QTableWidgetItem(bill.issue_date.strftime("%d/%m/%Y")))
                
                due_str = bill.due_date.strftime("%d/%m/%Y") if bill.due_date else "-"
                self.table.setItem(i, 3, QTableWidgetItem(due_str))
                
                # Format Amount
                amt = f"{bill.currency} {bill.amount:,.2f}"
                self.table.setItem(i, 4, QTableWidgetItem(amt))
                
                # Status with Color
                st_item = QTableWidgetItem(bill.status)
                st_item.setForeground(QColor("#f1c40f")) # Default Yellow
                
                if bill.status == 'OVERDUE':
                    st_item.setForeground(QColor("#e74c3c")) # Red
                elif bill.status == 'PAID':
                    st_item.setForeground(QColor("#2ecc71")) # Green
                    
                self.table.setItem(i, 5, st_item)
                self.table.setItem(i, 6, QTableWidgetItem(bill.description))

    def on_add_bill(self):
        dlg = RegisterBillDialog(self.session_factory, self)
        if dlg.exec():
            self.load_data()
            self.data_changed.emit()

    def on_pay_bill(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Atención", "Seleccione una factura por pagar")
            return
            
        bill_id = int(self.table.item(row, 0).text())
        
        # Check status
        status = self.table.item(row, 5).text()
        if status == 'PAID':
            QMessageBox.information(self, "Info", "Esta factura ya está pagada")
            return
            
        dlg = PayBillDialog(bill_id, self.session_factory, self)
        if dlg.exec():
            self.load_data()
            self.data_changed.emit()

class RegisterBillDialog(QDialog):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
        self.setWindowTitle("Registrar Cuenta por Pagar")
        self.resize(450, 400)
        
        layout = QFormLayout(self)
        
        self.txt_supplier = QLineEdit()
        self.txt_supplier.setPlaceholderText("Nombre del proveedor")
        self.txt_supplier.setStyleSheet("padding: 5px; background: #333; color: white;")
        
        self.txt_desc = QTextEdit()
        self.txt_desc.setMaximumHeight(60)
        self.txt_desc.setStyleSheet("padding: 5px; background: #333; color: white;")

        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.01, 1000000.0)
        self.spin_amount.setPrefix("$ ")
        self.spin_amount.setStyleSheet("padding: 5px; background: #333; color: white;")
        
        self.date_issue = QDateEdit(QDate.currentDate())
        self.date_issue.setCalendarPopup(True)
        self.date_issue.setStyleSheet("padding: 5px; background: #333; color: white;")
        
        self.date_due = QDateEdit(QDate.currentDate().addDays(7))
        self.date_due.setCalendarPopup(True)
        self.date_due.setStyleSheet("padding: 5px; background: #333; color: white;")
        
        layout.addRow("Proveedor:", self.txt_supplier)
        layout.addRow("Descripción:", self.txt_desc)
        layout.addRow("Monto (USD):", self.spin_amount)
        layout.addRow("Fecha Emisión:", self.date_issue)
        layout.addRow("Fecha Vencimiento:", self.date_due)
        
        btn_box = QHBoxLayout()
        btn_save = QPushButton("Guardar")
        btn_save.setProperty("accent", "primary")
        btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addRow(btn_box)
        
    def save(self):
        supp_name = self.txt_supplier.text().strip()
        desc = self.txt_desc.toPlainText().strip()
        amt = self.spin_amount.value()
        
        if not supp_name or not desc or amt <= 0:
            QMessageBox.warning(self, "Error", "Complete los campos obligatorios")
            return
            
        with self.session_factory() as session:
            # Check if supplier exists or create basic
            supplier = session.query(Supplier).filter(Supplier.name.ilike(supp_name)).first()
            if not supplier:
                supplier = Supplier(name=supp_name)
                session.add(supplier)
                session.flush() # get ID
            
            bill = AccountsPayable(
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                description=desc,
                amount=amt,
                currency="USD",
                issue_date=self.date_issue.date().toPython(),
                due_date=self.date_due.date().toPython(),
                status='PENDING'
            )
            session.add(bill)
            session.commit()
            
        self.accept()

class PayBillDialog(QDialog):
    def __init__(self, bill_id, session_factory, parent=None):
        super().__init__(parent)
        self.bill_id = bill_id
        self.session_factory = session_factory
        
        self.setWindowTitle("Pagar Factura")
        self.resize(350, 200)
        self.setStyleSheet("background-color: #2b2b2b; color: white;")
        
        layout = QFormLayout(self)
        
        # Info
        self.lbl_info = QLabel("Cargando info...")
        layout.addRow(self.lbl_info)
        
        self.cb_account = QComboBox()
        self.cb_account.setStyleSheet("padding: 5px; background: #333; color: white;")
        layout.addRow("Cuenta Origen:", self.cb_account)
        
        self.txt_ref = QLineEdit()
        self.txt_ref.setStyleSheet("padding: 5px; background: #333; color: white;")
        layout.addRow("Referencia Pago:", self.txt_ref)
        
        btn_pay = QPushButton("Confirmar Pago")
        btn_pay.setProperty("accent", "primary")
        btn_pay.clicked.connect(self.pay)
        layout.addRow(btn_pay)
        
        self.load_info()
        
    def load_info(self):
        with self.session_factory() as session:
            bill = session.query(AccountsPayable).get(self.bill_id)
            if bill:
                self.lbl_info.setText(f"Pago a: {bill.supplier_name}\nMonto: {bill.currency} {bill.amount:,.2f}")
                self.amount_to_pay = bill.amount
                
            # Load accounts standard
            accounts = session.query(Account).filter(Account.is_active == True).all()
            for a in accounts:
                self.cb_account.addItem(f"{a.name} ({a.currency})", a.id)
                
    def pay(self):
        acc_id = self.cb_account.currentData()
        ref = self.txt_ref.text()
        
        if not acc_id:
            return
            
        with self.session_factory() as session:
            bill = session.query(AccountsPayable).get(self.bill_id)
            acc = session.query(Account).get(acc_id)
            
            if not bill or not acc:
                return

            # 1. Deduct from account
            acc.balance -= bill.amount
            
            # 2. Create Transaction
            txn = Transaction(
                date=datetime.now(),
                amount=bill.amount,
                transaction_type='EXPENSE',
                description=f"Pago Factura #{bill.id} - {bill.supplier_name}",
                account_id=acc.id,
                reference=ref,
                related_table="accounts_payable",
                related_id=bill.id
            )
            session.add(txn)
            session.flush() # get ID
            
            # 3. Update Bill
            bill.status = 'PAID'
            bill.transaction_id = txn.id
            
            session.commit()
            
        QMessageBox.information(self, "Éxito", "Factura pagada correctamente")
        self.accept()
