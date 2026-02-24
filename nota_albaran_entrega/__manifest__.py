{
    'name': 'Nota Albarán Entrega',
    'version': '17.0.1.0.0',
    'summary': 'Gestiona notas de albarán para entregas',
    'category': 'Warehouse',
    'author': 'Toni',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['base','stock','sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/nota_albaran_views.xml',
        'views/stock_picking_views.xml',
        'views/report_picking_templates.xml',
    ],
    'installable': True,
    'application': False,
}
