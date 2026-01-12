import sys
import os
from sqlalchemy import inspect, text
from src.admin_app.db import make_engine
from src.admin_app.models import Base

def check_and_add_column():
    engine = make_engine()
    inspector = inspect(engine)
    
    # Check if 'sales' table exists
    if 'sales' not in inspector.get_table_names():
        print("Table 'sales' not found.")
        return

    # Check columns
    cols = [c['name'] for c in inspector.get_columns('sales')]
    print("Existing columns in sales:", cols)
    
    if 'commission_paid' in cols:
        print("Column 'commission_paid' already exists.")
    else:
        print("Adding 'commission_paid' column...")
        with engine.connect() as conn:
            try:
                # Check for postgres by assumption or just try standard SQL boolean
                # SQLAlchemy text handling sometimes varies, but for literal SQL execution:
                # Postgres prefers 'FALSE' or 'false', SQLite accepts 0/1.
                # Let's try explicit FALSE which works in PG.
                # If it fails (sqlite might complain if strict), we try 0.
                try:
                     conn.execute(text("ALTER TABLE sales ADD COLUMN commission_paid BOOLEAN DEFAULT FALSE"))
                except Exception:
                     conn.rollback()
                     conn.execute(text("ALTER TABLE sales ADD COLUMN commission_paid BOOLEAN DEFAULT 0"))
                
                conn.commit()
                print("Column added successfully.")
            except Exception as e:
                print(f"Error adding column: {e}")

if __name__ == "__main__":
    check_and_add_column()
