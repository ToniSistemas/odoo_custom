from odoo import models, fields


class StockLot(models.Model):
    _inherit = 'stock.lot'

    # --- Campos de Bodega ---
    anada = fields.Integer(
        string='Añada',
        help='Año de cosecha de la uva',
    )
    tipo_vino = fields.Selection([
        ('tinto', 'Tinto'),
        ('blanco', 'Blanco'),
        ('rosado', 'Rosado'),
        ('espumoso', 'Espumoso'),
        ('generoso', 'Generoso'),
        ('otro', 'Otro'),
    ], string='Tipo de vino')
    denominacion = fields.Char(string='Denominación de Origen / DO')
    variedad_ids = fields.Many2many(
        'bodega.variedad',
        'bodega_lot_variedad_rel',
        'lot_id',
        'variedad_id',
        string='Variedades',
    )
    parametro_quimico_ids = fields.One2many(
        'bodega.parametro.quimico',
        'lot_id',
        string='Parámetros Químicos',
    )
    notas_cata = fields.Text(string='Notas de cata')
    precintas = fields.Integer(string='Precintas')
    etiquetado = fields.Boolean(string='Etiquetado', default=False)
