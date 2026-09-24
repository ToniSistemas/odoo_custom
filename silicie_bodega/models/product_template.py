from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    silicie_codigo_nc_id = fields.Many2one(
        'silicie.codigo.nc',
        string='Código NC',
        domain=[('active', '=', True)],
        help='Código NC que se arrastrará automáticamente a los asientos SILICIE.',
    )
    silicie_epigrafe_fiscal = fields.Char(
        related='silicie_codigo_nc_id.epigrafe_fiscal',
        string='Epígrafe fiscal AEAT',
        store=True,
        readonly=True,
    )
    silicie_grado_alcoholico = fields.Float(
        string='Grado alcohólico (% vol)', digits=(5, 2),
        help='Grado alcohólico volumétrico adquirido del producto.',
    )
    silicie_capacidad_envase = fields.Float(
        string='Capacidad del envase (litros)', digits=(5, 3),
        help='Capacidad de cada envase para calcular los litros del asiento.',
    )