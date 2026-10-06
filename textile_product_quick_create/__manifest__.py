{
    'name': 'Creación rápida de productos textiles',
    'version': '19.0.1.1.0',
    'summary': 'Agiliza la creación de productos textiles desde las líneas de compra',
    'description': """
        * Al crear un producto desde una línea de compra se activan por defecto
          "Punto de venta" y "Rastrear inventario".
        * En "Atributos y variantes", al elegir un atributo se abre directamente
          la selección múltiple de sus valores.
    """,
    'author': 'Toni',
    'category': 'Inventory/Purchase',
    'depends': ['purchase', 'stock', 'point_of_sale'],
    'data': [
        'views/product_template_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'textile_product_quick_create/static/src/attribute_quick_values_field.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
