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
            # Si es un string, int o lista, convertir a recordset
            if isinstance(products, str):
                products = Product.browse([])
            elif isinstance(products, int):
                products = Product.browse([products])
            elif isinstance(products, (list, tuple)):
                # Si es lista de ids o strings
                try:
                    products = Product.browse([int(x) for x in products])
                except Exception:
                    products = Product.browse([])
            # Si sigue vacío, buscar en active_ids
            if not products or not hasattr(products, 'ids'):
                active_ids = self.env.context.get('active_ids')
                if active_ids:
                    try:
                        products = Product.browse([int(x) for x in active_ids])
                    except Exception:
                        products = Product.browse([])
            # Si sigue vacío, buscar en self.product_ids/product_id
            if (not products or not hasattr(products, 'ids') or not products.ids):
                if hasattr(self, 'product_ids') and self.product_ids:
                    val = self.product_ids
                    if hasattr(val, 'ids'):
                        products = val
                    elif isinstance(val, (list, tuple)):
                        try:
                            products = Product.browse([int(x) for x in val])
                        except Exception:
                            products = Product.browse([])
                elif hasattr(self, 'product_id') and self.product_id:
                    val = self.product_id
                    if hasattr(val, 'ids'):
                        products = val
                    elif isinstance(val, (int, str)):
                        try:
                            products = Product.browse([int(val)])
                        except Exception:
                            products = Product.browse([])
            # Garantizar que es un recordset válido
            if not products or not hasattr(products, 'ids'):
                products = Product.browse([])
            data['products'] = products
        return xml_id, data
