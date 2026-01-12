from src.admin_app.db import make_engine
from sqlalchemy import text, inspect

def migrate():
    engine = make_engine()
    insp = inspect(engine)
    
    if "workers" in insp.get_table_names():
        cols = [c["name"] for c in insp.get_columns("workers")]
        
        with engine.connect() as conn:
            if "binance_email" not in cols:
                print("Adding binance_email to workers...")
                conn.execute(text("ALTER TABLE workers ADD COLUMN binance_email VARCHAR(200)"))
                conn.commit()
            
            if "zelle_email" not in cols:
                print("Adding zelle_email to workers...")
                conn.execute(text("ALTER TABLE workers ADD COLUMN zelle_email VARCHAR(200)"))
                conn.commit()
                
            print("Migration complete.")

if __name__ == "__main__":
    migrate()
