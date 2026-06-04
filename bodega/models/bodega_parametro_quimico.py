from odoo import models, fields


class BodegaParametroQuimico(models.Model):
    _name = 'bodega.parametro.quimico'
    _description = 'Parámetro Químico de Lote'
    _order = 'fecha desc, tipo_id'

    lot_id = fields.Many2one(
        'stock.lot', string='Lote', required=True, ondelete='cascade', index=True
    )
    tipo_id = fields.Many2one(
        'bodega.tipo.parametro', string='Parámetro', required=True
    )
    name = fields.Char(related='tipo_id.name', string='Parámetro', store=True)
    valor = fields.Float(string='Valor', digits=(10, 3))
    unidad = fields.Char(
        related='tipo_id.unidad', string='Unidad', store=True, readonly=False
    )
    fecha = fields.Date(string='Fecha análisis', default=fields.Date.today)
    laboratorio = fields.Char(string='Laboratorio')
    observaciones = fields.Text(string='Observaciones')
