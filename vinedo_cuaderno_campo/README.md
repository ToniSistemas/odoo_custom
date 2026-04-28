# Viñedo - Cuaderno de Campo v2.2.0

Módulo de Odoo 19 CE para la gestión completa del Cuaderno de Campo vitivinícola.

## Características

### Gestión de Fincas
- Geolocalización con latitud/longitud y apertura directa en visor SIGPAC
- Consulta automática de recintos y superficies desde la API de SIGPAC por coordenadas GPS
- Recintos SIGPAC con uso, superficie y distribución de variedades por porcentaje
- Extensión calculada automáticamente en ha y m²
- Vinculación con territorios/D.O.

### Variedades y Plantaciones
- Catálogo de variedades de uva
- Plantaciones por finca y variedad con superficie calculada desde recintos SIGPAC
- Constraint de unicidad por finca + variedad

### Climatología (NUEVO)
- Registro meteorológico diario por finca: temperatura, precipitación, humedad, viento
- Valoración de riesgos (helada, pedrisco, incendio, viento fuerte)

### Seguimiento Fenológico (NUEVO)
- Estados BBCH de la vid por finca y fecha
- Código BBCH, descripción, observaciones

### Añadas (Cosechas)
- Registro por finca, variedad y año con nombre auto-generado
- Análisis enológico completo: graduación alcohólica, cantidad, sulfuroso total, pH, densidad, acidez total, acidez volátil, málico
- **NUEVO:** Fecha de vendimia, cuadrilla, rendimiento (kg/ha), destino (bodega/venta directa)
- **NUEVO:** Lote de cosecha con trazabilidad
- Adjuntos de analíticas PDF por añada

### Podas (NUEVO)
- Registro de poda de invierno y poda en verde
- Vista tree, form, pivot y gráfico

### Tratamientos Fitosanitarios
- Registro por finca con tipo (fitosanitario / otro)
- Campo Producto enlazado a productos Odoo (categoría Fitosanitarios)
- Autoenlace con Registro MAPA por Nº Registro o nombre
- **NUEVO:** Plazo de Seguridad (PHI) en días. Advertencia visual si no se respeta.
- Integración con el Registro Oficial MAPA: búsqueda, importación masiva del catálogo
- Precio unitario y cálculo automático de coste
- Maquinaria utilizada, empleado, dosis/observaciones

### Aportaciones de Minerales/Abonos
- Registro por finca con tipo (mineral / orgánico)
- Producto enlazado a productos Odoo (categoría Minerales)
- Precio de coste tomado automáticamente desde el producto
- Cálculo automático de coste

### Trabajos
- Registro de horas por tipo de trabajo, finca y empleado
- Tipos de trabajo configurables

### Maquinaria
- Catálogo de maquinaria agrícola por tipo
- Titular enlazado a contactos de Odoo
- Fecha de compra

### Informe PDF (NUEVO)
- Informe imprimible del Cuaderno de Campo completo por finca y año
- Incluye: datos de finca, climatología, fenología, tratamientos, añadas, podas, trabajos

### Grupos de Seguridad (NUEVO)
- Grupo "Cuaderno de Campo - Usuario": acceso de lectura/escritura
- Grupo "Cuaderno de Campo - Responsable": acceso completo + informes
- Grupo "Cuaderno de Campo - Consulta": solo lectura

### Vista Calendario (NUEVO)
- Calendario de tratamientos
- Calendario de trabajos
- Calendario de aportaciones

## Instalación

1. Copiar el módulo a la carpeta de addons
2. Actualizar lista de aplicaciones en Odoo
3. Instalar "Viñedo - Cuaderno de Campo"

## Dependencias

- `base`
- `hr` — empleados en trabajos y tratamientos
- `mail` — chatter en añadas
- `product` — enlace con productos de Odoo
- `spreadsheet_dashboard` — grupo Viñedo en Tableros

## Autor

ToniSistemas
https://github.com/ToniSistemas/odoo_custom

## Licencia

LGPL-3
