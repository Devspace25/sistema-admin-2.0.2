param(
    [string]$Source,
    [string]$AppDataDir
)

$ErrorActionPreference = 'Stop'

if (-not $Source) {
    $projectRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
    $Source = Join-Path $projectRoot 'data/app.db'
}
if (-not $AppDataDir) {
    $AppDataDir = Join-Path $env:APPDATA 'Sistema-Admin-2.0/data'
}

Write-Host "Copiando base de datos..." -ForegroundColor Cyan
$srcPath = Resolve-Path -LiteralPath $Source
New-Item -ItemType Directory -Force -Path $AppDataDir | Out-Null
$dstPath = Join-Path $AppDataDir 'app.db'
Copy-Item -Force -Path $srcPath -Destination $dstPath
Get-Item $dstPath | Select-Object FullName, Length, LastWriteTime
