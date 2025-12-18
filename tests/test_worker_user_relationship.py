
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.admin_app.models import Base, User, Worker

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_worker_user_relationship_active_check(session):
    # 1. Create active user and worker
    user_active = User(username="active", password_hash="x", is_active=True, full_name="Active User")
    session.add(user_active)
    session.commit()
    
    worker_active = Worker(full_name="Worker Active", user_id=user_active.id)
    session.add(worker_active)
    session.commit()
    
    # 2. Create inactive user and worker (simulating old deletion)
    user_inactive = User(username="inactive", password_hash="x", is_active=False, full_name="Inactive User")
    session.add(user_inactive)
    session.commit()
    
    worker_inactive = Worker(full_name="Worker Inactive", user_id=user_inactive.id)
    session.add(worker_inactive)
    session.commit()
    
    # 3. Refresh workers
    session.refresh(worker_active)
    session.refresh(worker_inactive)
    
    # 4. Check relationship and is_active status
    assert worker_active.user is not None
    assert worker_active.user.is_active is True
    
    assert worker_inactive.user is not None
    assert worker_inactive.user.is_active is False
    
    # 5. Simulate UI Logic
    def get_display_text(w):
        text = w.full_name
        if w.user_id and w.user and w.user.is_active:
            text += " (Tiene usuario)"
        return text

    assert "(Tiene usuario)" in get_display_text(worker_active)
    assert "(Tiene usuario)" not in get_display_text(worker_inactive)
