"""
Pruebas para la protección del usuario administrador
"""

import pytest
from sqlalchemy.orm import sessionmaker

from src.admin_app.models import User, Role, UserRole, Base
from src.admin_app.repository import delete_user, create_user, ensure_role
from src.admin_app.db import make_engine


@pytest.fixture
def admin_session():
    """Configurar sesión de base de datos con usuario admin."""
    engine = make_engine(':memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Crear rol admin
    admin_role = Role(name="ADMIN", description="Administrador del sistema")
    session.add(admin_role)
    session.flush()
    
    # Crear usuario admin
    admin_user = User(
        username="admin",
        password_hash="hash123", 
        full_name="Administrador",
        is_active=True
    )
    session.add(admin_user)
    session.flush()
    
    # Asignar rol admin
    user_role = UserRole(user_id=admin_user.id, role_id=admin_role.id)
    session.add(user_role)
    session.flush()
    
    # Crear usuario normal para comparar
    normal_user = User(
        username="usuario_normal",
        password_hash="hash456",
        full_name="Usuario Normal", 
        is_active=True
    )
    session.add(normal_user)
    session.commit()
    
    yield session, admin_user, normal_user
    session.close()


def test_cannot_delete_admin_user(admin_session):
    """Probar que no se puede eliminar al usuario admin."""
    session, admin_user, normal_user = admin_session
    
    # Intentar eliminar usuario admin debe lanzar excepción
    with pytest.raises(ValueError, match="No se puede eliminar al usuario administrador del sistema"):
        delete_user(session, user_id=admin_user.id)
    
    # Verificar que el usuario admin sigue existiendo
    admin_exists = session.get(User, admin_user.id)
    assert admin_exists is not None
    assert admin_exists.username == "admin"


def test_can_delete_normal_user(admin_session):
    """Probar que sí se puede eliminar un usuario normal."""
    session, admin_user, normal_user = admin_session
    
    # Eliminar usuario normal debe funcionar correctamente
    result = delete_user(session, user_id=normal_user.id)
    assert result is True
    
    # Verificar que el usuario normal fue eliminado
    normal_exists = session.get(User, normal_user.id)
    assert normal_exists is None


def test_admin_user_protection_by_username(admin_session):
    """Probar que la protección se basa en el username 'admin'."""
    session, admin_user, normal_user = admin_session
    
    # Crear usuario con username similar pero diferente (no debe estar protegido)
    similar_user = User(
        username="administrator",  # Similar pero no exactamente "admin"
        password_hash="hash789",
        full_name="Administrador Similar",
        is_active=True
    )
    session.add(similar_user)
    session.commit()
    
    # Eliminar usuario con username diferente debe funcionar
    result = delete_user(session, user_id=similar_user.id)
    assert result is True
    
    # Verificar que fue eliminado
    similar_exists = session.get(User, similar_user.id)
    assert similar_exists is None