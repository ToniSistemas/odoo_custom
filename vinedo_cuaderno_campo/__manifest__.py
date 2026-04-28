{
    'name': 'Viñedo - Cuaderno de Campo',
    'version': '2.2.0',
    'summary': 'Cuaderno de Campo digital para viñedos: climatología, fenología, fitosanitarios, cosecha y costes',
    'description': """
        Cuaderno de Campo Digital para Viñedos
        ========================================
        * Gestión de fincas con geolocalización y parcelas SIGPAC
        * Control de variedades plantadas por finca y recinto
        * Registro meteorológico (temperaturas, precipitaciones, humedad) con valoración de riesgos
        * Seguimiento fenológico (estados BBCH de la vid)
        * Registro de añadas con análisis enológico completo (graduación, acidez, pH, densidad...)
        * Trazabilidad de cosecha con lotes, rendimiento y destino
        * Tratamientos fitosanitarios enlazados con el Registro MAPA y productos de Odoo
        * Aportaciones de minerales/abonos con enlace a productos y cálculo de costes
        * Registro de trabajos por empleado con horas
        * Registro de podas (invierno/verde)
        * Maquinaria agrícola con titular (contacto Odoo) y fecha de compra
        * Cálculo automático de costes (litros × precio, cantidad × precio)
        * Plazos de seguridad fitosanitarios y advertencias PHI
        * Autoenlace fitosanitario ↔ producto Odoo por Nº Registro / nombre
        * Integración con Tableros (spreadsheet_dashboard)
        * SIGPAC: consulta automática de recintos y superficies por coordenadas GPS
        * Informe PDF imprimible: Cuaderno de Campo completo por finca y año
        * Vistas calendario de operaciones
        * Búsquedas, agrupaciones y vistas pivot/gráfico en todos los modelos
    """,
    'category': 'Agriculture/Field Service',
    'author': 'ToniSistemas',
    'website': 'https://github.com/ToniSistemas/odoo_custom',
    'license': 'LGPL-3',
    'depends': ['base', 'hr', 'mail', 'spreadsheet_dashboard', 'product'],
    'data': [
        'security/vinedo_categories.xml',
        'security/vinedo_security.xml',
        'security/ir.model.access.csv',
        'views/vinedo_views.xml',
        'reports/vinedo_reports.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'vinedo_cuaderno_campo/static/src/js/sigpac_iframe_widget.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
