
import sys
import os
import logging
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.admin_app.db import make_engine as app_make_engine

# CONSTANTS
BASELINE_REVISION = "9b0cb9a8992d" # ID of the initial baseline migration

APP_ROOT = Path(__file__).parent.parent
ALEMBIC_INI = APP_ROOT / "alembic.ini"
ALEMBIC_DIR = APP_ROOT / "alembic"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MigrationManager")

def main():
    logger.info("Starting migration process...")
    
    # 1. Ensure CWD is project root (alebic.ini needs to be found)
    os.chdir(APP_ROOT)
    
    # 2. Config Alembic
    alembic_cfg = Config(str(ALEMBIC_INI))
    alembic_cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    
    # 3. Connect to DB to check status
    engine = app_make_engine()
    inspector = inspect(engine)
    
    existing_tables = inspector.get_table_names()
    has_users = "users" in existing_tables
    has_alembic = "alembic_version" in existing_tables
    
    with engine.connect() as connection:
        # Check current version if alembic exists
        current_rev = None
        if has_alembic:
            try:
                # Use text() for query
                result = connection.execute(text("SELECT version_num FROM alembic_version"))
                row = result.fetchone()
                if row:
                    current_rev = row[0]
            except Exception as e:
                logger.warning(f"Could not read alembic version: {e}")

        logger.info(f"DB Status: Users Table={has_users}, Alembic Table={has_alembic}, Current Rev={current_rev}")

        # LOGIC:
        # If (NO alembic table) AND (YES users table) -> Existing legacy DB. Stamp as baseline.
        # OR If (alembic table exists BUT is empty) AND (YES users table) -> Failed/Empty init. Stamp as baseline.
        needs_stamping = False
        if has_users:
            if not has_alembic:
                needs_stamping = True
            elif current_rev is None:
                needs_stamping = True

        if needs_stamping:
            logger.info("Detected existing database without migrations (or empty version). Stamping as baseline...")
            # Close our inspection connection before running alembic commands to avoid locks
            if not connection.closed:
                connection.close() 
            
            command.stamp(alembic_cfg, BASELINE_REVISION)
            logger.info(f"Stamped database at {BASELINE_REVISION}")
            
            logger.info("Database stamped to baseline. Skipping upgrade as we are at head.")
            return

        # If NO alembic and NO users (empty DB) -> Upgrade head will create everything.
        # If Alembic exists -> Upgrade head will apply new changes.
        
        # Check current version from alembic table if it exists
        # If we stamped above, we returned.
        
        logger.info("Running upgrade head...")
        # Ensure our connection is closed so alembic can have its own
        if not connection.closed:
            connection.close()
            
        command.upgrade(alembic_cfg, "head")
        logger.info("Migration complete.")

if __name__ == "__main__":
    main()
