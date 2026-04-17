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
    var REF_SIGPAC2 = root.getAttribute('data-ref-sigpac2') || '';
    var RECINTOS_JSON = root.getAttribute('data-recintos') || '[]';

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
       Claves: número (1ª parcela) o '2p_N' (2ª parcela). */
    var recintoLayers = {};
    /* previewLayer: contorno naranja de la parcela seleccionada al hacer clic */
    var previewLayer = null;

    /* Estilo 1ª parcela: rojo (activo) / gris (inactivo) */
    function recintoStyle(activo) {
        return activo
            ? { color: '#cc0000', weight: 2.5, fillColor: '#ff4444', fillOpacity: 0.25 }
            : { color: '#888888', weight: 1.5, fillColor: '#cccccc', fillOpacity: 0.1 };
    }

    /* Estilo 2ª parcela: azul (activo) / azul claro (inactivo) */
    function recintoStyleSegunda(activo) {
        return activo !== false
            ? { color: '#0056b3', weight: 2.5, fillColor: '#17a2b8', fillOpacity: 0.25 }
            : { color: '#6baed6', weight: 1.5, fillColor: '#c6dbef', fillOpacity: 0.1 };
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

    /* Dibuja los recintos de la 2ª parcela en azul.
       En Odoo el recinto_num es offset+original (offset = 1000), por eso
       se busca activoMap[1000 + num] para obtener el estado real. */
    function drawSegundaParcelaLayers(geojson, activoMap) {
        (geojson.features || []).forEach(function (f) {
            var num = f.properties && f.properties.recinto;
            var odooNum = 1000 + parseInt(num || 0, 10);
            var activo = activoMap[odooNum] !== undefined ? activoMap[odooNum] : true;
            var layer = L.geoJSON(f, { style: recintoStyleSegunda(activo) }).addTo(map);
            recintoLayers['2p_' + num] = layer;
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

    if (REF_SIGPAC2) {
        _fetchGeojson(REF_SIGPAC2, function (geojson) {
            drawSegundaParcelaLayers(geojson, recintoActivoMap);
        });
    }

    /* ── 8. Sincronizar colores con los checkboxes de Odoo (postMessage) ── */
    window.addEventListener('message', function (e) {
        if (!e.data || e.data.type !== 'recinto_update') { return; }
        var activos = e.data.activos || [];
        Object.keys(recintoLayers).forEach(function (key) {
            if (key.indexOf('2p_') === 0) {
                /* 2ª parcela: recinto_num en Odoo = 1000 + num_original */
                var origNum = parseInt(key.slice(3), 10);
                var isActivo = activos.indexOf(1000 + origNum) !== -1;
                recintoLayers[key].setStyle(recintoStyleSegunda(isActivo));
            } else {
                var isActivo = activos.indexOf(parseInt(key, 10)) !== -1;
                recintoLayers[key].setStyle(recintoStyle(isActivo));
            }
        });
    });

    /* ── 9. Helpers de consulta ── */
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
        document.getElementById('btn-import').addEventListener('click', doImport);
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
            showParcelPanel({ ref: ref, uso: '?', m2: 0 }, lat, lon);
        });
    }

    /* ── 10. Clic en el mapa ── */
    map.on('click', function (e) {
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

    /* ── 11. Importar parcela (reemplaza todos los recintos existentes) ── */
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

    /* ── 12. Añadir recintos de otra parcela (no borra los existentes) ── */
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
