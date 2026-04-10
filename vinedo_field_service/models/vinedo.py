from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import json
import logging

_logger = logging.getLogger(__name__)


class Territorio(models.Model):
    _name = 'vinedo.territorio'
    _description = 'Territorio/Región'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True, index=True)


class Variedad(models.Model):
    _name = 'vinedo.variedad'
    _description = 'Variedad de uva'
    _order = 'name'

    name = fields.Char(string='Variedad', required=True, index=True)
    descripcion = fields.Text(string='Descripción')


class Finca(models.Model):
    _name = 'vinedo.finca'
    _description = 'Finca / Parcela'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True, index=True)
    territory_id = fields.Many2one('vinedo.territorio', string='Territorio', index=True)
    area = fields.Float(string='Extensión (ha)')
    latitude = fields.Float(string='Latitud', digits=(10, 7))
    longitude = fields.Float(string='Longitud', digits=(10, 7))
    gmap_url = fields.Char(string='Google Maps', compute='_compute_map_urls')
    osm_url = fields.Char(string='OpenStreetMap', compute='_compute_map_urls')
    map_embed = fields.Html(string='Mapa OSM', compute='_compute_map_urls', sanitize=False)
    ref_sigpac = fields.Char(string='Referencia SIGPAC', index=True, help='Prov-Municipio-Polígono-Parcela-Recinto')
    ref_catastral = fields.Char(string='Referencia Catastral', index=True, help='Obtenida de SIGPAC')
    sigpac_json = fields.Text(string='Datos SIGPAC', readonly=True)
    sigpac_info = fields.Html(string='SIGPAC', compute='_compute_sigpac_info', sanitize=False)
    variedad_ids = fields.One2many('vinedo.plantacion', 'finca_id', string='Variedades plantadas')
    aportacion_ids = fields.One2many('vinedo.aportacion', 'finca_id', string='Aportaciones de minerales')
    tratamiento_ids = fields.One2many('vinedo.tratamiento', 'finca_id', string='Tratamientos')
    poda_ids = fields.One2many('vinedo.poda', 'finca_id', string='Podas')
    trabajo_ids = fields.One2many('vinedo.trabajo', 'finca_id', string='Trabajos')
    anada_ids = fields.One2many('vinedo.anada', 'finca_id', string='Añadas')

    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        """Validate GPS coordinates range"""
        for rec in self:
            if rec.latitude and not (-90 <= rec.latitude <= 90):
                raise ValidationError(_('Latitud debe estar entre -90 y 90 grados.'))
            if rec.longitude and not (-180 <= rec.longitude <= 180):
                raise ValidationError(_('Longitud debe estar entre -180 y 180 grados.'))

    @api.depends('latitude', 'longitude')
    def _compute_map_urls(self):
        for rec in self:
            if rec.latitude and rec.longitude:
                lat, lon = rec.latitude, rec.longitude
                rec.gmap_url = f'https://www.google.com/maps?q={lat},{lon}'
                rec.osm_url = f'https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=15/{lat}/{lon}'
                rec.map_embed = (
                    f'<iframe src="https://www.openstreetmap.org/export/embed.html'
                    f'?bbox={lon-0.01},{lat-0.01},{lon+0.01},{lat+0.01}'
                    f'&amp;layer=mapnik&amp;marker={lat},{lon}"'
                    f' style="width:100%;height:380px;border:1px solid #ccc;border-radius:4px;"'
                    f' frameborder="0" scrolling="no"></iframe>'
                    f'<p style="margin-top:6px;">'
                    f'<a href="https://www.openstreetmap.org/?mlat={lat}&amp;mlon={lon}#map=15/{lat}/{lon}" target="_blank">Ver mapa completo</a>'
                    f' &nbsp;|&nbsp; '
                    f'<a href="https://www.google.com/maps?q={lat},{lon}" target="_blank">Abrir en Google Maps</a>'
                    f'</p>'
                )
            else:
                rec.gmap_url = False
                rec.osm_url = False
                rec.map_embed = (
                    '<div style="padding:12px;background:#e8f4fc;border:1px solid #bee5eb;border-radius:4px;">'
                    '<strong>Sin coordenadas.</strong> Rellena los campos Latitud y Longitud para ver el mapa.'
                    '</div>'
                )

    @api.depends('sigpac_json', 'latitude', 'longitude')
    def _compute_sigpac_info(self):
        USO_LABELS = {
            'VI': 'Viñedo', 'TA': 'Tierra Arable', 'OV': 'Olivar', 'FO': 'Forestal',
            'PA': 'Pasto Arbolado', 'PR': 'Prado o Pradera', 'IM': 'Improductivo',
            'AG': 'Agua', 'CA': 'Vial', 'ZU': 'Zona Urbana', 'FF': 'Frutos Secos',
            'CF': 'Cítricos', 'EP': 'Elemento Paisaje', 'PS': 'Pastos',
            'FV': 'Frutales Varios', 'FL': 'Flores/Ornamentales', 'ZC': 'Zona Concentrada',
            # Catastro cultivo codes
            'OL': 'Olivar', 'FP': 'Frutales Pepita', 'FH': 'Frutales Hueso',
            'FS': 'Frutos Secos', 'CT': 'Citrus', 'VN': 'Viñedo (VN)',
            'HU': 'Huerta', 'FL2': 'Flores', 'ME': 'Matorral', 'PI': 'Pinar',
            'MT': 'Monte alto', 'RO': 'Repoblación', 'ED': 'Edificio',
        }
        for rec in self:
            osm_html = ''
            if rec.latitude and rec.longitude:
                lat, lon = rec.latitude, rec.longitude
                osm_html = (
                    f'<iframe src="https://www.openstreetmap.org/export/embed.html'
                    f'?bbox={lon-0.005},{lat-0.005},{lon+0.005},{lat+0.005}'
                    f'&amp;layer=mapnik&amp;marker={lat},{lon}"'
                    f' style="width:100%;height:220px;border:1px solid #ccc;border-radius:4px;margin-top:8px;"'
                    f' frameborder="0" scrolling="no"></iframe>'
                )

            if not rec.sigpac_json:
                if rec.latitude and rec.longitude:
                    visor = (
                        f'https://sigpac.mapa.es/fega/visor/'
                        f'#lat={rec.latitude}&lng={rec.longitude}&zoom=17'
                    )
                    rec.sigpac_info = (
                        '<div style="padding:10px;background:#e8f4fc;border:1px solid #bee5eb;border-radius:6px;margin-bottom:8px;">'
                        f'<a href="{visor}" target="_blank">&#128506; Ver en visor SIGPAC</a>'
                        '<span style="font-size:12px;color:#6c757d;margin-left:10px;">'
                        'Pulsa <strong>«Consultar SIGPAC»</strong> para capturar datos automáticamente, '
                        'o introduce la Ref. Catastral y pulsa <strong>«Buscar por Ref. Catastral»</strong>.'
                        '</span></div>'
                        + osm_html
                    )
                else:
                    rec.sigpac_info = (
                        '<div style="padding:12px;background:#fff3cd;border:1px solid #ffc107;border-radius:4px;">'
                        '<strong>Sin coordenadas.</strong> Introduce Latitud/Longitud para consultar SIGPAC, '
                        'o escribe la Ref. Catastral y pulsa <strong>«Buscar por Ref. Catastral»</strong>.'
                        '</div>'
                    )
                continue

            try:
                data = json.loads(rec.sigpac_json)
            except Exception:
                rec.sigpac_info = '<div>Error leyendo datos SIGPAC.</div>'
                continue

            ref = data.get('ref_sigpac', '')
            ref_cat = data.get('ref_catastral', '')
            prov = data.get('provincia', '')
            mun = data.get('municipio', '')
            pol = data.get('poligono', '')
            par = data.get('parcela', '')
            recintos = data.get('recintos', [])
            source = data.get('source', 'sigpac')
            descripcion = data.get('descripcion', '')

            # Agrupar superficie por uso
            from collections import defaultdict
            uso_totals = defaultdict(float)
            for r in recintos:
                uso_totals[r.get('uso', '?')] += r.get('superficie', 0)
            if not uso_totals:
                uso_totals[data.get('uso_principal', '?')] = data.get('superficie_principal_m2', 0)
            total_m2 = sum(uso_totals.values())

            rows = ''
            for uso_code, m2 in sorted(uso_totals.items()):
                label = USO_LABELS.get(uso_code, uso_code)
                ha = m2 / 10000
                pct = (m2 / total_m2 * 100) if total_m2 else 0
                color = '#28a745' if uso_code == 'VI' else '#6c757d'
                rows += (
                    f'<tr>'
                    f'<td style="padding:5px 8px;">'
                    f'<span style="background:{color};color:#fff;padding:2px 6px;border-radius:3px;font-size:11px;">{uso_code}</span>'
                    f' {label}</td>'
                    f'<td style="text-align:right;padding:5px 8px;">{m2:,.0f}</td>'
                    f'<td style="text-align:right;padding:5px 8px;">{ha:.4f}</td>'
                    f'<td style="text-align:right;padding:5px 8px;">{pct:.1f}%</td>'
                    f'</tr>'
                )
            rows += (
                f'<tr style="font-weight:bold;border-top:2px solid #dee2e6;">'
                f'<td style="padding:5px 8px;">TOTAL</td>'
                f'<td style="text-align:right;padding:5px 8px;">{total_m2:,.0f}</td>'
                f'<td style="text-align:right;padding:5px 8px;">{total_m2/10000:.4f}</td>'
                f'<td style="text-align:right;padding:5px 8px;">100%</td>'
                f'</tr>'
            )

            if data.get('sigpac_status') == 'unavailable':
                rows = (
                    '<tr><td colspan="4" style="padding:10px;color:#856404;background:#fff3cd;'
                    'border-radius:4px;text-align:center;">'
                    '&#9888; SIGPAC en mantenimiento (campaña 2026). '
                    'Pulsa <strong>«Consultar SIGPAC»</strong> cuando el servicio vuelva.'
                    '</td></tr>'
                )

            visor = (
                f'https://sigpac.mapa.es/fega/visor/#lat={rec.latitude}&lng={rec.longitude}&zoom=17'
                if rec.latitude else '#'
            )

            if source == 'catastro':
                # Header for catastro-sourced data
                url_ficha = f'https://www1.sedecatastro.gob.es/OVCFrames.aspx?TIPO=CONSULTA&rc={ref_cat}'
                header_html = (
                    '<div style="padding:10px;background:#f8f9fa;border:1px solid #dee2e6;border-radius:6px;">'
                    f'<p style="margin:0 0 6px 0;font-size:13px;">'
                    f'<strong>Catastro:</strong> <code>{ref_cat}</code>'
                    + (f'&nbsp;&nbsp;<em style="color:#6c757d;font-size:12px;">{descripcion}</em>' if descripcion else '')
                    + '</p>'
                    f'<a href="{url_ficha}" target="_blank" style="display:inline-block;padding:5px 10px;'
                    f'background:#fff;border:1px solid #dee2e6;border-radius:4px;'
                    f'text-decoration:none;color:#495057;font-size:12px;">&#128196; Ficha catastral</a>'
                    + (f'&nbsp;&nbsp;<a href="{visor}" target="_blank" style="display:inline-block;padding:5px 10px;'
                    f'background:#fff;border:1px solid #dee2e6;border-radius:4px;'
                    f'text-decoration:none;color:#495057;font-size:12px;">&#128506; Visor SIGPAC</a>' if rec.latitude else '')
                    + '</div>'
                )
            else:
                cat_html = f'&nbsp;&nbsp;<strong>Cat:</strong> <code>{ref_cat}</code>' if ref_cat else ''
                header_html = (
                    '<div style="padding:10px;background:#f8f9fa;border:1px solid #dee2e6;border-radius:6px;">'
                    f'<p style="margin:0 0 6px 0;font-size:13px;">'
                    f'<strong>SIGPAC:</strong> <code>{ref}</code>'
                    f'&nbsp;&nbsp;Prov.{prov} Mun.{mun} Pol.{pol} Par.{par}'
                    f'{cat_html}</p>'
                    f'<a href="{visor}" target="_blank" style="display:inline-block;padding:5px 10px;'
                    f'background:#fff;border:1px solid #dee2e6;border-radius:4px;'
                    f'text-decoration:none;color:#495057;font-size:12px;">&#128506; Ver en visor SIGPAC</a>'
                    '</div>'
                )
                header_html = (
                    '<div style="padding:10px;background:#f8f9fa;border:1px solid #dee2e6;border-radius:6px;">'
                    f'<p style="margin:0 0 6px 0;font-size:13px;">'
                    f'<strong>SIGPAC:</strong> <code>{ref}</code>'
                    f'&nbsp;&nbsp;Prov.{prov} Mun.{mun} Pol.{pol} Par.{par}'
                    f'{cat_html}</p>'
                    f'<a href="{visor}" target="_blank" style="display:inline-block;padding:5px 10px;'
                    f'background:#fff;border:1px solid #dee2e6;border-radius:4px;'
                    f'text-decoration:none;color:#495057;font-size:12px;">&#128506; Ver en visor SIGPAC</a>'
                    '</div>'
                )

            rec.sigpac_info = (
                header_html
                + '<table style="width:100%;border-collapse:collapse;margin-top:8px;font-size:13px;">'
                '<thead><tr style="background:#e9ecef;">'
                '<th style="text-align:left;padding:6px 8px;">Uso</th>'
                '<th style="text-align:right;padding:6px 8px;">m²</th>'
                '<th style="text-align:right;padding:6px 8px;">ha</th>'
                '<th style="text-align:right;padding:6px 8px;">%</th>'
                '</tr></thead>'
                f'<tbody>{rows}</tbody>'
                '</table>'
                + osm_html
            )

    def action_consultar_sigpac(self):
        """Consulta la API de SIGPAC para obtener referencia y superficies por uso."""
        self.ensure_one()
        if not self.latitude or not self.longitude:
            raise UserError(_('Introduce la Latitud y Longitud antes de consultar SIGPAC.'))
        import requests
        lat, lon = self.latitude, self.longitude

        # Paso 1: recinto en las coordenadas
        url1 = f'https://sigpac.mapa.es/fega/serviciosvisorsigpac/query/recintos/{lon}/{lat}'
        try:
            resp1 = requests.get(url1, timeout=15)
            resp1.raise_for_status()
            geo1 = resp1.json()
        except Exception as e:
            raise UserError(_('Error al conectar con SIGPAC: %s') % str(e))

        if geo1.get('error') and 'recintos_temp' in str(geo1.get('error', '')):
            raise UserError(_(
                'SIGPAC está actualizando los datos de la campaña 2026 (mantenimiento temporal).\n'
                'El servicio volverá a estar disponible en breve. Inténtalo de nuevo más tarde.'
            ))

        features = geo1.get('features', [])
        if not features:
            raise UserError(_(
                'No se encontró ningún recinto SIGPAC en esas coordenadas.\n'
                'Prueba a ajustar ligeramente la posición GPS.'
            ))

        props = features[0].get('properties', {})
        prov = str(props.get('provincia', ''))
        mun = str(props.get('municipio', ''))
        pol = str(props.get('poligono', ''))
        par = str(props.get('parcela', ''))
        rec_num = str(props.get('recinto', ''))
        uso_principal = props.get('dn_uso', props.get('uso', ''))
        sfc_principal = float(props.get('dn_surface', props.get('superficie', 0)) or 0)
        ref_catastral = str(props.get('referencia_catastral', props.get('ref_catastral', '')) or '')
        ref_sigpac = f'{prov}-{mun}-{pol}-{par}-{rec_num}'

        # Paso 2: todos los recintos de la parcela
        all_recintos = []
        try:
            url2 = (
                f'https://sigpac.mapa.es/fega/serviciosvisorsigpac/query/recintos/'
                f'{prov}/{mun}/{pol}/{par}'
            )
            resp2 = requests.get(url2, timeout=15)
            if resp2.status_code == 200:
                for f2 in resp2.json().get('features', []):
                    p = f2.get('properties', {})
                    all_recintos.append({
                        'recinto': str(p.get('recinto', '')),
                        'uso': p.get('dn_uso', p.get('uso', '?')),
                        'superficie': float(p.get('dn_surface', p.get('superficie', 0)) or 0),
                    })
        except Exception as e:
            _logger.warning('SIGPAC: no se pudieron cargar todos los recintos de la parcela: %s', e)

        summary = {
            'ref_sigpac': ref_sigpac,
            'ref_catastral': ref_catastral,
            'provincia': prov,
            'municipio': mun,
            'poligono': pol,
            'parcela': par,
            'recinto_principal': rec_num,
            'uso_principal': uso_principal,
            'superficie_principal_m2': sfc_principal,
            'recintos': all_recintos,
        }
        vals = {
            'ref_sigpac': ref_sigpac,
            'sigpac_json': json.dumps(summary, ensure_ascii=False, indent=2),
        }
        if ref_catastral:
            vals['ref_catastral'] = ref_catastral
        self.write(vals)

        total_m2 = sum(r['superficie'] for r in all_recintos) or sfc_principal
        n_rec = len(all_recintos)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SIGPAC actualizado'),
                'message': _('Ref: %s | %d recinto(s) | %.0f m²') % (ref_sigpac, n_rec, total_m2),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_consultar_por_catastral(self):
        """Busca la parcela en SIGPAC usando query/parrefcat (el mismo endpoint que el visor oficial),
        calcula el centroide del polígono y luego llama a action_consultar_sigpac."""
        self.ensure_one()
        if not self.ref_catastral:
            raise UserError(_('Escribe la Referencia Catastral antes de consultar.'))
        import requests

        ref = self.ref_catastral.strip().replace(' ', '').upper()
        if len(ref) != 20:
            raise UserError(_('La referencia catastral debe tener 20 caracteres. Recibida: "%s"') % ref)

        prov = int(ref[0:2])
        mun  = int(ref[2:5])

        # Endpoint usado internamente por el visor oficial de SIGPAC
        url = (
            f'https://sigpac.mapa.es/fega/serviciosvisorsigpac/query/parrefcat/'
            f'{prov}/{mun}/{ref}'
        )
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            geo = r.json()
        except Exception as e:
            raise UserError(_('Error al conectar con SIGPAC: %s') % str(e))

        features = geo.get('features', [])
        if not features:
            raise UserError(_(
                'No se encontró la referencia catastral "%s" en SIGPAC.\n'
                'Comprueba que la referencia es correcta.'
            ) % ref)

        # Calcular centroide del polígono
        coords_flat = []
        def _collect(obj):
            t = obj.get('type', '')
            c = obj.get('coordinates', [])
            if t == 'Point':
                coords_flat.append(c)
            elif t in ('MultiPoint', 'LineString'):
                coords_flat.extend(c)
            elif t in ('MultiLineString', 'Polygon'):
                for ring in c:
                    coords_flat.extend(ring)
            elif t == 'MultiPolygon':
                for poly in c:
                    for ring in poly:
                        coords_flat.extend(ring)
            elif t == 'GeometryCollection':
                for g in obj.get('geometries', []):
                    _collect(g)

        for feat in features:
            _collect(feat.get('geometry', {}) or {})

        if not coords_flat:
            raise UserError(_('SIGPAC devolvió la parcela pero sin geometría. Introduce las coordenadas manualmente.'))

        lon = round(sum(c[0] for c in coords_flat) / len(coords_flat), 7)
        lat = round(sum(c[1] for c in coords_flat) / len(coords_flat), 7)
        _logger.info('SIGPAC parrefcat centroid for %s: lon=%s lat=%s', ref, lon, lat)

        vals = {'ref_catastral': ref}
        if not self.latitude:
            vals['latitude'] = lat
        if not self.longitude:
            vals['longitude'] = lon
        self.write(vals)

        return self.action_consultar_sigpac()

    def action_importar_superficie_sigpac(self):
        """Copia la superficie total SIGPAC al campo Extensión (ha)."""
        self.ensure_one()
        if not self.sigpac_json:
            raise UserError(_('Primero consulta SIGPAC para obtener la superficie.'))
        data = json.loads(self.sigpac_json)
        recintos = data.get('recintos', [])
        total_m2 = sum(r.get('superficie', 0) for r in recintos) or data.get('superficie_principal_m2', 0)
        if not total_m2:
            raise UserError(_('No se encontró superficie en los datos SIGPAC guardados.'))
        ha = round(total_m2 / 10000.0, 4)
        self.area = ha
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Superficie importada'),
                'message': _('%.0f m² → %.4f ha') % (total_m2, ha),
                'type': 'success',
                'sticky': False,
            },
        }


class Plantacion(models.Model):
    _name = 'vinedo.plantacion'
    _description = 'Plantación por variedad en finca'
    _order = 'finca_id, variedad_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    variedad_id = fields.Many2one('vinedo.variedad', string='Variedad', required=True, index=True)
    fecha_plantacion = fields.Date(string='Fecha de plantación')
    superficie = fields.Float(string='Superficie (ha)', digits=(10, 2))

    @api.constrains('finca_id', 'variedad_id')
    def _check_unique_finca_variedad(self):
        """Ensure unique combination of finca and variedad"""
        for rec in self:
            if rec.finca_id and rec.variedad_id:
                existing = self.search([
                    ('finca_id', '=', rec.finca_id.id),
                    ('variedad_id', '=', rec.variedad_id.id),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_('Ya existe esta variedad en esta finca. Use el registro existente para actualizar datos.'))


class Anada(models.Model):
    _name = 'vinedo.anada'
    _description = 'Añada / Cosecha por variedad'
    _order = 'anio desc, finca_id, variedad_id'

    name = fields.Char(string='Nombre', compute='_compute_name', store=True, index=True)
    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, index=True)
    variedad_id = fields.Many2one('vinedo.variedad', string='Variedad', required=True, index=True)
    anio = fields.Integer(string='Año', required=True, default=lambda self: fields.Date.today().year)
    graduacion = fields.Float(string='Graduación alcohólica (%vol)', digits=(5, 2))
    acidez = fields.Float(string='Acidez (g/L)', digits=(5, 2))
    cantidad = fields.Float(string='Cantidad recolectada (kg)', digits=(12, 2))

    @api.depends('finca_id', 'variedad_id', 'anio')
    def _compute_name(self):
        """Auto-generate name from components"""
        for rec in self:
            parts = []
            if rec.anio:
                parts.append(str(rec.anio))
            if rec.finca_id:
                parts.append(rec.finca_id.name)
            if rec.variedad_id:
                parts.append(rec.variedad_id.name)
            rec.name = ' - '.join(parts) if parts else _('Nueva Añada')

    @api.constrains('finca_id', 'variedad_id', 'anio')
    def _check_unique_finca_variedad_anio(self):
        """Ensure unique combination of finca, variedad and year"""
        for rec in self:
            if rec.finca_id and rec.variedad_id and rec.anio:
                existing = self.search([
                    ('finca_id', '=', rec.finca_id.id),
                    ('variedad_id', '=', rec.variedad_id.id),
                    ('anio', '=', rec.anio),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_('Ya existe una añada para esta combinación de finca, variedad y año.'))


class Aportacion(models.Model):
    _name = 'vinedo.aportacion'
    _description = 'Aportación de minerales'
    _order = 'fecha desc, finca_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    fecha = fields.Date(string='Fecha', default=fields.Date.today, required=True)
    descripcion = fields.Text(string='Descripción')
    producto = fields.Char(string='Producto/Mineral', required=True)
    cantidad = fields.Float(string='Cantidad (kg)', digits=(10, 2))


class Tratamiento(models.Model):
    _name = 'vinedo.tratamiento'
    _description = 'Tratamiento (fitosanitario u otros)'
    _order = 'fecha desc, finca_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    tipo = fields.Selection([('fitosanitario', 'Fitosanitario'), ('otro', 'Otro')], 
                           string='Tipo', default='fitosanitario', required=True)
    fecha = fields.Date(string='Fecha', default=fields.Date.today, required=True, index=True)
    producto = fields.Char(string='Producto', required=True)
    dosis = fields.Char(string='Dosis / Observaciones')
    empleado_id = fields.Many2one('hr.employee', string='Empleado', index=True)


class Poda(models.Model):
    _name = 'vinedo.poda'
    _description = 'Registro de podas'
    _order = 'fecha desc, finca_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    fecha = fields.Date(string='Fecha', default=fields.Date.today, required=True, index=True)
    tipo_poda = fields.Selection([('invierno', 'Poda de invierno'), ('verde', 'Poda en verde')],
                                 string='Tipo de poda')
    descripcion = fields.Text(string='Descripción')
    empleado_id = fields.Many2one('hr.employee', string='Empleado', index=True)


class Trabajo(models.Model):
    _name = 'vinedo.trabajo'
    _description = 'Trabajo realizado en finca'
    _order = 'fecha desc, finca_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    fecha = fields.Date(string='Fecha', default=fields.Date.today, required=True, index=True)
    empleado_id = fields.Many2one('hr.employee', string='Empleado', index=True)
    tipo_trabajo = fields.Char(string='Trabajo realizado', required=True)
    horas = fields.Float(string='Horas', digits=(5, 2))
    observaciones = fields.Text(string='Observaciones')
