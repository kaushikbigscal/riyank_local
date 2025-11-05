from datetime import datetime, date, timedelta
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    @api.constrains('date_from', 'date_to', 'employee_id', 'holiday_status_id')
    def _check_earned_leave_limit(self):
        for leave in self:
            if leave.holiday_status_id.name == 'Earned Leaves':
                self._check_monthly_limit(leave)

    def _check_monthly_limit(self, leave):
        def to_date(value):
            if isinstance(value, datetime):
                return value.date()
            elif isinstance(value, date):
                return value
            else:
                return fields.Date.from_string(value)

        start_date = to_date(leave.date_from)
        end_date = to_date(leave.date_to)

        # Check if the leave spans two months
        if start_date.month != end_date.month:
            raise ValidationError(_(
                "You cannot take Earned Leaves that span across two months. "
                "Please create separate leave requests for each month."
            ))

        # Get the first and last day of the month
        first_day = start_date.replace(day=1)
        next_month = first_day + timedelta(days=32)
        last_day = next_month.replace(day=1) - timedelta(days=1)

        # Count existing Earned Leaves in the same month
        existing_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', leave.employee_id.id),
            ('holiday_status_id.name', '=', 'Earned Leaves'),
            ('state', 'not in', ['refuse', 'cancel']),
            ('date_from', '>=', first_day),
            ('date_to', '<=', last_day),
            ('id', '!=', leave.id)
        ])

        # Calculate total days of Earned Leaves in the month
        total_days = sum(existing_leaves.mapped('number_of_days')) + leave.number_of_days

        if total_days > 5:
            raise ValidationError(_(
                "You can only take up to 5 Earned Leaves days per month. "
                "Your current request for the month of %s exceeds this limit."
            ) % start_date.strftime('%B %Y'))

        # Check for continuous leaves at month boundaries
        month_boundary = last_day
        next_month_start = month_boundary + timedelta(days=1)

        continuous_leave = self.env['hr.leave'].search([
            ('employee_id', '=', leave.employee_id.id),
            ('holiday_status_id.name', '=', 'Earned Leaves'),
            ('state', 'not in', ['refuse', 'cancel']),
            '|',
            '&', ('date_from', '<=', month_boundary), ('date_to', '>=', next_month_start),
            '&', ('date_from', '=', next_month_start), ('date_to', '>=', next_month_start),
        ], limit=1)

        if continuous_leave:
            raise ValidationError(_(
                "You cannot take Earned Leaves that continue into the next month. "
                "Please create separate leave requests for each month."
            ))