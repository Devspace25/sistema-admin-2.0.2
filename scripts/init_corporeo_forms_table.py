"""
Script para crear la tabla corporeo_forms en la base de datos SQLite.
Ejecuta este script una sola vez para inicializar la tabla.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.admin_app.models import Base
from src.admin_app.db import make_engine

if __name__ == "__main__":
    engine = make_engine()
    print("Creando tabla corporeo_forms...")
    Base.metadata.create_all(engine)
    print("Tabla corporeo_forms creada (si no existía).")
