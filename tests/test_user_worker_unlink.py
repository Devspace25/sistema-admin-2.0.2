
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.admin_app.models import Base, User, Worker
from src.admin_app.repository import delete_user, create_user

# Use an in-memory SQLite database for testing
@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_delete_user_unlinks_worker(session):
    # 1. Create user
    user = create_user(session, username="testuser", password="password")
    assert user.id is not None
    
    # 2. Create worker and assign user
    worker = Worker(full_name="Test Worker", user_id=user.id)
    session.add(worker)
    session.commit()
    session.refresh(worker)
    
    assert worker.user_id == user.id
    
    # 3. Delete user
    result = delete_user(session, user_id=user.id)
    assert result is True
    
    # 4. Verify user is inactive
    session.refresh(user)
    assert user.is_active is False
    
    # 5. Verify worker is unlinked
    session.refresh(worker)
    assert worker.user_id is None
