param(
    [string]$DistDir = "$PSScriptRoot/../dist",
    [string]$OutZip = "$PSScriptRoot/../dist/Sistema-Admin-2.0.zip"
)

$ErrorActionPreference = 'Stop'

$exePath = Join-Path (Resolve-Path $DistDir) 'Sistema-Admin-2.0.exe'
if (!(Test-Path $exePath)) {
    throw "No se encontró el ejecutable en: $exePath. Ejecuta scripts/build-exe.ps1 primero."
}

$tmp = Join-Path $env:TEMP ('sa2_pkg_' + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

Copy-Item -Force -Path $exePath -Destination (Join-Path $tmp 'Sistema-Admin-2.0.exe')

$readme = @"
Sistema-Admin 2.0 — Despliegue
================================

Ejecución
---------
1. Doble clic en "Sistema-Admin-2.0.exe".

Datos persistentes
------------------
- La base de datos se guarda en: %APPDATA%\Sistema-Admin-2.0\data\app.db
- Para reutilizar datos existentes, copie su app.db a esa ruta antes de abrir el exe.

Configuración (opcional)
------------------------
- APP_THEME=dark para tema oscuro.
- ADMIN_APP_DATA_DIR=C:\\MiRuta\\datos para cambiar la carpeta de datos.

Soporte
-------
Ante cualquier error, comparta la captura y el archivo de log si existiera.
"@
Set-Content -LiteralPath (Join-Path $tmp 'README-DEPLOY.txt') -Value $readme -Encoding UTF8

if (Test-Path $OutZip) { Remove-Item -Force $OutZip }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($tmp, $OutZip)

Write-Host "Paquete creado:" (Resolve-Path $OutZip)
