from odoo import fields, models

from .product_template import DEFAULT_COEFFICIENT, DEFAULT_ENDING, PARAM_COEFFICIENT, PARAM_ENDING


# Parámetros del sistema en vez de campos de res.company: así el módulo se actualiza desde Aplicaciones
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    textile_price_coefficient = fields.Float(
        string="Coeficiente de venta textil", digits=(16, 2),
        config_parameter=PARAM_COEFFICIENT, default=DEFAULT_COEFFICIENT,
        help="Precio de venta = coste de compra × coeficiente. 0 desactiva el cálculo.")
    textile_price_ending = fields.Float(
        string="Terminación de precio", digits=(16, 2),
        config_parameter=PARAM_ENDING, default=DEFAULT_ENDING,
        help="Redondea el precio hacia arriba hasta esta terminación (p. ej. 0,95 → 24,95). "
             "0 = sin redondeo.")
