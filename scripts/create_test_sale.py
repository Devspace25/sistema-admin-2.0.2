from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import os, sys
# Añadir la raíz del repo al path para poder importar 'src.admin_app'
repo_root = os.path.dirname(os.path.dirname(__file__))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.admin_app.models import Base
from src.admin_app.repository import add_sale

# Usar DB de data/app.db para replicar el entorno real
db = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'app.db')
print('DB:', db)
engine = create_engine(f"sqlite+pysqlite:///{db}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)

with Session(bind=engine) as session:
    sale = add_sale(
        session,
        articulo='Producto de prueba',
        asesor='tester',
        venta_usd=123.0,
        descripcion='Descripción detallada desde UI: prueba generacion pedido',
        cantidad=1.0,
        precio_unitario=123.0,
        total_bs=4428.0,
        created_by='script',
    )
    print('Created sale id:', sale.id, 'numero_orden:', sale.numero_orden)
