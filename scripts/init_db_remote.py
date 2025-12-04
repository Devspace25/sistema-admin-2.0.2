from __future__ import annotations

import os
import sys
from sqlalchemy import create_engine

# Permite cargar .env si existe
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Reutilizar lógica del repo
from src.admin_app.repository import init_db


def main():
    """Inicializa el esquema de la base de datos en el servidor remoto/local.

    Uso:
      - Sin argumentos: usa la variable de entorno DATABASE_URL
      - Con argumento URL: scripts/init_db_remote.py postgresql+psycopg2://user:pass@host:5432/db
    """
    url = None
    if len(sys.argv) >= 2:
        url = sys.argv[1]
    else:
        url = os.getenv("DATABASE_URL")

    if not url:
        print("ERROR: proporcione una DATABASE_URL por argumento o variable de entorno")
        sys.exit(2)

    # Crear engine con algunos parámetros de pool razonables
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
    )

    # Crear tablas y seed básico
    init_db(engine, seed=True)
    print("Esquema inicializado correctamente en:", url)


if __name__ == "__main__":
    main()
