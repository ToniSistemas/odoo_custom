from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
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
