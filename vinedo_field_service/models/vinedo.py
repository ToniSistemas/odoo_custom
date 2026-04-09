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
    polygon = fields.Text(string='Polígono (GeoJSON Feature)', help='Almacena GeoJSON Feature con coordenadas del polígono')
    gmap_url = fields.Char(string='Google Maps', compute='_compute_map_urls')
    osm_url = fields.Char(string='OpenStreetMap', compute='_compute_map_urls')
    map_embed = fields.Html(string='Mapa OSM', compute='_compute_map_urls', sanitize=False)
    ref_catastral = fields.Char(string='Referencia Catastral', index=True)
    catastro_superficie = fields.Float(string='Superficie Catastral (m²)', digits=(10, 2))
    catastro_embed = fields.Html(string='Mapa Catastro', compute='_compute_catastro_embed', sanitize=False)
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

    @api.depends('latitude', 'longitude', 'ref_catastral')
    def _compute_catastro_embed(self):
        base = 'https://www1.sedecatastro.gob.es'
        for rec in self:
            if rec.ref_catastral:
                ref = rec.ref_catastral.strip()
                src = f'{base}/Cartografia/mapa.aspx?pest=rc&final=&rc={ref}&del=&mun='
                ficha = f'{base}/OVCFrames.aspx?TIPO=CONSULTA&rc={ref}'
                rec.catastro_embed = (
                    '<iframe src="' + src + '" style="width:100%;height:440px;border:1px solid #ccc;border-radius:4px;"'
                    ' frameborder="0"></iframe>'
                    '<p style="margin-top:6px;">'
                    f'<strong>Ref:</strong> {ref} &nbsp;|&nbsp; '
                    f'<a href="{ficha}" target="_blank">Ver ficha completa</a>'
                    '</p>'
                )
            elif rec.latitude and rec.longitude:
                src = (
                    f'{base}/Cartografia/mapa.aspx?pest=coordenadas&from=OVCBusqueda'
                    f'&final=&ZV=NO&ZR=NO&anyoZV=&tematicos=&anyotem=&historica='
                    f'&coordinadas={rec.latitude},{rec.longitude}'
                )
                rec.catastro_embed = (
                    '<iframe src="' + src + '" style="width:100%;height:440px;border:1px solid #ccc;border-radius:4px;"'
                    ' frameborder="0"></iframe>'
                    '<p style="margin-top:6px;">'
                    '<a href="' + src + '" target="_blank">Abrir Catastro en nueva pestaña</a> &mdash; '
                    'Haz clic en la parcela del mapa y pulsa <strong>«Consultar Catastro»</strong> para guardar la referencia.'
                    '</p>'
                )
            else:
                rec.catastro_embed = (
                    '<div style="padding:12px;background:#fff3cd;border:1px solid #ffc107;border-radius:4px;">'
                    '<strong>Sin coordenadas.</strong> Introduce Latitud y Longitud para ver el Catastro.'
                    '</div>'
                )

    def action_consultar_catastro(self):
        """Consulta la API del Catastro por coordenadas GPS para obtener referencia y superficie."""
        self.ensure_one()
        if not self.latitude or not self.longitude:
            raise UserError(_('Introduce la Latitud y Longitud antes de consultar el Catastro.'))
        try:
            import requests
            import xml.etree.ElementTree as ET
            url = 'https://ovc.catastro.meh.es/ovcservweb/OVCSWDataAccessDistrib/OVCCOORDENADAS.asmx/Consulta_RCCOOR'
            resp = requests.get(url, params={
                'SRS': 'EPSG:4326',
                'Coordenada_X': self.longitude,
                'Coordenada_Y': self.latitude,
            }, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            ns = root.tag.split('}')[0].lstrip('{') if '}' in root.tag else ''
            tag = lambda t: f'{{{ns}}}{t}' if ns else t
            pc1_el = root.find(f'.//{tag("pc1")}')
            pc2_el = root.find(f'.//{tag("pc2")}')
            if pc1_el is None or pc2_el is None:
                raise UserError(_('No se encontró ninguna parcela catastral en esas coordenadas.\nPrueba a ajustar la posición GPS.'))
            ref = (pc1_el.text or '').strip() + (pc2_el.text or '').strip()
        except UserError:
            raise
        except Exception as e:
            raise UserError(_('Error al conectar con el Catastro: %s') % str(e))

        # Obtener superficie de la parcela
        sfc = 0.0
        try:
            url2 = 'https://ovc.catastro.meh.es/ovcservweb/OVCSWDataAccessDistrib/OVCCOORDENADAS.asmx/Consulta_DNPRC'
            resp2 = requests.get(url2, params={'Provincia': '', 'Municipio': '', 'RC': ref}, timeout=15)
            if resp2.status_code == 200:
                root2 = ET.fromstring(resp2.content)
                ns2 = root2.tag.split('}')[0].lstrip('{') if '}' in root2.tag else ''
                tag2 = lambda t: f'{{{ns2}}}{t}' if ns2 else t
                sfc_el = root2.find(f'.//{tag2("sfc")}')
                if sfc_el is not None and sfc_el.text:
                    sfc = float(sfc_el.text.replace(',', '.'))
        except Exception as e:
            _logger.warning('No se pudo obtener superficie catastral para %s: %s', ref, e)

        self.write({'ref_catastral': ref, 'catastro_superficie': sfc})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Catastro actualizado'),
                'message': _('Referencia: %s | Superficie: %s m²') % (ref, int(sfc) if sfc else '?'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_importar_superficie_catastro(self):
        """Copia la superficie catastral (m²) al campo de extensión (ha)."""
        self.ensure_one()
        if not self.catastro_superficie:
            raise UserError(_('Primero consulta el Catastro para obtener la superficie.'))
        self.area = round(self.catastro_superficie / 10000.0, 4)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Superficie importada'),
                'message': _('%s m² → %.4f ha') % (int(self.catastro_superficie), self.area),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to normalize polygon after creation"""
        records = super().create(vals_list)
        records._normalize_polygon()
        return records

    def write(self, vals):
        """Override write to normalize polygon only if polygon field changed"""
        res = super().write(vals)
        if 'polygon' in vals:
            self._normalize_polygon()
        return res

    def _normalize_polygon(self):
        """Normalize polygon field to GeoJSON Feature format (no recursive write)"""
        for rec in self.filtered('polygon'):
            try:
                parsed = json.loads(rec.polygon) if isinstance(rec.polygon, str) else rec.polygon
                if not isinstance(parsed, dict):
                    continue
                # Already a Feature? skip
                if parsed.get('type') == 'Feature':
                    continue
                # Wrap geometry as Feature
                feature = {
                    'type': 'Feature',
                    'geometry': parsed,
                    'properties': {'name': rec.name, 'finca_id': rec.id}
                }
                feature_text = json.dumps(feature)
                # Use SQL update to avoid recursion
                self.env.cr.execute(
                    "UPDATE vinedo_finca SET polygon = %s WHERE id = %s",
                    (feature_text, rec.id)
                )
                self.env.cache.invalidate([(rec._fields['polygon'], rec.ids)])
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                _logger.warning('Failed to normalize polygon for finca %s: %s', rec.id, e)


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
