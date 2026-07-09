from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    is_parent_project = fields.Boolean(
        string='Es proyecto principal',
        default=False,
        help='Activa esta opción para usar este proyecto como contenedor de subproyectos.',
    )
    parent_id = fields.Many2one(
        'project.project',
        string='Proyecto principal',
        ondelete='restrict',
        index=True,
        domain="[('is_parent_project', '=', True), ('id', '!=', id)]",
    )
    child_ids = fields.One2many(
        'project.project',
        'parent_id',
        string='Subproyectos',
    )
    child_count = fields.Integer(
        string='Nº Subproyectos',
        compute='_compute_child_count',
        store=True,
    )
    hierarchy_template_id = fields.Many2one(
        'project.hierarchy.template',
        string='Plantilla jerarquia',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='Plantilla para generar subproyectos, tareas y subtareas de forma automatica.',
    )

    @api.depends('child_ids')
    def _compute_child_count(self):
        for project in self:
            project.child_count = len(project.child_ids)

    @api.constrains('parent_id')
    def _check_no_cycles(self):
        if not self._check_recursion('parent_id'):
            raise ValidationError(_(
                'No se puede crear una referencia circular entre proyectos.'
            ))

    @api.constrains('parent_id', 'is_parent_project', 'company_id')
    def _check_hierarchy_business_rules(self):
        for project in self:
            # A child project can only point to projects explicitly marked as parents.
            if project.parent_id and not project.parent_id.is_parent_project:
                raise ValidationError(_(
                    'El proyecto principal seleccionado debe estar marcado como "Es proyecto principal".'
                ))

            # A project cannot be both parent container and child at the same time.
            if project.is_parent_project and project.parent_id:
                raise ValidationError(_(
                    'Un proyecto marcado como principal no puede tener proyecto principal asignado.'
                ))

            # Parent and child must stay in the same company to avoid cross-company leakage.
            if (
                project.parent_id
                and project.company_id
                and project.parent_id.company_id
                and project.company_id != project.parent_id.company_id
            ):
                raise ValidationError(_(
                    'El proyecto y su proyecto principal deben pertenecer a la misma compañía.'
                ))

    def action_view_subprojects(self):
        """Abre el kanban de subproyectos de este proyecto principal."""
        self.ensure_one()
        kanban_view = self.env.ref(
            'ingenieria_subproyectos.view_subproject_kanban',
            raise_if_not_found=False,
        )
        return {
            'type': 'ir.actions.act_window',
            'name': 'Subproyectos — %s' % self.name,
            'res_model': 'project.project',
            'view_mode': 'kanban,list,form',
            'views': [
                (kanban_view.id if kanban_view else False, 'kanban'),
                (False, 'list'),
                (False, 'form'),
            ],
            'domain': [('parent_id', '=', self.id)],
            'context': {'default_parent_id': self.id},
        }

    def action_open_tasks(self):
        """Abre las tareas de este subproyecto (flujo estándar de Odoo)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'project.task',
            'view_mode': 'kanban,list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def _collect_stage_ids(self, base_stage_ids, task_templates):
        stage_ids = set(base_stage_ids)
        for task_line in task_templates:
            if task_line.stage_id:
                stage_ids.add(task_line.stage_id.id)
            for subtask_line in task_line.subtask_template_ids:
                if subtask_line.stage_id:
                    stage_ids.add(subtask_line.stage_id.id)
        return stage_ids

    def _create_tasks_from_templates(self, project, task_templates):
        Task = self.env['project.task'].sudo()
        for task_line in task_templates:
            task_vals = {
                'name': task_line.name,
                'project_id': project.id,
                'description': task_line.description or False,
            }
            if task_line.stage_id:
                task_vals['stage_id'] = task_line.stage_id.id

            task = Task.create(task_vals)
            for subtask_line in task_line.subtask_template_ids:
                subtask_vals = {
                    'name': subtask_line.name,
                    'project_id': project.id,
                    'parent_id': task.id,
                    'description': subtask_line.description or False,
                }
                if subtask_line.stage_id:
                    subtask_vals['stage_id'] = subtask_line.stage_id.id
                Task.create(subtask_vals)

    def action_apply_hierarchy_template(self):
        self.ensure_one()
        if not self.is_parent_project:
            raise ValidationError(_(
                'Solo puedes aplicar una plantilla en un proyecto principal.'
            ))
        if not self.hierarchy_template_id:
            raise ValidationError(_(
                'Selecciona una plantilla antes de aplicarla.'
            ))

        template = self.hierarchy_template_id
        if template.company_id and self.company_id and template.company_id != self.company_id:
            raise ValidationError(_(
                'La plantilla seleccionada debe pertenecer a la misma compania que el proyecto principal.'
            ))

        Project = self.env['project.project'].sudo()

        main_task_templates = template.main_task_template_ids.sorted(lambda x: (x.sequence, x.id))
        main_stage_ids = self._collect_stage_ids(template.main_task_stage_ids.ids, main_task_templates)
        if main_stage_ids:
            self.write({'type_ids': [(6, 0, list(main_stage_ids))]})

        self._create_tasks_from_templates(self, main_task_templates)

        for sub_template in template.subproject_template_ids.sorted(lambda x: (x.sequence, x.id)):
            subproject = Project.create({
                'name': sub_template.name,
                'is_parent_project': False,
                'parent_id': self.id,
                'company_id': self.company_id.id,
                'user_id': sub_template.user_id.id or False,
            })
            sub_task_templates = sub_template.task_template_ids.sorted(lambda x: (x.sequence, x.id))
            sub_stage_ids = self._collect_stage_ids(sub_template.task_stage_ids.ids, sub_task_templates)
            if sub_stage_ids:
                subproject.write({'type_ids': [(6, 0, list(sub_stage_ids))]})
            self._create_tasks_from_templates(subproject, sub_task_templates)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Plantilla aplicada'),
                'message': _('Se generaron subproyectos, tareas y subtareas desde la plantilla seleccionada.'),
                'sticky': False,
                'type': 'success',
            },
        }
