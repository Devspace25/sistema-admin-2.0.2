from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.admin_app.models import Base, Customer
from src.admin_app.repository import add_customers, list_customers


def test_customer_crud_in_memory():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    with Session(bind=engine) as session:
        add_customers(session, [Customer(name="Test 1"), Customer(name="Test 2")])
        result = list_customers(session)
        assert [c.name for c in result] == ["Test 1", "Test 2"]
