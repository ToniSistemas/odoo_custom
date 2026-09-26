{
    'name': 'Fashion - Asignación de EAN en Recepción',
    'version': '19.0.1.0.0',
    'summary': 'Asigna EANs desconocidos a variantes pendientes del albarán de entrada durante la recepción',
    'description': """
        Sector textil/moda: las variantes se compran sin EAN y el proveedor los
        etiqueta en fábrica. Durante la recepción, al escanear un EAN desconocido
        se muestran SOLO las variantes pendientes del albarán actual para
        asignarle el código y recibir +1 unidad en un solo paso.

        - Wizard "Asignar EAN" en la recepción (Community).
        - La app Barcode (Enterprise) se integra con el módulo puente
          fashion_barcode_receiving_stock_barcode (auto-instalable).
    """,
    'author': 'Toni',
    'category': 'Inventory/Inventory',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/fashion_barcode_assign_wizard_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
