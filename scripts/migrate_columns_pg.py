import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# Use the URL found in .env
DB_URL = "postgresql+psycopg://admin_app:postgres@127.0.0.1:5432/admin_app"

def migrate():
    print(f"Connecting to {DB_URL}...")
    engine = create_engine(DB_URL)
    
    with engine.connect() as conn:
        print("Checking/Adding delivered_at column...")
        try:
            # Check if column exists to avoid error or blindly try add
            # Postgres: ADD COLUMN IF NOT EXISTS is supported
            conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP WITHOUT TIME ZONE"))
            print("Done: delivered_at")
        except Exception as e:
            print(f"Error adding delivered_at: {e}")

        print("Checking/Adding delivery_method column...")
        try:
            conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_method VARCHAR(50)"))
            print("Done: delivery_method")
        except Exception as e:
            print(f"Error adding delivery_method: {e}")
            
        conn.commit()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
