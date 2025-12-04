param(
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$BackupDir = "C:\\Backups\\admin_app",
    [int]$KeepDays = 7
)

if (-not $DatabaseUrl) { Write-Error "DATABASE_URL no definida. Pasa -DatabaseUrl o configura la variable de entorno."; exit 2 }

# Extraer parámetros para pg_dump si la URL es del tipo postgresql://user:pass@host:port/db
$uri = [System.Uri]$DatabaseUrl.Replace("postgresql+psycopg2://","postgresql://")
$host = $uri.Host
$port = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }
$db = $uri.AbsolutePath.Trim('/')
$user = $uri.UserInfo.Split(':')[0]
$pass = if ($uri.UserInfo.Contains(':')) { $uri.UserInfo.Split(':')[1] } else { "" }

# Crear carpeta
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

# Archivo con fecha
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $BackupDir "${db}_$timestamp.sql"

# Configurar password para pg_dump
$env:PGPASSWORD = $pass

# Ejecutar pg_dump (requiere que pg_dump esté en PATH)
pg_dump -h $host -p $port -U $user -d $db -F p -f $backupFile
if ($LASTEXITCODE -ne 0) { Write-Error "pg_dump falló con código $LASTEXITCODE"; exit $LASTEXITCODE }

Write-Host "Backup creado: $backupFile"

# Rotación: eliminar archivos viejos
Get-ChildItem -Path $BackupDir -Filter "${db}_*.sql" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) } | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "Rotación completada (manteniendo $KeepDays días)."
