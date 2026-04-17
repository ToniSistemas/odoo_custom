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
    '  data-ref-sigpac="__REF_SIGPAC__"'
    '  data-ref-sigpac2="__REF_SIGPAC2__"'
    '  data-recintos="__RECINTOS__"'
    '  __MARKER_ATTRS__>'
    '<head>'
    '<meta charset="utf-8"/>'
    '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
    '<title>Visor SIGPAC</title>'
    # CSS externo - mismo origen - pasa CSP style-src 'self'
    '<link rel="stylesheet"'
    '  href="/vinedo_field_service/static/src/lib/leaflet/leaflet.css?v=2.0.7"/>'
    '<link rel="stylesheet"'
    '  href="/vinedo_field_service/static/src/sigpac_viewer.css?v=2.0.7"/>'
    '</head>'
    '<body>'
    '<div id="descripcion">'
    '  <strong>Visor SIGPAC</strong> &mdash; Haz clic sobre una parcela en el mapa para obtener su referencia SIGPAC, superficie y coordenadas.'
    '  Una vez seleccionada, pulsa <strong>Importar a Odoo</strong> para guardar los datos en la finca.'
    '  Usa la capa <em>Recintos SIGPAC</em> para identificar los l&iacute;mites de las parcelas.'
    '  El checkbox controla si se importa la superficie total de la parcela (suma de todos sus recintos) o solo la del recinto clicado.'
    '</div>'
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
    '<script src="/vinedo_field_service/static/src/lib/leaflet/leaflet.js?v=2.0.7"></script>'
        '<script src="/vinedo_field_service/static/src/sigpac_viewer.js?v=2.0.7"></script>'
    '</body>'
    '</html>'
)


def _render_viewer(rec_id, lat, lon, zoom, marker_attrs, ref_sigpac='', recintos_json='[]', ref_sigpac2=''):
    """Sustituye los marcadores __PLACEHOLDER__ en el template HTML."""
    import html as _html
    return (
        _VIEWER_HTML
        .replace('__REC_ID__',       str(rec_id))
        .replace('__LAT__',          str(lat))
        .replace('__LON__',          str(lon))
        .replace('__ZOOM__',         str(zoom))
        .replace('__MARKER_ATTRS__', marker_attrs)
        .replace('__REF_SIGPAC__',   _html.escape(ref_sigpac,  quote=True))
        .replace('__REF_SIGPAC2__',  _html.escape(ref_sigpac2, quote=True))
        .replace('__RECINTOS__',     _html.escape(recintos_json, quote=True))
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

        import json as _json
        ref_sigpac = record.ref_sigpac or ''
        recintos_json = _json.dumps([
            {'recinto': r.recinto_num, 'activo': r.activo}
            for r in record.recinto_ids
        ])
        # Leer ref_sigpac2 guardada en sigpac_json (por sigpac_agregar_parcela)
        ref_sigpac2 = ''
        if record.sigpac_json:
            try:
                _sj = _json.loads(record.sigpac_json)
                ref_sigpac2 = _sj.get('ref_sigpac2', '') or ''
            except Exception:
                pass

        html_content = _render_viewer(rec_id, lat, lon, zoom, marker_attrs, ref_sigpac, recintos_json, ref_sigpac2)
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
    def sigpac_importar(self, rec_id, lat, lon, area_ha=None, **kwargs):
        """Escribe las coordenadas en la finca y ejecuta la consulta SIGPAC completa.
        Si area_ha se recibe, sobreescribe el área calculada por action_consultar_sigpac
        (se usa cuando el usuario deselecciona 'Importar superficie total' en el mapa)."""
        record = request.env['vinedo.finca'].browse(int(rec_id))
        if not record.exists():
            return {'error': 'Finca no encontrada'}
        try:
            record.write({'latitude': float(lat), 'longitude': float(lon)})
            record.action_consultar_sigpac()
            if area_ha is not None:
                record.write({'area': round(float(area_ha), 4)})
            return {'ok': True, 'ref_sigpac': record.ref_sigpac or ''}
        except UserError as e:
            return {'error': str(e.args[0] if e.args else e)}
        except Exception as e:
            _logger.exception('sigpac_importar error rec_id=%s', rec_id)
            return {'error': str(e)}

    @http.route('/vinedo/sigpac_agregar_parcela', type='jsonrpc', auth='user', csrf=False)
    def sigpac_agregar_parcela(self, rec_id, lat, lon, **kwargs):
        """Añade los recintos de una segunda parcela a continuación de los ya existentes.
        No borra los recintos previos ni modifica lat/lon ni ref_sigpac.
        Incrementa la numeración de recinto_num para evitar colisiones."""
        import requests as _req2
        import json as _json2

        record = request.env['vinedo.finca'].browse(int(rec_id))
        if not record.exists():
            return {'error': 'Finca no encontrada'}

        try:
            # Paso 1: consultar recinto en las coordenadas
            url1 = (
                'https://sigpac-hubcloud.es/servicioconsultassigpac'
                '/query/recinfobypoint/4326/'
                + str(float(lon)) + '/' + str(float(lat)) + '.json'
            )
            resp1 = _req2.get(url1, timeout=15,
                              headers={'User-Agent': 'OdooSIGPAC/1.8',
                                       'Accept-Encoding': 'gzip'})
            resp1.raise_for_status()
            arr = resp1.json()
        except Exception as e:
            return {'error': 'Error conectando con SIGPAC: ' + str(e)}

        if not isinstance(arr, list) or not arr:
            return {'error': 'No se encontró recinto SIGPAC en esas coordenadas.'}

        p = arr[0]
        prov = str(p.get('provincia', ''))
        mun  = str(p.get('municipio', ''))
        agr  = str(p.get('agregado', 0) or 0)
        zona = str(p.get('zona', 0) or 0)
        pol  = str(p.get('poligono', ''))
        par  = str(p.get('parcela', ''))
        ref2 = f'{prov}:{mun}:{agr}:{zona}:{pol}:{par}'

        # Paso 2: todos los recintos de la segunda parcela
        all_recintos = []
        try:
            url2 = (
                'https://sigpac-hubcloud.es/servicioconsultassigpac'
                '/query/recinfoparc/'
                + prov + '/' + mun + '/' + agr + '/' + zona + '/' + pol + '/' + par + '.json'
            )
            resp2 = _req2.get(url2, timeout=15,
                              headers={'User-Agent': 'OdooSIGPAC/1.8',
                                       'Accept-Encoding': 'gzip'})
            if resp2.status_code == 200:
                arr2 = resp2.json()
                if isinstance(arr2, list):
                    all_recintos = [
                        {
                            'recinto': str(r.get('recinto', '')),
                            'uso': r.get('uso_sigpac', '?'),
                            'superficie': round(float(r.get('superficie', 0) or 0) * 10000, 2),
                        }
                        for r in arr2
                    ]
        except Exception as e:
            _logger.warning('SIGPAC recinfoparc (agregar) error: %s', e)

        if not all_recintos:
            all_recintos = [
                {
                    'recinto': str(r.get('recinto', '')),
                    'uso': r.get('uso_sigpac', '?'),
                    'superficie': round(float(r.get('superficie', 0) or 0) * 10000, 2),
                }
                for r in arr
            ]

        # Offset de recinto_num para no colisionar con los existentes
        # Usamos un bloque 1000+ para identificar fácilmente la segunda parcela
        existing_nums = record.recinto_ids.mapped('recinto_num')
        base_offset = (max(existing_nums) // 1000 + 1) * 1000 if existing_nums else 1000

        recinto_vals = []
        total_m2 = 0
        for r in all_recintos:
            try:
                rnum = int(r['recinto'])
            except (ValueError, TypeError):
                continue
            total_m2 += r['superficie']
            recinto_vals.append((0, 0, {
                'recinto_num': base_offset + rnum,
                'uso_sigpac': r['uso'],
                'superficie_ha': round(r['superficie'] / 10000, 4),
                'activo': True,
            }))

        if not recinto_vals:
            return {'error': 'No se obtuvieron recintos válidos de la segunda parcela.'}

        record.write({'recinto_ids': recinto_vals})

        # Guardar ref_sigpac2 en sigpac_json para que el visor la cargue automáticamente
        import json as _json3
        try:
            _sj = _json3.loads(record.sigpac_json) if record.sigpac_json else {}
        except Exception:
            _sj = {}
        _sj['ref_sigpac2'] = ref2
        record.write({'sigpac_json': _json3.dumps(_sj, ensure_ascii=False, indent=2)})

        n_rec = len(recinto_vals)
        return {'ok': True, 'ref_sigpac2': ref2, 'n_recintos': n_rec, 'total_m2': round(total_m2, 0)}


