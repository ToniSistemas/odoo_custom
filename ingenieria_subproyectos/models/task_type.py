from odoo import fields, models


class ProjectTaskType(models.Model):
    _name = 'project.task.type.category'
    _description = 'Tipo de tarea'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    task_type_id = fields.Many2one(
        'project.task.type.category',
        string='Tipo de tarea',
        ondelete='restrict',
        index=True,
    )