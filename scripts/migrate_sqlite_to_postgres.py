from __future__ import annotations

"""
Herramienta mejorada de migración de datos desde SQLite (archivo local) hacia PostgreSQL.

- Lee desde un archivo SQLite (por defecto ./data/app.db) y copia todas las tablas definidas en
  `src.admin_app.models.Base.metadata` hacia la base de datos PostgreSQL indicada por
  `DATABASE_URL` o argumento.
- Opciones:
  --sqlite PATH       Ruta al archivo sqlite (por defecto data/app.db)
  --target URL        URL destino (postgres) o usar env DATABASE_URL
  --dry-run           No ejecuta INSERTs, solo indica qué haría
  --truncate          Trunca las tablas destino antes de insertar
  --preserve-ids      Preserva valores de PK (por defecto True)
  --batch-size N      Cuántas filas insertar por lote (default 500)

Uso:
  .venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py --target postgresql+psycopg2://user:pass@host/db

El script intenta mantener el orden de inserción respetando FKs (usa metadata.sorted_tables),
y ajusta secuencias en Postgres al finalizar para mantener autoincrement coherente.
"""

import os
import sys
import argparse
from pathlib import Path
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

# Carga .env opcional
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Asegurar que el paquete src.* se pueda importar aunque ejecutemos el script
# directamente desde la carpeta scripts (PyInstaller suele copiarlo aparte).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.admin_app.models import Base


def get_sqlite_url(path: str) -> str:
    return f"sqlite:///{path}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Migrar datos SQLite -> PostgreSQL usando modelos del proyecto")
    p.add_argument("--sqlite", default=os.path.join("data", "app.db"), help="Ruta al archivo sqlite")
    p.add_argument("--target", default=os.getenv("DATABASE_URL"), help="URL SQLAlchemy destino (Postgres)")
    p.add_argument("--dry-run", action="store_true", help="No realiza INSERTs, solo simula")
    p.add_argument("--truncate", action="store_true", help="Trunca las tablas destino antes de insertar")
    p.add_argument("--preserve-ids", dest="preserve_ids", action="store_true", help="Preservar valores de PK (por defecto)" )
    p.add_argument("--no-preserve-ids", dest="preserve_ids", action="store_false", help="No preservar PKs, dejar que Postgres genere nuevos IDs")
    p.add_argument("--batch-size", type=int, default=500, help="Número de filas por lote en inserts")
    p.add_argument("--on-conflict", choices=["error", "ignore", "update"], default="error", help="Estrategia ante duplicados en Postgres: error (por defecto), ignore (NOOP) o update (upsert)")
    p.set_defaults(preserve_ids=True)
    return p.parse_args()


def adjust_sequences(dst_conn, table_name: str, pk_col: str = "id") -> None:
    """Ajusta la secuencia de Postgres para que comience después del máximo id insertado.
    Intenta el nombre de secuencia convencional '<table>_<pk>_seq' y, si falla, busca en pg_get_serial_sequence.
    """
    seq_name = f"{table_name}_{pk_col}_seq"
    try:
        dst_conn.execute(text(f"SELECT setval(:seq, (SELECT COALESCE(MAX({pk_col}), 1) FROM {table_name}))"), {"seq": seq_name})
        print(f"  - Secuencia ajustada: {seq_name}")
        return
    except Exception:
        # Fallback: usar pg_get_serial_sequence para determinar secuencia real
        try:
            res = dst_conn.execute(text("SELECT pg_get_serial_sequence(:tbl, :col) as seq"), {"tbl": table_name, "col": pk_col}).mappings().first()
            seq = res and res.get("seq")
            if seq:
                dst_conn.execute(text(f"SELECT setval(:seq, (SELECT COALESCE(MAX({pk_col}), 1) FROM {table_name}))"), {"seq": seq})
                print(f"  - Secuencia ajustada: {seq}")
        except Exception as ex:
            print(f"  - aviso: no se pudo ajustar secuencia para {table_name}: {ex}")


def migrate(args: argparse.Namespace) -> None:
    sqlite_path = args.sqlite
    target_url = args.target

    if not target_url:
        print("ERROR: Proporcione la URL de PostgreSQL mediante --target o en DATABASE_URL")
        sys.exit(2)

    print(f"Fuente SQLite: {sqlite_path}")
    print(f"Destino Postgres: {target_url}")
    print(f"Opciones: dry_run={args.dry_run}, truncate={args.truncate}, preserve_ids={args.preserve_ids}")

    src_engine = create_engine(get_sqlite_url(sqlite_path), connect_args={"check_same_thread": False})
    # AUTOCOMMIT ayuda a evitar que un fallo en una tabla deje la conexión en estado de transacción abortada
    dst_engine = create_engine(target_url, pool_pre_ping=True, isolation_level="AUTOCOMMIT")

    # Asegurar esquema destino
    print("Asegurando esquema destino (Base.metadata.create_all)...")
    Base.metadata.create_all(dst_engine)

    # Trabajaremos con conexiones core para copiar tablas con metadata
    with src_engine.connect() as src_conn, dst_engine.connect() as dst_conn:
        # Orden de inserción guiado por metadata (resuelve dependencias entre FKs)
        tables = list(Base.metadata.sorted_tables)

        if args.truncate:
            print("Truncando tablas destino (orden inverso para evitar FKs)...")
            for table in reversed(tables):
                try:
                    if not args.dry_run:
                        dst_conn.execute(text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE"))
                    print(f"  - truncado: {table.name}")
                except Exception as ex:
                    print(f"  - aviso truncando {table.name}: {ex}")

        for table in tables:
            print(f"Procesando tabla: {table.name}")
            # Leer filas desde sqlite
            try:
                res = src_conn.execute(select(table)).mappings().all()
            except Exception as ex:
                print(f"  - aviso: no se pudo leer tabla {table.name} desde sqlite: {ex}")
                continue

            if not res:
                print("  - sin filas, omitiendo")
                continue

            print(f"  - filas a migrar: {len(res)}")

            # Insert en batches
            batch = []
            cols = [c.name for c in table.columns]
            pk_cols = [c.name for c in table.primary_key.columns]

            for row in res:
                row_data = {k: row.get(k) for k in cols}
                if not args.preserve_ids:
                    for pk in pk_cols:
                        row_data.pop(pk, None)
                batch.append(row_data)

                if len(batch) >= args.batch_size:
                    if not args.dry_run:
                        try:
                            _execute_insert(dst_conn, table, batch, pk_cols, args)
                        except Exception as ex:
                            print(f"  - error insert batch en {table.name}: {ex}")
                            try:
                                dst_conn.execute(text("ROLLBACK"))
                            except Exception:
                                pass
                    batch = []

            # Insert remaining
            if batch:
                if not args.dry_run:
                    try:
                        _execute_insert(dst_conn, table, batch, pk_cols, args)
                    except Exception as ex:
                        print(f"  - error insert final en {table.name}: {ex}")
                        try:
                            dst_conn.execute(text("ROLLBACK"))
                        except Exception:
                            pass

            # Ajustar secuencia si preservamos IDs y tabla tiene PK llamada 'id'
            if args.preserve_ids and 'id' in pk_cols:
                try:
                    adjust_sequences(dst_conn, table.name, 'id')
                except Exception as ex:
                    print(f"  - aviso al ajustar secuencia para {table.name}: {ex}")

            print(f"  - completada: {table.name}")

        if not args.dry_run:
            try:
                dst_conn.execute(text('COMMIT'))
            except Exception:
                pass

    print("Migración finalizada.")


def main() -> None:
    args = parse_args()
    migrate(args)


# --- helpers -----------------------------------------------------------------

def _execute_insert(dst_conn, table, rows, pk_cols, args) -> None:
    """Ejecuta un INSERT por lotes con estrategia de conflicto opcional para Postgres.

    - En motores que no sean Postgres o cuando on_conflict=error, hace un insert() normal.
    - Para Postgres, si on_conflict=ignore/update usa on_conflict_do_nothing / on_conflict_do_update.
    """
    try:
        backend = dst_conn.engine.url.get_backend_name()
    except Exception:
        backend = ""

    if backend != "postgresql" or args.on_conflict == "error":
        dst_conn.execute(table.insert(), rows)
        return

    # Dialecto Postgres con estrategia de conflicto
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(table).values(rows)
    if args.on_conflict == "ignore":
        if pk_cols:
            stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
        else:
            stmt = stmt.on_conflict_do_nothing()
    elif args.on_conflict == "update":
        # Actualizar columnas no PK con valores de EXCLUDED
        non_pk = [c.name for c in table.columns if c.name not in pk_cols]
        if not non_pk:
            # No hay columnas que actualizar; degrada a ignore
            if pk_cols:
                stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
            else:
                stmt = stmt.on_conflict_do_nothing()
        else:
            update_map = {col: getattr(stmt.excluded, col) for col in non_pk}
            # Requiere claves de conflicto; usar las PK conocidas
            if pk_cols:
                stmt = stmt.on_conflict_do_update(index_elements=pk_cols, set_=update_map)
            else:
                # Si no hay PK definida, degradar a do nothing
                stmt = stmt.on_conflict_do_nothing()

    dst_conn.execute(stmt)


if __name__ == "__main__":
    main()
