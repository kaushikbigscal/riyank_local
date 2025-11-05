from odoo import models, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    @api.constrains('date_from', 'date_to', 'holiday_status_id', 'state')
    def _check_sick_leave_clubbing(self):
        for leave in self:
            self._check_leave_proximity(leave)

    def _check_leave_proximity(self, leave):
        # Define the range to check (14 days before and after the leave)
        check_start = leave.date_from.date() - timedelta(days=14)
        check_end = leave.date_to.date() + timedelta(days=14)

        # Search for all leaves within this range, including the current one
        all_leaves = self.search([
            ('employee_id', '=', leave.employee_id.id),
            ('state', 'not in', ['refuse', 'cancel']),
            '|',
            '&', ('date_from', '>=', check_start), ('date_from', '<=', check_end),
            '&', ('date_to', '>=', check_start), ('date_to', '<=', check_end),
        ])

        # Sort leaves by start date
        sorted_leaves = sorted(all_leaves, key=lambda l: l.date_from)

        for i, current_leave in enumerate(sorted_leaves):
            if current_leave.id == leave.id:
                # Check previous leave
                if i > 0:
                    prev_leave = sorted_leaves[i-1]
                    self._check_working_days_between(prev_leave, current_leave)

                # Check next leave
                if i < len(sorted_leaves) - 1:
                    next_leave = sorted_leaves[i+1]
                    self._check_working_days_between(current_leave, next_leave)

    def _check_working_days_between(self, leave1, leave2):
        days_between = self._get_working_days_between(leave1.date_to.date(), leave2.date_from.date()) - 1
        if days_between < 2:
            if leave1.holiday_status_id.name == 'Sick Leave' or leave2.holiday_status_id.name == 'Sick Leave':
                raise ValidationError(_("There must be at least 1 working days between Sick Leave and any other leave."))

    def _get_working_days_between(self, start_date, end_date):
        working_days = 0
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                working_days += 1
            current_date += timedelta(days=1)
        return working_days