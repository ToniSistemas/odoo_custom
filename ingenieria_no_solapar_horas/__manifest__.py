{
    'name': 'Ingeniería - No solapar horas',
    'version': '19.0.1.1.1',
    'summary': 'Imputaciones por intervalos de 15 minutos sin solapes',
    'category': 'Services/Timesheets',
    'author': 'Equipo Ingenieria',
    'license': 'LGPL-3',
    'depends': ['hr_timesheet'],
    'data': [
        'views/project_task_views.xml',
        'views/hr_timesheet_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ingenieria_no_solapar_horas/static/src/js/timesheet_day_timeline.js',
            'ingenieria_no_solapar_horas/static/src/xml/timesheet_day_timeline.xml',
            'ingenieria_no_solapar_horas/static/src/scss/timesheet_day_timeline.scss',
        ],
    },
    'installable': True,
    'application': False,
}