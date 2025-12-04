
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.admin_app.db import make_engine, make_session_factory
from src.admin_app.models import ProductParameterTable, ProductParameterValue, ConfigurableProduct, Product

def inspect_tables():
    engine = make_engine()
    session_factory = make_session_factory(engine)
    
    with session_factory() as session:
        print("--- Configurable Products ---")
        products = session.query(ConfigurableProduct).all()
        for p in products:
            print(f"ID: {p.id}, Name: {p.name}")
            
        print("\n--- Product Parameter Tables ---")
        tables = session.query(ProductParameterTable).all()
        for t in tables:
            print(f"ID: {t.id}, ProductID: {t.product_id}, TableName: {t.table_name}, DisplayName: {t.display_name}")
            
            # Get values for this table
            values = session.query(ProductParameterValue).filter_by(parameter_table_id=t.id).all()
            print(f"  Values ({len(values)}):")
            for v in values:
                print(f"    - {v.row_data_json}")

if __name__ == "__main__":
    inspect_tables()
