from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    fashion_product_barcode = fields.Char(related='product_id.barcode', string="EAN variante")

    def _fashion_qty_picked(self):
        self.ensure_one()
        return sum(
            ml.product_uom_id._compute_quantity(ml.quantity, self.product_uom)
            for ml in self.move_line_ids.filtered('picked')
        )

    def action_fashion_open_assign_wizard(self):
        self.ensure_one()
        return self.env['fashion.barcode.assign.wizard']._fashion_action(
            self.picking_id, product=self.product_id)
