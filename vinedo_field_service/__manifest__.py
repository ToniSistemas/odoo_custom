{
    'name': 'Viñedo - Field Service',
    'version': '2.1.8',
    'summary': 'Gestión completa de viñedos: fincas, costes, fitosanitarios, añadas y análisis',
    'description': """
        Gestión de Viñedos
        ==================
        * Gestión de fincas con geolocalización y parcelas SIGPAC
        * Control de variedades plantadas por finca y recinto
        * Registro de añadas con análisis enológico completo (graduación, acidez, pH, densidad...)
        * Tratamientos fitosanitarios enlazados con el Registro MAPA y productos de Odoo
        * Aportaciones de minerales/abonos con enlace a productos y cálculo de costes
        * Registro de trabajos por empleado con horas
        * Maquinaria agrícola con titular (contacto Odoo) y fecha de compra
        * Cálculo automático de costes (litros × precio, cantidad × precio)
        * Autoenlace fitosanitario ↔ producto Odoo por Nº Registro / nombre
        * Integración con Tableros (spreadsheet_dashboard)
        * SIGPAC: consulta automática de recintos y superficies por coordenadas GPS
        * Búsquedas, agrupaciones y vistas pivot/gráfico en todos los modelos
    """,
    'category': 'Agriculture/Field Service',
    'author': 'ToniSistemas',
    'website': 'https://github.com/ToniSistemas/odoo_custom',
    'license': 'LGPL-3',
    'depends': ['base', 'hr', 'mail', 'spreadsheet_dashboard', 'product'],
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
