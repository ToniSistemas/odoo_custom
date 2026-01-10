# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    quick_ean = fields.Char(
        string='Código EAN',
        help='Escanear o introducir código EAN para asignarlo a la variante del producto'
    )

    @api.onchange('quick_ean')
    def _onchange_quick_ean(self):
        """Assign EAN code to product variant when entered"""
        if self.quick_ean and self.product_id:
            # Check if EAN already exists on another product
            existing_product = self.env['product.product'].search([
                ('barcode', '=', self.quick_ean),
                ('id', '!=', self.product_id.id)
            ], limit=1)
            
            if existing_product:
                raise UserError(
                    f"El código EAN {self.quick_ean} ya está asignado al producto: "
                    f"{existing_product.display_name}"
                )
            
            # Assign EAN to the current product variant
            self.product_id.barcode = self.quick_ean
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'EAN Asignado',
                    'message': f'Código EAN {self.quick_ean} asignado a {self.product_id.display_name}',
                    'type': 'success',
                    'sticky': False,
                }
            }


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    quick_ean = fields.Char(
        string='EAN Code',
        help='Scan or enter EAN code to assign it to the product variant'
    )

    @api.onchange('quick_ean')
    def _onchange_quick_ean(self):
        """Assign EAN code to product variant when entered"""
        if self.quick_ean and self.product_id:
            # Check if EAN already exists on another product
            existing_product = self.env['product.product'].search([
                ('barcode', '=', self.quick_ean),
                ('id', '!=', self.product_id.id)
            ], limit=1)
            
            if existing_product:
                raise UserError(
                    f"El código EAN {self.quick_ean} ya está asignado al producto: "
                    f"{existing_product.display_name}"
                )
            
            # Assign EAN to the current product variant
            self.product_id.barcode = self.quick_ean
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'EAN Asignado',
                    'message': f'Código EAN {self.quick_ean} asignado a {self.product_id.display_name}',
                    'type': 'success',
                    'sticky': False,
                }
            }

    @api.model_create_multi
    def create(self, vals_list):
        """Handle EAN assignment on record creation"""
        lines = super().create(vals_list)
        for line in lines:
            if line.quick_ean and line.product_id and not line.product_id.barcode:
                line.product_id.barcode = line.quick_ean
        return lines

    def write(self, vals):
        """Handle EAN assignment on record update"""
        res = super().write(vals)
        if 'quick_ean' in vals:
            for line in self:
                if line.quick_ean and line.product_id and not line.product_id.barcode:
                    line.product_id.barcode = line.quick_ean
        return res
