from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    textile_price_coefficient = fields.Float(
        string="Coeficiente de venta textil", digits=(16, 2), default=2.5,
        help="Precio de venta = coste de compra × coeficiente. 0 desactiva el cálculo.")
    textile_price_ending = fields.Float(
        string="Terminación de precio", digits=(16, 2), default=0.95,
        help="Redondea el precio hacia arriba hasta esta terminación (p. ej. 0,95 → 24,95). "
             "0 = sin redondeo.")
