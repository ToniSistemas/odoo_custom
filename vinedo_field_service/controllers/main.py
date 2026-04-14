# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Visor SIGPAC  –  HTML embebido en el formulario de Finca
#
# El iframe apunta a /vinedo/sigpac_viewer/<rec_id> (mismo origen que Odoo),
# evitando el bloqueo X-Frame-Options del visor oficial de SIGPAC.
#
# La CSP de Odoo 19 bloquea inline-scripts e inline-styles y fuentes externas.
# Solución: HTML mínimo sin nada inline; datos pasados via data-* en <html>;
# todos los scripts y estilos servidos desde /vinedo_field_service/static/src/
# (mismo origen → pasan script-src 'self' y style-src 'self').
# ─────────────────────────────────────────────────────────────────────────────

# Template 100% libre de inline scripts e inline styles.
# Variables de Python sustituidas con str.replace() sobre marcadores __NOMBRE__.
_VIEWER_HTML = (
    '<!DOCTYPE html>'
    '<html lang="es"'
    '  data-rec-id="__REC_ID__"'
    '  data-lat="__LAT__"'
    '  data-lon="__LON__"'
    '  data-zoom="__ZOOM__"'
    '  __MARKER_ATTRS__>'
    '<head>'
    '<meta charset="utf-8"/>'
    '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
    '<title>Visor SIGPAC</title>'
    # CSS externo - mismo origen - pasa CSP style-src 'self'
    '<link rel="stylesheet"'
    '  href="/vinedo_field_service/static/src/lib/leaflet/leaflet.css"/>'
    '<link rel="stylesheet"'
    '  href="/vinedo_field_service/static/src/sigpac_viewer.css"/>'
    '</head>'
    '<body>'
    '<div id="map">'
    '  <div id="zoom-hint">'
    '    Acerca el mapa (&ge;&nbsp;14) para ver las parcelas SIGPAC'
    '  </div>'
    '</div>'
    '<div id="panel">'
    '  Haz clic en una parcela del mapa para seleccionarla.'
    '  <span class="hint">(zoom &ge;&nbsp;14 para ver los l&iacute;mites)</span>'
    '</div>'
    # Scripts externos - mismo origen - pasan CSP script-src 'self'
    '<script src="/vinedo_field_service/static/src/lib/leaflet/leaflet.js"></script>'
    '<script src="/vinedo_field_service/static/src/sigpac_viewer.js"></script>'
    '</body>'
    '</html>'
)


def _render_viewer(rec_id, lat, lon, zoom, marker_attrs):
    """Sustituye los marcadores __PLACEHOLDER__ en el template HTML."""
    return (
        _VIEWER_HTML
        .replace('__REC_ID__',      str(rec_id))
        .replace('__LAT__',         str(lat))
        .replace('__LON__',         str(lon))
        .replace('__ZOOM__',        str(zoom))
        .replace('__MARKER_ATTRS__', marker_attrs)
    )


class SigpacController(http.Controller):

    @http.route('/vinedo/sigpac_viewer/<int:rec_id>', type='http', auth='user')
    def sigpac_viewer(self, rec_id, **kwargs):
        """Sirve el visor SIGPAC como HTML propio de Odoo (mismo origen).
        Evita el bloqueo X-Frame-Options del visor oficial de SIGPAC.
        Sin ningún inline script/style para cumplir con la CSP de Odoo 19."""
        record = request.env['vinedo.finca'].browse(rec_id)
        if not record.exists():
            return request.make_response(
                '<html><body style="font-family:Arial;padding:20px;color:#dc3545;">'
                '<strong>Finca no encontrada.</strong></body></html>',
                headers=[('Content-Type', 'text/html; charset=utf-8')]
            )

        has_coords = bool(record.latitude and record.longitude)
        lat  = record.latitude  or 40.4168
        lon  = record.longitude or -3.7038
        zoom = 17 if has_coords else 6

        if has_coords:
            marker_attrs = (
                'data-marker-lat="' + str(record.latitude) + '"'
                + ' data-marker-lon="' + str(record.longitude) + '"'
            )
        else:
            marker_attrs = ''

        html_content = _render_viewer(rec_id, lat, lon, zoom, marker_attrs)
        return request.make_response(
            html_content,
            headers=[
                ('Content-Type', 'text/html; charset=utf-8'),
                ('X-Frame-Options', 'SAMEORIGIN'),
            ]
        )

    @http.route('/vinedo/sigpac_consultar', type='json', auth='user', csrf=False)
    def sigpac_consultar(self, lat, lon, **kwargs):
        """Proxy server-side: llama a la API REST de SIGPAC desde Odoo.
        Evita el bloqueo CORS que tendría la llamada directa del navegador."""
        import urllib.request as _req
        import json as _json

        url = (
            'https://sigpac.mapa.es/fega/serviciosvisorsigpac'
            '/query/recintos/' + str(float(lon)) + '/' + str(float(lat))
        )
        try:
            req = _req.Request(url, headers={'User-Agent': 'Mozilla/5.0 (OdooSIGPAC/1.7)'})
            with _req.urlopen(req, timeout=12) as resp:
                return _json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            _logger.warning('sigpac_consultar error: %s', e)
            return {'error': str(e), 'features': []}

    @http.route('/vinedo/sigpac_importar', type='json', auth='user', csrf=False)
    def sigpac_importar(self, rec_id, lat, lon, **kwargs):
        """Escribe las coordenadas en la finca y ejecuta la consulta SIGPAC completa."""
        record = request.env['vinedo.finca'].browse(int(rec_id))
        if not record.exists():
            return {'error': 'Finca no encontrada'}
        try:
            record.write({'latitude': float(lat), 'longitude': float(lon)})
            record.action_consultar_sigpac()
            return {'ok': True, 'ref_sigpac': record.ref_sigpac or ''}
        except UserError as e:
            return {'error': str(e.args[0] if e.args else e)}
        except Exception as e:
            _logger.exception('sigpac_importar error rec_id=%s', rec_id)
            return {'error': str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Visor SIGPAC  –  HTML embebido en el formulario de Finca
# El iframe apunta a /vinedo/sigpac_viewer/<rec_id> (mismo origen Odoo),
# evitando el bloqueo X-Frame-Options del visor oficial de SIGPAC.
# Las llamadas a la API de SIGPAC se hacen desde el servidor Odoo (proxy),
# evitando el bloqueo CORS en el navegador.
#
# NOTA: el template usa marcadores __PLACEHOLDER__ en lugar de {placeholder}
# para evitar conflictos con las llaves de CSS y JavaScript al concatenar.
# ─────────────────────────────────────────────────────────────────────────────

# CSP permisiva para la respuesta del visor:
# - script-src: permite unpkg.com (Leaflet)
# - style-src: permite unpkg.com (Leaflet CSS) e inline
# - img-src: permite tiles OSM, IGN PNOA y SIGPAC WMS
# - connect-src: permite llamadas AJAX al propio Odoo (/vinedo/sigpac_*)
_VIEWER_CSP = (
    "default-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline' https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https://unpkg.com; "
    "img-src 'self' data: blob: "
    "https://*.tile.openstreetmap.org "
    "https://*.ign.es "
    "https://sigpac.mapa.es http://sigpac.mapa.es; "
    "connect-src 'self'; "
    "font-src 'self' https://unpkg.com;"
)

_VIEWER_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Visor SIGPAC</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="anonymous"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin="anonymous"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 100%; height: 100%; overflow: hidden; }

  /* Posicionamiento absoluto: no depende de height:100% en cadena */
  #map {
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 52px;
    background: #d0e8f5;   /* color visible si Leaflet tarda en cargar */
  }
  #panel {
    position: absolute;
    bottom: 0; left: 0; right: 0; height: 52px;
    padding: 6px 12px;
    background: #f8f9fa;
    border-top: 1px solid #dee2e6;
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    font-family: Arial, sans-serif; font-size: 13px;
    overflow: hidden;
  }
  #panel.loading { color: #6c757d; }
  #panel.ok   { background: #d4edda; border-top-color: #28a745; }
  #panel.err  { background: #f8d7da; border-top-color: #dc3545; }
  #panel.done { background: #cce5ff; border-top-color: #004085; }

  .tag {
    display: inline-block;
    background: #495057; color: #fff;
    padding: 1px 6px; border-radius: 3px; font-size: 11px;
  }
  #btn-import {
    padding: 3px 12px;
    background: #28a745; color: #fff;
    border: none; border-radius: 4px;
    cursor: pointer; font-size: 12px; font-weight: bold;
  }
  #btn-import:hover    { background: #218838; }
  #btn-import:disabled { background: #6c757d; cursor: default; }

  #zoom-hint {
    position: absolute; bottom: 10px; left: 50%;
    transform: translateX(-50%);
    background: rgba(0,0,0,.6); color: #fff;
    padding: 5px 12px; border-radius: 16px; font-size: 12px;
    font-family: Arial, sans-serif;
    pointer-events: none; z-index: 1000; display: none;
  }
  #leaflet-error {
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    background: #fff3cd; border: 1px solid #ffc107;
    padding: 16px 20px; border-radius: 6px;
    font-family: Arial, sans-serif; font-size: 13px;
    text-align: center; z-index: 2000; display: none;
    max-width: 360px;
  }
</style>
</head>
<body>
<div id="map">
  <div id="zoom-hint">Acerca el mapa (zoom &ge; 14) para ver las parcelas SIGPAC</div>
  <div id="leaflet-error">
    <strong>&#9888; No se pudo cargar Leaflet</strong><br/>
    <span style="font-size:11px;color:#856404;">
      Comprueba que el servidor tiene acceso a internet (unpkg.com)
    </span>
  </div>
</div>
<div id="panel">
  Haz clic en una parcela del mapa para seleccionarla.
  <span style="color:#6c757d;font-size:11px;">(zoom &ge; 14 para ver los l&iacute;mites)</span>
</div>

<script>
var REC_ID = __REC_ID__;
var LAT    = __LAT__;
var LON    = __LON__;
var ZOOM   = __ZOOM__;

// Comprobamos que Leaflet cargo correctamente
if (typeof L === 'undefined') {
    document.getElementById('leaflet-error').style.display = 'block';
    document.getElementById('map').style.background = '#fff3cd';
    throw new Error('Leaflet no disponible');
}

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

__MARKER_JS__

// Forzar recalculo de tama\u00f1o por si el iframe no lo pasa bien
setTimeout(function() { map.invalidateSize(); }, 200);

var zoomHint = document.getElementById('zoom-hint');
function updateZoomHint() {
    zoomHint.style.display = map.getZoom() < 14 ? 'block' : 'none';
}
map.on('zoomend', updateZoomHint);
updateZoomHint();

var panel = document.getElementById('panel');
var selection = null;

map.on('click', async function(e) {
    var lat = e.latlng.lat.toFixed(7);
    var lon = e.latlng.lng.toFixed(7);
    panel.className = 'loading';
    panel.innerHTML = '&#8987; Consultando SIGPAC&hellip;';
    try {
        var resp = await fetch('/vinedo/sigpac_consultar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0', method: 'call', id: 1,
                params: { lat: parseFloat(lat), lon: parseFloat(lon) }
            })
        });
        var data = await resp.json();
        var result = data.result;
        if (!result || result.error) {
            panel.className = 'err';
            panel.innerHTML = '&#9888; ' + ((result && result.error) || 'Error desconocido');
            return;
        }
        var features = result.features || [];
        if (!features.length) {
            panel.className = '';
            panel.innerHTML = 'No se encontr\u00f3 ninguna parcela en ese punto. '
                + 'Prueba a hacer clic m\u00e1s cerca del centro de una parcela.';
            return;
        }
        var p = features[0].properties || {};
        var prov = p.provincia  || '';
        var mun  = p.municipio  || '';
        var pol  = p.poligono   || '';
        var par  = p.parcela    || '';
        var rec  = p.recinto    || '';
        var uso  = p.dn_uso     || p.uso       || '?';
        var m2   = p.dn_surface || p.superficie || 0;
        var ref  = prov + '-' + mun + '-' + pol + '-' + par + '-' + rec;
        selection = { lat: parseFloat(lat), lon: parseFloat(lon), ref: ref };
        panel.className = 'ok';
        panel.innerHTML = '<strong>&#10003; Parcela:</strong>'
            + ' <code>' + ref + '</code>'
            + ' &nbsp;<span class="tag">' + uso + '</span>'
            + ' &nbsp;' + parseFloat(m2).toLocaleString('es-ES') + '&nbsp;m&sup2;'
            + ' &nbsp;|&nbsp; ' + lat + ', ' + lon
            + ' &nbsp;<button id="btn-import" onclick="doImport()">&#8681; Importar a Odoo</button>';
    } catch(err) {
        panel.className = 'err';
        panel.innerHTML = '&#9888; Error de red: ' + err.message;
    }
});

async function doImport() {
    if (!selection) return;
    var btn = document.getElementById('btn-import');
    if (btn) { btn.disabled = true; btn.textContent = 'Importando\u2026'; }
    try {
        var resp = await fetch('/vinedo/sigpac_importar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0', method: 'call', id: 1,
                params: { rec_id: REC_ID, lat: selection.lat, lon: selection.lon }
            })
        });
        var data = await resp.json();
        var result = data.result;
        if (result && result.ok) {
            panel.className = 'done';
            panel.innerHTML = '&#9989; Importado: <strong>' + (result.ref_sigpac || selection.ref)
                + '</strong> &mdash; Recargando\u2026';
            setTimeout(function() { window.parent.location.reload(); }, 1400);
        } else {
            panel.className = 'err';
            panel.innerHTML = '&#9888; ' + ((result && result.error) || 'Error desconocido')
                + ' &nbsp;<button id="btn-import" onclick="doImport()">Reintentar</button>';
        }
    } catch(err) {
        panel.className = 'err';
        panel.innerHTML = '&#9888; Error de red: ' + err.message
            + ' &nbsp;<button id="btn-import" onclick="doImport()">Reintentar</button>';
    }
}
</script>
</body>
</html>"""


def _render_viewer(rec_id, lat, lon, zoom, marker_js):
    """Sustituye los marcadores __PLACEHOLDER__ en el template HTML."""
    return (
        _VIEWER_HTML
        .replace('__REC_ID__', str(rec_id))
        .replace('__LAT__', str(lat))
        .replace('__LON__', str(lon))
        .replace('__ZOOM__', str(zoom))
        .replace('__MARKER_JS__', marker_js)
    )


class SigpacController(http.Controller):

    @http.route('/vinedo/sigpac_viewer/<int:rec_id>', type='http', auth='user')
    def sigpac_viewer(self, rec_id, **kwargs):
        """Sirve el visor SIGPAC como HTML propio de Odoo (mismo origen).
        Evita el bloqueo X-Frame-Options del visor oficial de SIGPAC."""
        record = request.env['vinedo.finca'].browse(rec_id)
        if not record.exists():
            return request.make_response(
                '<html><body style="font-family:Arial;padding:20px;color:#dc3545;">'
                '<strong>Finca no encontrada.</strong></body></html>',
                headers=[('Content-Type', 'text/html; charset=utf-8')]
            )

        has_coords = bool(record.latitude and record.longitude)
        lat  = record.latitude  or 40.4168
        lon  = record.longitude or -3.7038
        zoom = 17 if has_coords else 6

        if has_coords:
            marker_js = (
                "L.marker([" + str(record.latitude) + ", " + str(record.longitude) + "]).addTo(map)"
                ".bindPopup('Ubicaci\u00f3n actual de la finca');"
            )
        else:
            marker_js = "// sin coordenadas guardadas"

        html_content = _render_viewer(rec_id, lat, lon, zoom, marker_js)
        return request.make_response(
            html_content,
            headers=[
                ('Content-Type', 'text/html; charset=utf-8'),
                ('Content-Security-Policy', _VIEWER_CSP),
                ('X-Frame-Options', 'SAMEORIGIN'),
            ]
        )

    @http.route('/vinedo/sigpac_consultar', type='json', auth='user', csrf=False)
    def sigpac_consultar(self, lat, lon, **kwargs):
        """Proxy: consulta la API REST de SIGPAC desde el servidor Odoo.
        Evita el bloqueo CORS que tendría la llamada directa desde el navegador."""
        import urllib.request as _req
        import json as _json

        url = (
            'https://sigpac.mapa.es/fega/serviciosvisorsigpac'
            '/query/recintos/' + str(float(lon)) + '/' + str(float(lat))
        )
        try:
            req = _req.Request(url, headers={'User-Agent': 'Mozilla/5.0 (OdooSIGPAC/1.7)'})
            with _req.urlopen(req, timeout=12) as resp:
                return _json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            _logger.warning('sigpac_consultar error: %s', e)
            return {'error': str(e), 'features': []}

    @http.route('/vinedo/sigpac_importar', type='json', auth='user', csrf=False)
    def sigpac_importar(self, rec_id, lat, lon, **kwargs):
        """Escribe las coordenadas en la finca y ejecuta la consulta SIGPAC completa."""
        record = request.env['vinedo.finca'].browse(int(rec_id))
        if not record.exists():
            return {'error': 'Finca no encontrada'}
        try:
            record.write({'latitude': float(lat), 'longitude': float(lon)})
            record.action_consultar_sigpac()
            return {'ok': True, 'ref_sigpac': record.ref_sigpac or ''}
        except UserError as e:
            return {'error': str(e.args[0] if e.args else e)}
        except Exception as e:
            _logger.exception('sigpac_importar error rec_id=%s', rec_id)
            return {'error': str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Visor SIGPAC  –  HTML embebido en el formulario de Finca
# El iframe apunta a /vinedo/sigpac_viewer/<rec_id> (mismo origen Odoo),
# evitando el bloqueo X-Frame-Options del visor oficial de SIGPAC.
# Las llamadas a la API de SIGPAC se hacen desde el servidor Odoo (proxy),
# evitando el bloqueo CORS en el navegador.
#
# NOTA: el template usa marcadores __PLACEHOLDER__ en lugar de {placeholder}
# para evitar conflictos con las llaves de CSS y JavaScript.
# ─────────────────────────────────────────────────────────────────────────────

_VIEWER_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Visor SIGPAC</title>
<link rel="stylesheet"
      href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV/XN/WPeE=" crossorigin=""></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; font-family: Arial, sans-serif; font-size: 13px; }
  body { display: flex; flex-direction: column; }
  #map { flex: 1; min-height: 0; }
  #panel {
    padding: 8px 12px;
    background: #f8f9fa;
    border-top: 1px solid #dee2e6;
    min-height: 40px;
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  #panel.loading { color: #6c757d; }
  #panel.ok  { background: #d4edda; border-top-color: #28a745; }
  #panel.err { background: #f8d7da; border-top-color: #dc3545; }
  #panel.done { background: #cce5ff; border-top-color: #004085; }
  .tag {
    display: inline-block;
    background: #495057; color: #fff;
    padding: 1px 6px; border-radius: 3px; font-size: 11px;
  }
  #btn-import {
    padding: 4px 14px;
    background: #28a745; color: #fff;
    border: none; border-radius: 4px;
    cursor: pointer; font-size: 12px; font-weight: bold;
  }
  #btn-import:hover    { background: #218838; }
  #btn-import:disabled { background: #6c757d; cursor: default; }
  #zoom-hint {
    position: absolute; bottom: 50px; left: 50%;
    transform: translateX(-50%);
    background: rgba(0,0,0,.65); color: #fff;
    padding: 6px 14px; border-radius: 20px; font-size: 12px;
    pointer-events: none; z-index: 1000;
  }
</style>
</head>
<body>
<div id="map" style="position:relative;">
  <div id="zoom-hint" style="display:none;">
    Acerca el mapa (zoom &ge; 14) para ver las parcelas SIGPAC
  </div>
</div>
<div id="panel">
  Haz clic en una parcela del mapa para seleccionarla.
  <span style="color:#6c757d;font-size:11px;">(usa zoom &ge; 14 para ver los l\u00edmites)</span>
</div>

<script>
var REC_ID = __REC_ID__;
var LAT    = __LAT__;
var LON    = __LON__;
var ZOOM   = __ZOOM__;

var map = L.map('map').setView([LAT, LON], ZOOM);

var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap',
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

__MARKER_JS__

var zoomHint = document.getElementById('zoom-hint');
function updateZoomHint() {
    zoomHint.style.display = map.getZoom() < 14 ? 'block' : 'none';
}
map.on('zoomend', updateZoomHint);
updateZoomHint();

var panel = document.getElementById('panel');
var selection = null;

map.on('click', async function(e) {
    var lat = e.latlng.lat.toFixed(7);
    var lon = e.latlng.lng.toFixed(7);
    panel.className = 'loading';
    panel.innerHTML = '&#8987; Consultando SIGPAC&hellip;';
    try {
        var resp = await fetch('/vinedo/sigpac_consultar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0', method: 'call', id: 1,
                params: { lat: parseFloat(lat), lon: parseFloat(lon) }
            })
        });
        var data = await resp.json();
        var result = data.result;
        if (!result || result.error) {
            panel.className = 'err';
            panel.innerHTML = '&#9888; ' + ((result && result.error) || 'Error desconocido');
            return;
        }
        var features = result.features || [];
        if (!features.length) {
            panel.className = '';
            panel.innerHTML = 'No se encontr\u00f3 ninguna parcela en ese punto. '
                + 'Prueba a hacer clic m\u00e1s cerca del centro de una parcela.';
            return;
        }
        var p = features[0].properties || {};
        var prov = p.provincia  || '';
        var mun  = p.municipio  || '';
        var pol  = p.poligono   || '';
        var par  = p.parcela    || '';
        var rec  = p.recinto    || '';
        var uso  = p.dn_uso     || p.uso       || '?';
        var m2   = p.dn_surface || p.superficie || 0;
        var ref  = prov + '-' + mun + '-' + pol + '-' + par + '-' + rec;
        selection = { lat: parseFloat(lat), lon: parseFloat(lon), ref: ref };
        panel.className = 'ok';
        panel.innerHTML = '<strong>&#10003; Parcela:</strong>'
            + ' <code>' + ref + '</code>'
            + ' &nbsp;<span class="tag">' + uso + '</span>'
            + ' &nbsp;' + parseFloat(m2).toLocaleString('es-ES') + '&nbsp;m&sup2;'
            + ' &nbsp;|&nbsp; ' + lat + ', ' + lon
            + ' &nbsp;<button id="btn-import" onclick="doImport()">&#8681; Importar a Odoo</button>';
    } catch(err) {
        panel.className = 'err';
        panel.innerHTML = '&#9888; Error de red: ' + err.message;
    }
});

async function doImport() {
    if (!selection) return;
    var btn = document.getElementById('btn-import');
    if (btn) { btn.disabled = true; btn.textContent = 'Importando\u2026'; }
    try {
        var resp = await fetch('/vinedo/sigpac_importar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0', method: 'call', id: 1,
                params: { rec_id: REC_ID, lat: selection.lat, lon: selection.lon }
            })
        });
        var data = await resp.json();
        var result = data.result;
        if (result && result.ok) {
            panel.className = 'done';
            panel.innerHTML = '&#9989; Importado: <strong>' + (result.ref_sigpac || selection.ref)
                + '</strong> &mdash; Recargando\u2026';
            setTimeout(function() { window.parent.location.reload(); }, 1400);
        } else {
            panel.className = 'err';
            panel.innerHTML = '&#9888; ' + ((result && result.error) || 'Error desconocido')
                + ' &nbsp;<button id="btn-import" onclick="doImport()">Reintentar</button>';
        }
    } catch(err) {
        panel.className = 'err';
        panel.innerHTML = '&#9888; Error de red: ' + err.message
            + ' &nbsp;<button id="btn-import" onclick="doImport()">Reintentar</button>';
    }
}
</script>
</body>
</html>"""


def _render_viewer(rec_id, lat, lon, zoom, marker_js):
    """Sustituye los marcadores __PLACEHOLDER__ en el template HTML."""
    return (
        _VIEWER_HTML
        .replace('__REC_ID__', str(rec_id))
        .replace('__LAT__', str(lat))
        .replace('__LON__', str(lon))
        .replace('__ZOOM__', str(zoom))
        .replace('__MARKER_JS__', marker_js)
    )


class SigpacController(http.Controller):

    @http.route('/vinedo/sigpac_viewer/<int:rec_id>', type='http', auth='user')
    def sigpac_viewer(self, rec_id, **kwargs):
        """Sirve el visor SIGPAC como HTML propio de Odoo (mismo origen).
        Evita el bloqueo X-Frame-Options del visor oficial de SIGPAC."""
        record = request.env['vinedo.finca'].browse(rec_id)
        if not record.exists():
            return request.make_response(
                '<html><body style="font-family:Arial;padding:20px;color:#dc3545;">'
                '<strong>Finca no encontrada.</strong></body></html>',
                headers=[('Content-Type', 'text/html; charset=utf-8')]
            )

        has_coords = bool(record.latitude and record.longitude)
        lat  = record.latitude  or 40.4168
        lon  = record.longitude or -3.7038
        zoom = 17 if has_coords else 6

        if has_coords:
            marker_js = (
                "L.marker([" + str(record.latitude) + ", " + str(record.longitude) + "]).addTo(map)"
                ".bindPopup('Ubicaci\u00f3n actual de la finca');"
            )
        else:
            marker_js = "// sin coordenadas guardadas aun"

        html_content = _render_viewer(rec_id, lat, lon, zoom, marker_js)
        return request.make_response(
            html_content,
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )

    @http.route('/vinedo/sigpac_consultar', type='json', auth='user', csrf=False)
    def sigpac_consultar(self, lat, lon, **kwargs):
        """Proxy: consulta la API REST de SIGPAC desde el servidor Odoo.
        Evita el bloqueo CORS que tendría la llamada directa desde el navegador."""
        import urllib.request as _req
        import json as _json

        url = (
            'https://sigpac.mapa.es/fega/serviciosvisorsigpac'
            '/query/recintos/' + str(float(lon)) + '/' + str(float(lat))
        )
        try:
            req = _req.Request(url, headers={'User-Agent': 'Mozilla/5.0 (OdooSIGPAC/1.7)'})
            with _req.urlopen(req, timeout=12) as resp:
                return _json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            _logger.warning('sigpac_consultar error: %s', e)
            return {'error': str(e), 'features': []}

    @http.route('/vinedo/sigpac_importar', type='json', auth='user', csrf=False)
    def sigpac_importar(self, rec_id, lat, lon, **kwargs):
        """Escribe las coordenadas en la finca y ejecuta la consulta SIGPAC completa."""
        record = request.env['vinedo.finca'].browse(int(rec_id))
        if not record.exists():
            return {'error': 'Finca no encontrada'}
        try:
            record.write({'latitude': float(lat), 'longitude': float(lon)})
            record.action_consultar_sigpac()
            return {'ok': True, 'ref_sigpac': record.ref_sigpac or ''}
        except UserError as e:
            return {'error': str(e.args[0] if e.args else e)}
        except Exception as e:
            _logger.exception('sigpac_importar error rec_id=%s', rec_id)
            return {'error': str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Visor SIGPAC  –  HTML embebido en el formulario de Finca
# El iframe apunta a /vinedo/sigpac_viewer/<rec_id> (mismo origen Odoo),
# evitando el bloqueo X-Frame-Options del visor oficial de SIGPAC.
# Las llamadas a la API de SIGPAC se hacen desde el servidor Odoo (proxy),
# evitando el bloqueo CORS en el navegador.
# ─────────────────────────────────────────────────────────────────────────────

_VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Visor SIGPAC</title>
<link rel="stylesheet"
      href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV/XN/WPeE=" crossorigin=""></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; font-family: Arial, sans-serif; font-size: 13px; }
  body { display: flex; flex-direction: column; }
  #map { flex: 1; min-height: 0; }
  #panel {
    padding: 8px 12px;
    background: #f8f9fa;
    border-top: 1px solid #dee2e6;
    min-height: 40px;
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  #panel.loading { color: #6c757d; }
  #panel.ok     { background: #d4edda; border-top-color: #28a745; }
  #panel.err    { background: #f8d7da; border-top-color: #dc3545; }
  #panel.done   { background: #cce5ff; border-top-color: #004085; }
  .tag {
    display: inline-block;
    background: #495057; color: #fff;
    padding: 1px 6px; border-radius: 3px; font-size: 11px;
  }
  #btn-import {
    padding: 4px 14px;
    background: #28a745; color: #fff;
    border: none; border-radius: 4px;
    cursor: pointer; font-size: 12px; font-weight: bold;
  }
  #btn-import:hover   { background: #218838; }
  #btn-import:disabled { background: #6c757d; cursor: default; }
  #zoom-hint {
    position: absolute; bottom: 50px; left: 50%; transform: translateX(-50%);
    background: rgba(0,0,0,.65); color: #fff;
    padding: 6px 14px; border-radius: 20px; font-size: 12px;
    pointer-events: none; z-index: 1000; transition: opacity .3s;
  }
</style>
</head>
<body>
<div id="map" style="position:relative;">
  <div id="zoom-hint" style="display:none;">
    Acerca el mapa (zoom &ge; 14) para ver las parcelas SIGPAC
  </div>
</div>
<div id="panel">
  Haz clic en una parcela del mapa para seleccionarla.
  <span style="color:#6c757d;font-size:11px;">(usa zoom &ge; 14 para ver los límites)</span>
</div>

<script>
// ── datos inyectados por el controlador ──
var REC_ID = {rec_id};
var LAT    = {lat};
var LON    = {lon};
var ZOOM   = {zoom};

// ── mapa ──
var map = L.map('map').setView([LAT, LON], ZOOM);

var osmLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; OpenStreetMap',
    maxZoom: 19
}});

var pnoaLayer = L.tileLayer.wms('https://www.ign.es/wms-inspire/pnoa-ma', {{
    layers: 'OI.OrthoimageCoverage',
    format: 'image/jpeg',
    transparent: false,
    attribution: '&copy; IGN PNOA',
    maxZoom: 20
}});

var sigpacLayer = L.tileLayer.wms(
    'https://sigpac.mapa.es/fega/serviciosvisorsigpac/wms/wms.aspx', {{
    layers: 'SIGPAC',
    format: 'image/png',
    transparent: true,
    version: '1.3.0',
    opacity: 0.85,
    attribution: '&copy; MAPA SIGPAC',
    maxZoom: 19
}});

osmLayer.addTo(map);
sigpacLayer.addTo(map);

L.control.layers(
    {{ 'OpenStreetMap': osmLayer, 'Foto aérea (PNOA)': pnoaLayer }},
    {{ 'Parcelas SIGPAC': sigpacLayer }},
    {{ collapsed: false }}
).addTo(map);

// marcador posición actual si hay coords
{marker_js}

// aviso de zoom
var zoomHint = document.getElementById('zoom-hint');
function updateZoomHint() {{
    zoomHint.style.display = map.getZoom() < 14 ? 'block' : 'none';
}}
map.on('zoomend', updateZoomHint);
updateZoomHint();

// ── interacción ──
var panel = document.getElementById('panel');
var selection = null;

map.on('click', async function(e) {{
    var lat = e.latlng.lat.toFixed(7);
    var lon = e.latlng.lng.toFixed(7);
    panel.className = 'loading';
    panel.innerHTML = '&#8987; Consultando SIGPAC&hellip;';

    try {{
        var resp = await fetch('/vinedo/sigpac_consultar', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                jsonrpc: '2.0', method: 'call', id: 1,
                params: {{lat: parseFloat(lat), lon: parseFloat(lon)}}
            }})
        }});
        var data = await resp.json();
        var result = data.result;

        if (!result || result.error) {{
            panel.className = 'err';
            panel.innerHTML = '&#9888; ' + ((result && result.error) || 'Error desconocido');
            return;
        }}

        var features = result.features || [];
        if (!features.length) {{
            panel.className = '';
            panel.innerHTML = 'No se encontró ninguna parcela en ese punto. '
                + 'Prueba a hacer clic más cerca del centro de una parcela.';
            return;
        }}

        var p = features[0].properties || {{}};
        var prov = p.provincia   || '';
        var mun  = p.municipio   || '';
        var pol  = p.poligono    || '';
        var par  = p.parcela     || '';
        var rec  = p.recinto     || '';
        var uso  = p.dn_uso      || p.uso       || '?';
        var m2   = p.dn_surface  || p.superficie || 0;
        var ref  = prov + '-' + mun + '-' + pol + '-' + par + '-' + rec;

        selection = {{ lat: parseFloat(lat), lon: parseFloat(lon), ref: ref }};

        panel.className = 'ok';
        panel.innerHTML = '<strong>&#10003; Parcela:</strong>'
            + ' <code>' + ref + '</code>'
            + ' &nbsp;<span class="tag">' + uso + '</span>'
            + ' &nbsp;' + parseFloat(m2).toLocaleString('es-ES') + '\u00a0m\u00b2'
            + ' &nbsp;|&nbsp; ' + lat + ', ' + lon
            + ' &nbsp;<button id="btn-import" onclick="doImport()">&#8681; Importar a Odoo</button>';

    }} catch(err) {{
        panel.className = 'err';
        panel.innerHTML = '&#9888; Error de red: ' + err.message;
    }}
}});

async function doImport() {{
    if (!selection) return;
    var btn = document.getElementById('btn-import');
    if (btn) {{ btn.disabled = true; btn.textContent = 'Importando\u2026'; }}

    try {{
        var resp = await fetch('/vinedo/sigpac_importar', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                jsonrpc: '2.0', method: 'call', id: 1,
                params: {{ rec_id: REC_ID, lat: selection.lat, lon: selection.lon }}
            }})
        }});
        var data = await resp.json();
        var result = data.result;

        if (result && result.ok) {{
            panel.className = 'done';
            panel.innerHTML = '&#9989; Importado: <strong>' + (result.ref_sigpac || selection.ref)
                + '</strong> &mdash; Recargando\u2026';
            setTimeout(function() {{ window.parent.location.reload(); }}, 1400);
        }} else {{
            panel.className = 'err';
            panel.innerHTML = '&#9888; ' + ((result && result.error) || 'Error desconocido')
                + ' &nbsp;<button id="btn-import" onclick="doImport()">Reintentar</button>';
        }}
    }} catch(err) {{
        panel.className = 'err';
        panel.innerHTML = '&#9888; Error de red: ' + err.message
            + ' &nbsp;<button id="btn-import" onclick="doImport()">Reintentar</button>';
    }}
}}
</script>
</body>
</html>"""


class SigpacController(http.Controller):

    @http.route('/vinedo/sigpac_viewer/<int:rec_id>', type='http', auth='user')
    def sigpac_viewer(self, rec_id, **kwargs):
        """Sirve el visor SIGPAC como HTML propio de Odoo (mismo origen).
        Evita el bloqueo X-Frame-Options del visor oficial de SIGPAC."""
        record = request.env['vinedo.finca'].browse(rec_id)
        if not record.exists():
            return request.make_response(
                '<html><body style="font-family:Arial;padding:20px;color:#dc3545;">'
                '<strong>Finca no encontrada.</strong></body></html>',
                headers=[('Content-Type', 'text/html; charset=utf-8')]
            )

        has_coords = bool(record.latitude and record.longitude)
        lat  = record.latitude  or 40.4168
        lon  = record.longitude or -3.7038
        zoom = 17 if has_coords else 6

        # Marcador JS para la posición actual (sólo si hay coords)
        if has_coords:
            marker_js = (
                f"L.marker([{record.latitude}, {record.longitude}]).addTo(map)"
                f".bindPopup('Ubicación actual de la finca');"
            )
        else:
            marker_js = "// sin coordenadas guardadas aún"

        html_content = _VIEWER_HTML.format(
            rec_id=rec_id,
            lat=lat,
            lon=lon,
            zoom=zoom,
            marker_js=marker_js,
        )
        return request.make_response(
            html_content,
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )

    @http.route('/vinedo/sigpac_consultar', type='json', auth='user', csrf=False)
    def sigpac_consultar(self, lat, lon, **kwargs):
        """Proxy: consulta la API REST de SIGPAC desde el servidor Odoo.
        Evita el bloqueo CORS que tendría la llamada directa desde el navegador."""
        import urllib.request as _req
        import json as _json

        url = (
            f'https://sigpac.mapa.es/fega/serviciosvisorsigpac'
            f'/query/recintos/{float(lon)}/{float(lat)}'
        )
        try:
            req = _req.Request(url, headers={'User-Agent': 'Mozilla/5.0 (OdooSIGPAC/1.7)'})
            with _req.urlopen(req, timeout=12) as resp:
                return _json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            _logger.warning('sigpac_consultar error: %s', e)
            return {'error': str(e), 'features': []}

    @http.route('/vinedo/sigpac_importar', type='json', auth='user', csrf=False)
    def sigpac_importar(self, rec_id, lat, lon, **kwargs):
        """Escribe las coordenadas en la finca y ejecuta la consulta SIGPAC completa."""
        record = request.env['vinedo.finca'].browse(int(rec_id))
        if not record.exists():
            return {'error': 'Finca no encontrada'}
        try:
            record.write({'latitude': float(lat), 'longitude': float(lon)})
            record.action_consultar_sigpac()
            return {'ok': True, 'ref_sigpac': record.ref_sigpac or ''}
        except UserError as e:
            return {'error': str(e.args[0] if e.args else e)}
        except Exception as e:
            _logger.exception('sigpac_importar error rec_id=%s', rec_id)
            return {'error': str(e)}
