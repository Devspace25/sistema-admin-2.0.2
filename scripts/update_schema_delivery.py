
import sys
import os

# Ajustar path al root para importar src
sys.path.insert(0, os.getcwd())

from src.admin_app.db import make_engine
from src.admin_app.models import Base

def update_schema():
    engine = make_engine()
    print("Contectando a la base de datos...")
    print(f"URL: {engine.url}")
    # create_all comprueba si existen y solo crea las faltantes
    Base.metadata.create_all(engine)
    print("Tablas actualizadas (DeliveryZone, Delivery creadas si faltaban).")

if __name__ == "__main__":
    update_schema()
