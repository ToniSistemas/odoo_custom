from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProjectHierarchyTemplate(models.Model):
    _name = 'project.hierarchy.template'
    _description = 'Plantilla de jerarquia de proyectos'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        default=lambda self: self.env.company,
    )
    main_task_stage_ids = fields.Many2many(
        'project.task.type',
        'project_hierarchy_template_main_stage_rel',
        'template_id',
        'stage_id',
        string='Etapas de tareas del proyecto principal',
    )
    main_task_template_ids = fields.One2many(
        'project.hierarchy.template.task',
        'template_id',
        string='Tareas del proyecto principal',
    )
    subproject_template_ids = fields.One2many(
        'project.hierarchy.template.subproject',
        'template_id',
        string='Subproyectos',
    )


class ProjectHierarchyTemplateSubproject(models.Model):
    _name = 'project.hierarchy.template.subproject'
    _description = 'Plantilla de subproyecto'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Nombre subproyecto', required=True)
    template_id = fields.Many2one(
        'project.hierarchy.template',
        required=True,
        ondelete='cascade',
    )
    user_id = fields.Many2one('res.users', string='Responsable')
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        related='template_id.company_id',
        store=True,
        readonly=True,
    )
    task_stage_ids = fields.Many2many(
        'project.task.type',
        'project_hierarchy_template_sub_stage_rel',
        'subproject_template_id',
        'stage_id',
        string='Etapas de tareas del subproyecto',
    )
    task_template_ids = fields.One2many(
        'project.hierarchy.template.task',
        'subproject_template_id',
        string='Tareas',
    )


class ProjectHierarchyTemplateTask(models.Model):
    _name = 'project.hierarchy.template.task'
    _description = 'Plantilla de tarea'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Nombre tarea', required=True)
    description = fields.Html(string='Descripcion')
    template_id = fields.Many2one(
        'project.hierarchy.template',
        string='Plantilla principal',
        ondelete='cascade',
    )
    subproject_template_id = fields.Many2one(
        'project.hierarchy.template.subproject',
        string='Subproyecto de plantilla',
        ondelete='cascade',
    )
    stage_id = fields.Many2one('project.task.type', string='Etapa')
    subtask_template_ids = fields.One2many(
        'project.hierarchy.template.subtask',
        'task_template_id',
        string='Subtareas',
    )

    @api.constrains('template_id', 'subproject_template_id')
    def _check_parent_scope(self):
        for line in self:
            if bool(line.template_id) == bool(line.subproject_template_id):
                raise ValidationError(_(
                    'Cada tarea de plantilla debe pertenecer al proyecto principal o a un subproyecto, pero no a ambos.'
                ))


class ProjectHierarchyTemplateSubtask(models.Model):
    _name = 'project.hierarchy.template.subtask'
    _description = 'Plantilla de subtarea'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Nombre subtarea', required=True)
    description = fields.Html(string='Descripcion')
    stage_id = fields.Many2one('project.task.type', string='Etapa')
    task_template_id = fields.Many2one(
        'project.hierarchy.template.task',
        required=True,
        ondelete='cascade',
    )
