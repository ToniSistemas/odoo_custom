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
        # Get default data first
        xml_id, data = super()._prepare_report_data()
        
        # For 4x11 formats, we change rows from 12 to 11 but keep everything else
        if self.print_format == '4x11':
            data['rows'] = 11
            data['price_included'] = False
        elif self.print_format == '4x11_with_price':
            data['rows'] = 11
            data['price_included'] = True
        
        return xml_id, data
