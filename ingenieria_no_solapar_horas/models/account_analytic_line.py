from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


def _time_slots(start, stop):
    slots = []
    for minutes in range(start, stop + 1, 15):
        hours, remainder = divmod(minutes, 60)
        slots.append((f'{minutes:04d}', f'{hours:02d}:{remainder:02d}'))
    return slots


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    start_slot = fields.Selection(
        selection=lambda self: _time_slots(0, 24 * 60 - 15),
        string='Hora inicio',
        index=True,
    )
    end_slot = fields.Selection(
        selection=lambda self: _time_slots(15, 24 * 60),
        string='Hora fin',
        index=True,
    )
    occupied_intervals = fields.Char(
        string='Horas ocupadas',
        compute='_compute_occupied_intervals',
    )

    @api.depends('date', 'employee_id', 'start_slot', 'end_slot')
    def _compute_occupied_intervals(self):
        for line in self:
            line.occupied_intervals = line._get_occupied_intervals_label()

    @api.onchange('start_slot', 'end_slot')
    def _onchange_time_slots(self):
        for line in self:
            if line.start_slot and line.end_slot:
                start_minutes = int(line.start_slot)
                end_minutes = int(line.end_slot)
                line.unit_amount = max(end_minutes - start_minutes, 0) / 60

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._set_duration_in_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        if not {'start_slot', 'end_slot', 'unit_amount'} & vals.keys():
            return super().write(vals)

        for line in self:
            line_vals = dict(vals)
            self._set_duration_in_vals(line_vals, line)
            super(AccountAnalyticLine, line).write(line_vals)
        return True

    @api.model
    def _set_duration_in_vals(self, vals, line=None):
        start_slot = vals.get('start_slot', line.start_slot if line else False)
        end_slot = vals.get('end_slot', line.end_slot if line else False)
        if start_slot and end_slot:
            vals['unit_amount'] = max(int(end_slot) - int(start_slot), 0) / 60

    @api.constrains('date', 'employee_id', 'start_slot', 'end_slot')
    def _check_time_interval(self):
        for line in self.filtered(lambda item: item.project_id):
            if not line.start_slot and not line.end_slot:
                continue
            if not line.start_slot or not line.end_slot:
                raise ValidationError(_(
                    'Debes indicar tanto la hora de inicio como la hora de fin.'
                ))
            if not line.date or not line.employee_id:
                raise ValidationError(_(
                    'Debes indicar la fecha y el empleado de la imputación.'
                ))

            start_minutes = int(line.start_slot)
            end_minutes = int(line.end_slot)
            if start_minutes >= end_minutes:
                raise ValidationError(_(
                    'La hora de fin debe ser posterior a la hora de inicio.'
                ))
            if start_minutes % 15 or end_minutes % 15:
                raise ValidationError(_(
                    'Las horas deben indicarse en intervalos de 15 minutos.'
                ))

            line._check_employee_working_interval(start_minutes, end_minutes)
            self.env.cr.execute(
                'SELECT pg_advisory_xact_lock(%s, %s)',
                [line.employee_id.id, line.date.toordinal()],
            )
            conflict = self.search([
                ('id', '!=', line.id),
                ('employee_id', '=', line.employee_id.id),
                ('date', '=', line.date),
                ('start_slot', '!=', False),
                ('end_slot', '!=', False),
                ('start_slot', '<', f'{end_minutes:04d}'),
                ('end_slot', '>', f'{start_minutes:04d}'),
            ], limit=1)
            if conflict:
                raise ValidationError(_(
                    'El empleado ya tiene una imputación de %(start)s a %(end)s en la tarea "%(task)s".',
                    start=conflict._format_slot(conflict.start_slot),
                    end=conflict._format_slot(conflict.end_slot),
                    task=conflict.task_id.display_name or conflict.name,
                ))

    def _check_employee_working_interval(self, start_minutes, end_minutes):
        self.ensure_one()
        if not self.employee_id or not self.date:
            return

        resource = self.employee_id.resource_id
        calendar = resource.calendar_id or self.employee_id.company_id.resource_calendar_id
        if not calendar:
            return

        timezone = pytz.timezone(calendar.tz or self.env.user.tz or 'UTC')
        local_start = timezone.localize(datetime.combine(
            self.date,
            time(start_minutes // 60, start_minutes % 60),
        ))
        if end_minutes == 24 * 60:
            local_end = timezone.localize(datetime.combine(
                self.date + timedelta(days=1),
                time.min,
            ))
        else:
            local_end = timezone.localize(datetime.combine(
                self.date,
                time(end_minutes // 60, end_minutes % 60),
            ))

        intervals = calendar._work_intervals_batch(
            local_start,
            local_end,
            resources=resource,
        )[resource.id]
        worked_seconds = sum((stop - start).total_seconds() for start, stop, _meta in intervals)
        requested_seconds = (local_end - local_start).total_seconds()
        if worked_seconds < requested_seconds:
            raise ValidationError(_(
                'No puedes imputar este intervalo porque está fuera del horario laboral, es festivo o corresponde a una ausencia.'
            ))

    def _get_occupied_intervals_label(self):
        self.ensure_one()
        if not self.employee_id or not self.date:
            return False
        lines = self.search([
            ('id', '!=', self.id),
            ('employee_id', '=', self.employee_id.id),
            ('date', '=', self.date),
            ('start_slot', '!=', False),
            ('end_slot', '!=', False),
        ], order='start_slot')
        return ', '.join(
            f'{self._format_slot(line.start_slot)}-{self._format_slot(line.end_slot)}'
            for line in lines
        ) or _('Libre')

    @api.model
    def _format_slot(self, slot):
        minutes = int(slot)
        hours, remainder = divmod(minutes, 60)
        return f'{hours:02d}:{remainder:02d}'