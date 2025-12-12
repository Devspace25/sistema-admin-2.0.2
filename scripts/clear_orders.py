from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.admin_app.db import make_engine
from src.admin_app.models import Order, CorporeoConfig, CorporeoPayload

def clear_orders():
    engine = make_engine()
    Session = sessionmaker(bind=engine)
    with Session() as session:
        try:
            # Delete dependent records first
            session.query(CorporeoConfig).filter(CorporeoConfig.order_id != None).delete(synchronize_session=False)
            session.query(CorporeoPayload).filter(CorporeoPayload.order_id != None).delete(synchronize_session=False)
            
            # Delete all orders
            session.query(Order).delete()
            session.commit()
            print("All orders have been deleted successfully.")
        except Exception as e:
            session.rollback()
            print(f"Error deleting orders: {e}")

if __name__ == "__main__":
    clear_orders()
