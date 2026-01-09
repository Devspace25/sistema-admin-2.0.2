import os
import sys
from sqlalchemy import text

# Add root path
sys.path.insert(0, os.getcwd())

from src.admin_app.db import make_engine

def migrate():
    engine = make_engine()
    
    with engine.connect() as conn:
        conn.begin()
        
        # 1. Create delivery_payments table
        print("Creatin Add delivery_payments table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS delivery_payments (
                id SERIAL PRIMARY KEY,
                rider_id INTEGER NOT NULL REFERENCES users(id),
                amount_bs DOUBLE PRECISION DEFAULT 0.0,
                quantity INTEGER DEFAULT 0,
                start_date TIMESTAMP NOT NULL,
                end_date TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT timezone('utc', now()),
                notes TEXT
            );
        """))
        
        # 2. Add payment_id to deliveries
        print("Adding payment_id to deliveries...")
        try:
            conn.execute(text("""
                ALTER TABLE deliveries 
                ADD COLUMN payment_id INTEGER REFERENCES delivery_payments(id);
            """))
            print("Column payment_id added.")
        except Exception as e:
            print(f"Column might already exist or error: {e}")
            
        conn.commit()
    
    print("Migration finished.")

if __name__ == "__main__":
    migrate()
