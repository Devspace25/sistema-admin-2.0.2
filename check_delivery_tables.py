from src.admin_app.db import make_engine
from sqlalchemy import inspect

engine = make_engine()
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"Tables: {tables}")
if 'delivery_zones' in tables and 'deliveries' in tables:
    print("SUCCESS: Delivery tables found.")
else:
    print("ERROR: Delivery tables MISSING.")
