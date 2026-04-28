/* sigpac_viewer.js – lógica del visor SIGPAC para Odoo 19
   Archivo externo para cumplir con la CSP de Odoo 19 (no inline scripts).
   Los datos (rec_id, lat, lon, zoom, marker) se pasan como atributos
   data-* en el elemento <html> por el controlador Odoo. */

(function () {
    'use strict';

    /* ── 1. Leer datos inyectados por el controlador ── */
    var root = document.documentElement;
    var REC_ID      = parseInt(root.getAttribute('data-rec-id')     || '0',       10);
    var LAT         = parseFloat(root.getAttribute('data-lat')       || '40.4168');
    var LON         = parseFloat(root.getAttribute('data-lon')       || '-3.7038');
    var ZOOM        = parseInt(root.getAttribute('data-zoom')        || '6',       10);
    var MARKER_LAT  = root.getAttribute('data-marker-lat');
    var MARKER_LON  = root.getAttribute('data-marker-lon');
    var REF_SIGPAC  = root.getAttribute('data-ref-sigpac')  || '';
    var RECINTOS_JSON = root.getAttribute('data-recintos') || '[]';
    /* REFS_EXTRA: [{ref: 'prov:mun:...',  offset: 1000}, {ref: ..., offset: 2000}, ...] */
    var REFS_EXTRA = [];
    try { REFS_EXTRA = JSON.parse(root.getAttribute('data-refs-extra') || '[]'); } catch (e) {}

    /* ── 2. Rutas locales de los iconos de Leaflet ── */
    delete L.Icon.Default.prototype._getIconUrl;
    L.Icon.Default.mergeOptions({
        iconUrl:       '/vinedo_field_service/static/src/lib/leaflet/images/marker-icon.png',
        iconRetinaUrl: '/vinedo_field_service/static/src/lib/leaflet/images/marker-icon-2x.png',
        shadowUrl:     '/vinedo_field_service/static/src/lib/leaflet/images/marker-shadow.png',
    });

    /* ── 3. Crear mapa ── */
    var map = L.map('map', { zoomControl: true }).setView([LAT, LON], ZOOM);

    var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a>',
        maxZoom: 19
    });

    var pnoaLayer = L.tileLayer.wms('https://www.ign.es/wms-inspire/pnoa-ma', {
        layers: 'OI.OrthoimageCoverage',
        format: 'image/jpeg',
        transparent: false,
        attribution: '&copy; IGN PNOA',
        maxZoom: 20
    });

    var sigpacRecintoLayer = L.tileLayer.wms('https://sigpac-hubcloud.es/wms?', {
        layers: 'AU.Sigpac:recinto',
        format: 'image/png',
        transparent: true,
        version: '1.3.0',
        crs: L.CRS.EPSG3857,
        opacity: 0.7,
        attribution: '&copy; FEGA SIGPAC',
        maxZoom: 19
    });

    pnoaLayer.addTo(map);
    sigpacRecintoLayer.addTo(map);

    L.control.layers(
        { 'OpenStreetMap': osmLayer, 'Foto a\u00e9rea (PNOA)': pnoaLayer },
        { 'Recintos SIGPAC': sigpacRecintoLayer },
        { collapsed: false }
    ).addTo(map);

    /* Marcador de posición actual */
    if (MARKER_LAT && MARKER_LON) {
        L.marker([parseFloat(MARKER_LAT), parseFloat(MARKER_LON)])
            .addTo(map)
            .bindPopup('Ubicaci\u00f3n actual de la finca');
    }

    setTimeout(function () { map.invalidateSize(); }, 300);

    /* ── 4. Aviso de zoom ── */
    var zoomHint = document.getElementById('zoom-hint');
    function updateZoomHint() {
        zoomHint.style.display = map.getZoom() < 14 ? 'block' : 'none';
    }
    map.on('zoomend', updateZoomHint);
    updateZoomHint();

    /* ── 5. Capas y estilos ── */
    var panel = document.getElementById('panel');
    var selection = null;
    var singleRecintoHa = 0;
    var parcelaTotalHa = null;
    /* recintoLayers: capas de recintos ya importados en Odoo.
       Claves: número entero (1ª parcela) o 'ex_OFFSET_N' (parcelas extra). */
    var recintoLayers = {};
    /* previewLayer: contorno naranja de la parcela seleccionada al hacer clic */
    var previewLayer = null;

    /* Estilo 1ª parcela: rojo (activo) / gris (inactivo) */
    function recintoStyle(activo) {
        return activo
            ? { color: '#cc0000', weight: 2.5, fillColor: '#ff4444', fillOpacity: 0.25 }
            : { color: '#888888', weight: 1.5, fillColor: '#cccccc', fillOpacity: 0.1 };
    }

    /* Paleta de colores para parcelas extra (índice 0 = primera extra, etc.) */
    var _extraColors = [
        ['#0056b3', '#6baed6', '#17a2b8', '#c6dbef'],  /* azul      */
        ['#276927', '#74c374', '#3caa3c', '#b5e2b5'],  /* verde     */
        ['#8b008b', '#cc85cc', '#bb00bb', '#e8c0e8'],  /* morado    */
        ['#cc5500', '#ffaa66', '#ff7700', '#ffd9b3'],  /* naranja   */
        ['#996600', '#ccaa44', '#cc8800', '#ffe8bb'],  /* ámbar     */
    ];

    /* Estilo para parcela extra según índice de color (0-based) y activo/inactivo */
    function extraStyle(activo, colorIdx) {
        var c = _extraColors[(colorIdx || 0) % _extraColors.length];
        return activo !== false
            ? { color: c[0], weight: 2.5, fillColor: c[2], fillOpacity: 0.25 }
            : { color: c[1], weight: 1.5, fillColor: c[3], fillOpacity: 0.1 };
    }

    /* Estilo de previsualización (parcela clicada) */
    var _previewStyle = { color: '#e67e00', weight: 2.5, fillColor: '#ffaa00', fillOpacity: 0.15 };

    /* Borra todas las capas de recintos importados */
    function clearRecintoLayers() {
        Object.keys(recintoLayers).forEach(function (k) { map.removeLayer(recintoLayers[k]); });
        recintoLayers = {};
    }

    /* Borra la capa de previsualización */
    function clearPreview() {
        if (previewLayer) { map.removeLayer(previewLayer); previewLayer = null; }
    }

    /* Dibuja los recintos de la 1ª parcela según activoMap {num → bool} */
    function drawRecintoLayers(geojson, activoMap) {
        clearRecintoLayers();
        (geojson.features || []).forEach(function (f) {
            var num = f.properties && f.properties.recinto;
            var activo = activoMap[num] !== undefined ? activoMap[num] : true;
            var layer = L.geoJSON(f, { style: recintoStyle(activo) }).addTo(map);
            recintoLayers[num] = layer;
        });
    }

    /* Dibuja los recintos de una parcela extra con su color y offset.
       Clave en recintoLayers: 'ex_OFFSET_num' para mapear el postMessage. */
    function drawExtraParcelaLayers(geojson, activoMap, offset, colorIdx) {
        (geojson.features || []).forEach(function (f) {
            var num = f.properties && f.properties.recinto;
            var odooNum = offset + parseInt(num || 0, 10);
            var activo = activoMap[odooNum] !== undefined ? activoMap[odooNum] : true;
            var layer = L.geoJSON(f, { style: extraStyle(activo, colorIdx) }).addTo(map);
            recintoLayers['ex_' + offset + '_' + num] = layer;
        });
    }

    /* Dibuja la previsualización naranja de una parcela (no modifica recintoLayers).
       Actualiza parcelaTotalHa y #span-total-ha si existe. */
    function drawPreview(ref) {
        clearPreview();
        parcelaTotalHa = null;
        var parts = ref.split(':');
        if (parts.length < 6) { return; }
        var url = 'https://sigpac-hubcloud.es/servicioconsultassigpac/query/recinfoparc/'
            + parts[0] + '/' + parts[1] + '/' + parts[2] + '/'
            + parts[3] + '/' + parts[4] + '/' + parts[5] + '.geojson';
        fetch(url)
            .then(function (r) { if (!r.ok) { throw new Error('HTTP ' + r.status); } return r.json(); })
            .then(function (geojson) {
                previewLayer = L.geoJSON(geojson, { style: _previewStyle }).addTo(map);
                parcelaTotalHa = (geojson.features || []).reduce(function (s, f) {
                    return s + parseFloat((f.properties && f.properties.superficie) || 0);
                }, 0);
                var spanTotal = document.getElementById('span-total-ha');
                if (spanTotal) { spanTotal.textContent = parcelaTotalHa.toFixed(4) + ' ha'; }
            })
            .catch(function () {});
    }

    /* ── 6. Construir mapa de activos desde RECINTOS_JSON ── */
    var recintoActivoMap = {};
    try {
        var rList = JSON.parse(RECINTOS_JSON);
        rList.forEach(function (r) { recintoActivoMap[r.recinto] = r.activo; });
    } catch (e) {}

    /* ── 7. Auto-cargar recintos existentes al abrir el visor ── */
    function _fetchGeojson(ref, onSuccess) {
        var parts = ref.split(':');
        if (parts.length < 6) { return; }
        var url = 'https://sigpac-hubcloud.es/servicioconsultassigpac/query/recinfoparc/'
            + parts[0] + '/' + parts[1] + '/' + parts[2] + '/'
            + parts[3] + '/' + parts[4] + '/' + parts[5] + '.geojson';
        fetch(url)
            .then(function (r) { if (!r.ok) { throw new Error(); } return r.json(); })
            .then(onSuccess)
            .catch(function () {});
    }

    if (REF_SIGPAC) {
        _fetchGeojson(REF_SIGPAC, function (geojson) {
            drawRecintoLayers(geojson, recintoActivoMap);
        });
    }

    /* Cargar cada parcela extra con su offset y color */
    REFS_EXTRA.forEach(function (item, idx) {
        _fetchGeojson(item.ref, function (geojson) {
            drawExtraParcelaLayers(geojson, recintoActivoMap, item.offset, idx);
        });
    });

    /* ── 8. Sincronizar colores con los checkboxes de Odoo (postMessage) ── */
    window.addEventListener('message', function (e) {
        if (e.origin !== window.location.origin) { return; }
        if (!e.data || e.data.type !== 'recinto_update') { return; }
        var activos = e.data.activos || [];
        Object.keys(recintoLayers).forEach(function (key) {
            if (key.indexOf('ex_') === 0) {
                /* Clave formato 'ex_OFFSET_num' */
                var rest = key.slice(3);                      /* 'OFFSET_num' */
                var sep  = rest.indexOf('_');
                var kOffset = parseInt(rest.slice(0, sep), 10);
                var kNum    = parseInt(rest.slice(sep + 1),  10);
                var isActivo = activos.indexOf(kOffset + kNum) !== -1;
                recintoLayers[key].setStyle(extraStyle(isActivo, kOffset / 1000 - 1));
            } else {
                var isActivo = activos.indexOf(parseInt(key, 10)) !== -1;
                recintoLayers[key].setStyle(recintoStyle(isActivo));
            }
        });
    });

    /* ── 9. Dibujo de zona (polígono libre) para capturar múltiples parcelas ── */

    var _drawMode   = false;
    var _drawVerts  = [];      /* array de L.LatLng */
    var _drawLine   = null;    /* L.Polyline de preview */
    var _drawPoly   = null;    /* L.Polygon pintado al cerrar */
    var _zonaResult = null;    /* último resultado de detección */

    /* Botón "Dibujar zona" como control Leaflet (top-right, encima de zoom) */
    var _DrawZonaControl = L.Control.extend({
        options: { position: 'topright' },
        onAdd: function () {
            var div = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
            var btn = L.DomUtil.create('a', 'sigpac-draw-zona-btn', div);
            btn.href  = '#';
            btn.title = 'Dibujar zona para capturar todos sus recintos SIGPAC';
            btn.innerHTML = '&#9651;&nbsp;Zona';
            btn.setAttribute('role', 'button');
            L.DomEvent.disableClickPropagation(div);
            L.DomEvent.on(btn, 'click', function (e) {
                L.DomEvent.stop(e);
                _enterDrawMode();
            });
            return div;
        }
    });
    new _DrawZonaControl().addTo(map);

    function _enterDrawMode() {
        _drawMode  = true;
        _drawVerts = [];
        clearPreview();
        _clearDrawLayers();
        map.getContainer().style.cursor = 'crosshair';
        panel.className = 'draw';
        panel.innerHTML =
            '<strong>&#9999; Modo dibujo de zona</strong>'
            + ' &mdash; Haz clic para a&ntilde;adir v&eacute;rtices.'
            + ' <strong>Doble&nbsp;clic</strong> para cerrar.'
            + ' <span id="draw-count" class="hint">(0 v&eacute;rtices)</span>'
            + ' &nbsp;<button id="btn-cerrar-zona" disabled>Cerrar pol&iacute;gono</button>'
            + ' &nbsp;<button id="btn-cancelar-zona">Cancelar</button>';
        document.getElementById('btn-cerrar-zona').addEventListener('click', _finishDraw);
        document.getElementById('btn-cancelar-zona').addEventListener('click', _cancelDraw);
    }

    function _cancelDraw() {
        _drawMode  = false;
        _drawVerts = [];
        _clearDrawLayers();
        _zonaResult = null;
        map.getContainer().style.cursor = '';
        panel.className = '';
        panel.innerHTML = 'Haz clic en una parcela del mapa para seleccionarla.'
            + ' <span class="hint">(zoom &ge;&nbsp;14 para ver los l&iacute;mites)</span>';
    }

    function _clearDrawLayers() {
        if (_drawLine) { map.removeLayer(_drawLine); _drawLine = null; }
        if (_drawPoly) { map.removeLayer(_drawPoly); _drawPoly = null; }
    }

    function _addDrawVertex(latlng) {
        _drawVerts.push(latlng);
        var n = _drawVerts.length;
        if (_drawLine) { map.removeLayer(_drawLine); }
        if (n >= 2) {
            var pts = _drawVerts.concat([_drawVerts[0]]);   /* cierra visualmente */
            _drawLine = L.polyline(pts, { color: '#e67e00', weight: 2, dashArray: '5,5' }).addTo(map);
        }
        var countEl = document.getElementById('draw-count');
        if (countEl) {
            countEl.textContent = '(' + n + ' vértice' + (n !== 1 ? 's' : '') + ')';
        }
        var btnCerrar = document.getElementById('btn-cerrar-zona');
        if (btnCerrar) { btnCerrar.disabled = n < 3; }
    }

    function _finishDraw() {
        if (_drawVerts.length < 3) { return; }
        _drawMode = false;
        map.getContainer().style.cursor = '';

        if (_drawLine) { map.removeLayer(_drawLine); _drawLine = null; }
        _drawPoly = L.polygon(_drawVerts, {
            color: '#e67e00', weight: 2,
            fillColor: '#ffaa00', fillOpacity: 0.12
        }).addTo(map);

        /* Enviar polígono al servidor como array [[lon, lat], ...] */
        var polyCoords = _drawVerts.map(function (ll) { return [ll.lng, ll.lat]; });
        panel.className = 'loading';
        panel.innerHTML = '&#8987; Analizando zona&hellip; consultando SIGPAC';
        _detectarZona(polyCoords);
    }

    /* ── Detectar recintos dentro del polígono (llamada al servidor) ── */
    function _detectarZona(polyCoords) {
        fetch('/vinedo/sigpac_detectar_zona', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0', method: 'call', id: 1,
                params: { polygon: polyCoords }
            })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var result = data.result;
            if (!result || result.error) {
                panel.className = 'err';
                panel.innerHTML = '⚠ ' + ((result && result.error) || 'Error al analizar la zona')
                    + ' &nbsp;<button id="btn-zona-retry">Reintentar</button>'
                    + ' &nbsp;<button id="btn-zona-cancel2">Cancelar</button>';
                document.getElementById('btn-zona-retry').addEventListener('click', function () {
                    var pts = _drawVerts.map(function (ll) { return [ll.lng, ll.lat]; });
                    panel.className = 'loading';
                    panel.innerHTML = '&#8987; Reintentando&hellip;';
                    _detectarZona(pts);
                });
                document.getElementById('btn-zona-cancel2').addEventListener('click', _cancelDraw);
                return;
            }
            _zonaResult = result;
            _showZonaResultado(result);
        })
        .catch(function (err) {
            panel.className = 'err';
            panel.innerHTML = '⚠ Error de red: ' + err.message
                + ' &nbsp;<button id="btn-zona-cancel3">Cancelar</button>';
            document.getElementById('btn-zona-cancel3').addEventListener('click', _cancelDraw);
        });
    }

    function _showZonaResultado(result) {
        var parcelas = result.parcelas || [];
        var totalR   = result.total_recintos || 0;

        if (!parcelas.length) {
            panel.className = '';
            panel.innerHTML = 'No se encontraron recintos SIGPAC en la zona dibujada.'
                + ' Prueba a ampliarla o usa el visor de capas.'
                + ' &nbsp;<button id="btn-zona-nuevo">Dibujar de nuevo</button>';
            document.getElementById('btn-zona-nuevo').addEventListener('click', function () {
                _clearDrawLayers();
                _enterDrawMode();
            });
            return;
        }

        var listHtml = parcelas.map(function (p) {
            var supTot = (p.recintos || []).reduce(function (s, r) {
                return s + (parseFloat(r.superficie_ha) || 0);
            }, 0);
            return '<li><code>' + p.ref + '</code>: '
                + p.recintos.length + ' recinto(s) &mdash; '
                + supTot.toFixed(4) + '&nbsp;ha</li>';
        }).join('');

        panel.className = 'ok';
        panel.innerHTML =
            '<strong>✅ Zona analizada:</strong> '
            + parcelas.length + ' parcela(s), ' + totalR + ' recinto(s) en total'
            + '<ul class="zona-list">' + listHtml + '</ul>'
            + '<button id="btn-zona-reemplazar">⬇ Importar (reemplaza)</button>'
            + ' &nbsp;<button id="btn-zona-agregar" class="btn-agregar">&#43; A&ntilde;adir recintos</button>'
            + ' &nbsp;<button id="btn-zona-cancelar" class="btn-cancelar">Cancelar</button>';

        document.getElementById('btn-zona-reemplazar').addEventListener('click', function () {
            if (!confirm('¿Reemplazar todos los recintos existentes con los '
                    + totalR + ' recintos de la zona dibujada?')) { return; }
            _importarZona('reemplazar');
        });
        document.getElementById('btn-zona-agregar').addEventListener('click', function () {
            _importarZona('agregar');
        });
        document.getElementById('btn-zona-cancelar').addEventListener('click', _cancelDraw);
    }

    function _importarZona(modo) {
        if (!_zonaResult) { return; }
        panel.className = 'loading';
        panel.innerHTML = '&#8987; Importando recintos&hellip;';
        fetch('/vinedo/sigpac_importar_zona', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0', method: 'call', id: 1,
                params: { rec_id: REC_ID, parcelas: _zonaResult.parcelas, modo: modo }
            })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var res = data.result;
            if (res && res.ok) {
                _clearDrawLayers();
                panel.className = 'done';
                panel.innerHTML =
                    '✅ Importadas: ' + res.n_parcelas + ' parcela(s), '
                    + res.n_recintos + ' recinto(s)'
                    + ' &nbsp;<button id="btn-zona-reload"'
                    + ' style="padding:3px 10px;background:#6c757d;color:#fff;border:none;'
                    + 'border-radius:4px;cursor:pointer;font-size:12px;">'
                    + 'Recargar página</button>';
                document.getElementById('btn-zona-reload').addEventListener('click', function () {
                    window.parent.location.reload();
                });
            } else {
                panel.className = 'err';
                panel.innerHTML = '⚠ ' + ((res && res.error) || 'Error al importar')
                    + ' &nbsp;<button id="btn-zona-cancel4">Cancelar</button>';
                document.getElementById('btn-zona-cancel4').addEventListener('click', _cancelDraw);
            }
        })
        .catch(function (err) {
            panel.className = 'err';
            panel.innerHTML = '⚠ Error de red: ' + err.message;
        });
    }

    /* Doble clic en mapa: cierra polígono si estamos en draw mode */
    map.on('dblclick', function (e) {
        if (_drawMode && _drawVerts.length >= 3) {
            L.DomEvent.stop(e);
            _finishDraw();
        }
    });

    /* ── 10. Helpers de consulta ── */
    function buildHubcloudUrl(latlng) {
        return (
            'https://sigpac-hubcloud.es/servicioconsultassigpac'
            + '/query/recinfobypoint/4326/'
            + latlng.lng.toFixed(7) + '/' + latlng.lat.toFixed(7) + '.json'
        );
    }

    function parseHubcloudResult(arr) {
        if (!Array.isArray(arr) || !arr.length) { return null; }
        var p = arr[0];
        var agr = (p.agregado !== undefined && p.agregado !== null) ? p.agregado : 0;
        var zon = (p.zona  !== undefined && p.zona  !== null) ? p.zona  : 0;
        var ref = [p.provincia, p.municipio, agr, zon, p.poligono, p.parcela]
                    .map(function (v) { return v !== undefined ? String(v) : ''; }).join(':');
        var uso = p.uso_sigpac || '?';
        singleRecintoHa = parseFloat(p.superficie || 0);
        return { ref: ref, uso: uso, m2: singleRecintoHa * 10000 };
    }

    /* Muestra la selección en el panel con los dos botones de acción */
    function showParcelPanel(info, lat, lon) {
        selection = { lat: parseFloat(lat), lon: parseFloat(lon), ref: info.ref };
        drawPreview(info.ref);
        panel.className = 'ok';
        panel.innerHTML =
            '<strong>Parcela:</strong> <code>' + info.ref + '</code>'
            + ' &nbsp;<span class="tag">' + info.uso + '</span>'
            + ' &nbsp;' + info.m2.toLocaleString('es-ES') + '&nbsp;m&sup2;'
            + ' &nbsp;|&nbsp;' + parseFloat(lat).toFixed(5) + ', ' + parseFloat(lon).toFixed(5)
            + '<br><label style="font-size:12px;cursor:pointer;">'
            + '<input type="checkbox" id="chk-parcela" checked style="margin-right:4px;"/>'
            + 'Importar superficie total (&Sigma; recintos):'
            + ' <span id="span-total-ha">calculando&hellip;</span>'
            + '</label>'
            + ' &nbsp;<button id="btn-import">&#8681; Importar (reemplaza)</button>'
            + ' &nbsp;<button id="btn-agregar"'
            + ' style="padding:3px 12px;background:#17a2b8;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px;font-weight:bold;white-space:nowrap;">'
            + '&#43; A\u00f1adir recintos</button>';
        document.getElementById('btn-import').addEventListener('click', function () {
            if (!confirm('¿Importar esta parcela? Se eliminarán todos los recintos existentes y se sustituirán por los nuevos.')) { return; }
            doImport();
        });
        document.getElementById('btn-agregar').addEventListener('click', doAgregarParcela);
    }

    function showManualInput(lat, lon) {
        var sigpacLink = 'https://sigpac.mapa.es/fega/visor/#lon=' + lon + '&lat=' + lat + '&zoom=17';
        panel.className = '';
        panel.innerHTML =
            'Coords: <code>' + lat + ', ' + lon + '</code>'
            + ' &nbsp;<a href="' + sigpacLink + '" target="_blank"'
            + ' style="color:#0056b3;font-size:11px;">Abrir en SIGPAC &#8599;</a>'
            + '<br><small>Introduce la referencia SIGPAC (prov:mun:agr:zona:pol:par):</small>'
            + '<br><input id="ref-input" type="text" placeholder="ej: 27:16:0:0:79:1047"'
            + ' style="width:200px;margin-top:4px;padding:3px 6px;border:1px solid #aaa;border-radius:3px;font-size:13px;"/>'
            + ' <button id="btn-ref-ok"'
            + ' style="padding:3px 10px;background:#28a745;color:#fff;border:none;border-radius:3px;cursor:pointer;">OK</button>';
        document.getElementById('btn-ref-ok').addEventListener('click', function () {
            var ref = ((document.getElementById('ref-input') || {}).value || '').trim().replace(/-/g, ':');
            if (!ref) { return; }
            if (!/^\d+:\d+:\d+:\d+:\d+:\d+$/.test(ref)) {
                alert('Formato incorrecto. Usa: prov:mun:agr:zona:pol:par (ej: 27:16:0:0:79:1047)');
                return;
            }
            showParcelPanel({ ref: ref, uso: '?', m2: 0 }, lat, lon);
        });
    }

    /* ── 11. Clic en el mapa ── */
    map.on('click', function (e) {
        /* En modo dibujo, añadir vértice en lugar de consultar SIGPAC */
        if (_drawMode) {
            _addDrawVertex(e.latlng);
            return;
        }
        var lat = e.latlng.lat.toFixed(7);
        var lon = e.latlng.lng.toFixed(7);
        panel.className = 'loading';
        panel.innerHTML = '&#8987; Consultando SIGPAC&hellip;';

        /* Estrategia 1: REST directo desde el navegador */
        fetch(buildHubcloudUrl(e.latlng))
            .then(function (r) {
                if (!r.ok) { throw new Error('HTTP ' + r.status); }
                return r.json();
            })
            .then(function (arr) {
                var info = parseHubcloudResult(arr);
                if (!info) {
                    panel.className = '';
                    panel.innerHTML = 'Sin parcela. Haz clic dentro de una parcela SIGPAC.';
                    return;
                }
                showParcelPanel(info, lat, lon);
            })
            .catch(function () {
                /* Estrategia 2: proxy Odoo (por si hay CORS) */
                fetch('/vinedo/sigpac_consultar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: '2.0', method: 'call', id: 1,
                        params: { lat: parseFloat(lat), lon: parseFloat(lon) }
                    })
                })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    var info = Array.isArray(data.result) ? parseHubcloudResult(data.result) : null;
                    if (info) {
                        showParcelPanel(info, lat, lon);
                    } else {
                        showManualInput(lat, lon);
                    }
                })
                .catch(function () { showManualInput(lat, lon); });
            });
    });

    /* ── 12. Importar parcela por clic (reemplaza todos los recintos existentes) ── */
    function doImport() {
        if (!selection) { return; }
        var btnIm = document.getElementById('btn-import');
        var btnAg = document.getElementById('btn-agregar');
        if (btnIm) { btnIm.disabled = true; btnIm.textContent = 'Importando\u2026'; }
        if (btnAg) { btnAg.disabled = true; }

        var chk = document.getElementById('chk-parcela');
        var importarTotal = !chk || chk.checked;
        var params = { rec_id: REC_ID, lat: selection.lat, lon: selection.lon };
        if (!importarTotal) { params.area_ha = singleRecintoHa; }

        fetch('/vinedo/sigpac_importar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', id: 1, params: params })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var result = data.result;
            if (result && result.ok) {
                clearPreview();
                panel.className = 'done';
                panel.innerHTML =
                    '\u2705 Importada: <strong>' + (result.ref_sigpac || selection.ref) + '</strong>'
                    + ' &nbsp;<button id="btn-reload"'
                    + ' style="padding:3px 10px;background:#6c757d;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px;">'
                    + 'Recargar p\u00e1gina</button>';
                document.getElementById('btn-reload').addEventListener('click', function () {
                    window.parent.location.reload();
                });
            } else {
                panel.className = 'err';
                panel.innerHTML = '\u26a0 ' + ((result && result.error) || 'Error desconocido')
                    + ' &nbsp;<button id="btn-retry">Reintentar</button>';
                document.getElementById('btn-retry').addEventListener('click', doImport);
            }
        })
        .catch(function (err) {
            panel.className = 'err';
            panel.innerHTML = '\u26a0 Error de red: ' + err.message
                + ' &nbsp;<button id="btn-retry">Reintentar</button>';
            document.getElementById('btn-retry').addEventListener('click', doImport);
        });
    }

    /* ── 13. Añadir recintos de otra parcela por clic (no borra los existentes) ── */
    function doAgregarParcela() {
        if (!selection) { return; }
        var btnAg = document.getElementById('btn-agregar');
        var btnIm = document.getElementById('btn-import');
        if (btnAg) { btnAg.disabled = true; btnAg.textContent = 'A\u00f1adiendo\u2026'; }
        if (btnIm) { btnIm.disabled = true; }

        fetch('/vinedo/sigpac_agregar_parcela', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0', method: 'call', id: 1,
                params: { rec_id: REC_ID, lat: selection.lat, lon: selection.lon }
            })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var result = data.result;
            if (result && result.ok) {
                clearPreview();
                panel.className = 'done';
                panel.innerHTML =
                    '\u2705 A\u00f1adida: <strong>' + result.ref_sigpac2 + '</strong>'
                    + ' &mdash; ' + result.n_recintos + ' recinto(s)'
                    + ' | ' + result.total_m2.toLocaleString('es-ES') + '&nbsp;m&sup2;'
                    + ' &nbsp;<button id="btn-reload2"'
                    + ' style="padding:3px 10px;background:#6c757d;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px;">'
                    + 'Recargar p\u00e1gina</button>';
                document.getElementById('btn-reload2').addEventListener('click', function () {
                    window.parent.location.reload();
                });
            } else {
                panel.className = 'err';
                panel.innerHTML = '\u26a0 ' + ((result && result.error) || 'Error desconocido')
                    + ' &nbsp;<button id="btn-retry3">Reintentar</button>';
                document.getElementById('btn-retry3').addEventListener('click', doAgregarParcela);
            }
        })
        .catch(function (err) {
            panel.className = 'err';
            panel.innerHTML = '\u26a0 Error de red: ' + err.message
                + ' &nbsp;<button id="btn-retry3">Reintentar</button>';
            document.getElementById('btn-retry3').addEventListener('click', doAgregarParcela);
        });
    }

}());
