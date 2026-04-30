# Plan de mejora - vinedo_cuaderno_campo

## Fase 1: ✅ Correcciones críticas (rutas y manifiesto)
- [x] 1.1 Arreglar __manifest__.py (name, assets, rutas)
- [x] 1.2 Arreglar controllers/main.py (rutas a estáticos)
- [x] 1.3 Arreglar views/vinedo_views.xml (web_icon)
- [x] 1.4 Actualizar README.md e index.html

## Fase 2: ✅ Vistas para Podas (modelo existe sin UI)
- [x] 2.1 Añadir vistas tree, form para vinedo.poda
- [x] 2.2 Añadir action_poda y menuitem
- [x] 2.3 Añadir pivot y graph para podas

## Fase 3: ✅ Climatología
- [x] 3.1 Crear modelo vinedo.registro.clima en models/vinedo.py
- [x] 3.2 Añadir vistas en vinedo_views.xml
- [x] 3.3 Añadir acceso en ir.model.access.csv
- [x] 3.4 Añadir menuitem

## Fase 4: ✅ Seguimiento Fenológico (BBCH)
- [x] 4.1 Crear modelo vinedo.seguimiento.fenologico
- [x] 4.2 Añadir vistas en vinedo_views.xml
- [x] 4.3 Añadir acceso en ir.model.access.csv
- [x] 4.4 Añadir menuitem

## Fase 5: ✅ Mejora de Añadas/Cosecha
- [x] 5.1 Añadir campos: fecha_vendimia, cuadrilla, rendimiento, destino, lote
- [x] 5.2 Actualizar vistas de añadas
- [x] 5.3 Añadir lote de cosecha como modelo nuevo

## Fase 6: ✅ Grupos de seguridad
- [x] 6.1 Crear grupos de seguridad en security/
- [x] 6.2 Actualizar ir.model.access.csv con grupos
- [x] 6.3 Actualizar vistas con grupo_id

## Fase 7: ✅ Vista calendario
- [x] 7.1 Añadir vista calendar para tratamientos
- [x] 7.2 Añadir vista calendar para trabajos
- [x] 7.3 Añadir vista calendar para aportaciones

## Fase 8: ✅ Informe PDF Cuaderno de Campo
- [x] 8.1 Crear template de informe (QWeb)
- [x] 8.2 Añadir acción de reporte
- [x] 8.3 Añadir botón en finca para generar informe

## Fase 9: ✅ Plazos de seguridad fitosanitarios
- [x] 9.1 Añadir campo plazo_seguridad en fitosanitario
- [x] 9.2 Añadir advertencia PHI en tratamientos
