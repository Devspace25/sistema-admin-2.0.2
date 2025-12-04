"""Launcher compatible con PyInstaller.

Evita ejecutar `src/admin_app/__main__.py` como archivo suelto (lo que provoca
`attempted relative import with no known parent package`) y en su lugar importa
el paquete por su nombre y llama a la función `main()`.
"""
def main():
    # Import dentro de la función para retrasar resolución de paquetes hasta runtime
    from src.admin_app.__main__ import main as app_main
    app_main()


if __name__ == "__main__":
    main()
