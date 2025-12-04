# Ensure project root is on sys.path so `import src.admin_app...` works when running tests in various environments.
import os
import sys
from pathlib import Path

# Usar una base de datos aislada para pruebas (evita contaminar data/app.db)
ROOT_PATH = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
DATA_DIR = ROOT_PATH / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB = DATA_DIR / 'app_test.db'

# Forzar DATABASE_URL a una DB de pruebas
os.environ.setdefault('DATABASE_URL', f'sqlite:///{TEST_DB.as_posix()}')

# Resetear la DB de pruebas al inicio de la sesión de pytest
try:
    if TEST_DB.exists():
        TEST_DB.unlink()
except Exception:
    pass

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest
from src.admin_app.db import make_engine, make_session_factory
from src.admin_app.models import Base

@pytest.fixture(scope="session")
def engine():
    engine = make_engine()
    Base.metadata.create_all(engine)
    return engine

@pytest.fixture
def session_factory(engine):
    Session = make_session_factory(engine)
    return Session
