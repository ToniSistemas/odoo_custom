# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    print_format = fields.Selection(
        selection_add=[('4x11_apli', 'Etiquetas 4x11 APLI')],
        ondelete={'4x11_apli': 'set default'}
    )

    def _prepare_report_data(self):
        """Prepare data for report generation"""
        if self.print_format == '4x11_apli':
            xml_id = 'product_label_apli.action_report_product_label_4x11'
            active_model = self.env.context.get('active_model', 'product.template')
            
            if active_model == 'product.template':
                products = self.move_line_ids.product_id if self.move_line_ids else self.product_tmpl_ids.product_variant_ids
            elif active_model == 'product.product':
                products = self.move_line_ids.product_id if self.move_line_ids else self.product_ids
            else:
                products = self.move_line_ids.product_id
            
            quantity_by_product = {}
            for line in self.move_line_ids:
                quantity_by_product[line.product_id.id] = int(line.quantity)
            
            # Si no hay move_line_ids, usar custom_quantity
            if not self.move_line_ids:
                for product in products:
                    quantity_by_product[product.id] = self.custom_quantity or 1
                    
            data = {
                'quantity_by_product': quantity_by_product
            }
            return xml_id, data
        return super()._prepare_report_data()
