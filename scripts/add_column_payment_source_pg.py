import sys
import os
from sqlalchemy import text

# Add root path
sys.path.insert(0, os.getcwd())

from src.admin_app.db import make_engine

def migrate():
    engine = make_engine()
    with engine.connect() as conn:
        print("Checking 'deliveries' table for 'payment_source' column...")
        try:
           # Check if column exists
           result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='deliveries' AND column_name='payment_source'"))
           row = result.fetchone()
           
           if not row:
               print("Adding 'payment_source' column...")
               conn.execute(text("ALTER TABLE deliveries ADD COLUMN payment_source VARCHAR(50) DEFAULT 'EMPRESA'"))
               conn.commit()
               print("Column added successfully.")
           else:
               print("Column 'payment_source' already exists.")
        except Exception as e:
            print(f"Error: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()