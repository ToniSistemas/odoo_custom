# Viñedo Field Service v2.1.8

Módulo de Odoo 19 CE para gestión completa de viñedos.

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

### Añadas (Cosechas)
- Registro por finca, variedad y año con nombre auto-generado
- Análisis enológico completo: graduación alcohólica, cantidad, sulfuroso total, pH, densidad, acidez total, acidez volátil, málico
- Agregaciones correctas (avg en campos de ratio, sum en cantidades)
- Adjuntos de analíticas PDF por añada
- Variedad filtrada por las variedades plantadas en la finca seleccionada

### Tratamientos Fitosanitarios
- Registro por finca con tipo (fitosanitario / otro)
- Campo **Producto** enlazado a productos Odoo (categoría Fitosanitarios, filtra automáticamente)
- Autoenlace con Registro MAPA por Referencia Interna (Nº Registro) o por nombre
- Integración con el **Registro Oficial MAPA**: búsqueda, importación masiva del catálogo
- Precio unitario y cálculo automático de coste (litros × precio)
- Maquinaria utilizada, empleado, dosis/observaciones

### Aportaciones de Minerales/Abonos
- Registro por finca con tipo (mineral / orgánico)
- Campo **Producto** enlazado a productos Odoo (categoría Minerales)
- Precio de coste tomado automáticamente desde el producto al seleccionarlo
- Cálculo automático de coste (cantidad × precio)

### Trabajos
- Registro de horas por tipo de trabajo, finca y empleado
- Tipos de trabajo configurables desde Configuración

### Maquinaria
- Catálogo de maquinaria agrícola por tipo
- Titular enlazado a contactos de Odoo (res.partner)
- Fecha de compra

### Costes e Integración con Compras
- Los precios de tratamientos y aportaciones se sincronizan con el coste estándar (`standard_price`) del producto en Odoo
- Compatible con método de valoración **AVCO**: al registrar una compra, el precio se actualiza automáticamente en el producto y se reflejará en los próximos registros

### Vistas y Análisis
- Vistas pivot y gráfico en Añadas, Tratamientos, Aportaciones y Trabajos
- Grupo **Viñedo** en el módulo Tableros (`spreadsheet_dashboard`) para dashboards personalizados
- Filtros, agrupaciones y búsquedas avanzadas en todos los modelos

## Instalación

1. Copiar el módulo a la carpeta de addons
2. Actualizar lista de aplicaciones en Odoo
3. Instalar "Viñedo - Field Service"

## Configuración inicial

1. **Categorías de productos**: crear "Fitosanitarios" y "Minerales/Abonos" en Inventario → Configuración → Categorías de productos
2. **Fitosanitarios Odoo**: al crear un producto fitosanitario, asignar categoría "Fitosanitarios" y poner el Nº de Registro MAPA en el campo **Referencia Interna** para el autoenlace automático
3. **Territorios**: configurar desde Viñedo → Configuración → Territorios
4. **Tipos de trabajo**: configurar desde Viñedo → Configuración

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

