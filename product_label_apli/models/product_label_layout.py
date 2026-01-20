# -*- coding: utf-8 -*-

from odoo import models, fields


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    print_format = fields.Selection(
        selection_add=[('4x11_apli', 'Etiquetas 4x11 APLI')],
        ondelete={'4x11_apli': 'set default'}
    )

    def _prepare_report_data(self):
        """Prepare data for report generation"""
        xml_id, data = super()._prepare_report_data()
        if self.print_format == '4x11_apli':
            xml_id = 'product_label_apli.action_report_product_label_4x11_custom'
            # Forzar que 'products' siempre tenga contenido
            products = data.get('products')
            if not products:
                # Intentar con active_ids
                active_ids = self.env.context.get('active_ids')
                if active_ids:
                    products = self.env['product.product'].browse(active_ids)
            if not products:
                # Intentar con los productos del propio wizard (soporta product_ids o product_id)
                if hasattr(self, 'product_ids'):
                    products = self.product_ids
                elif hasattr(self, 'product_id'):
                    products = self.product_id
            data['products'] = products
        return xml_id, data
