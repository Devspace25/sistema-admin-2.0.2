"""Script para inicializar tablas de Talonarios con datos de ejemplo.

Crea las tablas TipoTalonario, Impresion y TalonarioConfig,
y añade algunos registros de ejemplo para pruebas.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path para poder importar src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.admin_app.db import make_engine, make_session_factory
from src.admin_app.models import Base, TipoTalonario, Impresion, TalonarioConfig


def init_talonario_tables():
    """Inicializar tablas de talonarios y datos de ejemplo."""
    print("Inicializando tablas de Talonarios...")
    
    # Crear engine y tablas
    engine = make_engine()
    Base.metadata.create_all(engine)
    print("✓ Tablas creadas exitosamente")
    
    # Crear session
    session_factory = make_session_factory(engine)
    
    with session_factory() as session:
        # Verificar si ya existen datos
        existing_tipos = session.query(TipoTalonario).count()
        if existing_tipos > 0:
            print(f"✓ Ya existen {existing_tipos} tipos de talonario, omitiendo datos de ejemplo")
            return
        
        # Insertar tipos de talonario de ejemplo
        tipos = [
            TipoTalonario(
                nombre="Talonario Estándar",
                descripcion="Talonario básico de 100 hojas",
                precio_base=15.00,
                is_active=True
            ),
            TipoTalonario(
                nombre="Talonario Premium",
                descripcion="Talonario de alta calidad de 50 hojas",
                precio_base=25.00,
                is_active=True
            ),
            TipoTalonario(
                nombre="Talonario Factura",
                descripcion="Talonario para facturas con copias",
                precio_base=20.00,
                is_active=True
            ),
        ]
        
        for tipo in tipos:
            session.add(tipo)
        
        print(f"✓ Insertados {len(tipos)} tipos de talonario")
        
        # Insertar tipos de impresión de ejemplo
        impresiones = [
            Impresion(
                nombre="Blanco y Negro",
                descripcion="Impresión monocromática",
                costo_adicional=0.00,
                is_active=True
            ),
            Impresion(
                nombre="Color",
                descripcion="Impresión a full color",
                costo_adicional=5.00,
                is_active=True
            ),
            Impresion(
                nombre="Alta Resolución",
                descripcion="Impresión de alta calidad",
                costo_adicional=8.00,
                is_active=True
            ),
        ]
        
        for imp in impresiones:
            session.add(imp)
        
        print(f"✓ Insertadas {len(impresiones)} opciones de impresión")
        
        # Commit
        session.commit()
        print("✓ Datos de ejemplo guardados exitosamente")


if __name__ == "__main__":
    try:
        init_talonario_tables()
        print("\n✅ Inicialización completada exitosamente")
    except Exception as e:
        print(f"\n❌ Error durante la inicialización: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
