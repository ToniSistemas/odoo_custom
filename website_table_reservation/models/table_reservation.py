# -*- coding: utf-8 -*-
# Part of Odoo Module Developed by Bizople Solutions Pvt. Ltd.
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo import http , _
from odoo.http import request
from odoo.exceptions import UserError, ValidationError


class TableReservation(models.Model):
    _name = "table.reservation"
    _description = "Table Reservation"

    name = fields.Char("Name", compute='_compute_name')
    customer_id = fields.Many2one('res.partner',string="Customer")
    order_id = fields.Many2one('sale.order',string="Order")
    pos_id = fields.Many2one('pos.config',string="Point Of Sale")
    table_ids = fields.Many2many("restaurant.table",string="Table")
    start = fields.Datetime(string="Starting At")
    end = fields.Datetime(string="Ending At")
    floor = fields.Many2one('restaurant.floor', string="Floor Plan", compute='_compute_floor')
    selected_time_slots = fields.One2many('time.slot.line','reservation_id',related="order_id.selected_time_slots", string='Selected Time Slots')

    @api.depends('customer_id')
    def _compute_name(self):
        for reservation in self:
            customer_name = reservation.customer_id.name
            reservation.name = 'Booking for %s' % customer_name

    @api.depends('table_ids')
    def _compute_floor(self):
        for reservation in self:
            floor_id = reservation.table_ids.floor_id.id
            reservation.floor = floor_id
            
class PosConfig(models.Model):
    _inherit = "pos.config"

    table_reservation_ids = fields.One2many('table.reservation','pos_id',string='Table Reservation')
    website_publish = fields.Boolean("Publish on Website")
    reservation_duration = fields.Float('Reservation Duration', default=1.0)
    min__allow_reservation_hours = fields.Float('Reserve before (hours)', required=True, default=1.0)
    max__allow_reservation_days = fields.Integer('Reserve not after (days)', required=True, default=30)
    table_reservation_slot_ids = fields.One2many('table.reservation.slot','pos_id',string='Table Reservation Slot')

    @api.constrains('website_publish')
    def _check_only_one_website_publish(self):
        active_website_publish = self.env['pos.config'].search([
            ('website_publish', '=', True),
        ])
        if len(active_website_publish) > 1:
            raise ValidationError(_("Only one Point of Sale can be allowed on website for table reservation."))


class RestaurantTable(models.Model):
    _inherit = "restaurant.table"

    price = fields.Float('Reservation Price', digits='Product Price')
    so_id = fields.Many2one('sale.order',string="Sale Order")
    # currency_id = fields.Many2one('res.currency', 'Currency', compute='_compute_currency_id')


class SaleOrder(models.Model):
    _inherit = "sale.order"

    table_reservation_id = fields.Many2one('table.reservation',string="Table Reservation", readonly=True)
    pos_id = fields.Many2one('pos.config',string="Point Of Sale")
    reserve_start = fields.Datetime(string="Starting At")
    reserve_end = fields.Datetime(string="Ending At")
    booked_table_ids = fields.One2many('restaurant.table','so_id',string='Booked Tables')
    selected_time_slots = fields.One2many('time.slot.line','order_id', string='Selected Time Slots')
    

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:

            booked_tables = order.booked_table_ids
            if booked_tables:
                table_reservation = request.env['table.reservation']
                booked_tables_id = []
                for table in booked_tables:
                    booked_tables_id.append(table.id)
                table_customer_id = order.partner_id.id
                table_pos_id = order.pos_id.id
                floor_id = booked_tables[0].floor_id.id

                booking_details = table_reservation.sudo().create({
                    'customer_id': table_customer_id,
                    'order_id': order.id,
                    'pos_id': table_pos_id,
                    'floor': floor_id,
                    'table_ids': [(6, 0, booked_tables_id)],
                })

                order.sudo().write({
                    'table_reservation_id':  booking_details.id,
                })

        return res


class ProductTemplate(models.Model):
    _inherit = "product.template"

    booking_product = fields.Boolean("Is Booking Product")

class TimeSlotLine(models.Model):
    _name = "time.slot.line"
    _description = "Time Slot Line"
    _rec_name = "start_date"

    order_id = fields.Many2one('sale.order', string = 'Order')
    start_date = fields.Datetime(string="Start date")
    end_date = fields.Datetime(string="End date")
    reservation_id = fields.Many2one('sale.order', string = 'Reservation')
