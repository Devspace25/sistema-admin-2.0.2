from src.admin_app.db import make_engine, make_session_factory
from src.admin_app.models import Order, Sale
from src.admin_app.repository import update_order

engine = make_engine()
session_factory = make_session_factory(engine)

with session_factory() as session:
    # Find orders in NUEVO created recently that might be misclassified
    orders = session.query(Order).filter(Order.status == 'NUEVO').all()
    count = 0
    for o in orders:
        sale = o.sale
        if sale:
            # Check if design cost is 0 and no explicit design flag (we can't check checkbox history easily, 
            # but usually if cost is 0 it doesn't need design unless 'incluye_diseno' was just a flag without cost)
            # But the user said "ventas no llevan diseño", implying cost 0 usually.
            
            # Using sale.diseno_usd
            cost = sale.diseno_usd or 0.0
            
            if cost == 0.0:
                print(f"Migrating Order {o.order_number} to POR_PRODUCIR (Design Cost: {cost})")
                o.status = 'POR_PRODUCIR'
                count += 1
    
    if count > 0:
        session.commit()
        print(f"Updated {count} orders.")
    else:
        print("No orders needed update.")
