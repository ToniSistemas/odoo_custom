from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sale_note = fields.Text(
        string='Nota del Pedido',
        compute='_compute_sale_note',
        store=True,
        readonly=False,
    )

    @api.depends('sale_id', 'origin')
    def _compute_sale_note(self):
        SaleOrder = self.env['sale.order']
        for pick in self:
            note = False
            if hasattr(pick, 'sale_id') and pick.sale_id:
                note = pick.sale_id.note
            elif pick.origin:
                order = SaleOrder.search([('name', '=', pick.origin)], limit=1)
                if order:
                    note = order.note
            pick.sale_note = note
