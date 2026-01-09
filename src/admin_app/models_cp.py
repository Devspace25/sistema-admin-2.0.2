
from sqlalchemy import Date, Text

class Supplier(Base):
    """Proveedores de la empresa"""
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(150))
    tax_id: Mapped[str | None] = mapped_column(String(50)) # RIF
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"Supplier(id={self.id!r}, name={self.name!r})"

class AccountsPayable(Base):
    """Cuentas por Pagar (Facturas de Proveedores)"""
    __tablename__ = "accounts_payable"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("suppliers.id"), nullable=True) # Optional for ad-hoc
    supplier_name: Mapped[str] = mapped_column(String(200), nullable=False) # Fallback or cache
    
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default='USD') # USD or VES
    
    issue_date: Mapped[datetime] = mapped_column(Date, default=datetime.utcnow)
    due_date: Mapped[datetime | None] = mapped_column(Date)
    
    status: Mapped[str] = mapped_column(String(20), default='PENDING', nullable=False) # PENDING, PAID, OVERDUE, CANCELLED
    
    # Link to payment transaction if paid
    transaction_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("transactions.id"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    supplier: Mapped["Supplier"] = relationship("Supplier")
    transaction: Mapped["Transaction"] = relationship("Transaction")

    def __repr__(self) -> str:
        return f"Bill(id={self.id!r}, to={self.supplier_name!r}, amount={self.amount!r}, status={self.status!r})"
