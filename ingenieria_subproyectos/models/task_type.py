from odoo import _, fields, models


class ProjectTaskType(models.Model):
    _name = 'project.task.type.category'
    _description = 'Tipo de tarea'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    description_template_id = fields.Many2one(
        'project.task.description.template',
        string='Plantilla de descripción',
        ondelete='set null',
    )


class ProjectTask(models.Model):
    _inherit = 'project.task'

    task_type_id = fields.Many2one(
        'project.task.type.category',
        string='Tipo de tarea',
        ondelete='restrict',
        index=True,
    )

    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        for node in arch.xpath("//field[@name='type_id']"):
            node.set('string', _('Tipo de proyecto'))
        return arch, view