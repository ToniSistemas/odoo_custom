import math

from odoo import api, fields, models
from odoo.tools import float_round


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    textile_auto_price = fields.Boolean(
        string="Precio de venta automático", copy=False,
        help="Se activa al crear el producto desde una compra: el precio de venta se recalcula "
             "desde el coste hasta que se confirma el pedido o se edita el precio a mano.")

    def _textile_compute_sale_price(self, cost):
        self.ensure_one()
        company = self.company_id or self.env.company
        coefficient = (self.categ_id and self.categ_id._textile_get_price_coefficient()) \
            or company.textile_price_coefficient
        if not coefficient or cost <= 0:
            return False
        price = cost * coefficient
        ending = company.textile_price_ending
        if ending:
            # Redondeo hacia arriba para no perder margen: 24,90 → 24,95; 25,00 → 25,95
            price = math.ceil(float_round(price - ending, precision_digits=6)) + ending
        return company.currency_id.round(price)

    def _textile_apply_cost(self, cost):
        self.ensure_one()
        template = self.with_context(textile_auto_pricing=True)
        template.product_variant_ids.write({'standard_price': cost})
        sale_price = template._textile_compute_sale_price(cost)
        if sale_price:
            template.list_price = sale_price

    @api.onchange('standard_price')
    def _onchange_textile_standard_price(self):
        if self.textile_auto_price and self.standard_price > 0:
            sale_price = self._textile_compute_sale_price(self.standard_price)
            if sale_price:
                self.list_price = sale_price

    def write(self, vals):
        if 'list_price' in vals and 'textile_auto_price' not in vals \
                and not self.env.context.get('textile_auto_pricing'):
            vals = dict(vals, textile_auto_price=False)
        return super().write(vals)
