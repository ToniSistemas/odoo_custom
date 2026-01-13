# -*- coding: utf-8 -*-
{
    'name': 'Product Labels 4x11',
    'version': '18.0.1.0.9',
    'category': 'Inventory',
    'summary': 'Add 4x11 product label format',
    'description': """
        Product Labels 4x11
        ===================
        Adds a new product label format with 4 columns and 11 rows.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['product', 'stock'],
    'data': [
        'data/paperformat_data.xml',
        'report/product_label_report.xml',
        'views/product_label_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
