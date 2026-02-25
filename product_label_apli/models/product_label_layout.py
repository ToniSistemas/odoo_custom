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
            Product = self.env['product.product']
            def ensure_recordset(val):
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
                        ids = [int(x) for x in val.replace('[', '').replace(']', '').split(',') if x.strip().isdigit()]
                        return Product.browse(ids)
                    except Exception:
                        return Product.browse([])
                return Product.browse([])

            products = ensure_recordset(data.get('products'))
            if not products.ids:
                products = ensure_recordset(self.env.context.get('active_ids') or self.env.context.get('active_id'))
            if not products.ids:
                # try wizard fields
                if hasattr(self, 'product_ids') and self.product_ids:
                    products = ensure_recordset(self.product_ids)
                elif hasattr(self, 'product_id') and self.product_id:
                    products = ensure_recordset(self.product_id)
            # Pass a serializable list of ids to the report, avoid sending recordsets directly
            data['products_ids'] = products.ids if products else []
            # Do not pass the recordset itself (may be serialized as string); template will rebuild it
            data['products'] = None
        return xml_id, data
