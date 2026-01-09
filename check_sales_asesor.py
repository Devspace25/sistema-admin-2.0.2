from src.admin_app.db import make_session_factory
from src.admin_app.models import Sale, Order, User

def check():
    Session = make_session_factory()
    with Session() as session:
        orders = session.query(Order).join(Sale).all()
        print(f"Total Orders: {len(orders)}")
        for o in orders:
             sale = session.query(Sale).get(o.sale_id)
             sale_asesor = sale.asesor if sale else "N/A"
             print(f"Order: {o.order_number}, Status: '{o.status}', Asesor: '{sale_asesor}'")
            
        users = session.query(User).all()
        print("-" * 20)
        for u in users:
            print(f"User: {u.username} (ID: {u.id})")

if __name__ == "__main__":
    check()
