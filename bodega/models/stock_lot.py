from odoo import models, fields, api


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
    precintas_desde = fields.Integer(string='Precintas desde')
    precintas_hasta = fields.Integer(string='Precintas hasta')
    precintas_total = fields.Integer(
        string='Total precintas',
        compute='_compute_precintas_total',
        store=True,
    )
    etiquetado = fields.Boolean(string='Etiquetado', default=False)

    @api.depends('precintas_desde', 'precintas_hasta')
    def _compute_precintas_total(self):
        for rec in self:
            if rec.precintas_hasta and rec.precintas_desde:
                rec.precintas_total = rec.precintas_hasta - rec.precintas_desde + 1
            else:
                rec.precintas_total = 0
