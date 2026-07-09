{
    'name': 'Ingeniería - Subproyectos',
    'version': '19.0.1.0.0',
    'summary': 'Jerarquía de proyectos principales y subproyectos para empresas de ingeniería',
    'description': """
        Permite organizar proyectos en una jerarquía de dos niveles:

        - Proyecto principal: agrupa varios subproyectos relacionados
        - Subproyectos: cada uno con sus propias tareas, etapas y equipo

        Vista Kanban en dos niveles:
          1. Kanban de proyectos principales → muestra nº de subproyectos
          2. Kanban de subproyectos          → muestra nº de tareas
          3. Vista estándar de Odoo por subproyecto (tareas, subtareas, horas)
    """,
    'author': 'Equipo Ingenieria',
    'category': 'Project',
    'depends': ['project'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_project_views.xml',
        'views/project_template_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
