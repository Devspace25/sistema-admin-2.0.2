import os
import sys


def _ensure_src_in_path() -> None:
    """Garantiza que la carpeta 'src' esté en sys.path para imports absolutos.
    Esto permite importar el paquete 'admin_app' correctamente tanto en dev como en ejecutable.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(base_dir, 'src')
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)


def main() -> None:
    _ensure_src_in_path()
    # Importar el main del paquete usando import absoluto, así funcionan los imports relativos internos
    from admin_app.__main__ import main as app_main  # type: ignore
    app_main()


if __name__ == '__main__':
    main()
