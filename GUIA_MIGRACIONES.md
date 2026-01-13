# Guía de Migraciones de Base de Datos

Este proyecto utiliza **Alembic** para gestionar los cambios en el esquema de la base de datos de forma segura.

## 1. Configuración Inicial (Solo desarrolladores)

Alembic ya está configurado. La migración "Baseline" (`9b0cb9a8992d`) contiene el esquema inicial completo.

Si tienes una base de datos local con datos y sin tabla `alembic_version`, ejecuta el script de migración automática una vez:
```powershell
python scripts/apply_migrations.py
```
Esto marcará tu base de datos actual como "al día" con la versión base.

## 2. Flujo de Trabajo para Nuevas Funcionalidades

Cuando necesites agregar una columna o tabla (ej. agregar `phone` a `Customer`):

1.  Modifica `src/admin_app/models.py` agregando el campo.
2.  Genera el script de migración (autodetección):
    ```powershell
    alembic revision --autogenerate -m "Agregar columna phone a customers"
    ```
3.  Revisa el archivo generado en `alembic/versions/`. Verifica que los cambios sean correctos.
4.  Aplica los cambios en tu PC:
    ```powershell
    alembic upgrade head
    ```
5.  Verifica que tu app funcione.

## 3. Despliegue / Actualización al Cliente

Para actualizar un cliente que ya tiene el sistema:

1.  Incluye en el paquete de actualización:
    *   La carpeta `alembic/` (con las nuevas versiones).
    *   El archivo `alembic.ini`.
    *   El script `scripts/apply_migrations.py`.
2.  Haz que el actualizador o el script de inicio ejecute:
    ```powershell
    python scripts/apply_migrations.py
    ```

El script `apply_migrations.py` es inteligente:
*   Si el cliente tiene una DB vieja sin alembic, la marca como "Baseline" y luego aplica lo nuevo.
*   Si el cliente tiene una DB nueva (vacía), crea todo desde cero.
*   Si el cliente ya tiene alembic, solo aplica las últimas novedades.

## Comandos Típicos de Alembic

*   `alembic current`: Ver versión actual de la DB.
*   `alembic history`: Ver historial de cambios.
*   `alembic upgrade head`: Ir a la última versión.
*   `alembic downgrade -1`: Deshacer la última migración.
