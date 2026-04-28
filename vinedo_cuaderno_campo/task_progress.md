# Plan de mejora - vinedo_cuaderno_campo

## Fase 1: 🔴 Correcciones críticas (rutas y manifiesto)
- [ ] 1.1 Arreglar __manifest__.py (name, assets, rutas)
- [ ] 1.2 Arreglar controllers/main.py (rutas a estáticos)
- [ ] 1.3 Arreglar views/vinedo_views.xml (web_icon)
- [ ] 1.4 Actualizar README.md e index.html

## Fase 2: 🟡 Vistas para Podas (modelo existe sin UI)
- [ ] 2.1 Añadir vistas tree, form para vinedo.poda
- [ ] 2.2 Añadir action_poda y menuitem
- [ ] 2.3 Añadir pivot y graph para podas

## Fase 3: 🟡 Climatología
- [ ] 3.1 Crear modelo vinedo.registro.clima en models/vinedo.py
- [ ] 3.2 Añadir vistas en vinedo_views.xml
- [ ] 3.3 Añadir acceso en ir.model.access.csv
- [ ] 3.4 Añadir menuitem

## Fase 4: 🟡 Seguimiento Fenológico (BBCH)
- [ ] 4.1 Crear modelo vinedo.seguimiento.fenologico
- [ ] 4.2 Añadir vistas en vinedo_views.xml
- [ ] 4.3 Añadir acceso en ir.model.access.csv
- [ ] 4.4 Añadir menuitem

## Fase 5: 🟡 Mejora de Añadas/Cosecha
- [ ] 5.1 Añadir campos: fecha_vendimia, cuadrilla, rendimiento, destino, lote
- [ ] 5.2 Actualizar vistas de añadas
- [ ] 5.3 Añadir lote de cosecha como modelo nuevo

## Fase 6: 🟢 Grupos de seguridad
- [ ] 6.1 Crear grupos de seguridad en security/
- [ ] 6.2 Actualizar ir.model.access.csv con grupos
- [ ] 6.3 Actualizar vistas con grupo_id

## Fase 7: 🟢 Vista calendario
- [ ] 7.1 Añadir vista calendar para tratamientos
- [ ] 7.2 Añadir vista calendar para trabajos
- [ ] 7.3 Añadir vista calendar para aportaciones

## Fase 8: 🟢 Informe PDF Cuaderno de Campo
- [ ] 8.1 Crear template de informe (QWeb)
- [ ] 8.2 Añadir acción de reporte
- [ ] 8.3 Añadir botón en finca para generar informe

## Fase 9: 🟢 Plazos de seguridad fitosanitarios
- [ ] 9.1 Añadir campo plazo_seguridad en fitosanitario
- [ ] 9.2 Añadir advertencia PHI en tratamientos
