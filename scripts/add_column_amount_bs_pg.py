import sys
import os
from sqlalchemy import text

# Add root path
sys.path.insert(0, os.getcwd())

from src.admin_app.db import make_engine

def migrate():
    engine = make_engine()
    with engine.connect() as conn:
        print("Checking 'deliveries' table for 'amount_bs' column...")
        try:
           # Check if column exists
           result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='deliveries' AND column_name='amount_bs'"))
           row = result.fetchone()
           
           if not row:
               print("Adding 'amount_bs' column...")
               conn.execute(text("ALTER TABLE deliveries ADD COLUMN amount_bs FLOAT DEFAULT 0.0"))
               conn.commit()
               print("Column added successfully.")
           else:
               print("Column 'amount_bs' already exists.")
        except Exception as e:
            print(f"Error: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()