# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
    "name" : "Point of Sale Product Sequence",
    "version" : "15.0.0.0",
    "category" : "Point of Sale",
    "summary": "point of sale product sequence set pos product sequence in point of sales arrange sequence number product in pos screen user pos sequence product warning pos product sequence number validation point of sale sequence pos screen product sequence number",
    "description": """
        
        POS Product Sequence Odoo App helps users to arrange the product by sequencing in POS. User can set point of sale sequence for each product in form view. User can view arranged the product by sequencing based on the given sequence number in POS Screen. If user tries to add repeated sequence for another product, Warning raised.

    """,
    'author': 'BROWSEINFO',
    "price": 10,
    "currency": 'EUR',
    'website': 'https://www.browseinfo.com/demo-request?app=bi_pos_product_sequence&version=15&edition=Community',
    "depends" : ['base','point_of_sale'],
    "data": [
        'views/pos_product_view.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            "bi_pos_product_sequence/static/src/js/Screens/ProductScreen/ProductsWidget.js",
            "bi_pos_product_sequence/static/src/js/models.js",
        ],
    },
    'license':'OPL-1',
    'installable': True,
    'auto_install': False,
    'live_test_url':'https://www.browseinfo.com/demo-request?app=bi_pos_product_sequence&version=15&edition=Community',
    "images":['static/description/Product-Sequence-POS-Banner.gif'],
}
