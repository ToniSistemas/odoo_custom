# -*- coding: utf-8 -*-
{
    'name': 'Quick EAN Assignment',
    'version': '18.0.1.1.2',
    'category': 'Inventory',
    'summary': 'Assign EAN codes quickly from purchase receipts and mass assignment view',
    'description': """
        Quick EAN Assignment
        ====================
        This module provides two ways to quickly assign EAN codes to product variants:
        
        1. Direct assignment from purchase receipt lines
           - Scan or enter EAN codes directly in the receipt lines
           - Automatically assigns the EAN to the corresponding product variant
        
        2. Mass EAN assignment view
           - View all product variants without EAN codes
           - Quickly assign EAN codes to multiple variants at once
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['stock', 'purchase', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_move_line_views.xml',
        'wizard/assign_ean_wizard_views.xml',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
