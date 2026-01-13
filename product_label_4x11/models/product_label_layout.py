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
        if self.print_format == '4x11':
            xml_id = 'product_label_4x11.action_report_product_variant_label_4x11'
            data = {
                'price_included': False,
                'custom_barcodes': self.custom_barcodes,
            }
            return xml_id, data
        elif self.print_format == '4x11_with_price':
            xml_id = 'product_label_4x11.action_report_product_variant_label_4x11_price'
            data = {
                'price_included': True,
                'custom_barcodes': self.custom_barcodes,
            }
            return xml_id, data
        
        return super()._prepare_report_data()
