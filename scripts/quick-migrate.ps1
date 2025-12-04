Param(
  [string]$Target,
  [string]$Sqlite = "data/app.db",
  [switch]$NoPreserveIds,
  [switch]$Truncate,
  [switch]$AutoConfirm,
  [switch]$CleanBackup
)

$ErrorActionPreference = 'Stop'

# Ubicar raíz del proyecto
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$proj = Split-Path -Parent $scriptRoot
Set-Location $proj

if (-not $Target) {
  Write-Host "ERROR: Debes indicar --Target 'postgresql+psycopg2://user:pass@host:port/db'"
  exit 2
}

# Encontrar python dentro del .venv
$venvPython = Join-Path $proj '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
  Write-Host ".venv no encontrado en el proyecto. Por favor crea/activa el entorno virtual antes." -ForegroundColor Yellow
  Write-Host "Puedes crear uno con: py -3 -m venv .venv" -ForegroundColor Yellow
  exit 3
}

Write-Host "Proyecto: $proj"
Write-Host "SQLite fuente: $Sqlite"
Write-Host "Destino Postgres: $Target"

# Backup
if (-not (Test-Path $Sqlite)) {
  Write-Host "ERROR: archivo sqlite no encontrado: $Sqlite" -ForegroundColor Red
  exit 4
}

$ts = Get-Date -Format 'yyyyMMddHHmmss'
$bak = Join-Path $proj "data/app.db.bak.$ts"
Copy-Item -Path $Sqlite -Destination $bak -Force
Write-Host "Backup creado: $bak"

if ($CleanBackup) {
  # eliminar backups antiguos opcional (mantener últimos 5)
  $backups = Get-ChildItem -Path (Join-Path $proj 'data') -Filter 'app.db.bak.*' | Sort-Object LastWriteTime -Descending
  $keep = 5
  if ($backups.Count -gt $keep) {
    $toRemove = $backups | Select-Object -Skip $keep
    foreach ($b in $toRemove) { Remove-Item $b.FullName -Force }
  }
}

# Construir argumentos base
$baseArgs = @('--sqlite', $Sqlite, '--target', $Target)
if ($NoPreserveIds) { $baseArgs += '--no-preserve-ids' }
if ($Truncate) { $baseArgs += '--truncate' }

Write-Host "Ejecutando dry-run (simulación)...`n"
& $venvPython 'scripts/migrate_sqlite_to_postgres.py' @baseArgs '--dry-run'

if (-not $AutoConfirm) {
  $answer = Read-Host "¿Deseas continuar con la migración real? (Y/n)"
  if ($answer -ne '' -and $answer.ToLower() -ne 'y' -and $answer.ToLower() -ne 'yes') {
    Write-Host "Migración cancelada por usuario." -ForegroundColor Yellow
    exit 0
  }
}

Write-Host "Iniciando migración real...`n"
& $venvPython 'scripts/migrate_sqlite_to_postgres.py' @baseArgs

Write-Host "Migración finalizada. Ejecutando verificación de conteos...`n"
& $venvPython 'scripts/_migration_verify.py' --sqlite $Sqlite --target $Target

Write-Host "Proceso completado." -ForegroundColor Green
