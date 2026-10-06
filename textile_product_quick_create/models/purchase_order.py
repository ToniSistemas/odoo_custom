from odoo import api, fields, models

_TEXTILE_CONTEXT = (
    "'textile_quick_create': True, "
    "'default_type': 'consu', "
    "'default_is_storable': True, "
    "'default_available_in_pos': True, "
    "'default_sale_ok': True, "
    "'default_purchase_ok': True, "
    "'default_textile_auto_price': True"
)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form':
            # product_template_id solo existe con purchase_product_matrix; se cubre sin depender de él
            for node in arch.xpath(
                "//field[@name='order_line']//field[@name='product_id' or @name='product_template_id']"
            ):
                context = (node.get('context') or '{}').strip()
                body = context[1:-1].strip().rstrip(',')
                node.set('context', '{%s}' % (f'{body}, {_TEXTILE_CONTEXT}' if body else _TEXTILE_CONTEXT))
        return arch, view

    def button_confirm(self):
        res = super().button_confirm()
        self.order_line.product_id.product_tmpl_id.filtered('textile_auto_price').write(
            {'textile_auto_price': False})
        return res


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._textile_update_product_prices()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if vals.keys() & {'price_unit', 'discount', 'product_uom_id', 'product_id'}:
            self._textile_update_product_prices()
        return res

    def _textile_update_product_prices(self):
        for line in self:
            template = line.product_id.product_tmpl_id
            if line.display_type or not template.textile_auto_price or line.price_unit <= 0:
                continue
            cost = line.price_unit * (1 - (line.discount or 0.0) / 100)
            if line.product_uom_id:
                cost = line.product_uom_id._compute_price(cost, line.product_id.uom_id)
            cost = line.currency_id._convert(
                cost, line.company_id.currency_id, line.company_id,
                line.date_order or fields.Date.context_today(line))
            template._textile_apply_cost(cost)
