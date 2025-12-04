param(
  [switch]$Clean,
  [string]$OutDir = "$PSScriptRoot\..\releases",
  [switch]$NoZip
)

$ErrorActionPreference = 'Stop'

# Root project folder
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$proj = Split-Path -Parent $scriptRoot
Set-Location $proj

Write-Host "Proyecto: $proj"

if ($Clean) {
  Write-Host "Limpiando carpetas build/dist antes de compilar..."
  if (Test-Path (Join-Path $proj 'build')) { Remove-Item (Join-Path $proj 'build') -Recurse -Force }
  if (Test-Path (Join-Path $proj 'dist'))  { Remove-Item (Join-Path $proj 'dist') -Recurse -Force }
  if (Test-Path (Join-Path $proj 'release')) { Remove-Item (Join-Path $proj 'release') -Recurse -Force }
}

# Ensure virtualenv python exists
$venvPy = Join-Path $proj '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
  Write-Host ".venv no encontrado. Creando entorno virtual..."
  py -3 -m venv .venv
}

Write-Host "Instalando dependencias (si procede)..."
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r requirements.txt
& $venvPy -m pip install pyinstaller pillow

Write-Host "Generando icono .ico desde PNG (si aplica)..."
& $venvPy scripts/make-ico.py

Write-Host "Ejecutando build (PyInstaller) usando scripts/build-exe.ps1..."
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/build-exe.ps1

if ($NoZip) {
  Write-Host "No se generó ZIP (--NoZip). Build finalizado en dist/" -ForegroundColor Green
  exit 0
}

# Crear carpeta releases
$out = Resolve-Path $OutDir -ErrorAction SilentlyContinue
if (-not $out) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

$ts = Get-Date -Format 'yyyyMMdd-HHmm'
$zipName = "Sistema-Admin-2.0-$ts.zip"
$zipPath = Join-Path (Resolve-Path $OutDir) $zipName

Write-Host "Empaquetando dist/Sistema-Admin-2.0 -> $zipPath"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }


# Empaquetar: soportar build en carpeta (dist/Sistema-Admin-2.0) o build single-file (dist/Sistema-Admin-2.0.exe)
$folderPath = Join-Path $proj 'dist\Sistema-Admin-2.0'
$exePath = Join-Path $proj 'dist\Sistema-Admin-2.0.exe'
if (Test-Path $folderPath) {
  Compress-Archive -Path (Join-Path $folderPath '*') -DestinationPath $zipPath -Force
} elseif (Test-Path $exePath) {
  # Comprimir todo el contenido de dist/ (incluye exe, .env y otros recursos)
  $distAll = Join-Path $proj 'dist\*'
  Compress-Archive -Path $distAll -DestinationPath $zipPath -Force
} else {
  Write-Host "ERROR: no se encontró ninguna salida de build en 'dist/'. Revisa el directorio de salida." -ForegroundColor Red
  exit 5
}

Write-Host "ZIP creado: $zipPath" -ForegroundColor Green
Write-Host "Lista de archivos en el ZIP (primeros 20):"
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::OpenRead($zipPath).Entries | Select-Object -First 20 | ForEach-Object { Write-Host " - $_" }

Write-Host "Quick build completado." -ForegroundColor Cyan
