from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.admin_app.models import Base, Customer
from src.admin_app.repository import add_customers, update_customer, count_customers


def test_update_customer_and_count():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    with Session(bind=engine) as session:
        add_customers(session, [Customer(name="Alice", email=None)])
        assert count_customers(session) == 1

        # Obtener ID del único registro (forma robusta)
        cid = session.query(Customer.id).scalar()
        assert cid is not None
        ok = update_customer(session, cid, name="Alice Updated", email="alice@new.com")
        assert ok is True

        # Verificar cambios
        c = session.get(Customer, cid)
        assert c is not None
        assert c.name == "Alice Updated"
        assert c.email == "alice@new.com"