# -*- coding: utf-8 -*-
{
    'name': 'Product Labels APLI 4x11',
    'version': '18.0.1.0.4',
    'category': 'Inventory',
    'summary': 'APLI MF-O1718 label format (4x11)',
    'depends': ['product'],
    'data': [
        'data/paperformat_data.xml',
        'report/product_label_report.xml',
        'views/product_label_template.xml',
        'views/product_label_layout_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
