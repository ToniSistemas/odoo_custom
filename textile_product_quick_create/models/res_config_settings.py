from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    textile_price_coefficient = fields.Float(
        related='company_id.textile_price_coefficient', readonly=False)
    textile_price_ending = fields.Float(
        related='company_id.textile_price_ending', readonly=False)
