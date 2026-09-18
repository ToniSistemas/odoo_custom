from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import SavepointCase


@tagged('post_install', '-at_install')
class TestTimesheetIntervals(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env.user.employee_id
        cls.project = cls.env['project.project'].create({
            'name': 'Proyecto horas',
            'allow_timesheets': True,
        })
        cls.task_a = cls.env['project.task'].create({
            'name': 'Tarea A',
            'project_id': cls.project.id,
        })
        cls.task_b = cls.env['project.task'].create({
            'name': 'Tarea B',
            'project_id': cls.project.id,
        })

    def _create_timesheet(self, task, start, end):
        return self.env['account.analytic.line'].create({
            'name': 'Trabajo',
            'date': '2026-09-18',
            'employee_id': self.employee.id,
            'project_id': self.project.id,
            'task_id': task.id,
            'start_slot': f'{start:04d}',
            'end_slot': f'{end:04d}',
        })

    def test_overlapping_interval_is_rejected_across_tasks(self):
        self._create_timesheet(self.task_a, 15 * 60, 16 * 60)

        with self.assertRaises(ValidationError):
            self._create_timesheet(self.task_b, 15 * 60 + 30, 16 * 60 + 30)

    def test_adjacent_interval_is_allowed(self):
        self._create_timesheet(self.task_a, 15 * 60, 16 * 60)
        adjacent = self._create_timesheet(self.task_b, 16 * 60, 17 * 60)

        self.assertEqual(adjacent.unit_amount, 1.0)

    def test_duration_is_computed_from_slots(self):
        timesheet = self._create_timesheet(
            self.task_a,
            15 * 60,
            16 * 60 + 30,
        )

        self.assertEqual(timesheet.unit_amount, 1.5)

    def test_day_timeline_returns_occupied_interval(self):
        timesheet = self._create_timesheet(self.task_a, 15 * 60, 16 * 60)

        timeline = self.env['account.analytic.line'].get_day_timeline(
            '2026-09-18',
            self.employee.id,
        )

        self.assertIn({
            'start': 15 * 60,
            'end': 16 * 60,
            'label': self.task_a.display_name,
        }, timeline['occupied'])
        self.assertTrue(timeline['working'])

        timeline_without_current = self.env['account.analytic.line'].get_day_timeline(
            '2026-09-18',
            self.employee.id,
            timesheet.id,
        )
        self.assertFalse(timeline_without_current['occupied'])

    def test_day_timeline_accepts_many2one_formats(self):
        for employee_value in (
            self.employee.id,
            [self.employee.id, self.employee.display_name],
            {'id': self.employee.id},
            {'resId': self.employee.id},
        ):
            timeline = self.env['account.analytic.line'].get_day_timeline(
                '2026-09-18',
                employee_value,
            )
            self.assertTrue(timeline['working'])

        invalid_timeline = self.env['account.analytic.line'].get_day_timeline(
            '2026-09-18',
            '[object Object]',
        )
        self.assertEqual(invalid_timeline, {'working': [], 'occupied': []})

    def test_write_rejects_overlap(self):
        self._create_timesheet(self.task_a, 15 * 60, 16 * 60)
        timesheet = self._create_timesheet(self.task_b, 16 * 60, 17 * 60)

        with self.assertRaises(ValidationError):
            timesheet.write({'start_slot': '0930'})

    def test_non_working_day_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env['account.analytic.line'].create({
                'name': 'Trabajo en domingo',
                'date': '2026-09-20',
                'employee_id': self.employee.id,
                'project_id': self.project.id,
                'task_id': self.task_a.id,
                'start_slot': '0900',
                'end_slot': '1000',
            })