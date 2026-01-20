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
            Product = self.env['product.product']
            if not products:
                # Intentar con active_ids
                active_ids = self.env.context.get('active_ids')
                if active_ids:
                    products = Product.browse(active_ids)
            if not products:
                # Intentar con los productos del propio wizard (soporta product_ids o product_id)
                if hasattr(self, 'product_ids'):
                    # Puede ser un recordset, lista de ids o vacío
                    val = self.product_ids
                    if isinstance(val, (list, tuple)):
                        products = Product.browse(val)
                    else:
                        products = val if hasattr(val, 'ids') else Product.browse([])
                elif hasattr(self, 'product_id'):
                    val = self.product_id
                    if isinstance(val, (int, str)):
                        products = Product.browse([val])
                    else:
                        products = val if hasattr(val, 'ids') else Product.browse([])
            # Garantizar que es un recordset
            if not hasattr(products, 'ids'):
                products = Product.browse([])
            data['products'] = products
        return xml_id, data
