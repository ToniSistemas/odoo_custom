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

    var sigpacLayer = L.tileLayer.wms(
        'https://sigpac.mapa.es/fega/serviciosvisorsigpac/wms/wms.aspx', {
        layers: 'SIGPAC',
        format: 'image/png',
        transparent: true,
        version: '1.3.0',
        opacity: 0.85,
        attribution: '&copy; MAPA SIGPAC',
        maxZoom: 19
    });

    osmLayer.addTo(map);
    sigpacLayer.addTo(map);

    L.control.layers(
        { 'OpenStreetMap': osmLayer, 'Foto a\u00e9rea (PNOA)': pnoaLayer },
        { 'Parcelas SIGPAC': sigpacLayer },
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

    map.on('click', function (e) {
        var lat = e.latlng.lat.toFixed(7);
        var lon = e.latlng.lng.toFixed(7);
        panel.className = 'loading';
        panel.innerHTML = '&#8987; Consultando SIGPAC&hellip;';

        fetch('/vinedo/sigpac_consultar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0', method: 'call', id: 1,
                params: { lat: parseFloat(lat), lon: parseFloat(lon) }
            })
        })
        .then(function (resp) { return resp.json(); })
        .then(function (data) {
            var result = data.result;
            if (!result || result.error) {
                panel.className = 'err';
                panel.innerHTML = '&#9888; ' + ((result && result.error) || 'Error desconocido');
                return;
            }
            var features = result.features || [];
            if (!features.length) {
                panel.className = '';
                panel.innerHTML = 'No se encontr\u00f3 ninguna parcela. '
                    + 'Prueba a hacer clic m\u00e1s cerca del centro de la parcela.';
                return;
            }
            var p   = features[0].properties || {};
            var ref = [p.provincia, p.municipio, p.poligono, p.parcela, p.recinto]
                        .map(function (v) { return v || ''; }).join('-');
            var uso = p.dn_uso || p.uso || '?';
            var m2  = parseFloat(p.dn_surface || p.superficie || 0);

            selection = { lat: parseFloat(lat), lon: parseFloat(lon), ref: ref };

            panel.className = 'ok';
            panel.innerHTML =
                '<strong>&#10003; Parcela:</strong>'
                + ' <code>' + ref + '</code>'
                + ' &nbsp;<span class="tag">' + uso + '</span>'
                + ' &nbsp;' + m2.toLocaleString('es-ES') + '&nbsp;m&sup2;'
                + ' &nbsp;|&nbsp;' + lat + ', ' + lon
                + ' &nbsp;<button id="btn-import">&#8681; Importar a Odoo</button>';

            var btn = document.getElementById('btn-import');
            if (btn) { btn.addEventListener('click', doImport); }
        })
        .catch(function (err) {
            panel.className = 'err';
            panel.innerHTML = '&#9888; Error de red: ' + err.message;
        });
    });

    /* ── 6. Importar parcela seleccionada ── */
    function doImport() {
        if (!selection) { return; }
        var btn = document.getElementById('btn-import');
        if (btn) { btn.disabled = true; btn.textContent = 'Importando\u2026'; }

        fetch('/vinedo/sigpac_importar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0', method: 'call', id: 1,
                params: { rec_id: REC_ID, lat: selection.lat, lon: selection.lon }
            })
        })
        .then(function (resp) { return resp.json(); })
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
                    + ' &nbsp;<button id="btn-import">Reintentar</button>';
                var b2 = document.getElementById('btn-import');
                if (b2) { b2.addEventListener('click', doImport); }
            }
        })
        .catch(function (err) {
            panel.className = 'err';
            panel.innerHTML = '&#9888; Error de red: ' + err.message
                + ' &nbsp;<button id="btn-import">Reintentar</button>';
            var b2 = document.getElementById('btn-import');
            if (b2) { b2.addEventListener('click', doImport); }
        });
    }

}());
