from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sale_note = fields.Text(
        string='Nota del Pedido',
        copy=False,
    )

    @api.onchange('origin')
    def _onchange_origin_sale_note(self):
        """Auto-fill sale note from related sale order"""
        for pick in self:
            if not pick.sale_note and pick.origin:
                order = self.env['sale.order'].search([('name', '=', pick.origin)], limit=1)
                if order and order.note:
                    pick.sale_note = order.note

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-fill sale note on creation"""
        pickings = super().create(vals_list)
        for picking in pickings:
            if not picking.sale_note:
                # Try sale_id if available
                if 'sale_id' in picking._fields and picking.sale_id and picking.sale_id.note:
                    picking.sale_note = picking.sale_id.note
                # Fallback to origin search
                elif picking.origin:
                    order = self.env['sale.order'].search([('name', '=', picking.origin)], limit=1)
                    if order and order.note:
                        picking.sale_note = order.note
        return pickings
