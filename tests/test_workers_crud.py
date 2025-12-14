
import pytest
from datetime import datetime
from src.admin_app.models import Worker, User
from src.admin_app.repository import create_worker, update_worker, get_worker, list_workers

def test_worker_full_crud(session_factory):
    with session_factory() as db_session:
        # 1. Create a user to link
        user = User(username="worker_user", password_hash="hash")
        db_session.add(user)
        db_session.commit()
        
        # 2. Create Worker with all fields
        start_date = datetime(2023, 1, 15)
        worker = create_worker(
            db_session,
            full_name="Juan Perez",
            user_id=user.id,
            cedula="V-12345678",
            phone="0414-1234567",
            email="juan@example.com",
            address="Calle 1, Casa 2",
            job_title="Gerente",
            start_date=start_date,
            salary=1500.00
        )
        
        assert worker.id is not None
        assert worker.full_name == "Juan Perez"
        assert worker.cedula == "V-12345678"
        assert worker.phone == "0414-1234567"
        assert worker.email == "juan@example.com"
        assert worker.address == "Calle 1, Casa 2"
        assert worker.job_title == "Gerente"
        assert worker.start_date == start_date
        assert worker.salary == 1500.00
        assert worker.user_id == user.id
        
        # 3. Update Worker
        new_start_date = datetime(2023, 2, 1)
        updated_worker = update_worker(
            db_session,
            worker.id,
            full_name="Juan Perez Updated",
            cedula="V-87654321",
            phone="0412-7654321",
            email="juan.updated@example.com",
            address="Avenida 2",
            job_title="Supervisor",
            start_date=new_start_date,
            salary=2000.00,
            is_active=False
        )
        
        assert updated_worker.full_name == "Juan Perez Updated"
        assert updated_worker.cedula == "V-87654321"
        assert updated_worker.phone == "0412-7654321"
        assert updated_worker.email == "juan.updated@example.com"
        assert updated_worker.address == "Avenida 2"
        assert updated_worker.job_title == "Supervisor"
        assert updated_worker.start_date == new_start_date
        assert updated_worker.salary == 2000.00
        assert updated_worker.is_active is False
        
        # 4. Verify persistence
        db_session.expire_all()
        fetched = get_worker(db_session, worker.id)
        assert fetched.full_name == "Juan Perez Updated"
        assert fetched.salary == 2000.00

