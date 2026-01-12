from src.admin_app.db import make_engine
from sqlalchemy import text

def migrate_pg():
    engine = make_engine()
    
    with engine.connect() as conn:
        print(f"Connected to: {engine.url}")
        
        # Check if table exists (postgres way or generic sqlalchemy)
        # Using raw SQL for Postgres
        try:
             # Transaction
            trans = conn.begin()
            
            print("Altering 'deliveries' table to make order_id nullable...")
            conn.execute(text("ALTER TABLE deliveries ALTER COLUMN order_id DROP NOT NULL"))
            
            trans.commit()
            print("Migration successful.")
            
        except Exception as e:
            print(f"Error: {e}")
            trans.rollback()

if __name__ == "__main__":
    migrate_pg()
