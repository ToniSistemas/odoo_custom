# -*- coding: utf-8 -*-

from odoo import models, fields


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    print_format = fields.Selection(
        selection_add=[
            ('4x11', '4 x 11'),
            ('4x11_with_price', '4 x 11 con precio'),
        ],
        ondelete={
            '4x11': 'set default',
            '4x11_with_price': 'set default',
        }
    )

    def _prepare_report_data(self):
        if self.print_format in ('4x11', '4x11_with_price'):
            if self.print_format == '4x11':
                xml_id = 'product_label_4x11.action_report_product_variant_label_4x11'
            else:
                xml_id = 'product_label_4x11.action_report_product_variant_label_4x11_price'
            
            # Build quantity by product dict
            quantity_by_product = {}
            if hasattr(self, 'product_line_ids'):
                quantity_by_product = {p.id: p.quantity for p in self.product_line_ids}
            elif hasattr(self, 'move_line_ids'):
                quantity_by_product = {p.product_id.id: p.qty_done for p in self.move_line_ids}
            
            data = {
                'quantity_by_product': quantity_by_product,
                'price_included': self.print_format == '4x11_with_price',
                'rows': 11,
                'columns': 4,
            }
            return xml_id, data
        
        return super()._prepare_report_data()
