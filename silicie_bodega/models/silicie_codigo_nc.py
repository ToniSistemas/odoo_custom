import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SilicieCodigoNc(models.Model):
    _name = 'silicie.codigo.nc'
    _description = 'Código NC de SILICIE'
    _rec_name = 'codigo'
    _order = 'codigo'

    codigo = fields.Char(
        string='Código NC', required=True, size=8,
        help='Código de la Nomenclatura Combinada aplicable al producto.',
    )
    epigrafe_fiscal = fields.Char(string='Epígrafe fiscal AEAT', required=True)
    descripcion = fields.Char(string='Descripción', required=True)
    active = fields.Boolean(string='Activo', default=True)

    _sql_constraints = [
        ('codigo_nc_unique', 'unique(codigo)', 'El código NC debe ser único.'),
    ]

    @api.constrains('codigo')
    def _check_codigo(self):
        for record in self:
            if not re.fullmatch(r'\d{8}', record.codigo or ''):
                raise ValidationError('El código NC debe contener exactamente 8 dígitos.')