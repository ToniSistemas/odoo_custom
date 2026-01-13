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
        xml_id, data = super()._prepare_report_data()
        
        if self.print_format in ('4x11', '4x11_with_price'):
            # Modify the data to use 4x11 format
            data['rows'] = 11
            data['columns'] = 4
            data['price_included'] = self.print_format == '4x11_with_price'
            
            # Use the same report template but with different data
            if self.print_format == '4x11':
                xml_id = 'product_label_4x11.action_report_product_variant_label_4x11'
            else:
                xml_id = 'product_label_4x11.action_report_product_variant_label_4x11_price'
        
        return xml_id, data
