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
            Product = self.env['product.product']
            products = data.get('products')
                # Refuerzo final: forzar siempre recordset
                def to_recordset(val):
                    if hasattr(val, 'ids'):
                        return val
                    if isinstance(val, (list, tuple)):
                        try:
                            return Product.browse([int(x) for x in val])
                        except Exception:
                            return Product.browse([])
                    if isinstance(val, int):
                        return Product.browse([val])
                    if isinstance(val, str):
                        try:
                            return Product.browse([int(val)])
                        except Exception:
                            return Product.browse([])
                    return Product.browse([])

                # Intentar con products de data
                products = to_recordset(products)
                # Si sigue vacío, buscar en active_ids
                if not products or not products.ids:
                    active_ids = self.env.context.get('active_ids')
                    products = to_recordset(active_ids)
                # Si sigue vacío, buscar en self.product_ids/product_id
                if (not products or not products.ids):
                    if hasattr(self, 'product_ids') and self.product_ids:
                        products = to_recordset(self.product_ids)
                    elif hasattr(self, 'product_id') and self.product_id:
                        products = to_recordset(self.product_id)
                # Refuerzo final: nunca string
                products = to_recordset(products)
                data['products'] = products
        return xml_id, data
