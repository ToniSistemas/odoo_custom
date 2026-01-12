# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_referencia = fields.Char(
        string='Referencia',
        help='Campo de referencia libre para el producto',
        index=True
    )

    variants_without_ean_count = fields.Integer(
        string='Variants Without EAN',
        compute='_compute_variants_without_ean_count'
    )

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=None, order=None):
        """Extend name search to include x_referencia field"""
        domain = domain or []
        if name:
            domain = ['|', '|', ('x_referencia', operator, name), ('default_code', operator, name), ('name', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)

    @api.depends('product_variant_ids.barcode')
    def _compute_variants_without_ean_count(self):
        """Count how many variants don't have an EAN code"""
        for template in self:
            template.variants_without_ean_count = len(
                template.product_variant_ids.filtered(lambda v: not v.barcode)
            )

    def action_open_assign_ean_wizard(self):
        """Open wizard to assign EAN codes to variants"""
        return {
            'name': 'Asignar Códigos EAN',
            'type': 'ir.actions.act_window',
            'res_model': 'assign.ean.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_template_id': self.id,
            }
        }


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_open_product_form(self):
        """Open product variant form view"""
        return {
            'name': 'Variante de Producto',
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
