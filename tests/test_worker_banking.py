from datetime import datetime
from src.admin_app.models import Base, Worker
from src.admin_app.repository import create_worker, update_worker, get_worker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_worker_banking_info_crud():
    # Setup in-memory DB
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Create Worker with Banking Info
    try:
        worker = create_worker(
            session, 
            full_name="Juan Perez",
            bank_account="01021234567890123456",
            pago_movil_cedula="V-12345678",
            pago_movil_phone="0414-1234567",
            pago_movil_bank="Banco de Venezuela"
        )
        
        assert worker.id is not None
        assert worker.bank_account == "01021234567890123456"
        assert worker.pago_movil_cedula == "V-12345678"
        assert worker.pago_movil_phone == "0414-1234567"
        assert worker.pago_movil_bank == "Banco de Venezuela"

        # 2. Update Worker Banking Info
        updated_worker = update_worker(
            session,
            worker.id,
            bank_account="01340000000000000000",
            pago_movil_cedula="V-87654321",
            pago_movil_phone="0424-7654321",
            pago_movil_bank="Banesco"
        )
        
        assert updated_worker.bank_account == "01340000000000000000"
        assert updated_worker.pago_movil_cedula == "V-87654321"
        assert updated_worker.pago_movil_phone == "0424-7654321"
        assert updated_worker.pago_movil_bank == "Banesco"
        
        # 3. Verify Persistence
        session.expire_all()
        fetched_worker = get_worker(session, worker.id)
        assert fetched_worker.bank_account == "01340000000000000000"
        assert fetched_worker.pago_movil_bank == "Banesco"

    finally:
        session.close()
