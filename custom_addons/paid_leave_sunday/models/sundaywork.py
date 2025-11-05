from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import calendar
from datetime import datetime

import pytz





class SundayAttendance(models.Model):
    _name = 'hr.sunday.attendance'
    _description = 'Sunday Attendance Records'
    _inherit = ['mail.thread']

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    check_in = fields.Datetime(string='Check In')
    check_out = fields.Datetime(string='Check Out')
    state = fields.Selection([
        ('validate', 'Validate'),
        ('draft', 'Draft'),
        ('refused', 'Refused')
    ], string='Status', default='draft', tracking=True, required=True)

    work_hours = fields.Float(string='Work Hours', store=True)
    counter = fields.Float(string='counter', store=True)

    def action_validate(self):
        for attendance in self:
            attendance.write({'state': 'validate'})
            if attendance.employee_id:
                attendance.employee_id.worked_sundays_count += attendance.counter

    def action_refuse(self):
        for attendance in self:
            attendance.write({'state': 'refused'})


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.model
    def create(self, vals):

        check_in = vals.get('check_in')
        employee_id = vals.get('employee_id')

        employee = self.env['hr.employee'].browse(employee_id)

        check_in_datetime = (
            datetime.strptime(check_in, '%Y-%m-%d %H:%M:%S')
            if isinstance(check_in, str)
            else check_in
        )

        if check_in and employee_id:
            try:
                check_in_date = check_in_datetime.date()

                resource_calendar = employee.resource_calendar_id

                if not resource_calendar:
                    return super().create(vals)

                user_tz = self.env.user.tz or 'UTC'
                tz = pytz.timezone(user_tz)
                check_in_local = check_in_datetime.astimezone(tz)

                # Check for leave approval
                leave_model = self.env['hr.leave']
                is_on_leave = leave_model.is_leave_approved_today(employee_id, check_in_datetime)
                if is_on_leave:
                    raise ValidationError(
                        _("Cannot Day-in while on leave. Employee: %s, Date: %s")
                        % (employee.name, check_in_local.strftime('%d-%m-%Y %H:%M:%S'))
                    )

                # Check Sunday and Holiday with flags
                is_sunday = check_in_datetime.weekday() == 6

                is_holiday_user = self._is_public_holiday(resource_calendar, check_in_date)

                company = employee.company_id

                if is_sunday or is_holiday_user:
                    if not company.Enable_Sunday_Rule:
                        raise UserError(
                            "Check-in not allowed: Company does not allow work on weekly offs and holidays.")
                    if not employee.Allow_work_on_sunday:
                        raise UserError(
                            "Check-in not allowed: Employee is not permitted to work on weekly offs and holidays.")

                # Validate working day
                is_working_day = self._is_working_day(resource_calendar, check_in_date, employee)
                if not is_working_day:
                    raise ValidationError(_(
                        "Cannot check in on a non-working day. Employee: %s, Date: %s"
                    ) % (employee.name, check_in_date))

            except ValueError as e:
                raise ValidationError(_("Invalid check-in time format."))

        return super(HrAttendance, self.sudo()).create(vals)

    def _validate_check_in_date(self, calendar, check_date, employee):
        if not self._is_working_day(calendar, check_date,employee):
            raise ValidationError(_(
                "Cannot check in on a non-working day. Employee: %s, Date: %s"
            ) % (employee.name, check_date))

    def _is_public_holiday(self, calendar, check_date):
        """Check if the given date is a public holiday"""

        # Ensure the check_date is of type 'date' (in case it's a datetime object)
        if isinstance(check_date, datetime):
            check_date = check_date.date()

        # Convert datetime to date for easier comparison
        if hasattr(check_date, 'date'):
            check_date_only = check_date.date()
        else:
            check_date_only = check_date

        # Ensure that global leaves are taken into account and match the given date
        public_holiday = self.env['resource.calendar.leaves'].search([
            ('date_from', '<=', check_date),
            ('date_to', '>=', check_date),
            ('company_id', '=', self.env.user.company_id.id),  # Ensure it's for the same company
            ('resource_id', '=', False)
        ], limit=1)

        if public_holiday:
            return True

        # Check resource calendar leaves (where public holidays are stored)
        leave_model = self.env['resource.calendar.leaves']

        # Check global leaves (calendar_id = False) - affects all employees
        global_domain = [
            ('calendar_id', '=', False),  # Global leaves
            ('date_from', '<=', check_date_only),
            ('date_to', '>=', check_date_only),
        ]

        global_leaves = leave_model.search(global_domain)
        if global_leaves:
            return True

        return False


    def _is_working_day(self, resource_calendar, check_in_date,employee):
        weekday = check_in_date.weekday()
        # Get the weekday (0 = Monday, 6 = Sunday)
        if employee.Allow_work_on_sunday:
            return True
        if resource_calendar:
            for attendance in resource_calendar.attendance_ids:
                if int(attendance.dayofweek) == weekday:
                    return True
        return False


 
 
