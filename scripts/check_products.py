
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.admin_app.db import make_engine, make_session_factory
from src.admin_app.models import Product

def check_products():
    engine = make_engine()
    session_factory = make_session_factory(engine)
    
    with session_factory() as session:
        products = session.query(Product).all()
        for p in products:
            print(f"Product ID: {p.id}, Name: {p.name}")

if __name__ == "__main__":
    check_products()
