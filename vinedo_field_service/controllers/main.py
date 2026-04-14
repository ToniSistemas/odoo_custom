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
    '  href="/vinedo_field_service/static/src/lib/leaflet/leaflet.css?v=1.9.0"/>'
    '<link rel="stylesheet"'
    '  href="/vinedo_field_service/static/src/sigpac_viewer.css?v=1.9.0"/>'
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
    '<script src="/vinedo_field_service/static/src/lib/leaflet/leaflet.js?v=1.9.0"></script>'
    '<script src="/vinedo_field_service/static/src/sigpac_viewer.js?v=1.9.0"></script>'
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

    @http.route('/vinedo/sigpac_consultar', type='jsonrpc', auth='user', csrf=False)
    def sigpac_consultar(self, lat, lon, **kwargs):
        """Proxy server-side: llama a la API REST de SIGPAC desde Odoo.
        Evita el bloqueo CORS que tendría la llamada directa del navegador."""
        import urllib.request as _req
        import json as _json
        import gzip as _gzip

        url = (
            'https://sigpac-hubcloud.es/servicioconsultassigpac'
            '/query/recinfobypoint/4326/'
            + str(float(lon)) + '/' + str(float(lat)) + '.json'
        )
        try:
            req = _req.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (OdooSIGPAC/1.8)',
                'Accept-Encoding': 'gzip, deflate',
                'Accept': 'application/json',
            })
            with _req.urlopen(req, timeout=12) as resp:
                raw = resp.read()
                # SIGPAC devuelve la respuesta comprimida con gzip
                if raw[:2] == b'\x1f\x8b':
                    raw = _gzip.decompress(raw)
                return _json.loads(raw.decode('utf-8'))
        except Exception as e:
            _logger.warning('sigpac_consultar error: %s', e)
            return {'error': str(e), 'features': []}

    @http.route('/vinedo/sigpac_importar', type='jsonrpc', auth='user', csrf=False)
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
