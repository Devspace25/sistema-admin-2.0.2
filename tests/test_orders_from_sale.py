from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.admin_app.models import Base
from src.admin_app.repository import add_sale, list_orders


def test_add_sale_creates_order_for_corporeo():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    with Session(bind=engine) as session:
        # Crear venta con artículo que contiene 'corp' para disparar creación de pedido
        sale = add_sale(
            session,
            articulo="Corpóreo - Letras",
            asesor="tester",
            venta_usd=150.0,
            forma_pago="Efectivo $",
            descripcion="Pedido corpóreo personalizado",
            cantidad=1.0,
            precio_unitario=150.0,
            total_bs=5400.0,
            created_by='test'
        )
        assert sale is not None
        orders = list_orders(session)
        # Debe existir al menos un pedido asociado a la venta
        assert any(o.sale_id == sale.id for o in orders)
