# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
	_inherit = 'product.template'

	product_sequence = fields.Integer(string="POS Sequence")

	@api.constrains('product_sequence')
	def _check_product_sequence(self):
		product_obj = self.search([('product_sequence','=',self.product_sequence),('id', "!=", self.id),('product_sequence','!=',0)])
		if product_obj:
			raise ValidationError(('Please change the sequence it has already been added to another product.'))