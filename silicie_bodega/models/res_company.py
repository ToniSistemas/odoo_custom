from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    silicie_cae = fields.Char(
        string='CAE (Código de Actividad y Establecimiento)',
        size=13,
        help='Código asignado por la AEAT al establecimiento. Obligatorio para presentar asientos SILICIE.',
    )
    silicie_tipo_establecimiento = fields.Selection([
        ('fabrica', 'Fábrica'),
        ('deposito_fiscal', 'Depósito Fiscal'),
        ('almacen_fiscal', 'Almacén Fiscal'),
        ('deposito_recepcion', 'Depósito de Recepción'),
        ('fabrica_vinagre', 'Fábrica de Vinagre'),
    ], string='Tipo de establecimiento SILICIE')
    silicie_activo = fields.Boolean(
        string='SILICIE activo',
        default=False,
        help='Si está marcado, se generarán asientos SILICIE automáticamente al validar albaranes.',
    )
