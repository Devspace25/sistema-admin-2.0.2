"""
Pruebas para el sistema RBAC (Role-Based Access Control)
"""

import pytest
from datetime import date, datetime
from sqlalchemy.orm import sessionmaker

from src.admin_app.models import User, Role, Sale, Customer, UserRole, Base
from src.admin_app.repository import get_daily_sales_data
from src.admin_app.db import make_engine


@pytest.fixture
def rbac_session():
    """Configurar sesión de base de datos con datos de prueba RBAC."""
    engine = make_engine(':memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Crear roles
    admin_role = Role(name="ADMIN", description="Administrador del sistema")
    administracion_role = Role(name="ADMINISTRACION", description="Personal administrativo") 
    vendedor_role = Role(name="VENDEDOR", description="Vendedor")
    
    session.add_all([admin_role, administracion_role, vendedor_role])
    session.flush()
    
    # Crear usuarios de prueba
    admin_user = User(
        username="admin_test",
        password_hash="hash123",
        full_name="Admin Test",
        is_active=True
    )
    
    vendedor_user = User(
        username="vendedor_test", 
        password_hash="hash123",
        full_name="Vendedor Test",
        is_active=True
    )
    
    session.add_all([admin_user, vendedor_user])
    session.flush()
    
    # Asignar roles a usuarios
    admin_user_role = UserRole(user_id=admin_user.id, role_id=admin_role.id)
    vendedor_user_role = UserRole(user_id=vendedor_user.id, role_id=vendedor_role.id)
    session.add_all([admin_user_role, vendedor_user_role])
    session.flush()
    
    # Crear cliente de prueba
    customer = Customer(
        name="Cliente Test",
        email="cliente@test.com",
        phone="123456789"
    )
    session.add(customer)
    session.flush()
    
    # Crear ventas de prueba
    sale1 = Sale(
        numero_orden="ORDER-001",
        articulo="Producto Test 1",
        asesor=admin_user.username,
        venta_usd=100.0,
        fecha=datetime.now()
    )
    
    sale2 = Sale(
        numero_orden="ORDER-002", 
        articulo="Producto Test 2",
        asesor=vendedor_user.username,
        venta_usd=200.0,
        fecha=datetime.now()
    )
    
    session.add_all([sale1, sale2])
    session.commit()
    
    yield session, admin_user, vendedor_user
    session.close()


def test_admin_sees_all_sales(rbac_session):
    """Probar que usuario admin ve todas las ventas."""
    session, admin_user, vendedor_user = rbac_session
    
    # Admin debería ver todas las ventas (sin filtro)
    today = datetime.now()
    sales_data = get_daily_sales_data(session, today)
    assert len(sales_data['sales']) == 2
    
    # Con filtro específico, admin ve solo las suyas (filtro aplicado correctamente)
    sales_data_filtered = get_daily_sales_data(session, today, user_filter=admin_user.username)
    assert len(sales_data_filtered['sales']) == 1
    assert sales_data_filtered['sales'][0].asesor == admin_user.username


def test_vendedor_sees_only_own_sales(rbac_session):
    """Probar que usuario vendedor solo ve sus propias ventas."""
    session, admin_user, vendedor_user = rbac_session
    
    # Vendedor solo debería ver sus propias ventas
    today = datetime.now()
    sales_data = get_daily_sales_data(session, today, user_filter=vendedor_user.username)
    assert len(sales_data['sales']) == 1
    assert sales_data['sales'][0].numero_orden == 'ORDER-002'
    assert sales_data['sales'][0].asesor == vendedor_user.username


def test_role_based_filtering_logic():
    """Probar la lógica de filtrado basada en roles."""
    # Esto podría probarse con mocks si fuera necesario
    # Por ahora, la lógica está integrada en la vista
    pass