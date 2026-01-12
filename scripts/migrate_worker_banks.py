from src.admin_app.db import make_engine
from sqlalchemy import text

def migrate_worker_banks():
    engine = make_engine()
    
    with engine.connect() as conn:
        print(f"Connected to: {engine.url}")
        
        try:
             # Transaction
            trans = conn.begin()
            
            print("Adding bank fields to 'workers' table...")
            
            # Using ADD COLUMN IF NOT EXISTS logic handled by exception or just multiple statements
            # Postgres supports ADD COLUMN IF NOT EXISTS in newer versions, but to be safe we can wrap in blocks if key exists or just let it fail if exists (bad UX)
            # Better to assume they don't exist yet based on user request.
            
            sqls = [
                "ALTER TABLE workers ADD COLUMN IF NOT EXISTS bank_account VARCHAR(50)",
                "ALTER TABLE workers ADD COLUMN IF NOT EXISTS pago_movil_cedula VARCHAR(20)",
                "ALTER TABLE workers ADD COLUMN IF NOT EXISTS pago_movil_phone VARCHAR(20)",
                "ALTER TABLE workers ADD COLUMN IF NOT EXISTS pago_movil_bank VARCHAR(100)"
            ]
            
            for sql in sqls:
                print(f"Executing: {sql}")
                conn.execute(text(sql))
            
            trans.commit()
            print("Migration successful.")
            
        except Exception as e:
            print(f"Error: {e}")
            trans.rollback()

if __name__ == "__main__":
    migrate_worker_banks()
