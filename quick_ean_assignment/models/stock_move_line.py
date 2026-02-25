# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    quick_ean = fields.Char(
        string='Código EAN',
        compute='_compute_quick_ean',
        inverse='_inverse_quick_ean',
        store=False,
        help='Escanear o introducir código EAN para asignarlo a la variante del producto'
    )

    @api.depends('product_id.barcode')
    def _compute_quick_ean(self):
        """Show current product barcode"""
        for move in self:
            move.quick_ean = move.product_id.barcode or ''

    def _inverse_quick_ean(self):
        """Assign EAN code to product variant when entered"""
        for move in self:
            if move.quick_ean and move.product_id:
                # Check if EAN already exists on another product
                existing_product = self.env['product.product'].search([
                    ('barcode', '=', move.quick_ean),
                    ('id', '!=', move.product_id.id)
                ], limit=1)
                
                if existing_product:
                    raise UserError(
                        f"El código EAN {move.quick_ean} ya está asignado al producto: "
                        f"{existing_product.display_name}"
                    )
                
                # Assign EAN to the current product variant
                move.product_id.barcode = move.quick_ean


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    quick_ean = fields.Char(
        string='Código EAN',
        compute='_compute_quick_ean',
        inverse='_inverse_quick_ean',
        store=False,
        help='Escanear o introducir código EAN para asignarlo a la variante del producto'
    )

    @api.depends('product_id.barcode')
    def _compute_quick_ean(self):
        """Show current product barcode"""
        for line in self:
            line.quick_ean = line.product_id.barcode or ''

    def _inverse_quick_ean(self):
        """Assign EAN code to product variant when entered"""
        for line in self:
            if line.quick_ean and line.product_id:
                # Check if EAN already exists on another product
                existing_product = self.env['product.product'].search([
                    ('barcode', '=', line.quick_ean),
                    ('id', '!=', line.product_id.id)
                ], limit=1)
                
                if existing_product:
                    raise UserError(
                        f"El código EAN {line.quick_ean} ya está asignado al producto: "
                        f"{existing_product.display_name}"
                    )
                
                # Assign EAN to the current product variant
                line.product_id.barcode = line.quick_ean
