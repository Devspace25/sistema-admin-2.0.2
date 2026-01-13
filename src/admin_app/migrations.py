
import os
import sys
import logging
from pathlib import Path
from alembic.config import Config
from alembic import command
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

def run_migrations(engine, app_root: Path = None):
    """
    Ejecuta las migraciones de Alembic de forma automática desde la aplicación.
    Busca 'alembic.ini' en el directorio actual o en el del ejecutable.
    """
    if app_root is None:
        # Detectar si es PyInstaller
        if getattr(sys, 'frozen', False):
            app_root = Path(sys.executable).parent
        else:
            app_root = Path.cwd()

    alembic_ini = app_root / "alembic.ini"
    alembic_dir = app_root / "alembic"

    if not alembic_ini.exists() or not alembic_dir.exists():
        logger.warning(f"No se encontraron archivos de migración en {app_root}. Se omite migración automática.")
        return

    logger.info("Iniciando sistema de migraciones automáticas...")
    
    # Configurar Alembic
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(alembic_dir))
    
    # Inyectar la URL de la base de datos actual (para que use la que ya tenemos configurada)
    # env.py debe estar preparado para usar 'sqlalchemy.url' o 'engine' si se pasa (pero alembic API es por config)
    url = engine.url.render_as_string(hide_password=False)
    alembic_cfg.set_main_option("sqlalchemy.url", url)

    # Lógica de detección de estado (Legacy vs Nuevo)
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    has_users = "users" in existing_tables
    has_alembic = "alembic_version" in existing_tables

    # Baseline ID - debe coincidir con tu primera migración
    BASELINE_REVISION = "9b0cb9a8992d"  

    try:
        # Si hay tablas pero no alembic, sellar como baseline
        if has_users and not has_alembic:
            logger.info("Base de datos legacy detectada. Marcando como linea base (baseline)...")
            command.stamp(alembic_cfg, BASELINE_REVISION)
        
        # Ejecutar upgrade head
        logger.info("Ejecutando migraciones (upgrade head)...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Base de datos actualizada correctamente.")
        
    except Exception as e:
        logger.error(f"Error crítico durante la migración de base de datos: {e}")
        # No relanzamos el error para no impedir que la app abra si es algo menor, 
        # pero idealmente debería detenerse si la DB es incompatible.
        # En este caso, dejamos constancia en el log.
