![1768307293703](image/README/1768307293703.png)![1768307300656](image/README/1768307300656.png)# Sistema-Admin-2.0 (Python + PySide6)

Este proyecto es un punto de partida para un sistema administrativo de escritorio en Python usando PySide6 (Qt for Python) y SQLite.

## Requisitos

- Windows 10/11
- PowerShell (pwsh)
- Python 3.11+ recomendado

## Entorno

Se recomienda un entorno virtual:

```pwsh
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Ejecutar la aplicación


```pwsh
python -m src.admin_app
```

## Configuración con .env

La aplicación carga automáticamente variables desde un archivo `.env` si está presente (usa `python-dotenv`).

- `DATABASE_URL` controla el backend de base de datos. Si no está definida, se usa SQLite en `data/app.db`. Para pruebas locales sin servidor Postgres, simplemente omite esta variable o borra el `.env` junto al ejecutable.
- `ADMIN_APP_DATA_DIR` permite forzar la carpeta donde se guardan datos cuando el programa está empaquetado.
- Usa `.env.example` como plantilla. No se distribuye ningún secreto; personalízalo por entorno.

## Instalación paso a paso (Windows)

Estos son los pasos mínimos para preparar y ejecutar la aplicación en una máquina Windows de desarrollo.

1) Crear y activar un entorno virtual (PowerShell):

```pwsh
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Actualizar pip e instalar dependencias:

```pwsh
python -m pip install --upgrade pip
pip install -r requirements.txt
```

3) Inicializar la base de datos local (SQLite).

La app usa `data/app.db` por defecto. Para crear la base de datos y las filas iniciales (seed), ejecuta:

```pwsh
python scripts/init_db_remote.py
# (El script funciona tanto para SQLite local como para conexiones remotas si se configura DATABASE_URL)
```

4) Ejecutar la aplicación (desarrollo):

```pwsh
python -m src.admin_app
```

5) Ejecutar tests (pytest):

```pwsh
python -m pytest -q
```

## Empaquetado a .exe (PyInstaller)

El repositorio incluye `pyinstaller.spec` y un script PowerShell para facilitar la creación del ejecutable.

1) Abrir PowerShell como administrador (si se necesita acceso para agregar reglas de firewall al empacar redes).
2) Ejecutar el script de build:

```pwsh
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/build-exe.ps1
```

Al finalizar encontrarás el ejecutable en `dist/Sistema-Admin-2.0/Sistema-Admin-2.0.exe`.

> Nota: el script copia `.env.example` y, si existe, `.env` al directorio `dist/`. Si deseas entregar el instalador sin configuración predeterminada, elimina esos archivos después del build o ejecuta PyInstaller directamente (`.venv\Scripts\python.exe -m PyInstaller pyinstaller.spec`).

Si deseas además generar un ejecutable de migración (sin requerir Python en el cliente), usa el switch `-WithMigrator`:

```pwsh
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/build-exe.ps1 -WithMigrator
```

Esto creará también `dist/migrate-sqlite-to-postgres.exe`.

### Notas sobre datos y configuración

- En desarrollo, la base de datos está en `./data/app.db`.
- Para desplegar en múltiples estaciones, use PostgreSQL y configure `DATABASE_URL` en un archivo `.env` junto al exe o en la sesión del entorno.
- Variables útiles:
  - `DATABASE_URL` - URL SQLAlchemy para la BD remota (p. ej. postgresql+psycopg2://user:pass@host:5432/dbname)
  - `ADMIN_APP_DATA_DIR` - para forzar la ruta de almacenamiento de datos (por ejemplo, `%APPDATA%\Sistema-Admin-2.0\data`).

## ¿Qué hacer si algo falla?

- Si falta una dependencia, confirma el entorno activo (`.venv\Scripts\Activate.ps1`) y vuelve a instalar `pip install -r requirements.txt`.
- Para problemas de PySide6 en Windows: revisa que la versión de PySide6 sea compatible con tu versión de Python (3.11+ recomendado).
- Si la aplicación no carga datos, revisa `data/app.db` o la variable `DATABASE_URL` si usas Postgres. El archivo `scripts/init_db_remote.py` crea tablas y datos seed.

Si quieres, puedo añadir un pequeño script 'quickstart.ps1' que haga los pasos 1–3 automáticamente en una máquina de desarrollo Windows.

## Estructura

- `src/admin_app/` Código fuente de la app
  - `db.py` Helpers de conexión SQLite y sessions
  - `models.py` Modelos SQLAlchemy (p.ej., `Customer`)
  - `repository.py` Operaciones CRUD y seed inicial
  - `ui/` Vistas Qt (p.ej., `CustomersView`)
- `tests/` Pruebas unitarias
- `data/` (autogenerado) Base de datos SQLite (`app.db`)

## Ejecutable (Windows)

Para generar un .exe de la aplicación (PySide6 + SQLite):

1. Requisitos: Python 3.11+, PowerShell.
2. Ejecuta el script de build:

```pwsh
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/build-exe.ps1
```

Al finalizar, encontrarás el ejecutable en `dist/Sistema-Admin-2.0/Sistema-Admin-2.0.exe`.

### Persistencia de datos entre versiones

- En desarrollo, la base de datos vive en `./data/app.db`.
- En el ejecutable (PyInstaller), los datos se guardan en `%APPDATA%/Sistema-Admin-2.0/data/app.db` por usuario.
- Puedes forzar la ruta con la variable de entorno `ADMIN_APP_DATA_DIR`.

Esto asegura que si reemplazas el .exe por una versión nueva, la base de datos del usuario no cambia ni se sobrescribe.

### Incluir recursos

El empaquetado incluye `assets/img/logo.png` y los estilos `styles.qss` y `styles-dark.qss`. Si agregas recursos nuevos, añádelos también a `pyinstaller.spec` en la sección `datas`.

## Despliegue multiusuario (servidor de base de datos)

Para que varias PCs usen la misma base de datos de forma fluida y segura, se recomienda centralizar la BD en un servidor (PostgreSQL) y apuntar los clientes a esa URL. SQLite en red compartida no es recomendable por bloqueos/latencias y riesgo de corrupción.

### Opción recomendada: PostgreSQL

1. Instalar PostgreSQL (PC Servidor)

- Descargue desde postgresql.org y durante la instalación anote: contraseña del usuario `postgres` y puerto (por defecto 5432).

2. Crear base y usuario dedicados (en el servidor)

- Abra pgAdmin o la consola y ejecute:
  - CREATE DATABASE admin_app ENCODING 'UTF8';
  - CREATE USER admin_app WITH PASSWORD 'TuClaveSegura';
  - GRANT ALL PRIVILEGES ON DATABASE admin_app TO admin_app;

3. Habilitar conexiones remotas

- En `postgresql.conf`: `listen_addresses = '*'`
- En `pg_hba.conf`: agregue una línea para su red, por ejemplo: `host all all 192.168.1.0/24 md5`
- Abra el puerto 5432 en el Firewall de Windows (entrante TCP) sólo para la red local.
- Reinicie el servicio de PostgreSQL.

4. Inicializar el esquema desde la app

- En el servidor o en una PC con acceso:
  - Configure `DATABASE_URL` (ver .env.example), p. ej.:

    ```text
  postgresql+psycopg2://admin_app:TuClaveSegura@192.168.1.10:5432/admin_app
    ```

  - Ejecute el script: `python scripts/init_db_remote.py` (crea tablas y seed básico).

5) Configurar los clientes (PCs usuarias)

  - Copie un archivo `.env` junto al EXE (o en el proyecto si ejecuta con Python) con:

  - `DATABASE_URL=postgresql+psycopg2://admin_app:TuClaveSegura@IP_SERVIDOR:5432/admin_app`

  - La app detecta automáticamente `DATABASE_URL` y usará PostgreSQL; si no está, usará SQLite local.

6) Rendimiento y estabilidad

  - La app usa pool de conexiones (pre_ping, pool_size, max_overflow, recycle) para conexiones remotas estables.
  - En redes lentas, prefiera cableado y evite Wi‑Fi saturado.
  - Mantenga el servidor con energía estable y UPS si es posible.

### Alternativas

- MySQL/MariaDB: instale `pymysql` y use URL `mysql+pymysql://...`
- SQL Server Express: instale `pyodbc` y use URL `mssql+pyodbc://...` con un driver ODBC instalado.
- API intermedia: para más control/seguridad, puede exponerse una API (FastAPI) y que la app cliente consuma esa API.

### Migración desde SQLite (opcional)
El script `scripts/migrate_sqlite_to_postgres.py` copia los datos del archivo SQLite a PostgreSQL usando los modelos del proyecto.

1. Haga un respaldo rápido: `Copy-Item data/app.db data/app-backup.db`.
2. Ejecute una simulación para validar conexiones:

   ```pwsh
   .\.venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py --dry-run --target "postgresql+psycopg2://usuario:clave@host:5432/base"
   ```

3. Si todo va bien, lance la migración real (remueva `--dry-run`). Puede usar `--truncate` para limpiar tablas destino o `--no-preserve-ids` si no necesita conservar los IDs originales.

El script también ajusta las secuencias en Postgres para mantener los autoincrement coherentes.

### Entrega al cliente con PostgreSQL en su PC

Escenario: el cliente instala PostgreSQL y recibe el contenido de `dist/`.

1) Instalar PostgreSQL (recordar puerto y contraseña del superusuario `postgres`).
2) En `dist/.env`, configurar la URL (ejemplo local):
  ```
  DATABASE_URL=postgresql+psycopg://admin_app:TuClaveSegura@127.0.0.1:5432/admin_app
  ```
3) Crear base y usuario (vía psql):
  ```pwsh
  "C:\\Program Files\\PostgreSQL\\18\\bin\\psql.exe" -h 127.0.0.1 -U postgres -d postgres -c "CREATE USER admin_app WITH PASSWORD 'TuClaveSegura' LOGIN;"
  "C:\\Program Files\\PostgreSQL\\18\\bin\\psql.exe" -h 127.0.0.1 -U postgres -d postgres -c "CREATE DATABASE admin_app ENCODING 'UTF8';"
  "C:\\Program Files\\PostgreSQL\\18\\bin\\psql.exe" -h 127.0.0.1 -U postgres -d admin_app -c "GRANT USAGE, CREATE ON SCHEMA public TO admin_app;"
  ```
4) Si se debe migrar datos desde un SQLite previo, ejecutar (si construiste con `-WithMigrator`):
  ```pwsh
  .\migrate-sqlite-to-postgres.exe --sqlite "C:\\ruta\\al\\app.db" --on-conflict ignore
  ```
  - Usa `--truncate` para reemplazar completamente los datos destino.
5) Ejecutar `Sistema-Admin-2.0.exe`. Con `DATABASE_URL` la app usará PostgreSQL; si no, usará SQLite local.
