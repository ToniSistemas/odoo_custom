{
    'name': 'Viñedo - Field Service',
    'version': '2.1.6',
    'summary': 'Gestión completa de viñedos: fincas, variedades, trabajos y añadas con mapas',
    'description': """
        Gestión de Viñedos
        ==================
        * Gestión de fincas con geolocalización y polígonos en mapa
        * Control de variedades plantadas por finca
        * Registro de añadas con análisis (graduación, acidez, cantidad)
        * Tratamientos fitosanitarios y aportaciones de minerales
        * Registro de podas y trabajos por empleado
        * Búsquedas y agrupaciones avanzadas
        * Validaciones y constraints de datos
    """,
    'category': 'Agriculture/Field Service',
    'author': 'ToniSistemas',
    'website': 'https://github.com/ToniSistemas/odoo_custom',
    'license': 'LGPL-3',
    'depends': ['base', 'hr', 'mail', 'board'],
    'data': [
        'security/ir.model.access.csv',
        'views/vinedo_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'vinedo_field_service/static/src/js/sigpac_iframe_widget.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
