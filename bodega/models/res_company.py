from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    bodega_nidpb = fields.Char(
        string='NIDPB (Número de Identificación de la Bodega de Producción)',
        help='Número de Identificación de la Bodega de Producción asignado '
             'por el organismo competente.',
    )
    bodega_ria = fields.Char(
        string='RIA (Registro de Instalaciones de Actividad)',
        help='Número de inscripción en el Registro de Instalaciones de Actividad '
             'de la comunidad autónoma correspondiente.',
    )
    bodega_registro_sanitario = fields.Char(
        string='Registro Sanitario (RGSEAA)',
        help='Número de inscripción en el Registro General Sanitario de Empresas '
             'Alimentarias y Alimentos (RGSEAA), gestionado por la AESAN.',
    )
