# -*- coding: utf-8 -*-
# Developed by Bizople Solutions Pvt. Ltd.
# See LICENSE file for full copyright and licensing details.

import odoo
from odoo import http , _
from odoo.http import request
from odoo.exceptions import UserError
import json
import datetime
import pytz
import base64
from dateutil.relativedelta import relativedelta
import calendar
from odoo.addons.website_sale.controllers.main import WebsiteSale

class Appointment(http.Controller):
    @http.route([
        '/table/reservation',
    ], type='http', auth="public", website=True, sitemap=True)
    def table_reservation(self, **kwargs):
        user_id = request.env.user
        company_id = request.env.company
        if user_id.id != request.env.ref('base.public_user').id:
            request.session['timezone'] = user_id.tz if user_id.tz else 'UTC'
            pos_id = request.env['pos.config'].sudo().search([('module_pos_restaurant','=', True),('company_id','=', company_id.id),('website_publish', '=', True)])

            requested_tz = pytz.timezone(request.session['timezone'])
            today = requested_tz.fromutc(datetime.datetime.utcnow())

            start_date = datetime.datetime.strptime(today.strftime("%Y-%m-%d"), "%Y-%m-%d")
            end_date = start_date + datetime.timedelta(days=pos_id.sudo().max__allow_reservation_days)

            delta = end_date - start_date  # as timedelta
            days = [start_date + datetime.timedelta(days=i) for i in range(delta.days + 1)]

            months = []
            monthly_dates = []
            for d in days:
                if not d.strftime("%B") in months:
                    months.append(d.strftime("%B"))
            for m in months:
                dates = []
                for d in days:
                    if m == d.strftime("%B"):
                        dates.append(d)
                month_dates = {
                    'month': m,
                    'dates': dates,
                }
                monthly_dates.append(month_dates)
            return request.render("website_table_reservation.table_reservation_info",{
                'monthly_dates': monthly_dates,
                })
        else:
            return request.redirect("/web/login")


    @http.route(['/get/slot'], type='http', auth='public', website=True)
    def get_slot(self, **post):
        company_id = request.env.company
        user_id = request.env.user
        user_tz_offset = user_id.tz_offset
        user_tz_offset_time = datetime.datetime.strptime(user_tz_offset, '%z')

        selected_date = post.get('selected_date')
        selected_date_day = post.get('selected_date_day')
        slot_date = datetime.datetime.strptime(selected_date, "%Y-%m-%d")

        pos_id = request.env['pos.config'].sudo().search([
            ('module_pos_restaurant','=', True),
            ('company_id','=', company_id.id),
            ('website_publish', '=', True)
    	])
        slot_interval = pos_id.sudo().reservation_duration
        total_minutes = slot_interval * 60
        total_hours, total_minutes = divmod(total_minutes, 60)
        total_time = "%02d:%02d"%(total_hours,total_minutes)

        slot_interval_str = selected_date + ' ' + str(total_time)
        slot_interval_datetime = datetime.datetime.strptime(slot_interval_str, "%Y-%m-%d %H:%M")

        slot_interval_hour = slot_interval_datetime.strftime("%H")
        slot_interval_min = slot_interval_datetime.strftime("%M")

        day_slots = []
        for ts in pos_id.table_reservation_slot_ids:
            if ts.weekday == selected_date_day:

                min_allow_time = pos_id.sudo().min__allow_reservation_hours
                min_allow_total_minutes = min_allow_time * 60
                min_allow_total_hours, min_allow_total_minutes = divmod(min_allow_total_minutes, 60)
                min_allow_total_time = "%02d:%02d"%(min_allow_total_hours,min_allow_total_minutes)

                today = datetime.datetime.today() + user_tz_offset_time.utcoffset() + relativedelta(hours=min_allow_total_hours, minutes=min_allow_total_minutes)
                today_str = today.strftime("%Y-%m-%d %H.%M")
                today = datetime.datetime.strptime(today_str, "%Y-%m-%d %H.%M")

                start_hour = int(ts.start_hour)
                start_minute = int(round((ts.start_hour - start_hour) * 60, 2))
                start_hour_str = selected_date + ' ' + str(start_hour)+':'+str(start_minute)
                start_hour_datetime = datetime.datetime.strptime(start_hour_str, "%Y-%m-%d %H:%M")

                end_hour = int(ts.end_hour)
                end_minute = int(round((ts.end_hour - end_hour) * 60, 2))
                end_hour_str = selected_date + ' ' + str(end_hour)+':'+str(end_minute)
                end_hour_datetime = datetime.datetime.strptime(end_hour_str, "%Y-%m-%d %H:%M")

                while (start_hour_datetime)<(end_hour_datetime):
                    if start_hour_datetime > today:
                        end_slot_datetime = start_hour_datetime + relativedelta(hours=int(slot_interval_hour), minutes=int(slot_interval_min))
                        slot_dict = {
                            'start_hour': start_hour_datetime.strftime("%H:%M"),
                            'end_hour': end_slot_datetime.strftime("%H:%M"),
                        }
                        day_slots.append(slot_dict)
                    start_hour_datetime = start_hour_datetime + relativedelta(hours=int(slot_interval_hour), minutes=int(slot_interval_min))

        value = {
            'day_slots': day_slots,
            'selected_date': selected_date,
        }

        return request.render("website_table_reservation.table_reservation_slot", value)

    @http.route(['/get/tables'], type='http', auth='public', website=True)
    def get_table(self, **post):
        company_id = request.env.company
        selected_date = post.get('selected_date')
        slot_list = json.loads(post.get('slot_list'))

        user_id = request.env.user
        user_tz_offset = user_id.tz_offset
        user_tz_offset_time = datetime.datetime.strptime(user_tz_offset, '%z')

        total_reserverd_table = request.env['table.reservation']

        for sl in slot_list:
            start_hour = sl['start_hour']
            end_hour = sl['end_hour']

            start_date_str = selected_date + ' ' + start_hour
            start_date_datetime = datetime.datetime.strptime(start_date_str, "%Y-%m-%d %H:%M")
            new_start_date_datetime = start_date_datetime - user_tz_offset_time.utcoffset()

            end_date_str = selected_date + ' ' + end_hour
            end_date_datetime = datetime.datetime.strptime(end_date_str, "%Y-%m-%d %H:%M")
            new_end_date_datetime = end_date_datetime - user_tz_offset_time.utcoffset()

            reserved_slots = request.env['time.slot.line'].sudo().search([
                '|','|','|','|','|','|',
                '&', ('start_date', '<', new_start_date_datetime), ('end_date', '>', new_end_date_datetime),
                '&', ('start_date', '<', new_end_date_datetime), ('end_date', '>', new_end_date_datetime),
                '&', ('start_date', '<', new_start_date_datetime), ('end_date', '>', new_start_date_datetime),
                '&', ('start_date', '=', new_start_date_datetime), ('end_date', '=', new_end_date_datetime),
                '&', ('start_date', '>', new_start_date_datetime), ('end_date', '<', new_end_date_datetime),
                '&', ('start_date', '>', new_start_date_datetime), ('end_date', '=', new_end_date_datetime),
                '&', ('start_date', '=', new_start_date_datetime), ('end_date', '<', new_end_date_datetime),
                ('order_id','!=', False),
                ('order_id.state', 'not in', ['draft','sent'])
            ])

            for reserved_slot in reserved_slots:
                total_reserverd_table = total_reserverd_table + reserved_slot.order_id.table_reservation_id
        
        pos_id = request.env['pos.config'].sudo().search([
            ('module_pos_restaurant','=', True),
            ('company_id','=', company_id.id),
            ('website_publish', '=', True)
        ])

        value = {
            'pos_id': pos_id,
            'reserved_tables': total_reserverd_table,
            'slot_list': slot_list,
            'slot_list_length': len(slot_list),
            'selected_date': selected_date,
        }

        return request.render("website_table_reservation.table_preview", value)

    @http.route(['/book/table'], type='http', auth="public", methods=['POST'], website=True)
    def cart_update(self, price=0, **kw):
        sale_order = request.website.sale_get_order(force_create=True)
        user_id = request.env.user
        user_tz_offset = user_id.tz_offset
        user_tz_offset_time = datetime.datetime.strptime(user_tz_offset, '%z')
        company_id = request.env.company

        start_date = kw.get('start_date')
        end_date = kw.get('end_date')
        selected_table_ids = json.loads(kw.get('selected_table_ids'))
        selected_time_slots = json.loads(kw.get('selected_time_slots'))

        tuple_list = [[5,0]]

        for slot in selected_time_slots:
            slot_start_date = datetime.datetime.strptime(slot['start_date'], '%Y-%m-%d %H:%M') - user_tz_offset_time.utcoffset()

            slot_end_date = datetime.datetime.strptime(slot['end_date'], '%Y-%m-%d %H:%M') - user_tz_offset_time.utcoffset()
            
            tuple_list.append((0, 0, {'start_date': slot_start_date, 'end_date': slot_end_date}))

        start_date_datetime = datetime.datetime.strptime(start_date, "%Y-%m-%d %H:%M")
        end_date_datetime = datetime.datetime.strptime(end_date, "%Y-%m-%d %H:%M")

        new_start_date_datetime = start_date_datetime - user_tz_offset_time.utcoffset()
        new_end_date_datetime = end_date_datetime - user_tz_offset_time.utcoffset()

        product = request.env['product.product'].search([('booking_product','=',True)],limit=1)
        pos_id = request.env['pos.config'].sudo().search([
            ('module_pos_restaurant','=', True),
            ('company_id','=', company_id.id),
            ('website_publish', '=', True)
        ])

        sale_order.sudo().write({
            'order_line': [(5,0,0)]
        })

        sale_order.sudo().write({
            'partner_id': user_id.partner_id.id,
            'partner_invoice_id': user_id.partner_id.id,
            'partner_shipping_id': user_id.partner_id.id,
            'order_line': [(0,0, {
                'product_id':product.id,
                'product_uom_qty': 1,
                'qty_delivered': 0,
                'price_unit': price,
            })],
            'pos_id': pos_id.id,
            'reserve_start': new_start_date_datetime,
            'reserve_end': new_end_date_datetime,
            'booked_table_ids': [(6, 0, selected_table_ids)],
            'selected_time_slots': tuple_list,
        })
        return request.redirect("/shop/cart")

class WebsiteSale(WebsiteSale):
    @http.route(['/shop/confirm_order'], type='http', auth="public", website=True, sitemap=False)
    def confirm_order(self, **post):
        order = request.website.sale_get_order()
        redirection = self.checkout_redirection(order) or self.checkout_check_address(order)
        if redirection:
            return redirection

        order._compute_fiscal_position_id()
        order.order_line._compute_tax_id()
        request.session['sale_last_order_id'] = order.id
        request.website.sale_get_order()
        extra_step = request.website.viewref('website_sale.extra_info_option')
        if extra_step.active:
            return request.redirect("/shop/extra_info")

        return request.redirect("/shop/payment")
