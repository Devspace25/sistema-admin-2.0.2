import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.admin_app.db import make_engine, Base
from src.admin_app.models import Supplier, AccountsPayable

def update_schema():
    engine = make_engine()
    print("Creating new tables for Accounts Payable...")
    # Base.metadata.create_all checks for existence, so it's safe to run again
    Base.metadata.create_all(engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    update_schema()
