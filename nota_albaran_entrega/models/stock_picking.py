from odoo import models, fields, api
from odoo.tools import html2plaintext


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sale_note = fields.Html(
        string='Nota del Pedido',
        copy=False,
    )

    sale_note_plain = fields.Text(
        string='Nota del Pedido (texto plano)',
        compute='_compute_sale_note_plain',
        store=False,
    )

    def _compute_sale_note_plain(self):
        """Convert HTML note to plain text for reports"""
        for pick in self:
            pick.sale_note_plain = html2plaintext(pick.sale_note or '') if pick.sale_note else ''
    
    def _get_sale_order(self):
        """Get related sale order"""
        self.ensure_one()
        if 'sale_id' in self._fields and self.sale_id:
            return self.sale_id
        elif self.origin:
            return self.env['sale.order'].search([('name', '=', self.origin)], limit=1)
        return self.env['sale.order']
    
    def write(self, vals):
        """Auto-fill sale note on write if origin changes"""
        res = super().write(vals)
        if 'origin' in vals or ('sale_id' in vals and 'sale_id' in self._fields):
            for pick in self:
                if not pick.sale_note:
                    order = pick._get_sale_order()
                    if order and order.note:
                        pick.sale_note = order.note
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-fill sale note on creation"""
        pickings = super().create(vals_list)
        for picking in pickings:
            if not picking.sale_note:
                order = picking._get_sale_order()
                if order and order.note:
                    picking.sale_note = order.note
        return pickings
