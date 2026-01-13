
import sys
import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())

from src.admin_app.models import Base, Sale, Order, Delivery, SalePayment
from src.admin_app.db import make_engine
from src.admin_app.exchange import get_bcv_rate

def test_logic():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. Create Dummy Sale
        sale = Sale(
            numero_orden="TEST-DELIVERY-01",
            articulo="Test Item",
            asesor="TestUser",
            venta_usd=100.0,
            fecha=datetime.now(),
            delivery_usd=0.0,
            ingresos_usd=0.0,
            abono_usd=0.0
        )
        session.add(sale)
        session.flush()

        # 2. Create Dummy Order
        order = Order(
            sale_id=sale.id,
            order_number="ORD-TEST-01",
            product_name="Test Product",
            details_json="{}"
        )
        session.add(order)
        session.flush()

        print(f"Created Sale ID: {sale.id}, Order ID: {order.id}")

        # 3. Simulate Data from Dialog
        data = {
            'order_id': order.id,
            'payment_source': 'EMPRESA',
            'client_method': 'Efectivo $',
            'client_amount': 10.0,
            'client_ref': 'REF123'
        }

        # 4. Run Logic
        if data['payment_source'] == 'EMPRESA' and data['order_id']:
            order_obj = session.get(Order, data['order_id'])
            if order_obj and order_obj.sale_id:
                sale_obj = session.get(Sale, order_obj.sale_id)
                if sale_obj:
                    method = data['client_method']
                    amount_raw = data['client_amount']
                    rate = get_bcv_rate() or 36.0
                    print(f"Rate: {rate}")

                    usd_val = 0.0
                    is_usd_method = any(x in method for x in ['Efectivo $', 'Zelle', 'Panamá', 'USD'])
                    
                    if is_usd_method:
                        usd_val = amount_raw
                    else:
                        if rate > 0:
                            usd_val = amount_raw / rate
                    
                    print(f"USD Value to add: {usd_val}")

                    sale_obj.delivery_usd = (sale_obj.delivery_usd or 0.0) + usd_val
                    sale_obj.venta_usd = (sale_obj.venta_usd or 0.0) + usd_val
                    sale_obj.abono_usd = (sale_obj.abono_usd or 0.0) + usd_val
                    
                    if is_usd_method:
                        sale_obj.ingresos_usd = (sale_obj.ingresos_usd or 0.0) + usd_val

                    new_pay = SalePayment(
                        sale_id=sale_obj.id,
                        payment_method=method,
                        amount_bs=amount_raw if not is_usd_method else 0.0,
                        amount_usd=amount_raw if is_usd_method else 0.0,
                        exchange_rate=rate if not is_usd_method else None,
                        reference=data['client_ref'],
                        payment_date=datetime.now()
                    )
                    session.add(new_pay)

        session.flush()
        
        # 5. Verify
        session.refresh(sale)
        print(f"Sale Delivery USD: {sale.delivery_usd}")
        print(f"Sale Venta USD: {sale.venta_usd}")
        print(f"Sale Ingresos USD: {sale.ingresos_usd}")
        
        if sale.delivery_usd == 10.0:
            print("SUCCESS: Delivery USD updated.")
        else:
            print("FAILURE: Delivery USD NOT updated.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        try:
            if 'sale' in locals():
                session.execute(text(f"DELETE FROM sale_payments WHERE sale_id={sale.id}"))
                session.execute(text(f"DELETE FROM orders WHERE id={order.id}"))
                session.execute(text(f"DELETE FROM sales WHERE id={sale.id}"))
                session.commit()
        except:
            pass
        session.close()

from sqlalchemy import text
if __name__ == "__main__":
    test_logic()
