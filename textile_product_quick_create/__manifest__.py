{
    'name': 'Creación rápida de productos textiles',
    'version': '19.0.1.3.1',
    'summary': 'Agiliza la creación de productos textiles desde las líneas de compra',
    'description': """
        * Al crear un producto desde una línea de compra se activan por defecto
          "Punto de venta" y "Rastrear inventario".
        * En "Atributos y variantes", al elegir un atributo se abre directamente
          la selección múltiple de sus valores.
        * Juegos de valores por atributo (p. ej. "Tallas adulto") seleccionables con un clic.
        * Precio de venta calculado desde el coste de compra con un coeficiente
          (por compañía o por categoría) y terminación de precio.
    """,
    'author': 'Toni',
    'category': 'Inventory/Purchase',
    'depends': ['purchase', 'stock', 'point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/textile_attribute_value_set_views.xml',
        'views/product_category_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'textile_product_quick_create/static/src/attribute_quick_values_field.js',
            'textile_product_quick_create/static/src/attribute_quick_values_field.xml',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
