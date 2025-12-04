# Instrucciones para agentes en este repositorio (Sistema-Admin-2.0)

Estado actual del repo
- Workspace: `c:\Users\Jesus\OneDrive\Documents\Sistema-Admin-2.0`
- SO/terminal: Windows con PowerShell (pwsh). Genera comandos compatibles con pwsh.
- Stack establecido: Python 3.11+, PySide6 (Qt), SQLAlchemy 2.x, SQLite (archivo `data/app.db`).

Principios de operación
- Escribe mensajes y código en español cuando sea contenido para el usuario; nombra símbolos en inglés si el stack lo prefiere.
- Usa comandos de PowerShell y ejecútalos tú cuando sea razonable (p. ej., para inicializar dependencias), mostrando resultados resumidos.
- Mantén cambios pequeños y verificables. Tras crear código ejecutable, corre un smoke test mínimo.
- No realices llamadas externas ni uses secretos salvo instrucción explícita del usuario.

Descubrimiento y decisiones tempranas
- Primero, escanea el repo; si sigue vacío, confirma 1–2 decisiones críticas antes de scaffold: stack/tecnología (p. ej., Node.js/.NET/Python), tipo de app (API, web, escritorio), y base de datos (SQLite/Postgres/otra).
- Si el usuario no especifica, propone 2–3 opciones viables y argumenta pros/contras en 2–3 líneas; no avances con una elección sin aprobación cuando la decisión cambia el rumbo del proyecto.

Patrón de trabajo actual (Python desktop)
- Estructura clave: `src/admin_app/` (app), `tests/` (pytest), `.vscode/` (tareas y debug), `data/` (SQLite, ignorado por git).
- Entrypoint: `python -m src.admin_app` ejecuta `__main__.py` → `MainWindow`.
- Datos: SQLite se crea en `./data/app.db`; `init_db()` siembra 3 clientes demo.

Flujos de trabajo de desarrollo
- Instalar deps (pwsh): activar venv y `pip install -r requirements.txt`.
- Ejecutar app: `python -m src.admin_app` o tarea VS Code “Run App”.
- Debug: `launch.json` con `debugpy` (config “Python: Run App (PySide6)”).
- Tests: `python -m pytest -q` o tarea “Run Tests”. Tests de base no dependen de GUI; para GUI usar `pytest-qt` si se añade.

Convenciones del repositorio
- Capas: `ui/` (Qt widgets/views), `models.py` (ORM), `repository.py` (consultas/seed), `db.py` (engine/sessions).
- Evitar lógica de negocio en widgets; preferir funciones/repos y modelos.
- `data/` ignorado en git; no commitear `app.db`.

Puntos de extensión típicos
- Añadir entidades: definir modelo en `models.py`, exponer consultas en `repository.py`, crear vista en `ui/`.
- Migraciones: por ahora, `Base.metadata.create_all`. Si se requieren cambios controlados, integrar Alembic.
- Reporting/impresión: generar PDF/HTML desde Python y lanzar diálogo de impresión de Qt.

Entrega y validación
- Tras cambios: ejecutar tests (`pytest`), abrir la app y verificar carga de `CustomersView` y datos seed.
- Documentar en README cualquier comando adicional o ajustes de entorno.

- Utiliza por defecto python.
- Haz uso de buenas prácticas de desarrollo.
- Refactora el código siempre que se pueda.
- Crea tests de las funcionalidades principales.
- Crea un entorno virtual para las dependencias.
Notas finales
- Actualiza este documento al agregar nuevas capas (migraciones, autenticación, reporting) y tareas de VS Code.

- Utiliza por defecto python.
- Haz uso de buenas prácticas de desarrollo.
- Refactora el código siempre que se pueda.
- Crea tests de las funcionalidades principales.
- Crea un entorno virtual para las dependencias.