from odoo import models, fields, api
import json


class Territorio(models.Model):
    _name = 'vinedo.territorio'
    _description = 'Territorio/Región'

    name = fields.Char(string='Nombre', required=True)


class Variedad(models.Model):
    _name = 'vinedo.variedad'
    _description = 'Variedad de uva'

    name = fields.Char(string='Variedad', required=True)
    descripcion = fields.Text(string='Descripción')


class Finca(models.Model):
    _name = 'vinedo.finca'
    _description = 'Finca / Parcela'

    name = fields.Char(string='Nombre', required=True)
    territory_id = fields.Many2one('vinedo.territorio', string='Territorio')
    area = fields.Float(string='Extensión (ha)')
    latitude = fields.Float(string='Latitud')
    longitude = fields.Float(string='Longitud')
    polygon = fields.Text(string='Polígono (GeoJSON)')
    variedad_ids = fields.One2many('vinedo.plantacion', 'finca_id', string='Variedades plantadas')
    aportacion_ids = fields.One2many('vinedo.aportacion', 'finca_id', string='Aportaciones de minerales')
    tratamiento_ids = fields.One2many('vinedo.tratamiento', 'finca_id', string='Tratamientos')
    poda_ids = fields.One2many('vinedo.poda', 'finca_id', string='Podas')
    trabajo_ids = fields.One2many('vinedo.trabajo', 'finca_id', string='Trabajos')
    # polygon stores a GeoJSON Feature as text
    polygon = fields.Text(string='Polígono (GeoJSON Feature)')


class Plantacion(models.Model):
    _name = 'vinedo.plantacion'
    _description = 'Plantación por variedad en finca'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade')
    variedad_id = fields.Many2one('vinedo.variedad', string='Variedad', required=True)
    fecha_plantacion = fields.Date(string='Fecha de plantación')
    superficie = fields.Float(string='Superficie (ha)')


class Anada(models.Model):
    _name = 'vinedo.anada'
    _description = 'Añada / Cosecha por variedad'

    name = fields.Char(string='Nombre')
    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True)
    variedad_id = fields.Many2one('vinedo.variedad', string='Variedad', required=True)
    anio = fields.Integer(string='Año')
    graduacion = fields.Float(string='Graduación alcohólica (%vol)')
    acidez = fields.Float(string='Acidez (g/L)')
    cantidad = fields.Float(string='Cantidad recolectada (kg)')


class Aportacion(models.Model):
    _name = 'vinedo.aportacion'
    _description = 'Aportación de minerales'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade')
    fecha = fields.Date(string='Fecha')
    descripcion = fields.Text(string='Descripción')
    cantidad = fields.Float(string='Cantidad (kg)')


class Tratamiento(models.Model):
    _name = 'vinedo.tratamiento'
    _description = 'Tratamiento (fitosanitario u otros)'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade')
    tipo = fields.Selection([('fitosanitario', 'Fitosanitario'), ('otro', 'Otro')], string='Tipo', default='fitosanitario')
    fecha = fields.Date(string='Fecha')
    producto = fields.Char(string='Producto')
    dosis = fields.Char(string='Dosis / Observaciones')
    empleado_id = fields.Many2one('hr.employee', string='Empleado')


class Poda(models.Model):
    _name = 'vinedo.poda'
    _description = 'Registro de podas'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade')
    fecha = fields.Date(string='Fecha')
    descripcion = fields.Text(string='Descripción')
    empleado_id = fields.Many2one('hr.employee', string='Empleado')


class Trabajo(models.Model):
    _name = 'vinedo.trabajo'
    _description = 'Trabajo realizado en finca'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade')
    fecha = fields.Date(string='Fecha')
    empleado_id = fields.Many2one('hr.employee', string='Empleado')
    tipo_trabajo = fields.Char(string='Trabajo realizado')
    horas = fields.Float(string='Horas')

    @api.model
    def create(self, vals):
        record = super(Trabajo, self).create(vals)
        return record


class Finca(models.Model):
    _inherit = 'vinedo.finca'

    @api.model
    def create(self, vals):
        rec = super(Finca, self).create(vals)
        rec._ensure_polygon_feature()
        return rec

    def write(self, vals):
        res = super(Finca, self).write(vals)
        for rec in self:
            rec._ensure_polygon_feature()
        return res

    def _ensure_polygon_feature(self):
        """Ensure the `polygon` field is a GeoJSON Feature (wrap geometry if needed)
        and attempt to synchronize with geoengine if available."""
        for rec in self:
            if not rec.polygon:
                continue
            try:
                parsed = json.loads(rec.polygon) if isinstance(rec.polygon, str) else rec.polygon
            except Exception:
                continue
            # Normalize to Feature
            if isinstance(parsed, dict) and parsed.get('type') == 'Feature':
                feature = parsed
            else:
                # assume geometry object
                feature = {'type': 'Feature', 'geometry': parsed, 'properties': {'name': rec.name}}
            # store normalized feature as text if changed
            try:
                feature_text = json.dumps(feature)
                if rec.polygon != feature_text:
                    rec.sudo().write({'polygon': feature_text})
            except Exception:
                pass
            # Try syncing with geoengine (optional)
            try:
                layer_model = self.env['geoengine.layer']
                feature_model = self.env['geoengine.feature']
            except Exception:
                layer_model = False
                feature_model = False
            if layer_model and feature_model:
                try:
                    layer = layer_model.search([('name', '=', 'vinedo_fincas')], limit=1)
                    if not layer:
                        layer = layer_model.create({'name': 'vinedo_fincas', 'srid': 4326})
                    vals = {'layer_id': layer.id}
                    # Attempt common field names
                    if 'geom' in feature_model._fields:
                        vals['geom'] = feature_text
                    elif 'geometry' in feature_model._fields:
                        vals['geometry'] = feature_text
                    # attach reference if possible
                    if 'vinedo_finca_id' in feature_model._fields:
                        vals['vinedo_finca_id'] = rec.id
                    # create a new feature record (best effort)
                    feature_model.create(vals)
                except Exception:
                    # swallow errors to avoid breaking core create/write
                    pass
