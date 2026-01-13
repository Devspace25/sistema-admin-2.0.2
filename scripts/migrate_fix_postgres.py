
import sys
import os
from sqlalchemy import text

# Add src to path
sys.path.append(os.getcwd())

# Import make_engine from app logic to target correct DB (Postgres or SQLite)
from src.admin_app.db import make_engine

def migrate():
    print("Initializing migration...")
    # Use app's engine factory matches real config (env vars etc)
    engine = make_engine()
    print(f"Connected to DB: {engine.url}")
    
    with engine.connect() as conn:
        # Check if column exists
        column_exists = False
        try:
            conn.execute(text("SELECT delivery_usd FROM sales LIMIT 1"))
            print("Column 'delivery_usd' already exists.")
            column_exists = True
        except Exception:
             print("Column check failed (expected if missing).")
             # Rollback the failed transaction so we can start new one
             conn.rollback()

        if not column_exists:
            print("Adding 'delivery_usd' column...")
            with conn.begin():
                 conn.execute(text("ALTER TABLE sales ADD COLUMN delivery_usd FLOAT DEFAULT 0.0"))
            print("Column added successfully.")

if __name__ == "__main__":
    migrate()
