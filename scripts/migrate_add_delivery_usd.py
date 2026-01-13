
import sys
import os
from sqlalchemy import create_engine, text
from pathlib import Path

# Add src to path
sys.path.append(os.getcwd())

# Define DB path manually as it seems not exported directly or function based
def get_db_path():
    root = Path(os.getcwd())
    return root / "data" / "app.db"

def migrate():
    db_path = get_db_path()
    print(f"Migrating DB at {db_path}")
    engine = create_engine(f"sqlite:///{db_path}")
    
    with engine.connect() as conn:
        # Check if column exists
        try:
            res = conn.execute(text("SELECT delivery_usd FROM sales LIMIT 1"))
            print("Column 'delivery_usd' already exists.")
        except Exception:
            print("Adding 'delivery_usd' column...")
            conn.execute(text("ALTER TABLE sales ADD COLUMN delivery_usd FLOAT DEFAULT 0.0"))
            print("Done.")

if __name__ == "__main__":
    migrate()
