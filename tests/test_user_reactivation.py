
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.admin_app.models import Base, User
from src.admin_app.repository import create_user, delete_user, _verify_password

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_reactivate_deleted_user(session):
    username = "phoenix_user"
    password_v1 = "pass1"
    password_v2 = "pass2"
    
    # 1. Create user
    u1 = create_user(session, username=username, password=password_v1, full_name="Original Name")
    assert u1.is_active is True
    
    # 2. Delete user
    delete_user(session, user_id=u1.id)
    session.refresh(u1)
    assert u1.is_active is False
    
    # 3. Create user again (should reactivate)
    u2 = create_user(session, username=username, password=password_v2, full_name="Reborn Name")
    
    assert u2.id == u1.id  # Should be same record
    assert u2.is_active is True
    assert u2.full_name == "Reborn Name"
    assert _verify_password(password_v2, u2.password_hash) is True

def test_create_duplicate_active_user_fails(session):
    username = "duplicate_user"
    create_user(session, username=username, password="p")
    
    with pytest.raises(ValueError, match="ya existe y está activo"):
        create_user(session, username=username, password="p2")
