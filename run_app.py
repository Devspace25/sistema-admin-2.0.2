"""Launcher compatible con PyInstaller.

Evita ejecutar `src/admin_app/__main__.py` como archivo suelto (lo que provoca
`attempted relative import with no known parent package`) y en su lugar importa
el paquete por su nombre y llama a la función `main()`.
"""
import sys
import os

# Asegurar que el directorio raíz está en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.admin_app.__main__ import main as app_main

if __name__ == "__main__":
    app_main()
