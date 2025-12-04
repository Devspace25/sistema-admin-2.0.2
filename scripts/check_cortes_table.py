"""Script temporal para verificar los registros de la tabla cortes."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.admin_app.db import make_engine
from src.admin_app.models import ProductParameterValue, ProductParameterTable
from sqlalchemy.orm import Session
import json

engine = make_engine()
session = Session(engine)

# Buscar la tabla cortes
cortes_table = session.query(ProductParameterTable).filter(
    ProductParameterTable.table_name.like('%cortes%')
).first()

print('Tabla encontrada:', cortes_table.display_name if cortes_table else 'No encontrada')
print('ID tabla:', cortes_table.id if cortes_table else 'N/A')
print()

# Buscar tablas del producto 7
product_id = 7
product_tables = session.query(ProductParameterTable).filter(
    ProductParameterTable.product_id == product_id
).all()

print(f'\nTablas del producto {product_id}: {len(product_tables)}')
print()

for t in product_tables:
    print(f'ID: {t.id} | display_name: {t.display_name}')
    print(f'  table_name: {t.table_name}')
    
    rows = session.query(ProductParameterValue).filter(
        ProductParameterValue.parameter_table_id == t.id,
        ProductParameterValue.is_active == True
    ).all()
    
    print(f'  Registros activos: {len(rows)}')
    
    for r in rows[:5]:  # Mostrar solo los primeros 5
        data = json.loads(r.row_data_json or '{}')
        print(f'    ID {r.id}: {json.dumps(data, ensure_ascii=False)}')
    
    print()
