odoo.define('website_table_reservation.table_reservation', function(require) {
    'use strict';

    require('web.dom_ready');
    var publicWidget = require('web.public.widget');
    const wUtils = require('website.utils');
    var ajax = require('web.ajax');
    var core = require('web.core');
    var rpc = require('web.rpc');
    var _t = core._t;

    publicWidget.registry.table_reservation = publicWidget.Widget.extend({
        selector: ".table_reservation",
        events: {
            'click .select_slot': '_getslot',
            'click .slot-btn': '_selectslot',
            'click .confirm_slot_btn .btn': '_gettable',
            'click .table_preview': '_selecttable',
            'click .confirm_booking': '_confirmbooking',
        },

        start: function() {
            $('#wrapwrap').scroll(function() {
                var header_height = $('header').height()
                if ($(this).scrollTop() > 100) {
                    $('.slot_info').css('position','sticky')
                    $('.slot_info').css('top',header_height.toString() + 'px')
                } else {
                    $('.slot_info').css('position','unset')
                    $('.slot_info').css('top','unset')
                }
            });
        },

        _getslot: function(ev) {
            $('.select_slot').removeClass('selected')
            $(ev.currentTarget).addClass('selected')
            var selected_date = $(ev.currentTarget).attr('full_date') || ''
            var selected_date_day = $(ev.currentTarget).find('.day').attr('full_day_number')

            if (selected_date && selected_date_day) {
                $.get("/get/slot", {
                    'selected_date': selected_date,
                    'selected_date_day': selected_date_day,
                }).then(function(data) {
                    if (data) {
                        $('.table_reservation_availabilities').empty()
                        $('.table_reservation_availabilities').append(data)
                    }
                });
            }
        },
        _selectslot: function(ev) {
            $(ev.currentTarget).toggleClass("selected");

            var is_time_selected = $('.table_reservation_availabilities .slot-btn.selected')

            if (is_time_selected.length) {
                $('.table_reservation_availabilities .confirm_slot_btn .btn').removeClass('disabled')
            } else {
                $('.table_reservation_availabilities .confirm_slot_btn .btn').addClass('disabled')
            }
        },
        _gettable: function(ev) {
            var selected_slots = $('.slot-btn.selected')
            var slot_list = []

            $(selected_slots).each(function(ev){
                var slot_hours = {
                    'start_hour': $(this).find('.start_hour').text(),
                    'end_hour': $(this).find('.end_hour').text(),
                }
                slot_list.push(slot_hours)

            });
            var selected_date = $(ev.currentTarget).parents('.table_reservation_availabilities').find('.selected_date').text()
            var start_hour = $(selected_slots).first().find('.start_hour').text()
            var end_hour = $(selected_slots).last().find('.end_hour').text()

            $.get("/get/tables", {
                'selected_date': selected_date,
                'slot_list': JSON.stringify(slot_list),
            }).then(function(data) {
                if (data) {
                    $('.table_reservation').empty()
                    $('.table_reservation').append(data)
                    
                }
            });
        },
        _selecttable: function(ev) {
            $(ev.currentTarget).toggleClass("selected");
            $(ev.currentTarget).parents(".available_tables").find('.floor_plan').addClass('disabled')
            $(ev.currentTarget).parents(".floor_plan").addClass('selected').removeClass('disabled')


            var total_slots = $('.slot_info .slot_count').text()
            var selected_tables = $('.table_preview.selected')

            if (selected_tables.length === 0) {
                $(ev.currentTarget).parents(".available_tables").find('.floor_plan').removeClass('disabled selected')
                $('.booking_amount .confirm_booking').addClass('disabled')
            } else {
                $('.booking_amount .confirm_booking').removeClass('disabled')
            }
            var selected_tables_length = selected_tables.length
            var total_table_amount = 0
            
            $(selected_tables).each(function (ev) {
                var table_price = $(this).find('.table_price').text()
                total_table_amount = total_table_amount + parseFloat(table_price)
            });
            
            var total_payable_amount = total_table_amount * parseInt(total_slots)
            
            $('.booking_amount .table_numbers').text(selected_tables_length)
            $('.booking_amount .booking_price').text(total_payable_amount.toFixed(2))
            
        },

        _confirmbooking: function(ev) {

            var price = $('.booking_amount .booking_price').text()
            var selected_date = $('.select_date span').text()
            var selected_time_slots = $('.slot_time p')
            
            var selected_slots_dicts = [];
            selected_time_slots.each(function () {
                var start_hour = $(this).find('.start_hour').text();
                var end_hour = $(this).find('.end_hour').text();
        
                var formattedDate = $('.select_date span').text(); 
            
                var timeSlotDict = {
                    'start_date': formattedDate + ' ' + start_hour,
                    'end_date': formattedDate + ' ' + end_hour
                };
        
                selected_slots_dicts.push(timeSlotDict);
            });

            var start_time = $(selected_time_slots).first().find('.start_hour').text()
            var end_time = $(selected_time_slots).last().find('.end_hour').text()

            var start_date = selected_date + ' ' + start_time
            var end_date = selected_date + ' ' + end_time

            var selected_tables = $('.table_preview.selected')
            var selected_table_ids = []
            $(selected_tables).each(function(ev){
                var table_id = $(this).attr('table_id')
                selected_table_ids.push(parseInt(table_id))
            });

            var params = {
                'price': price,
                'start_date': start_date,
                'end_date': end_date,
                'selected_table_ids': JSON.stringify(selected_table_ids),
                'selected_time_slots': JSON.stringify(selected_slots_dicts),
            }
            return wUtils.sendRequest('/book/table', params);
        },  

    });
});