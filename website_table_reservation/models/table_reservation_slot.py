# -*- coding: utf-8 -*-
# Part of Odoo Module Developed by Bizople Solutions Pvt. Ltd.
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class TableReservationSlot(models.Model):
    _name = "table.reservation.slot"
    _description = "Online Table Reservation : Time Slot"
    _rec_name = "weekday"
    _order = "weekday, start_hour"

    pos_id = fields.Many2one('pos.config',string="Point Of Sale")
    
    # Recurring slot
    weekday = fields.Selection([
        ('1', 'Monday'),
        ('2', 'Tuesday'),
        ('3', 'Wednesday'),
        ('4', 'Thursday'),
        ('5', 'Friday'),
        ('6', 'Saturday'),
        ('0', 'Sunday'),
    ], string='Week Day', required=True, default='1')
    start_hour = fields.Float('Starting Hour', required=True, default=11.0)
    end_hour = fields.Float('Ending Hour', required=True, default=15.0)

    @api.constrains('start_hour')
    def _check_hour(self):
        if any(slot.start_hour < 0.00 or slot.start_hour >= 24.00 for slot in self):
            raise ValidationError(_("Please enter a valid hour between 0:00 and 24:00 for your slots."))

    @api.constrains('start_hour', 'end_hour')
    def _check_delta_hours(self):
        if any(self.filtered(lambda slot: slot.start_hour >= slot.end_hour)):
            raise ValidationError(_(
                "Atleast one slot duration from start to end is invalid: a slot should end after start"
            ))