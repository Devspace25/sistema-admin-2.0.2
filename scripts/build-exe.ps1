param(
  [switch]$Clean,
  [switch]$WithMigrator
)

$ErrorActionPreference = 'Stop'

# Ruta del proyecto
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$proj = Split-Path -Parent $root

Set-Location $proj

if ($Clean) {
  if (Test-Path 'dist') { Remove-Item 'dist' -Recurse -Force }
  if (Test-Path 'build') { Remove-Item 'build' -Recurse -Force }
}

# Asegurar entorno virtual
if (-not (Test-Path '.venv')) {
  py -3 -m venv .venv
}

$python = Join-Path (Resolve-Path '.venv').Path 'Scripts/python.exe'

# Instalar dependencias
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
& $python -m pip install pyinstaller pillow

# Generar ICO desde PNG antes del build
& $python scripts/make-ico.py

# Compilar con spec
& $python -m PyInstaller pyinstaller.spec

# (Opcional) Compilar ejecutable de migración (consola) para clientes
if ($WithMigrator) {
  Write-Host "Construyendo migrador SQLite -> PostgreSQL..."
  & $python -m PyInstaller --onefile --console `
    --name migrate-sqlite-to-postgres `
    scripts/migrate_sqlite_to_postgres.py
}

# Copiar .env.example junto al ejecutable para facilitar configuración en clientes
$distDir = Join-Path $proj 'dist'
$exePath = Join-Path $distDir 'Sistema-Admin-2.0.exe'
$envExample = Join-Path $proj '.env.example'
if (Test-Path $envExample) {
  Copy-Item $envExample (Join-Path $distDir '.env.example') -Force
  Write-Host "Copiado .env.example a: $distDir"
  $envTarget = Join-Path $distDir '.env'
  if (-not (Test-Path $envTarget)) {
    Copy-Item $envExample $envTarget -Force
    Write-Host "Generado .env (prellenado) en: $envTarget"
  }
}

Write-Host "Hecho. Ejecutable en: $exePath"
