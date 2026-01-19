# -*- coding: utf-8 -*-

from odoo import models, fields


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    print_format = fields.Selection(
        selection_add=[('4x11_apli', 'Etiquetas 4x11 APLI')],
        ondelete={'4x11_apli': 'set default'}
    )

    def _prepare_report_data(self):
        if self.print_format == '4x11_apli':
            xml_id = 'product_label_apli.action_report_product_label_4x11'
        else:
            return super()._prepare_report_data()
        
        return xml_id, {'quantity': self.product_print_quantity}
