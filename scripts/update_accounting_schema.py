import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.admin_app.db import make_engine, Base
from src.admin_app.models import Account, TransactionCategory, Transaction

def update_schema():
    engine = make_engine()
    print("Creating new tables for Accounting Module...")
    Base.metadata.create_all(engine)
    print("Tables created successfully.")
    
    # Initialize default categories if empty
    from sqlalchemy.orm import Session
    with Session(engine) as session:
        if session.query(TransactionCategory).count() == 0:
            print("Seeding default categories...")
            defaults = [
                TransactionCategory(name="Ventas", type="INCOME", description="Ingresos por ventas"),
                TransactionCategory(name="Nómina", type="EXPENSE", description="Pago de personal"),
                TransactionCategory(name="Servicios", type="EXPENSE", description="Electricidad, Internet, Agua"),
                TransactionCategory(name="Delivery", type="EXPENSE", description="Pagos a motorizados"),
                TransactionCategory(name="Materiales", type="EXPENSE", description="Compra de insumos"),
                TransactionCategory(name="Alquiler", type="EXPENSE", description="Arrendamiento de local"),
                TransactionCategory(name="Mantenimiento", type="EXPENSE", description="Reparaciones y mantenimiento"),
                TransactionCategory(name="Otros", type="EXPENSE", description="Gastos varios"),
            ]
            session.add_all(defaults)
            session.commit()
            print("Default categories seeded.")
            
        if session.query(Account).count() == 0:
            print("Seeding default accounts...")
            defaults = [
                Account(name="Caja Chica (USD)", type="CASH", currency="USD", balance=0.0),
                Account(name="Caja Chica (Bs)", type="CASH", currency="VES", balance=0.0),
                Account(name="Banesco (Bs)", type="BANK", currency="VES", balance=0.0),
                Account(name="Banco de Venezuela (Bs)", type="BANK", currency="VES", balance=0.0),
                Account(name="Zelle / Digital", type="DIGITAL", currency="USD", balance=0.0),
            ]
            session.add_all(defaults)
            session.commit()
            print("Default accounts seeded.")

if __name__ == "__main__":
    update_schema()
