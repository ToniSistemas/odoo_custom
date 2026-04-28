# Guía de Posicionamiento GPS para Viñedos

## ¿Cómo obtener las coordenadas GPS de tu finca?

### Método 1: Google Maps (Recomendado)

1. Abre [Google Maps](https://maps.google.com)
2. Busca tu finca o navega hasta ella en el mapa
3. Haz **clic derecho** en el punto central de tu finca
4. Selecciona las coordenadas (aparecen en la parte superior)
5. Las coordenadas se copian automáticamente

**Formato:** `42.123456, -3.456789`
- **Primer número** = Latitud (Norte/Sur)
- **Segundo número** = Longitud (Este/Oeste)

### Método 2: Teléfono móvil

#### En Google Maps (Android/iOS):
1. Abre la app Google Maps
2. Mantén presionado sobre tu finca
3. Aparece un pin rojo
4. Desliza hacia arriba la información
5. Verás las coordenadas

#### En iPhone (app Brújula):
1. Abre la app Brújula
2. Camina hasta el centro de tu finca
3. Las coordenadas aparecen en la parte inferior

## Coordenadas de ejemplo para España

- **Madrid**: Latitud 40.4168, Longitud -3.7038
- **Ribera del Duero**: Latitud 41.6, Longitud -4.0
- **La Rioja**: Latitud 42.5, Longitud -2.5
- **Priorat**: Latitud 41.2, Longitud 0.8

## ¿Qué es Latitud y Longitud?

### Latitud (Norte/Sur)
- **Rango**: -90 a 90 grados
- **Positivo**: Norte del Ecuador
- **Negativo**: Sur del Ecuador
- **España**: Entre 36° y 44° (siempre positivo)

### Longitud (Este/Oeste)
- **Rango**: -180 a 180 grados
- **Positivo**: Este de Greenwich (Europa del Este, Asia)
- **Negativo**: Oeste de Greenwich (América, España occidental)
- **España**: Entre -10° y 4° (mayormente negativo)

## Dibujar el polígono de tu finca en el mapa

1. Abre la finca en Odoo
2. Rellena Latitud y Longitud (opcional, para centrar el mapa)
3. En el campo **Polígono (GeoJSON Feature)** aparecerá un mapa interactivo
4. Haz clic en el icono del polígono (◇) en el mapa
5. Haz clic en cada esquina de tu finca siguiendo el contorno
6. Doble clic para cerrar el polígono
7. El sistema guarda automáticamente el contorno en formato GeoJSON

### Botones disponibles:
- **📐 Polígono**: Dibujar nuevo polígono
- **✏️ Editar**: Modificar polígono existente
- **🗑️ Borrar**: Eliminar polígono
- **⛶ Pantalla completa**: Ampliar mapa para mejor visualización

## Consejos

1. **Precisión**: Para mayor precisión, utiliza el modo satélite de Google Maps
2. **Altitud**: No es necesaria para el mapa plano (2D)
3. **Varios puntos**: Si tu finca tiene forma irregular, usa más puntos en el polígono
4. **Zoom**: Ajusta el zoom del mapa antes de dibujar para ver bien los límites

## Formatos admitidos

El campo de polígono acepta:
- **GeoJSON Feature**: Formato completo (automático con el widget)
- **GeoJSON Geometry**: Solo la geometría (se convierte automáticamente)
- **Texto JSON**: Para importación manual

Ejemplo de GeoJSON:
```json
{
  "type": "Feature",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[
      [-3.7, 42.5],
      [-3.6, 42.5],
      [-3.6, 42.6],
      [-3.7, 42.6],
      [-3.7, 42.5]
    ]]]
  },
  "properties": {}
}
```

## Validación

El sistema valida automáticamente:
✅ Latitud entre -90 y 90
✅ Longitud entre -180 y 180
✅ Formato GeoJSON correcto
✅ Polígono cerrado y válido

## Soporte

Si tienes problemas con el posicionamiento:
1. Verifica que las coordenadas estén en el rango correcto
2. Comprueba que el navegador permite acceso a CDN externas (Leaflet)
3. Actualiza la página si el mapa no se muestra
