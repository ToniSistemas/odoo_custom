# -*- coding: utf-8 -*-
# Developed by Bizople Solutions Pvt. Ltd.
# See LICENSE file for full copyright and licensing details.
{
    'name': 'POS Table Reservation From Website',
    'category': 'Website',
    'version': '16.0.1.0',
    'author': 'Bizople Solutions Pvt. Ltd.',
    'website': 'https://www.bizople.com',
    'summary': 'Website Table Reservation',
    'description': """Website Table Reservation""",
    'depends': [
        'point_of_sale',
        'website_sale',
        'pos_restaurant',
        'sale',
    ],

    'assets': {
        'web.assets_frontend': [
            '/website_table_reservation/static/src/js/table_reservation.js',
            '/website_table_reservation/static/src/scss/table_reservation.scss',
        ],
    },

    'data': [
        'security/ir.model.access.csv',
        'data/menu_data.xml',
        'data/product_data.xml',
        'views/restaurant_table_view.xml',
        'views/sale_order_view.xml',
        'views/table_reservation_view.xml',
        'views/table_reservation_slot_view.xml',
        'views/pos_config_view.xml',
        'views/pos_floor_view.xml',
        'views/product_view.xml',
        'views/table_reservation_template.xml',
        'report/sale_report_template.xml',
    ],
    'images': [
        'static/description/banner.png'
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'OPL-1',
    'price': 200,
    'currency': 'EUR',
}
