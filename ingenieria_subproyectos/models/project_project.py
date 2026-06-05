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
