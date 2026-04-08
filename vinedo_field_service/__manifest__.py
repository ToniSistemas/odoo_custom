{
    'name': 'Viñedo - Field Service',
    'version': '1.0.0',
    'summary': 'Gestión sencilla de viñedos: fincas, trabajos y añadas',
    'category': 'Field Service',
    'author': 'Auto-generated',
    'depends': ['base', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/vinedo_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'vinedo_field_service/static/src/js/vinedo_map_widget.js',
            'vinedo_field_service/static/src/css/vinedo_map.css',
        ],
    },
    'installable': True,
    'application': False,
}
