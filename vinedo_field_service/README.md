# Viñedo Field Service v1.3.0

Módulo de Odoo 19 para gestión completa de viñedos.

## Características

### 🗺️ Gestión de Fincas
- Geolocalización con latitud/longitud
- **Widget de mapa interactivo** con Leaflet.js (compatible Odoo 19 OWL)
- Dibujo de polígonos para delimitar fincas
- Widget personalizado con botón pantalla completa
- Almacenamiento GeoJSON Feature
- Validación de coordenadas GPS
- Vinculación con territorios
- Búsquedas y filtros por territorio

### 📍 Posicionamiento GPS
Ver guía completa en [`doc/POSICIONAMIENTO_GPS.md`](doc/POSICIONAMIENTO_GPS.md)

**Cómo obtener coordenadas:**
1. Abre Google Maps
2. Haz clic derecho en tu finca → Copiar coordenadas
3. Primer número = Latitud (40.4 para centro España)
4. Segundo número = Longitud (-3.7 para centro España)

**Ejemplo España:**
- Latitud: 42.5 (positivo = Norte)
- Longitud: -3.0 (negativo = Oeste de Greenwich)

### 🍇 Variedades y Plantaciones
- Catálogo de variedades de uva
- Registro de plantaciones por finca y variedad
- Control de superficie y fecha de plantación
- Constraint de unicidad (finca + variedad)

### 📊 Añadas (Cosechas)
- Registro por finca, variedad y año
- Análisis: graduación alcohólica, acidez, cantidad
- Nombre auto-generado
- Agrupaciones y filtros avanzados
- Constraint de unicidad

### 🛠️ Trabajos y Mantenimiento
- **Tratamientos**: fitosanitarios y otros con producto y dosis
- **Podas**: registro de podas de invierno y en verde
- **Trabajos**: registro de horas por empleado y tipo
- **Aportaciones**: minerales con producto y cantidad

### ⚡ Optimizaciones
- Índices en campos clave (búsquedas rápidas)
- Ordenamiento predeterminado en vistas
- Validaciones y constraints SQL
- Normalización automática de polígonos (sin recursión)
- Campos calculados automáticamente
- Vistas de búsqueda con filtros y agrupaciones
- Suma/promedio automático en listas

## Instalación

1. Copiar el módulo a tu carpeta de addons
2. Actualizar lista de aplicaciones
3. Instalar "Viñedo - Field Service"

## Uso del Mapa

- El widget de mapa carga automáticamente Leaflet + Leaflet.draw desde CDN
- Botón "Editar pantalla completa" para trabajar con más espacio
- Dibujar polígono → se guarda como GeoJSON Feature
- Normalización automática al guardar

## Dependencias

- `base`
- `hr` (para empleados en trabajos/tratamientos/podas)

## Notas Técnicas

**Modelo de datos:**
- 9 modelos principales con relaciones One2many/Many2one
- Constraints SQL para unicidad
- Campos compute con store=True
- Validaciones @api.constrains

**Rendimiento:**
- Índices en campos FK y búsquedas frecuentes
- Normalización de polígonos sin write recursivo (SQL directo)
- Logging de errores sin bloquear operaciones
- Uso de `@api.model_create_multi` para creación masiva

**Próximas mejoras sugeridas:**
- Integración robusta con geoengine
- Proyección de coordenadas con proj4
- Reports PDF de añadas y tratamientos
- Dashboard analítico con gráficos
- Importación/exportación de datos
- Integración con inventario/facturación

## Autor

ToniSistemas  
https://github.com/ToniSistemas/odoo_custom

## Licencia

LGPL-3

