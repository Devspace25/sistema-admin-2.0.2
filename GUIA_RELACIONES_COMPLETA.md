# 🎯 Guía Completa: Relaciones y ComboBox en Tablas de Parámetros

## ✅ **Funcionalidades Implementadas**

### 1. **Acceso a Datos de Tabla Materiales desde Código**

```python
from src.admin_app.db import make_session_factory
from src.admin_app.repository import get_parent_table_options, get_parameter_table_data

factory = make_session_factory()
with factory() as session:
    # Obtener opciones para ComboBox (ID + texto para mostrar)
    options = get_parent_table_options(session, tabla_materiales_id)
    
    # Obtener datos completos de la tabla
    full_data = get_parameter_table_data(session, tabla_materiales_id)
```

### 2. **ComboBox Automático para Claves Foráneas**

Cuando crees una tabla relacionada (como "Espesor" → "Materiales"):
- ✅ **Detección automática**: El sistema detecta columnas con `foreign_key`
- ✅ **ComboBox inteligente**: Muestra automáticamente un selector en lugar de campo de texto
- ✅ **Carga dinámica**: Se llenan con los datos reales de la tabla padre
- ✅ **Formato amigable**: Muestra el nombre del material, no solo el ID

### 3. **Validación de Integridad Referencial**

```python
# Valida automáticamente al guardar
validate_foreign_key_value(session, tabla_padre_id, valor_fk)

# Ejemplos de validación:
✅ ID existente (1, 2, 3) → True
❌ ID inexistente (99999) → False  
✅ NULL/None → True (FKs opcionales)
```

### 4. **Consultas de Datos Relacionados**

```python
# Obtener datos combinados (simulando JOIN)
combined = get_related_data(session, tabla_espesor_id, tabla_materiales_id, 'id_materiales')

# Filtrar por material específico
filtered = get_filtered_data_by_parent(session, tabla_espesor_id, tabla_materiales_id, 'id_materiales', material_id)
```

## 🚀 **Ejemplo Práctico: Crear Tabla Espesor**

### Paso 1: Crear la tabla con relación
1. Ve a "Parámetros y Materiales" 
2. Selecciona producto "Corporeo"
3. Clic "Asignar Parámetros"
4. Clic "Crear Nueva Tabla"
5. Configura:
   - **Nombre**: Espesor
   - **✅ ID automático**: Activado
   - **Relacionar con**: Materiales  
   - **Columna relación**: id_materiales

### Paso 2: Agregar columnas personalizadas
- ➕ **Número**: `espesor_mm` (Espesor en milímetros)
- ➕ **Número**: `precio_adicional` (Costo extra por este espesor)
- ➕ **Texto**: `descripcion` (Descripción del espesor)

### Paso 3: Agregar valores
1. Selecciona la tabla "Espesor"
2. Clic "Agregar Valores" 
3. **¡MAGIA!** 🎩 La columna `id_materiales` será un ComboBox con:
   - "-- Seleccionar --"
   - "Aluminio" 
   - "Acero Inoxidable"
   - "PVC"

### Paso 4: Llenar datos
```
| ID | id_materiales | espesor_mm | precio_adicional | descripcion |
|----|---------------|------------|------------------|-------------|
| 1  | Aluminio      | 3.0        | 0.00             | Estándar    |
| 2  | Aluminio      | 6.0        | 5.25             | Reforzado   |
| 3  | Acero Inox.   | 4.0        | 2.50             | Estándar    |
| 4  | PVC           | 2.5        | -1.00            | Económico   |
```

## 📊 **Consultas Avanzadas (Código)**

### Ejemplo: Obtener todos los espesores con sus materiales
```python
factory = make_session_factory()
with factory() as session:
    # IDs de las tablas (obtener de get_product_parameter_tables)
    tabla_espesor_id = 2  # ID de tabla Espesor
    tabla_materiales_id = 1  # ID de tabla Materiales
    
    # Obtener datos relacionados
    combined_data = get_related_data(session, tabla_espesor_id, tabla_materiales_id, 'id_materiales')
    
    for row in combined_data:
        material_name = row['parent_data'].get('nombre', 'Sin material')
        espesor_mm = row['child_data'].get('espesor_mm', 0)
        precio_extra = row['child_data'].get('precio_adicional', 0)
        
        print(f"{material_name}: {espesor_mm}mm (+${precio_extra})")
```

### Ejemplo: Filtrar espesores de Aluminio solamente
```python
# Obtener solo espesores del material con ID 1 (Aluminio)
espesores_aluminio = get_filtered_data_by_parent(session, tabla_espesor_id, tabla_materiales_id, 'id_materiales', 1)

for espesor in espesores_aluminio:
    data = espesor['data']
    print(f"Espesor Aluminio: {data.get('espesor_mm')}mm - {data.get('descripcion')}")
```

## 💡 **Casos de Uso Avanzados**

### 1. **Jerarquía Múltiple**: Categorías → Materiales → Espesores → Precios
```
Categorías (ID auto)
    ↓ id_categoria  
Materiales (ID auto) 
    ↓ id_material
Espesores (ID auto)
    ↓ id_espesor
Precios Especiales
```

### 2. **Configuración Compleja**: Productos → Componentes → Variantes
```
Ventanas (producto base)
├── Marcos (id_ventana)
├── Vidrios (id_ventana) 
└── Herrajes (id_ventana)
    └── Colores Herrajes (id_herraje)
```

### 3. **Sistema de Costos**: Material Base + Modificadores
```
Material Base → Acabados → Tratamientos → Costo Final
```

## 🎉 **Resultado Final**

Ya no necesitas recordar IDs numéricos ni escribir manualmente valores de relación:

❌ **Antes**: Escribir "1" en campo de texto para Aluminio
✅ **Ahora**: Seleccionar "Aluminio" de una lista desplegable

❌ **Antes**: Sin validación, podías escribir IDs inexistentes  
✅ **Ahora**: Solo puedes seleccionar valores válidos

❌ **Antes**: Consultas manuales complejas para datos relacionados
✅ **Ahora**: Funciones helper que hacen JOINs automáticamente

**¡Tu sistema de parámetros dinámicos ahora es profesional y a prueba de errores!** 🚀