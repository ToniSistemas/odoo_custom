Módulo `vinedo_field_service` — Gestión básica de viñedos

Incluye:
- Modelos: Finca, Variedad, Plantación, Añada, Tratamiento, Poda, Trabajo, Aportación, Territorio
- Vistas básicas (tree/form) y permisos para usuarios internos

Notas:
- Geo: latitud/longitud en la ficha de `Finca`. Para mapa se puede integrar `web_map` o `geoengine` más adelante.
- Plantación: la fecha de plantación se registra por variedad en cada finca.
- Añadas: registran graduación, acidez y cantidad por finca y variedad.

Siguientes pasos sugeridos:
- Integrar mapa para marcar polígonos (territorios) con `geoengine` o `web_map`.
- Añadir reports y workflows para planificación de campañas.

Mapa y Geoengine

- El widget `vinedo_map` guarda ahora un GeoJSON `Feature` completo en el campo `polygon`.
- La vista acepta almacenar/leer tanto geometrías (GeoJSON geometry) como un Feature; el módulo normaliza a `Feature`.
- Hay un botón para editar en pantalla completa en la vista de `Finca`.

Proyección

- El widget puede ampliarse para proyectar coordenadas si instalas `proj4` y pasas opciones al widget. Actualmente guarda en EPSG:4326 (lat/lng).

Integración con geoengine

- Si instalas un módulo `geoengine` compatible, el módulo intentará crear un `geoengine.layer` llamado `vinedo_fincas` y añadir características en `geoengine.feature` en un intento de sincronización (esto es "best-effort" y dependerá de la API exacta del paquete instalado).
- Recomendación: instala y configura `geoengine` y ajusta los nombres de campos del feature model según tu instalación para una integración robusta.
