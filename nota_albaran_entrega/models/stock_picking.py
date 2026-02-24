from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sale_note = fields.Text(
        string='Nota del Pedido',
        compute='_compute_sale_note',
        store=True,
        readonly=False,
    )

    @api.depends('origin')
    def _compute_sale_note(self):
        for pick in self:
            note = False
            # Try to get note from sale_id if field exists (sale_stock installed)
            if 'sale_id' in pick._fields and pick.sale_id:
                note = pick.sale_id.note
            # Fallback: search by origin
            elif pick.origin:
                order = self.env['sale.order'].search([('name', '=', pick.origin)], limit=1)
                if order:
                    note = order.note
            pick.sale_note = note
