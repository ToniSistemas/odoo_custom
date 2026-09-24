from odoo import fields, models, _


class StockLot(models.Model):
    _inherit = 'stock.lot'

    silicie_codigo_nc_id = fields.Many2one(
        'silicie.codigo.nc',
        string='Código NC efectivo',
        domain=[('active', '=', True)],
        help='Código NC efectivo de esta partida. Si está vacío, se usa el del producto.',
    )
    silicie_epigrafe_fiscal = fields.Char(
        related='silicie_codigo_nc_id.epigrafe_fiscal',
        string='Epígrafe fiscal AEAT',
        store=True,
        readonly=True,
    )
    silicie_grado_alcoholico = fields.Float(
        string='Grado alcohólico efectivo (% vol)', digits=(5, 2),
        help='Graduación real obtenida en el análisis de esta partida.',
    )
    silicie_capacidad_envase = fields.Float(
        string='Capacidad efectiva del envase (litros)', digits=(5, 3),
        help='Capacidad real de los envases de esta partida.',
    )
