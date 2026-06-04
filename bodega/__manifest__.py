{
    'name': 'Bodega',
    'version': '1.0.0',
    'summary': 'Gestión de bodega de vinos: añadas, variedades y parámetros químicos',
    'description': """
        Gestión de Bodega
        =================
        * Añada (año de cosecha) en lotes de stock
        * Variedades de uva por lote
        * Parámetros químicos (pH, acidez, SO2, alcohol, etc.) por lote
        * Catálogo de variedades de uva
        * Catálogo de tipos de parámetros químicos con rangos recomendados
    """,
    'category': 'Inventory/Bodega',
    'author': 'ToniSistemas',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/bodega_variedad_views.xml',
        'views/bodega_tipo_parametro_views.xml',
        'views/stock_lot_views.xml',
        'views/bodega_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
