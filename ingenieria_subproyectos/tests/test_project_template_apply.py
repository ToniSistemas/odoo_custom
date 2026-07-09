from odoo.tests import tagged
from odoo.tests.common import SavepointCase


@tagged('post_install', '-at_install')
class TestProjectTemplateApply(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Project = cls.env['project.project'].sudo()
        cls.Task = cls.env['project.task'].sudo()
        cls.Stage = cls.env['project.task.type'].sudo()
        cls.Template = cls.env['project.hierarchy.template'].sudo()

    def test_apply_template_creates_hierarchy(self):
        stage_todo = self.Stage.create({'name': 'To Do Template'})
        stage_exec = self.Stage.create({'name': 'Execution Template'})

        template = self.Template.create({
            'name': 'Plantilla Ingenieria Base',
            'main_task_stage_ids': [(6, 0, [stage_todo.id])],
            'main_task_template_ids': [
                (0, 0, {
                    'name': 'Arranque principal',
                    'stage_id': stage_todo.id,
                    'subtask_template_ids': [
                        (0, 0, {
                            'name': 'Checklist arranque',
                            'stage_id': stage_todo.id,
                        }),
                    ],
                }),
            ],
            'subproject_template_ids': [
                (0, 0, {
                    'name': 'Subproyecto estructura',
                    'task_stage_ids': [(6, 0, [stage_exec.id])],
                    'task_template_ids': [
                        (0, 0, {
                            'name': 'Calculo de estructura',
                            'stage_id': stage_exec.id,
                            'subtask_template_ids': [
                                (0, 0, {
                                    'name': 'Revision de cargas',
                                    'stage_id': stage_exec.id,
                                }),
                            ],
                        }),
                    ],
                }),
            ],
        })

        main_project = self.Project.create({
            'name': 'Proyecto principal A',
            'is_parent_project': True,
            'hierarchy_template_id': template.id,
        })

        main_project.action_apply_hierarchy_template()

        self.assertIn(stage_todo, main_project.type_ids)

        child = self.Project.search([
            ('parent_id', '=', main_project.id),
            ('name', '=', 'Subproyecto estructura'),
        ], limit=1)
        self.assertTrue(child)
        self.assertIn(stage_exec, child.type_ids)

        main_task = self.Task.search([
            ('project_id', '=', main_project.id),
            ('name', '=', 'Arranque principal'),
            ('parent_id', '=', False),
        ], limit=1)
        self.assertTrue(main_task)

        child_task = self.Task.search([
            ('project_id', '=', child.id),
            ('name', '=', 'Calculo de estructura'),
            ('parent_id', '=', False),
        ], limit=1)
        self.assertTrue(child_task)

        child_subtask = self.Task.search([
            ('project_id', '=', child.id),
            ('name', '=', 'Revision de cargas'),
            ('parent_id', '=', child_task.id),
        ], limit=1)
        self.assertTrue(child_subtask)
