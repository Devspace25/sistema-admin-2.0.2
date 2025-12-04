from __future__ import annotations

from pathlib import Path
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from .models import Base

# Cargar variables desde .env si existe (opcional)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


def get_data_dir() -> Path:
    """Devuelve la carpeta de datos persistente.
    - En desarrollo: ./data
    - En ejecutable (PyInstaller): %APPDATA%/Sistema-Admin-2.0
    - Se puede forzar con la variable ADMIN_APP_DATA_DIR
    """
    # Override por variable de entorno
    override = os.getenv("ADMIN_APP_DATA_DIR")
    if override:
        d = Path(override).expanduser()
        d.mkdir(parents=True, exist_ok=True)
        return d

    # Detectar si corremos empaquetados con PyInstaller
    is_frozen = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    if is_frozen:
        # Carpeta de datos en AppData del usuario
        base = os.getenv('APPDATA') or os.getenv('LOCALAPPDATA') or str(Path.home())
        d = Path(base) / "Sistema-Admin-2.0" / "data"
    else:
        # Desarrollo: junto al proyecto
        d = Path.cwd() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_default_db_path() -> Path:
    return get_data_dir() / "app.db"

# Nota: utilidades de preferencias eliminadas; si se requiere en el futuro,
# considerar un módulo dedicado (p. ej., settings.py) o usar QSettings.


def make_engine(db_path: Path | str | None = None):
    """Crear un engine de SQLAlchemy.

    Prioridad de conexión:
    1) Si se pasa ``db_path`` (ruta SQLite o URL completa), respetar ese destino.
    2) Si existe la variable de entorno ``DATABASE_URL``, usarla (recomendado para despliegue multiusuario).
    3) Usar SQLite local por defecto en ``./data/app.db``.

    Notas de drivers:
    - PostgreSQL: instale 'psycopg2-binary' y use URL 'postgresql+psycopg2://user:pass@host:5432/dbname'
    - MySQL/MariaDB: instale 'pymysql' y use URL 'mysql+pymysql://user:pass@host:3306/dbname'
    - SQL Server: instale 'pyodbc' y use URL 'mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17+for+SQL+Server'
    """

    # 1) db_path explícito: puede ser ruta SQLite o URL completa
    if db_path is not None:
        s = str(db_path)
        if s in {":memory:", "sqlite:///:memory:", "sqlite+pysqlite:///:memory:"}:
            # Base de datos en memoria: usar StaticPool para que todas las conexiones
            # compartan el mismo contexto durante las pruebas.
            return create_engine(
                "sqlite+pysqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        if "://" in s:
            return create_engine(
                s,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                pool_recycle=1800,
            )
        # Ruta SQLite convencional
        return create_engine(f"sqlite:///{s}", connect_args={"check_same_thread": False})

    # 2) URL desde entorno (ideal para despliegue multiusuario)
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return create_engine(
            env_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
        )

    # 3) SQLite por defecto (monousuario/local)
    url = f"sqlite:///{get_default_db_path()}"
    return create_engine(url, connect_args={"check_same_thread": False})


def make_session_factory(engine=None):
    engine = engine or make_engine()
    # Asegurar que las tablas existen en el engine proporcionado a menos que
    # se pida explícitamente lo contrario con la variable de entorno
    # ADMIN_APP_SKIP_CREATE_ALL=1 (útil cuando el esquema se gestiona desde
    # el servidor o con migraciones controladas).
    skip_create = os.getenv("ADMIN_APP_SKIP_CREATE_ALL", "0").lower() in ("1", "true", "yes")
    if not skip_create:
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            # No bloquear si por alguna razón la creación de tablas falla aquí;
            # el caller puede manejarlo o la inicialización completa se hace en init_db.
            pass
    # expire_on_commit=False evita que las instancias se marquen como expiradas tras commit,
    # lo que previene errores de "not bound to a Session" al acceder a atributos fuera del contexto.
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def test_connection(engine=None) -> dict:
    """Probar la conexión a la base de datos actual.

    Retorna un dict con:
      - ok: bool
      - elapsed_ms: float | None
      - url: str (redactada si tiene password)
      - backend: str (sqlite, postgresql, etc.)
      - error: str | None
    """
    import time
    e = engine or make_engine()
    info = {"ok": False, "elapsed_ms": None, "url": "", "backend": "", "error": None}
    try:
        # URL segura (esconde contraseña)
        try:
            safe_url = e.url.render_as_string(hide_password=True)  # SQLAlchemy 2.x
        except Exception:
            safe_url = str(e.url)
        info["url"] = safe_url
        info["backend"] = getattr(e.url, "get_backend_name", lambda: e.url.get_backend_name())()

        t0 = time.perf_counter()
        with e.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        info["elapsed_ms"] = (time.perf_counter() - t0) * 1000.0
        info["ok"] = True
    except Exception as ex:
        info["error"] = str(ex)
    return info
