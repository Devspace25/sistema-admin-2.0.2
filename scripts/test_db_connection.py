"""Script de prueba para verificar la conexión a la base de datos usada por la app.

Uso:
  - Por defecto usa la configuración actual (DATABASE_URL o SQLite local)
  - Para probar Postgres temporalmente:
      $env:DATABASE_URL = 'postgresql+psycopg2://user:pass@host:5432/db'
      python scripts/test_db_connection.py

Imprime un resumen JSON con el resultado de test_connection().
"""
from __future__ import annotations
import json
import os
import sys

# Asegurarse de que el paquete src esté en sys.path cuando se ejecuta desde repo
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from src.admin_app.db import make_engine, test_connection
except Exception as e:
    print("ERROR importando módulo db:", e)
    raise


def main():
    # Si se pasó una URL como argumento, usarla temporalmente
    url = None
    if len(sys.argv) >= 2:
        url = sys.argv[1]

    engine = make_engine(url)
    info = test_connection(engine)
    print(json.dumps(info, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
