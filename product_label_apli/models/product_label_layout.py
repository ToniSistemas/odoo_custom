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
            # Normalizar data['products'] para evitar strings o iterables no válidos
            products = data.get('products')
            Product = self.env['product.product']
            if products and not hasattr(products, 'ids'):
                # Si viene como lista/tupla de ids (strings o ints)
                if isinstance(products, (list, tuple)):
                    try:
                        ids = [int(x) for x in products]
                        products = Product.browse(ids)
                    except Exception:
                        products = Product.browse([])
                elif isinstance(products, str):
                    # Intentar parsear '1,2,3' o '[1, 2, 3]'
                    try:
                        # extraer dígitos
                        ids = [int(x) for x in products.replace('[', '').replace(']', '').split(',') if x.strip().isdigit()]
                        products = Product.browse(ids)
                    except Exception:
                        products = Product.browse([])
                else:
                    products = Product.browse([])
                data['products'] = products
        return xml_id, data
