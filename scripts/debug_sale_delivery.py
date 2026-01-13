import sys
import os
sys.path.append(os.getcwd())

from sqlalchemy.orm import sessionmaker
from src.admin_app.db import make_engine
from src.admin_app.models import Order, Sale

def check_sale_delivery():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Find order 000002
        orders = session.query(Order).filter(Order.order_number.like('%000002%')).all()
        for o in orders:
            print(f"Checking Order: {o.order_number} (ID: {o.id})")
            if o.sale_id:
                sale = session.get(Sale, o.sale_id)
                if sale:
                    print(f"  -> Linked Sale ID: {sale.id}")
                    print(f"  -> Delivery USD: {sale.delivery_usd}")
                    print(f"  -> Venta USD: {sale.venta_usd}")
                    print(f"  -> Abono USD: {sale.abono_usd}")
                else:
                    print("  -> Sale Not Found")
            else:
                print("  -> No Sale ID linked")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_sale_delivery()
