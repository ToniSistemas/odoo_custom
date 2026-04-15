/* sigpac_viewer.js – lógica del visor SIGPAC para Odoo 19
   Archivo externo para cumplir con la CSP de Odoo 19 (no inline scripts).
   Los datos (rec_id, lat, lon, zoom, marker) se pasan como atributos
   data-* en el elemento <html> por el controlador Odoo. */

(function () {
    'use strict';

    /* ── 1. Leer datos inyectados por el controlador ── */
    var root = document.documentElement;
    var REC_ID     = parseInt(root.getAttribute('data-rec-id') || '0', 10);
    var LAT        = parseFloat(root.getAttribute('data-lat')  || '40.4168');
    var LON        = parseFloat(root.getAttribute('data-lon')  || '-3.7038');
    var ZOOM       = parseInt(root.getAttribute('data-zoom')   || '6', 10);
    var MARKER_LAT = root.getAttribute('data-marker-lat');
    var MARKER_LON = root.getAttribute('data-marker-lon');

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

    /* Marcador de posición actual si tiene coordenadas */
    if (MARKER_LAT && MARKER_LON) {
        L.marker([parseFloat(MARKER_LAT), parseFloat(MARKER_LON)])
            .addTo(map)
            .bindPopup('Ubicaci\u00f3n actual de la finca');
    }

    /* Forzar recalculo de tamaño tras el render del iframe */
    setTimeout(function () { map.invalidateSize(); }, 300);

    /* ── 4. Aviso de zoom ── */
    var zoomHint = document.getElementById('zoom-hint');
    function updateZoomHint() {
        zoomHint.style.display = map.getZoom() < 14 ? 'block' : 'none';
    }
    map.on('zoomend', updateZoomHint);
    updateZoomHint();

    /* ── 5. Clic en parcela ── */
    var panel = document.getElementById('panel');
    var selection = null;
    var parcelaLayer = null;
    var singleRecintoHa = 0;
    var parcelaTotalHa = null;

    /* Dibuja en el mapa los recintos de la parcela clicada usando recinfoparc.geojson
       y calcula parcelaTotalHa (suma de superficies de todos los recintos en ha) */
    function drawParcela(ref) {
        if (parcelaLayer) { map.removeLayer(parcelaLayer); parcelaLayer = null; }
        parcelaTotalHa = null;
        var parts = ref.split(':');
        if (parts.length < 6) { return; }
        var url = 'https://sigpac-hubcloud.es/servicioconsultassigpac/query/recinfoparc/'
            + parts[0] + '/' + parts[1] + '/' + parts[2] + '/'
            + parts[3] + '/' + parts[4] + '/' + parts[5] + '.geojson';
        fetch(url)
            .then(function (r) { if (!r.ok) { throw new Error('HTTP ' + r.status); } return r.json(); })
            .then(function (geojson) {
                parcelaLayer = L.geoJSON(geojson, {
                    style: {
                        color: '#cc0000',
                        weight: 2.5,
                        fillColor: '#ff4444',
                        fillOpacity: 0.15
                    }
                }).addTo(map);
                /* Calcular superficie total sumando todos los recintos */
                var features = geojson.features || [];
                var total = 0;
                features.forEach(function (f) {
                    total += parseFloat((f.properties && f.properties.superficie) || 0);
                });
                parcelaTotalHa = total;
                /* Actualizar etiqueta del check si el panel sigue visible */
                var spanTotal = document.getElementById('span-total-ha');
                if (spanTotal) {
                    spanTotal.textContent = parcelaTotalHa.toFixed(4) + ' ha';
                }
            })
            .catch(function () { /* silencioso si falla */ });
    }

    /* REST endpoint sigpac-hubcloud.es: consulta el recinto por coordenadas WGS84 */
    function buildHubcloudUrl(latlng) {
        var lon = latlng.lng.toFixed(7);
        var lat = latlng.lat.toFixed(7);
        return (
            'https://sigpac-hubcloud.es/servicioconsultassigpac'
            + '/query/recinfobypoint/4326/' + lon + '/' + lat + '.json'
        );
    }

    function showManualInput(lat, lon) {
        var sigpacLink = 'https://sigpac.mapa.es/fega/visor/#lon='
            + lon + '&lat=' + lat + '&zoom=17';
        panel.className = '';
        panel.innerHTML =
            'Coords: <code>' + lat + ', ' + lon + '</code>'
            + ' &nbsp;<a href="' + sigpacLink + '" target="_blank" '
            + 'style="color:#0056b3;font-size:11px;">Abrir en SIGPAC &#8599;</a>'
            + '<br><small>Introduce la referencia (prov-mun-pol-par-rec):</small>'
            + '<br><input id="ref-input" type="text" placeholder="ej: 27-16-79-1047-1"'
            + ' style="width:180px;margin-top:4px;padding:3px 6px;border:1px solid #aaa;border-radius:3px;font-size:13px;"/>'
            + ' <button id="btn-ref-ok"'
            + ' style="padding:3px 10px;background:#28a745;color:#fff;border:none;border-radius:3px;cursor:pointer;">OK</button>';

        var btnOk = document.getElementById('btn-ref-ok');
        if (btnOk) {
            btnOk.addEventListener('click', function () {
                var ref = (document.getElementById('ref-input') || {}).value || '';
                ref = ref.trim().replace(/:/g, '-');
                if (!ref) { return; }
                selection = { lat: parseFloat(lat), lon: parseFloat(lon), ref: ref };
                panel.className = 'ok';
                panel.innerHTML =
                    '<strong>&#10003; Referencia:</strong> <code>' + ref + '</code>'
                    + ' &nbsp;|&nbsp;' + lat + ', ' + lon
                    + ' &nbsp;<button id="btn-import">&#8681; Importar a Odoo</button>';
                var btn2 = document.getElementById('btn-import');
                if (btn2) { btn2.addEventListener('click', doImport); }
            });
        }
    }

    /* Analiza la respuesta JSON de sigpac-hubcloud.es/servicioconsultassigpac
       Formato: [{provincia, municipio, agregado, zona, poligono, parcela, recinto, superficie (ha), uso_sigpac, ...}] */
    function parseHubcloudResult(arr) {
        if (!Array.isArray(arr) || !arr.length) { return null; }
        var p = arr[0];
        var agr = (p.agregado !== undefined && p.agregado !== null) ? p.agregado : 0;
        var zon = (p.zona !== undefined && p.zona !== null) ? p.zona : 0;
        var ref = [p.provincia, p.municipio, agr, zon, p.poligono, p.parcela]
                    .map(function (v) { return v !== undefined ? String(v) : ''; }).join(':');
        var uso = p.uso_sigpac || '?';
        singleRecintoHa = parseFloat(p.superficie || 0); /* ha del recinto clicado */
        var m2  = singleRecintoHa * 10000; /* ha → m² */
        return { ref: ref, uso: uso, m2: m2 };
    }

    map.on('click', function (e) {
        var lat = e.latlng.lat.toFixed(7);
        var lon = e.latlng.lng.toFixed(7);
        if (parcelaLayer) { map.removeLayer(parcelaLayer); parcelaLayer = null; }
        panel.className = 'loading';
        panel.innerHTML = '&#8987; Consultando SIGPAC&hellip;';

        /* Estrategia 1: REST sigpac-hubcloud.es directo desde el navegador */
        var hubUrl = buildHubcloudUrl(e.latlng);
        fetch(hubUrl)
            .then(function (r) {
                if (!r.ok) { throw new Error('HTTP ' + r.status); }
                return r.json();
            })
            .then(function (arr) {
                var info = parseHubcloudResult(arr);
                if (!info) {
                    /* sin parcela en este punto */
                    panel.className = '';
                    panel.innerHTML = 'Sin parcela. Haz clic dentro de una parcela SIGPAC.';
                    return;
                }
                selection = { lat: parseFloat(lat), lon: parseFloat(lon), ref: info.ref };
                drawParcela(info.ref);
                panel.className = 'ok';
                panel.innerHTML =
                    '<strong>&#10003; Parcela:</strong>'
                    + ' <code>' + info.ref + '</code>'
                    + ' &nbsp;<span class="tag">' + info.uso + '</span>'
                    + ' &nbsp;' + info.m2.toLocaleString('es-ES') + '&nbsp;m&sup2;'
                    + ' &nbsp;|&nbsp;' + lat + ', ' + lon
                    + '<br><label style="font-size:12px;cursor:pointer;">'
                    + '<input type="checkbox" id="chk-parcela" checked style="margin-right:4px;"/>'
                    + 'Importar superficie total de la parcela'
                    + ' (<span id="span-total-ha">calculando&hellip;</span>)'
                    + '</label>'
                    + ' &nbsp;<button id="btn-import">&#8681; Importar a Odoo</button>';
                var btn = document.getElementById('btn-import');
                if (btn) { btn.addEventListener('click', doImport); }
            })
            .catch(function () {
                /* Estrategia 2: proxy Odoo (por si hay CORS en GFI) */
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
                    var result = data.result;
                    var info = Array.isArray(result) ? parseHubcloudResult(result) : null;
                    if (info) {
                        selection = { lat: parseFloat(lat), lon: parseFloat(lon), ref: info.ref };
                        drawParcela(info.ref);
                        panel.className = 'ok';
                        panel.innerHTML =
                            '<strong>&#10003; Parcela:</strong>'
                            + ' <code>' + info.ref + '</code>'
                            + ' &nbsp;<span class="tag">' + info.uso + '</span>'
                            + ' &nbsp;' + info.m2.toLocaleString('es-ES') + '&nbsp;m&sup2;'
                            + ' &nbsp;|&nbsp;' + lat + ', ' + lon
                            + '<br><label style="font-size:12px;cursor:pointer;">'
                            + '<input type="checkbox" id="chk-parcela" checked style="margin-right:4px;"/>'
                            + 'Importar superficie total de la parcela'
                            + ' (<span id="span-total-ha">calculando&hellip;</span>)'
                            + '</label>'
                            + ' &nbsp;<button id="btn-import">&#8681; Importar a Odoo</button>';
                        var btn = document.getElementById('btn-import');
                        if (btn) { btn.addEventListener('click', doImport); }
                    } else {
                        /* Estrategia 3: entrada manual con enlace al visor oficial */
                        showManualInput(lat, lon);
                    }
                })
                .catch(function () { showManualInput(lat, lon); });
            });
    });

    /* ── 6. Importar parcela seleccionada ── */
    function doImport() {
        if (!selection) { return; }
        var btn = document.getElementById('btn-import');
        if (btn) { btn.disabled = true; btn.textContent = 'Importando\u2026'; }

        var chk = document.getElementById('chk-parcela');
        var importarTotal = !chk || chk.checked;
        var params = { rec_id: REC_ID, lat: selection.lat, lon: selection.lon };
        if (!importarTotal) {
            /* Sólo el recinto clicado: pasar área explícita para sobrescribir el total */
            params.area_ha = singleRecintoHa;
        }

        fetch('/vinedo/sigpac_importar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0', method: 'call', id: 1,
                params: params
            })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var result = data.result;
            if (result && result.ok) {
                panel.className = 'done';
                panel.innerHTML = '&#9989; Importado: <strong>'
                    + (result.ref_sigpac || selection.ref)
                    + '</strong> &mdash; Recargando\u2026';
                setTimeout(function () { window.parent.location.reload(); }, 1500);
            } else {
                panel.className = 'err';
                panel.innerHTML = '&#9888; ' + ((result && result.error) || 'Error desconocido')
                    + ' &nbsp;<button id="btn-retry">Reintentar</button>';
                var b2 = document.getElementById('btn-retry');
                if (b2) { b2.addEventListener('click', doImport); }
            }
        })
        .catch(function (err) {
            panel.className = 'err';
            panel.innerHTML = '&#9888; Error de red: ' + err.message
                + ' &nbsp;<button id="btn-retry">Reintentar</button>';
            var b2 = document.getElementById('btn-retry');
            if (b2) { b2.addEventListener('click', doImport); }
        });
    }

}());
