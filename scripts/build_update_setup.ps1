# Script para construir el paquete de actualización completo
# Requiere PyInstaller instalado.

Write-Host "Iniciando construcción del paquete de actualización..." -ForegroundColor Green

# 1. Limpiar dist/
if (Test-Path "dist\admin_app") { Remove-Item "dist\admin_app" -Recurse -Force }

# 2. Construir Ejecutable (Modo Carpeta para fácil actualización de archivos)
# Asumimos que existe un spec o usamos uno básico.
# Usamos --onedir por defecto para updates, aunque --onefile es más limpio para distribución inicial.
# Si usamos --onefile, necesitamos extraerlo y tener alembic al lado.
# Para updates tipo "Setup", mejor --onedir (carpeta) y el usuario sobreescribe la carpeta.

Write-Host "Construyendo ejecutable con PyInstaller..." -ForegroundColor Cyan
# Asegurar que alembic está instalado
pip install pyinstaller alembic

# Ejecutar build (sin icono por ahora si no existe)
pyinstaller --noconfirm --onedir --windowed --name "SistemaAdmin" --add-data "assets;assets" --add-data "src/admin_app/styles.qss;src/admin_app" --hidden-import "alembic" --hidden-import "psycopg2" --hidden-import "pg8000" src/admin_app/__main__.py

if (-not $?) {
    Write-Host "Error en la compilación." -ForegroundColor Red
    exit 1
}

# 3. Copiar sistema de migraciones a la carpeta de distribución
Write-Host "Copiando archivos de migración..." -ForegroundColor Cyan
$DistDir = "dist\SistemaAdmin"

# Copiar carpeta alembic
Copy-Item -Path "alembic" -Destination "$DistDir\alembic" -Recurse -Force

# Copiar alembic.ini
Copy-Item -Path "alembic.ini" -Destination "$DistDir\alembic.ini" -Force

# 4. Comprimir el resultado (Formato Setup Zip)
Write-Host "Creando archivo ZIP de actualización..." -ForegroundColor Cyan
$Version = (Get-Content "src\version.py" | Select-String 'VERSION = "(.*)"').Matches.Groups[1].Value
$ZipName = "Update_SistemaAdmin_v$Version.zip"

if (Test-Path $ZipName) { Remove-Item $ZipName }
Compress-Archive -Path "$DistDir\*" -DestinationPath $ZipName

Write-Host "Paquete creado exitosamente: $ZipName" -ForegroundColor Green
Write-Host "Instrucciones de Despliegue:"
Write-Host "1. Enviar $ZipName al cliente."
Write-Host "2. El cliente debe descomprimir el contenido en su carpeta de instalación (reemplazando archivos)."
Write-Host "3. Al abrir el programa, se ejecutarán las migraciones automáticamente."
