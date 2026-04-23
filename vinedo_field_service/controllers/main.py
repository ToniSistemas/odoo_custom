# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
import logging
import json as _json
import gzip as _gzip
import urllib.request as _ureq

_logger = logging.getLogger(__name__)

_SIGPAC_HEADERS = {'User-Agent': 'OdooSIGPAC/1.8', 'Accept-Encoding': 'gzip'}


# ─── Helpers de muestreo geoespacial ──────────────────────────────────────────

def _point_in_poly(x, y, polygon):
    """Ray-casting point-in-polygon test. polygon = [[lon, lat], ...]"""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _grid_points_in_poly(polygon, max_points=180):
    """Returns a list of (lon, lat) grid points inside the polygon.

    Step is derived from the shorter bbox dimension so that small parcels
    (even < 1 ha) always get several sample points.  Falls back to the
    polygon centroid when the polygon is so narrow that no grid point lands
    inside it.
    """
    lons = [p[0] for p in polygon]
    lats = [p[1] for p in polygon]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    bbox_w = max_lon - min_lon
    bbox_h = max_lat - min_lat
    if bbox_w <= 0 or bbox_h <= 0:
        return []

    # Target ~8 grid cells across the shorter dimension → guarantees points
    # even in small parcels (~50 m wide ≈ 0.00045°).
    step = min(bbox_w, bbox_h) / 8.0
    step = max(step, 0.00005)   # never below ~5 m
    step = min(step, 0.002)     # never above ~200 m

    # Shrink further if bbox would still exceed the point budget
    estimated = (bbox_w / step) * (bbox_h / step)
    if estimated > max_points * 2:
        step = ((bbox_w * bbox_h) / max_points) ** 0.5

    points = []
    lat = min_lat + step / 2
    while lat <= max_lat:
        lon = min_lon + step / 2
        while lon <= max_lon:
            if _point_in_poly(lon, lat, polygon):
                points.append((round(lon, 7), round(lat, 7)))
            lon += step
        lat += step

    # Subsample evenly if still over limit
    if len(points) > max_points:
        step_i = max(1, len(points) // max_points)
        points = points[::step_i][:max_points]

    # Fallback for very thin/tiny polygons: use the centroid
    if not points:
        cx = round(sum(lons) / len(lons), 7)
        cy = round(sum(lats) / len(lats), 7)
        points = [(cx, cy)]   # centroid is always a valid sample even if outside

    return points


def _sigpac_fetch(url, timeout=9):
    """HTTP GET to SIGPAC, handles gzip. Returns parsed JSON or None."""
    try:
        req = _ureq.Request(url, headers=_SIGPAC_HEADERS)
        with _ureq.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if raw[:2] == b'\x1f\x8b':
                raw = _gzip.decompress(raw)
            return _json.loads(raw.decode('utf-8', errors='ignore'))
    except Exception as exc:
        _logger.debug('SIGPAC fetch %s: %s', url, exc)
        return None

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
    '  data-refs-extra="__REFS_EXTRA__"'
    '  data-recintos="__RECINTOS__"'
    '  __MARKER_ATTRS__>'
    '<head>'
    '<meta charset="utf-8"/>'
    '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
    '<title>Visor SIGPAC</title>'
    # CSS externo - mismo origen - pasa CSP style-src 'self'
    '<link rel="stylesheet"'
    '  href="/vinedo_field_service/static/src/lib/leaflet/leaflet.css?v=2.2.0"/>'
    '<link rel="stylesheet"'
    '  href="/vinedo_field_service/static/src/sigpac_viewer.css?v=2.2.0"/>'
    '</head>'
    '<body>'
    '<div id="descripcion">'
    '  <strong>Visor SIGPAC</strong> &mdash;'
    '  <strong>Clic</strong> en una parcela para importarla.'
    '  &nbsp;|&nbsp; Bot&oacute;n <strong>&#9651;&nbsp;Zona</strong> (arriba derecha) para dibujar un pol&iacute;gono'
    '  y capturar autom&aacute;ticamente todos los recintos del &aacute;rea: haz clic para a&ntilde;adir v&eacute;rtices'
    '  y <strong>doble&nbsp;clic</strong> para cerrar.'
    '  &nbsp;|&nbsp; Activa la capa <em>Recintos&nbsp;SIGPAC</em> para ver los l&iacute;mites.'
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
    '<script src="/vinedo_field_service/static/src/lib/leaflet/leaflet.js?v=2.2.0"></script>'
    '<script src="/vinedo_field_service/static/src/sigpac_viewer.js?v=2.2.0"></script>'
    '</body>'
    '</html>'
)


def _render_viewer(rec_id, lat, lon, zoom, marker_attrs, ref_sigpac='', recintos_json='[]', refs_extra='[]'):
    """Sustituye los marcadores __PLACEHOLDER__ en el template HTML."""
    import html as _html
    return (
        _VIEWER_HTML
        .replace('__REC_ID__',       str(rec_id))
        .replace('__LAT__',          str(lat))
        .replace('__LON__',          str(lon))
        .replace('__ZOOM__',         str(zoom))
        .replace('__MARKER_ATTRS__', marker_attrs)
        .replace('__REF_SIGPAC__',   _html.escape(ref_sigpac,    quote=True))
        .replace('__REFS_EXTRA__',   _html.escape(refs_extra,    quote=True))
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
        # Construir array JSON de parcelas extra [{ref, offset}] desde refs_sigpac_extra
        refs_extra = '[]'
        if record.refs_sigpac_extra:
            extra_list = [r.strip() for r in record.refs_sigpac_extra.strip().splitlines() if r.strip()]
            refs_extra = _json.dumps([
                {'ref': ref, 'offset': (i + 1) * 1000}
                for i, ref in enumerate(extra_list)
            ])

        html_content = _render_viewer(rec_id, lat, lon, zoom, marker_attrs, ref_sigpac, recintos_json, refs_extra)
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

        # Añadir ref2 a refs_sigpac_extra (una por línea, preservando las anteriores)
        existing_extra = record.refs_sigpac_extra or ''
        extra_lines = [r.strip() for r in existing_extra.strip().splitlines() if r.strip()]
        extra_lines.append(ref2)
        record.write({
            'recinto_ids': recinto_vals,
            'refs_sigpac_extra': '\n'.join(extra_lines),
        })

        n_rec = len(recinto_vals)
        return {'ok': True, 'ref_sigpac2': ref2, 'n_recintos': n_rec, 'total_m2': round(total_m2, 0)}

    # ── Nuevas rutas: dibujo de zona ──────────────────────────────────────────

    @http.route('/vinedo/sigpac_detectar_zona', type='jsonrpc', auth='user', csrf=False)
    def sigpac_detectar_zona(self, polygon, **kwargs):
        """Detecta todos los recintos SIGPAC dentro de un polígono dibujado por el usuario.

        polygon: lista de [lon, lat] representando los vértices del polígono.
        Devuelve: {parcelas: [{ref, recintos: [{recinto_num, uso_sigpac, superficie_ha}]}],
                   total_recintos: N}
        No escribe nada en la base de datos.
        """
        import concurrent.futures

        if not polygon or len(polygon) < 3:
            return {'error': 'El polígono debe tener al menos 3 vértices.'}

        # 1. Generar cuadrícula de puntos dentro del polígono
        points = _grid_points_in_poly(polygon, max_points=180)
        if not points:
            return {'error': 'No se pudieron generar puntos de muestreo en la zona dibujada.'}

        # 2. Consultar SIGPAC en paralelo para cada punto → recoger parcelas únicas
        parcela_map = {}   # ref → primer dict de datos devuelto por SIGPAC

        def _query_point(lonlat):
            lon, lat = lonlat
            url = (
                'https://sigpac-hubcloud.es/servicioconsultassigpac'
                f'/query/recinfobypoint/4326/{lon:.7f}/{lat:.7f}.json'
            )
            arr = _sigpac_fetch(url, timeout=9)
            if isinstance(arr, list) and arr:
                p = arr[0]
                agr = str(p.get('agregado', 0) or 0)
                zon = str(p.get('zona',     0) or 0)
                ref = (f"{p.get('provincia','')}:{p.get('municipio','')}:"
                       f"{agr}:{zon}:{p.get('poligono','')}:{p.get('parcela','')}")
                return ref, p
            return None, None

        with concurrent.futures.ThreadPoolExecutor(max_workers=14) as ex:
            futures = [ex.submit(_query_point, pt) for pt in points]
            for fut in concurrent.futures.as_completed(futures):
                ref, data = fut.result()
                if ref and ref not in parcela_map:
                    parcela_map[ref] = data

        if not parcela_map:
            return {'parcelas': [], 'total_recintos': 0}

        # 3. Para cada parcela única, obtener todos sus recintos en paralelo
        def _fetch_recintos(ref_data):
            ref, p = ref_data
            prov = str(p.get('provincia', ''))
            mun  = str(p.get('municipio', ''))
            agr  = str(p.get('agregado', 0) or 0)
            zon  = str(p.get('zona',     0) or 0)
            pol  = str(p.get('poligono', ''))
            par  = str(p.get('parcela',  ''))
            url  = (
                'https://sigpac-hubcloud.es/servicioconsultassigpac'
                f'/query/recinfoparc/{prov}/{mun}/{agr}/{zon}/{pol}/{par}.json'
            )
            arr = _sigpac_fetch(url, timeout=12)
            if isinstance(arr, list) and arr:
                recintos = [
                    {
                        'recinto_num':  int(r.get('recinto', 0)),
                        'uso_sigpac':   r.get('uso_sigpac', '?'),
                        'superficie_ha': round(float(r.get('superficie', 0) or 0), 4),
                    }
                    for r in arr if r.get('recinto')
                ]
            else:
                # Fallback: usar el único recinto del punto de muestreo
                recintos = [{
                    'recinto_num':  int(p.get('recinto', 0)),
                    'uso_sigpac':   p.get('uso_sigpac', '?'),
                    'superficie_ha': round(float(p.get('superficie', 0) or 0), 4),
                }]
            return {'ref': ref, 'recintos': recintos}

        parcelas_result = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(_fetch_recintos, item) for item in parcela_map.items()]
            for fut in concurrent.futures.as_completed(futures):
                parcelas_result.append(fut.result())

        total_recintos = sum(len(p['recintos']) for p in parcelas_result)
        return {'parcelas': parcelas_result, 'total_recintos': total_recintos}

    @http.route('/vinedo/sigpac_importar_zona', type='jsonrpc', auth='user', csrf=False)
    def sigpac_importar_zona(self, rec_id, parcelas, modo='agregar', **kwargs):
        """Importa los recintos detectados por sigpac_detectar_zona a la finca.

        parcelas: lista de {ref, recintos: [{recinto_num, uso_sigpac, superficie_ha}]}
        modo: 'reemplazar' elimina todos los recintos existentes primero;
              'agregar'    añade los nuevos con offset para no colisionar.
        """
        record = request.env['vinedo.finca'].browse(int(rec_id))
        if not record.exists():
            return {'error': 'Finca no encontrada'}
        if not parcelas:
            return {'error': 'No se recibieron parcelas para importar.'}

        try:
            recinto_vals = []

            if modo == 'reemplazar':
                recinto_vals.append((5, 0, 0))   # borrar todos los existentes
                # Parcela 0 → sin offset; parcelas 1..N → offsets 1000, 2000, ...
                offsets = [i * 1000 for i in range(len(parcelas))]
            else:
                # Calcular offset base desde los recintos existentes
                existing_nums = record.recinto_ids.mapped('recinto_num')
                base = (max(existing_nums) // 1000 + 1) * 1000 if existing_nums else 1000
                offsets = [base + i * 1000 for i in range(len(parcelas))]

            total_recintos = 0
            refs_nuevas = []

            for i, parcela in enumerate(parcelas):
                offset = offsets[i]
                ref = parcela.get('ref', '')
                for r in parcela.get('recintos', []):
                    rnum = int(r.get('recinto_num', 0))
                    if not rnum:
                        continue
                    recinto_vals.append((0, 0, {
                        'recinto_num':  offset + rnum,
                        'uso_sigpac':   r.get('uso_sigpac', '?'),
                        'superficie_ha': round(float(r.get('superficie_ha', 0)), 4),
                        'activo': True,
                    }))
                    total_recintos += 1
                if ref:
                    refs_nuevas.append(ref)

            if not total_recintos:
                return {'error': 'No hay recintos válidos para importar.'}

            write_vals = {'recinto_ids': recinto_vals}

            if modo == 'reemplazar':
                write_vals['ref_sigpac'] = refs_nuevas[0] if refs_nuevas else ''
                extra = refs_nuevas[1:] if len(refs_nuevas) > 1 else []
                write_vals['refs_sigpac_extra'] = '\n'.join(extra) or False
            else:
                existing_extra = record.refs_sigpac_extra or ''
                extra_lines = [l.strip() for l in existing_extra.splitlines() if l.strip()]
                extra_lines.extend(refs_nuevas)
                write_vals['refs_sigpac_extra'] = '\n'.join(extra_lines) or False

            record.write(write_vals)
            return {'ok': True, 'n_parcelas': len(parcelas), 'n_recintos': total_recintos}

        except Exception as exc:
            _logger.exception('sigpac_importar_zona rec_id=%s', rec_id)
            return {'error': str(exc)}

