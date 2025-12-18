
import pytest
from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.admin_app.models import Base, User, Worker
from src.admin_app.ui.worker_dialog import WorkerDialog
from datetime import datetime

# Mock QApplication if not already running
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

def test_worker_dialog_shows_user(qapp, session_factory):
    # Setup data
    with session_factory() as session:
        user = User(username="testuser", password_hash="x", is_active=True, full_name="Test User")
        session.add(user)
        session.commit()
        
        worker = Worker(full_name="Worker With User", user_id=user.id)
        session.add(worker)
        session.commit()
        worker_id = worker.id

    # Open dialog
    dialog = WorkerDialog(session_factory, worker_id=worker_id)
    
    # Check field
    assert dialog.edt_assigned_user.text() == "testuser (Activo)"
    
    dialog.close()

def test_worker_dialog_shows_inactive_user(qapp, session_factory):
    # Setup data
    with session_factory() as session:
        user = User(username="olduser", password_hash="x", is_active=False, full_name="Old User")
        session.add(user)
        session.commit()
        
        worker = Worker(full_name="Worker With Old User", user_id=user.id)
        session.add(worker)
        session.commit()
        worker_id = worker.id

    # Open dialog
    dialog = WorkerDialog(session_factory, worker_id=worker_id)
    
    # Check field
    assert dialog.edt_assigned_user.text() == "olduser (Inactivo)"
    
    dialog.close()
