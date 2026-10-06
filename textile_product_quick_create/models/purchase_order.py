from odoo import api, models

_TEXTILE_CONTEXT = (
    "'textile_quick_create': True, "
    "'default_type': 'consu', "
    "'default_is_storable': True, "
    "'default_available_in_pos': True, "
    "'default_sale_ok': True, "
    "'default_purchase_ok': True"
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
