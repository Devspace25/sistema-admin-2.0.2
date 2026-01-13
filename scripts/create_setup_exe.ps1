
Write-Host "Generador de Instalador (Setup.exe) - Sistema Admin" -ForegroundColor Cyan

# 1. Definir rutas
$InnoSetupPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
$VersionFile = "src\version.py"
$SetupScript = "setup.iss"

# 2. Verificar Inno Setup
if (-not (Test-Path $InnoSetupPath)) {
    Write-Host "ADVERTENCIA: No se encontro Inno Setup instalado en: $InnoSetupPath" -ForegroundColor Yellow
    Write-Host "El script preparara los archivos, pero DEBES compilar 'setup.iss' manualmente." -ForegroundColor Yellow
    Write-Host "Descarga Inno Setup aqui: https://jrsoftware.org/isdl.php" -ForegroundColor Gray
}

# 3. Construir la Aplicacion
Write-Host "-------- FASE 1: CONSTRUCCION --------" -ForegroundColor Green

# Limpiar dist previo
if (Test-Path "dist\SistemaAdmin") {
    Write-Host "Limpiando compilacion anterior..."
    Remove-Item "dist\SistemaAdmin" -Recurse -Force
}

# Llamar PyInstaller
Write-Host "Ejecutando PyInstaller..."
python -m PyInstaller --noconfirm --onedir --windowed --name "SistemaAdmin" --add-data "assets;assets" --add-data "src/admin_app/styles.qss;src/admin_app" --hidden-import "alembic" --hidden-import "psycopg2" --hidden-import "pg8000" run_app.py

if (-not $?) {
    Write-Host "Error Critico: Falla en PyInstaller." -ForegroundColor Red
    exit 1
}

# Copiar extras (Alembic)
Write-Host "Copiando sistema de migraciones (Alembic)..."
$DistDir = "dist\SistemaAdmin"
Copy-Item -Path "alembic" -Destination "$DistDir\alembic" -Recurse -Force
Copy-Item -Path "alembic.ini" -Destination "$DistDir\alembic.ini" -Force
if (Test-Path "assets\icon.ico") {
    Copy-Item -Path "assets\icon.ico" -Destination "$DistDir\icon.ico" -Force
}

# 4. Actualizar Version en setup.iss
Write-Host "-------- FASE 2: PREPARACION DEL SETUP --------" -ForegroundColor Green
$Version = (Get-Content $VersionFile | Select-String 'VERSION = "(.*)"').Matches.Groups[1].Value
Write-Host "Version detectada: $Version"

# Leer setup.iss
$IssContent = Get-Content $SetupScript -Raw
# Reemplazar version (Regex simple)
$NewIssContent = $IssContent -replace '#define MyAppVersion ".*?"', "#define MyAppVersion ""$Version"""
Set-Content $SetupScript $NewIssContent
Write-Host "Version actualizada en $SetupScript"

# 5. Compilar
if (Test-Path $InnoSetupPath) {
    Write-Host "-------- FASE 3: COMPILACION DEL INSTALADOR --------" -ForegroundColor Green
    Write-Host "Compilando $SetupScript con Inno Setup..."
    & $InnoSetupPath $SetupScript
    
    if ($?) {
        Write-Host "EXITO! Instalador generado en carpeta 'releases'." -ForegroundColor Cyan
    } else {
        Write-Host "Error durante la compilacion de Inno Setup." -ForegroundColor Red
    }
} else {
    Write-Host "-------- FINALIZADO (PENDIENTE COMPILACION MANUAL) --------" -ForegroundColor Yellow
    Write-Host "Los archivos estan listos en 'dist\SistemaAdmin'."
    Write-Host "La configuracion esta lista en '$SetupScript'."
    Write-Host "PASO FINAL: Instala Inno Setup y haz doble clic en '$SetupScript' para generar el ejecutable."
}
