# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class AssignEanWizard(models.TransientModel):
    _name = 'assign.ean.wizard'
    _description = 'Wizard for Mass EAN Assignment'

    product_template_id = fields.Many2one(
        'product.template',
        string='Product Template',
        readonly=True
    )
    line_ids = fields.One2many(
        'assign.ean.wizard.line',
        'wizard_id',
        string='Product Variants'
    )

    @api.model
    def default_get(self, fields_list):
        """Load product variants without EAN"""
        res = super().default_get(fields_list)
        
        if self.env.context.get('default_product_template_id'):
            template = self.env['product.template'].browse(
                self.env.context.get('default_product_template_id')
            )
            variants_without_ean = template.product_variant_ids.filtered(
                lambda v: not v.barcode
            )
            
            lines = []
            for variant in variants_without_ean:
                lines.append((0, 0, {
                    'product_id': variant.id,
                    'product_name': variant.display_name,
                }))
            res['line_ids'] = lines
        
        return res

    def action_assign_ean_codes(self):
        """Assign EAN codes to all variants in the wizard"""
        for line in self.line_ids:
            if line.new_ean:
                # Check if EAN already exists
                existing = self.env['product.product'].search([
                    ('barcode', '=', line.new_ean),
                    ('id', '!=', line.product_id.id)
                ], limit=1)
                
                if existing:
                    raise UserError(
                        f"El código EAN {line.new_ean} ya está asignado al producto: "
                        f"{existing.display_name}"
                    )
                
                # Assign the EAN code
                line.product_id.barcode = line.new_ean
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Códigos EAN Asignados',
                'message': f'{len(self.line_ids.filtered(lambda l: l.new_ean))} códigos EAN asignados correctamente',
                'type': 'success',
                'sticky': False,
            }
        }


class AssignEanWizardLine(models.TransientModel):
    _name = 'assign.ean.wizard.line'
    _description = 'EAN Assignment Line'

    wizard_id = fields.Many2one(
        'assign.ean.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product Variant',
        required=True,
        readonly=True
    )
    product_name = fields.Char(
        string='Product Name',
        readonly=True
    )
    current_ean = fields.Char(
        related='product_id.barcode',
        string='Current EAN',
        readonly=True
    )
    new_ean = fields.Char(
        string='New EAN Code',
        help='Scan or enter the new EAN code for this variant'
    )

    @api.onchange('new_ean')
    def _onchange_new_ean(self):
        """Validate EAN code in real-time"""
        if self.new_ean:
            # Check if EAN already exists
            existing = self.env['product.product'].search([
                ('barcode', '=', self.new_ean),
                ('id', '!=', self.product_id.id)
            ], limit=1)
            
            if existing:
                return {
                    'warning': {
                        'title': 'EAN Duplicado',
                        'message': f'El código EAN {self.new_ean} ya está asignado al producto: {existing.display_name}'
                    }
                }


class AssignEanMassWizard(models.TransientModel):
    _name = 'assign.ean.mass.wizard'
    _description = 'Mass EAN Assignment for All Products'

    line_ids = fields.One2many(
        'assign.ean.mass.wizard.line',
        'wizard_id',
        string='Product Variants Without EAN'
    )
    filter_categ_id = fields.Many2one(
        'product.category',
        string='Filter by Category'
    )

    @api.model
    def default_get(self, fields_list):
        """Load all product variants without EAN"""
        res = super().default_get(fields_list)
        
        domain = [('barcode', '=', False)]
        
        # Apply category filter if provided
        if self.env.context.get('default_filter_categ_id'):
            domain.append(('categ_id', '=', self.env.context.get('default_filter_categ_id')))
        
        variants_without_ean = self.env['product.product'].search(domain)
        
        lines = []
        for variant in variants_without_ean:
            lines.append((0, 0, {
                'product_id': variant.id,
                'product_name': variant.display_name,
                'product_category': variant.categ_id.name,
            }))
        
        res['line_ids'] = lines
        return res

    def action_assign_ean_codes(self):
        """Assign EAN codes to all variants in the wizard"""
        assigned_count = 0
        
        for line in self.line_ids:
            if line.new_ean:
                # Check if EAN already exists
                existing = self.env['product.product'].search([
                    ('barcode', '=', line.new_ean),
                    ('id', '!=', line.product_id.id)
                ], limit=1)
                
                if existing:
                    raise UserError(
                        f"El código EAN {line.new_ean} ya está asignado al producto: "
                        f"{existing.display_name}"
                    )
                
                # Assign the EAN code
                line.product_id.barcode = line.new_ean
                assigned_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Códigos EAN Asignados',
                'message': f'{assigned_count} códigos EAN asignados correctamente',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_refresh_list(self):
        """Refresh the list of products without EAN"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'assign.ean.mass.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }


class AssignEanMassWizardLine(models.TransientModel):
    _name = 'assign.ean.mass.wizard.line'
    _description = 'Mass EAN Assignment Line'

    wizard_id = fields.Many2one(
        'assign.ean.mass.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product Variant',
        required=True,
        readonly=True
    )
    product_name = fields.Char(
        string='Product',
        readonly=True
    )
    product_category = fields.Char(
        string='Category',
        readonly=True
    )
    current_ean = fields.Char(
        related='product_id.barcode',
        string='Current EAN',
        readonly=True
    )
    new_ean = fields.Char(
        string='Scan EAN',
        help='Scan or enter the EAN code for this variant'
    )

    @api.onchange('new_ean')
    def _onchange_new_ean(self):
        """Validate EAN and auto-move to next line"""
        if self.new_ean:
            # Check if EAN already exists
            existing = self.env['product.product'].search([
                ('barcode', '=', self.new_ean),
                ('id', '!=', self.product_id.id)
            ], limit=1)
            
            if existing:
                return {
                    'warning': {
                        'title': 'EAN Duplicado',
                        'message': f'El código EAN {self.new_ean} ya está asignado a: {existing.display_name}'
                    }
                }
