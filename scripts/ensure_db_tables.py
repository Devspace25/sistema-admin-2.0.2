from src.admin_app.db import make_engine
from src.admin_app.models import Base
from sqlalchemy import text

def init():
    engine = make_engine()
    Base.metadata.create_all(engine)
    print("Tables created (if not existed).")
    
    from sqlalchemy import inspect
    insp = inspect(engine)
    tables = insp.get_table_names()
    print("Tables in DB:", tables)
    
    if "workers" in tables:
        cols = [c["name"] for c in insp.get_columns("workers")]
        print("Columns in workers:", cols)
        
        if "payment_frequency" not in cols:
            print("Adding payment_frequency column to workers (Postgres)...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE workers ADD COLUMN payment_frequency VARCHAR(20) DEFAULT 'QUINCENAL'"))
                conn.commit()
            print("Column added.")
            
            # Update designers
            print("Migrating Designers...")
            with engine.connect() as conn:
                conn.execute(text("UPDATE workers SET payment_frequency = 'SEMANAL' WHERE rol LIKE '%diseñad%'"))
                conn.commit()
        else:
            print("Column payment_frequency exists.")
    else:
        print("Workers table missing even after create_all??")

if __name__ == "__main__":
    init()
