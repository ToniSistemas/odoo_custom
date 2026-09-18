{
    'name': 'Ingeniería - No solapar horas',
    'version': '19.0.1.0.0',
    'summary': 'Imputaciones por intervalos de 15 minutos sin solapes',
    'category': 'Services/Timesheets',
    'author': 'Equipo Ingenieria',
    'license': 'LGPL-3',
    'depends': ['hr_timesheet'],
    'data': [
        'views/project_task_views.xml',
        'views/hr_timesheet_views.xml',
    ],
    'installable': True,
    'application': False,
}