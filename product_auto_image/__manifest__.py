{
    'name': 'Product Auto Image',
    'version': '19.0.1.0.0',
    'summary': 'Busca y descarga imágenes de producto por referencia de fabricante o EAN mediante búsqueda web',
    'description': """
Búsqueda automática de imágenes de producto
===========================================

* Prioridad 1: marca + referencia del fabricante.
* Prioridad 2: EAN/GTIN de las variantes.
* Localiza fichas de producto mediante un buscador web público (proveedor intercambiable),
  extrae la imagen principal (og:image, JSON-LD, galería) y la valida antes de guardarla.
* Puntuación de confianza, modo simulación, procesamiento en lote controlado y registro.
""",
    'category': 'Sales/Products',
    'author': 'Toni',
    'license': 'LGPL-3',
    'depends': ['product'],
    'external_dependencies': {
        # Todas forman parte de los requisitos estándar de Odoo 19.
        'python': ['requests', 'lxml', 'Pillow'],
    },
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_config_parameter_data.xml',
        'data/ir_cron_data.xml',
        'views/image_log_views.xml',
        'views/product_template_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/auto_image_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
}
