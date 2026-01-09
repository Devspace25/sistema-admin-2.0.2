from sqlalchemy import create_engine, inspect
from src.admin_app.models import Base

def check_order_columns():
    engine = create_engine('sqlite:///data/app.db')
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('orders')]
    print("Columns in 'orders' table:")
    for c in columns:
        print(f"- {c}")

if __name__ == "__main__":
    check_order_columns()
