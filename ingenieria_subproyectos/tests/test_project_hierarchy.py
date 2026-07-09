from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import SavepointCase


@tagged('post_install', '-at_install')
class TestProjectHierarchy(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Project = cls.env['project.project'].sudo()
        cls.Company = cls.env['res.company'].sudo()
        cls.company_a = cls.env.company
        cls.company_b = cls.Company.create({'name': 'Hierarchy Test Company'})

    @classmethod
    def _create_project(cls, **vals):
        data = {'name': vals.pop('name', 'Project')}
        data.update(vals)
        return cls.Project.create(data)

    def test_parent_must_be_marked_as_parent_project(self):
        candidate_parent = self._create_project(
            name='Candidate Parent',
            company_id=self.company_a.id,
        )

        with self.assertRaises(ValidationError):
            self._create_project(
                name='Child with invalid parent',
                parent_id=candidate_parent.id,
                company_id=self.company_a.id,
            )

    def test_parent_project_cannot_have_parent(self):
        parent_a = self._create_project(
            name='Parent A',
            is_parent_project=True,
            company_id=self.company_a.id,
        )
        parent_b = self._create_project(
            name='Parent B',
            is_parent_project=True,
            company_id=self.company_a.id,
        )

        with self.assertRaises(ValidationError):
            parent_a.write({'parent_id': parent_b.id})

    def test_parent_and_child_must_share_company(self):
        parent = self._create_project(
            name='Parent A company',
            is_parent_project=True,
            company_id=self.company_a.id,
        )

        with self.assertRaises(ValidationError):
            self._create_project(
                name='Child B company',
                parent_id=parent.id,
                company_id=self.company_b.id,
            )
