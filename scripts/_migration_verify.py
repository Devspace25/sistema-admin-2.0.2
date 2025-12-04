"""Verificador simple post-migración: compara conteos por tabla entre SQLite y Postgres."""
import os
import argparse
from sqlalchemy import create_engine, select
from src.admin_app.models import Base


def get_sqlite_url(path: str) -> str:
    return f"sqlite:///{path}"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--sqlite', required=True)
    p.add_argument('--target', required=True)
    return p.parse_args()


def main():
    args = parse_args()
    src_engine = create_engine(get_sqlite_url(args.sqlite), connect_args={'check_same_thread': False})
    dst_engine = create_engine(args.target)

    tables = list(Base.metadata.sorted_tables)

    with src_engine.connect() as sconn, dst_engine.connect() as dconn:
        print("Tabla | SQLite_count | Postgres_count")
        print("-------------------------------------")
        mismatches = []
        for t in tables:
            try:
                rs = sconn.execute(select([t.count()])).scalar()
            except Exception:
                # fallback genérico
                rs = sconn.execute(select(t)).rowcount
            try:
                rd = dconn.execute(select([t.count()])).scalar()
            except Exception:
                rd = dconn.execute(select(t)).rowcount
            print(f"{t.name} | {rs} | {rd}")
            if rs != rd:
                mismatches.append((t.name, rs, rd))

        if mismatches:
            print("\nDiscrepancias encontradas:")
            for name, rs, rd in mismatches:
                print(f" - {name}: sqlite={rs} postgres={rd}")
        else:
            print("\nVerificación OK: los conteos coinciden para todas las tablas.")


if __name__ == '__main__':
    main()
