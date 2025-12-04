# Guía: IDs Automáticos y Relaciones entre Tablas

## 🆔 IDs Automáticos

### ¿Qué son?
Los IDs automáticos agregan automáticamente una columna `id` con incremento automático a tus tablas de parámetros. Esto es útil para:
- Identificar únicamente cada fila
- Crear relaciones con otras tablas
- Facilitar la gestión de datos

### Cómo usar:
1. Al crear una nueva tabla, la opción "Incluir columna ID automática" está marcada por defecto
2. Si la desmarcas, la tabla no tendrá una columna ID automática
3. Solo las tablas con ID automático pueden ser usadas como "tablas padre" en relaciones

## 🔗 Relaciones entre Tablas

### ¿Para qué sirven?
Las relaciones permiten conectar datos de una tabla con otra. Ejemplos:
- **Tabla Materiales** (padre): id, nombre, precio
- **Tabla Colores** (hija): id, id_material, color, codigo_hex

### Cómo crear una relación:

#### 1. Crear la tabla padre primero:
- Ejemplo: "Materiales"
- Asegúrate de que tenga "ID automático" activado
- Agrega columnas como: nombre, precio, descripción

#### 2. Crear la tabla hija:
- Ejemplo: "Colores de Materiales"  
- En "Relacionar con tabla" selecciona "Materiales"
- El nombre de la columna de relación se sugiere automáticamente: `id_materiales`
- Puedes cambiarlo si quieres: `material_id`, `id_mat`, etc.

#### 3. Resultado:
La tabla hija tendrá automáticamente:
- Su columna ID (si está habilitada)
- Sus columnas personalizadas
- Una columna adicional para la relación (ej: `id_material`)

## 📋 Interfaz Mejorada

### Nueva información mostrada:
- **Columnas**: Muestra "(con ID)" si la tabla tiene ID automático
- **Relación**: Muestra "→ Tabla Padre (columna_fk)" o "---" si no hay relación

### Ejemplo de visualización:
```
Nombre               | Descripción          | Columnas      | Relación
--------------------|---------------------|---------------|----------------
Materiales          | Lista de materiales | 4 columnas (con ID) | ---
Colores             | Colores por material| 3 columnas (con ID) | → Materiales (id_material)
Precios Especiales  | Precios por color   | 2 columnas    | → Colores (id_color)
```

## 💡 Casos de Uso Comunes

### 1. Catálogo de Productos:
- **Categorías** (padre): id, nombre, descripción
- **Productos** (hijo): id, id_categoria, nombre, precio

### 2. Configuración de Ventanas:
- **Perfiles** (padre): id, tipo, material, medida_estandar
- **Vidrios** (hijo): id, id_perfil, tipo_vidrio, espesor, precio_m2

### 3. Sistema de Inventario:
- **Proveedores** (padre): id, nombre, telefono, email
- **Materiales** (hijo): id, id_proveedor, codigo, nombre, stock

## ⚠️ Consideraciones Importantes

1. **Solo tablas con ID automático** pueden ser tablas padre
2. **El nombre de la columna de relación** debe ser único en la tabla
3. **Las relaciones son opcionales** - puedes crear tablas independientes
4. **Una tabla puede ser padre e hija** al mismo tiempo (para jerarquías complejas)

## 🔧 Próximos Pasos

Con esta funcionalidad implementada, ahora puedes:
1. ✅ Crear tablas con IDs automáticos
2. ✅ Establecer relaciones entre tablas
3. 🔄 Agregar valores manteniendo las relaciones
4. 📊 Consultar datos relacionados (próxima funcionalidad)

¡Tu sistema de parámetros dinámicos ahora es mucho más potente y flexible!