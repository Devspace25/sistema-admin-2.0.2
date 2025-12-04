import os, sys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Añadir raíz del repo al path
repo_root = os.path.dirname(os.path.dirname(__file__))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.admin_app.repository import list_orders
from src.admin_app.receipts import print_order_pdf

engine = create_engine(f"sqlite+pysqlite:///{os.path.join(repo_root,'data','app.db')}", connect_args={"check_same_thread": False})

with Session(bind=engine) as s:
    orders = list_orders(s)
    if not orders:
        print('No hay orders')
    else:
        o = orders[0]
        print('Imprimiendo orden', o.id)
        p = print_order_pdf(order_id=int(o.id), sale_id=int(o.sale_id or 0), product_name=(o.product_name or ''), status=(o.status or ''), details_json=(o.details_json or '{}'))
        print('Generado:', p)
