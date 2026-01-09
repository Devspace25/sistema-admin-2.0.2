import sys
import os
import subprocess
from src.updater.core import Updater, UpdateInfo
from src.version import VERSION

# CONFIGURACIÓN
UPDATE_URL = "https://tu-servidor.com/updates/latest.json"
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

def main():
    print(f"Sistema Admin Launcher - Versión {VERSION}")
    
    # 1. Verificar Actualizaciones (Solo si NO estamos en entorno de desarrollo controlado)
    #    Puedes poner un flag --no-update para desarrollo
    if "--no-update" not in sys.argv:
        updater = Updater(UPDATE_URL, APP_ROOT)
        update_info = updater.check_for_updates()
        
        if update_info and updater.is_newer(update_info.version):
            print(f"Nueva versión encontrada: {update_info.version}")
            print("Aplicando actualización...")
            
            success = updater.apply_update(update_info)
            if success:
                print("Actualización completada. Reiniciando...")
                # Reiniciamos el proceso actual (Launcher) para cargar nuevo código
                os.execv(sys.executable, ['python'] + sys.argv)
            else:
                print("La actualización falló. Iniciando versión actual...")
    
    # 2. Iniciar la Aplicación Principal
    print("Iniciando aplicación...")
    try:
        # Opción A: Ejecutar como subproceso (Más seguro para aislar errores de memoria)
        subprocess.run([sys.executable, "run_app.py"], check=True)
        
        # Opción B: Importar y ejecutar (Más rápido, comparte memoria)
        # from run_app import main as app_main
        # app_main()
        
    except Exception as e:
        print(f"Error fatal iniciando la aplicación: {e}")
        input("Presione Enter para salir...")

if __name__ == "__main__":
    main()
