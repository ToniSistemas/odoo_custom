from odoo import models, fields


class BodegaVariedad(models.Model):
    _name = 'bodega.variedad'
    _description = 'Variedad de Uva'
    _order = 'name'

    name = fields.Char(string='Variedad', required=True)
    tipo = fields.Selection([
        ('tinta', 'Tinta'),
        ('blanca', 'Blanca'),
        ('rosada', 'Rosada'),
    ], string='Tipo')
    descripcion = fields.Text(string='Descripción')
    active = fields.Boolean(string='Activo', default=True)


class BodegaTipoParametro(models.Model):
    _name = 'bodega.tipo.parametro'
    _description = 'Tipo de Parámetro Químico'
    _order = 'name'

    name = fields.Char(string='Parámetro', required=True)
    unidad = fields.Char(string='Unidad', help='Unidad de medida (g/L, mg/L, %, etc.)')
    rango_min = fields.Float(string='Mínimo recomendado', digits=(10, 3))
    rango_max = fields.Float(string='Máximo recomendado', digits=(10, 3))
    descripcion = fields.Text(string='Descripción')
    active = fields.Boolean(string='Activo', default=True)
