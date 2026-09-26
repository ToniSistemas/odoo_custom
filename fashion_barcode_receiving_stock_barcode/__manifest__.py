{
    'name': 'Fashion - Asignación de EAN en App Barcode',
    'version': '19.0.1.0.0',
    'summary': 'Puente entre fashion_barcode_receiving y stock_barcode (Enterprise)',
    'author': 'Toni',
    'category': 'Inventory/Inventory',
    'depends': ['fashion_barcode_receiving', 'stock_barcode'],
    'assets': {
        'web.assets_backend': [
            'fashion_barcode_receiving_stock_barcode/static/src/**/*',
        ],
    },
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
