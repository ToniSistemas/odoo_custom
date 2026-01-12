# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    x_referencia = fields.Char(
        string='Referencia',
        related='product_id.product_tmpl_id.x_referencia',
        readonly=True,
        store=False
    )
