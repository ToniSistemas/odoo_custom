# -*- coding: utf-8 -*-

from odoo import fields, models,tools,api
import logging

class pos_config(models.Model):
    _inherit = 'pos.config' 

    allow_open_cash_d = fields.Boolean('Open Cash Drawer',default=True)

