import pytest
from sqlalchemy.orm import Session
from src.admin_app.models import User, Order, Sale
from src.admin_app.repository import create_user, delete_user
from datetime import datetime
import json

def test_soft_delete_user_with_order(session_factory):
    """
    Test that deleting a user who is assigned as a designer to an order
    performs a soft delete (is_active=False) instead of raising a ForeignKeyViolation.
    """
    with session_factory() as session:
        # 1. Create a user (designer)
        # Ensure unique username
        designer = create_user(session, username="designer_fk_test", password="123", full_name="Designer Test")
        designer_id = designer.id
        
        # 2. Create a sale (required for order)
        sale = Sale(
            fecha=datetime.utcnow(),
            cliente="Test Client",
            articulo="Test Product",
            cantidad=1.0,
            asesor="Test User",
            venta_usd=100.0,
            tasa_bcv=35.0,
            monto_bs=3500.0,
            numero_orden="ORD-TEST-FK-001",
            details_json="{}"
        )
        session.add(sale)
        session.flush()
        
        # 3. Create an order assigned to the designer
        order = Order(
            sale_id=sale.id,
            order_number="ORD-TEST-FK-001",
            product_name="Test Product",
            details_json="{}",
            status="NUEVO",
            designer_id=designer_id
        )
        session.add(order)
        session.commit()
        
        # 4. Attempt to delete the user
        # This should NOT raise IntegrityError/ForeignKeyViolation now
        result = delete_user(session, user_id=designer_id)
        
        # 5. Verify result
        assert result is True
        
        # 6. Verify user is still in DB but inactive
        # Need to refresh or query again
        session.expire_all()
        deleted_user = session.get(User, designer_id)
        assert deleted_user is not None
        assert deleted_user.is_active is False
        
        # 7. Verify order still exists and references the user
        order_check = session.get(Order, order.id)
        assert order_check.designer_id == designer_id
