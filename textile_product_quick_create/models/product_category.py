from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    textile_price_coefficient = fields.Float(
        string="Coeficiente de venta textil", digits=(16, 2),
        help="Sustituye al coeficiente de la compañía para esta categoría y sus hijas. "
             "0 = usar el de la categoría padre o el de la compañía.")

    def _textile_get_price_coefficient(self):
        self.ensure_one()
        category = self
        while category:
            if category.textile_price_coefficient:
                return category.textile_price_coefficient
            category = category.parent_id
        return 0.0
