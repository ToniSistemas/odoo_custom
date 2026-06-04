{
    'name': 'SILICIE Bodega',
    'version': '19.0.1.0.0',
    'summary': 'Libros contables de Impuestos Especiales (SILICIE) para bodegas',
    'description': """
        Gestión de asientos contables SILICIE para bodegas con CAE (fábricas y depósitos fiscales).
        - Nivel 1: Registro manual de asientos con todos los campos requeridos por AEAT
        - Nivel 2: Generación automática de asientos desde albaranes de entrada/salida de Odoo
        - Exportación a fichero CSV compatible con importación en SILICIE 2.0
    """,
    'author': 'ToniSistemas',
    'category': 'Inventory/Inventory',
    'depends': ['bodega', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/silicie_data.xml',
        'views/res_company_views.xml',
        'views/silicie_asiento_views.xml',
        'views/stock_picking_views.xml',
        'wizard/silicie_export_wizard.xml',
        'views/silicie_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'application': False,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
