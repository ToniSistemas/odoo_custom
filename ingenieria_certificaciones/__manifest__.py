{
    'name': 'Ingeniería - Certificaciones de Obra',
    'version': '19.0.1.0.0',
    'summary': 'Gestión de certificaciones de obra y facturación por grados de avance',
    'description': """
        Módulo para empresas de ingeniería que necesitan emitir certificaciones de obra
        vinculadas a pedidos de venta y proyectos, con facturación por períodos.

        Permite:
        - Crear certificaciones vinculadas a un proyecto y a un pedido de venta (contrato)
        - Introducir manualmente las mediciones de cada partida (kg, m², ud., horas...)
        - Calcular acumulados certificados anteriores y pendientes por partida
        - Generar la factura de Odoo directamente desde la certificación
        - Imprimir el documento formal de certificación en PDF
    """,
    'author': '',
    'category': 'Project',
    'depends': ['mail', 'project', 'sale_project', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/ingenieria_certificacion_views.xml',
        'views/menu.xml',
        'reports/report_certificacion.xml',
        'reports/report_certificacion_template.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
