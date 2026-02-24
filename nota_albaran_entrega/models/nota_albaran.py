from odoo import models, fields


class NotaAlbaranEntrega(models.Model):
    _name = 'nota.albaran.entrega'
    _description = 'Nota de Albarán de Entrega'

    name = fields.Char(string='Referencia', required=True)
    delivery_date = fields.Date(string='Fecha de entrega')
    description = fields.Text(string='Descripción')
