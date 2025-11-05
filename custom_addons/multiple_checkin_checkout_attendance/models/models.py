from odoo import fields, models
import logging
from odoo import models, api, exceptions, _
from datetime import datetime, time, timedelta, date
from pytz import UTC
import pytz
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    allow_multiple_checkins = fields.Boolean(string='Allow Multiple Day-ins',
                                             config_parameter='hr_attendance.allow_multiple_checkins')

    check_out_time_limit = fields.Char(string='Day-out Time Limit (HH:MM)',
                                       config_parameter='hr_attendance.check_out_time_limit',
                                       help="Minimum duration before employees can Day out (in HH:MM format)")

    @api.onchange('check_out_time_limit')
    def _onchange_check_out_time_limit(self):
        if self.check_out_time_limit:
            try:
                hours, minutes = map(int, self.check_out_time_limit.split(':'))
                if hours < 0 or minutes < 0 or minutes >= 60:
                    raise ValueError
            except ValueError:
                return {'warning': {
                    'title': "Invalid Format",
                    'message': "Please enter the time limit in HH:MM format (e.g., 07:10 for 7 hours and 10 minutes)."
                }}

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res['check_out_time_limit'] = self.env['ir.config_parameter'].sudo().get_param(
            'hr_attendance.check_out_time_limit', '00:00')
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('hr_attendance.check_out_time_limit',
                                                         self.check_out_time_limit or '00:00')


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.model
    def create(self, vals):
        employee_id = vals.get('employee_id')

        allow_multiple_checkins = self.env['ir.config_parameter'].sudo().get_param(
            'hr_attendance.allow_multiple_checkins', 'False').lower() == 'true'
        if not allow_multiple_checkins:
            employee_id = vals.get('employee_id')
            check_in = vals.get('check_in')
            if employee_id and check_in:
                check_in_date = fields.Datetime.from_string(check_in).date()
                existing_attendance = self.env['hr.attendance'].search([
                    ('employee_id', '=', employee_id),
                    ('check_in', '>=', datetime.combine(check_in_date, time.min).replace(tzinfo=UTC)),
                    ('check_in', '<', datetime.combine(check_in_date, time.max).replace(tzinfo=UTC))
                ], limit=1)
                if existing_attendance:
                    raise exceptions.UserError(
                        _('You have already Day in today. Multiple Day-ins are not allowed.'))
        return super(HrAttendance, self).create(vals)

    def write(self, vals):
        try:
            check_out = vals.get('check_out')
            if check_out:
                check_out_time_limit = self.env['ir.config_parameter'].sudo().get_param(
                    'hr_attendance.check_out_time_limit', '00:00')
                hours, minutes = map(int, check_out_time_limit.split(':'))
                minimum_duration = timedelta(hours=hours, minutes=minutes)

                check_out_datetime = fields.Datetime.from_string(check_out)
                check_in_datetime = self.check_in

                # Convert both check-in and check-out to user's timezone
                user_tz = self.env.user.tz or 'UTC'
                local_tz = pytz.timezone(user_tz)
                local_check_out = UTC.localize(check_out_datetime).astimezone(local_tz)
                local_check_in = UTC.localize(check_in_datetime).astimezone(local_tz)

                # Calculate the required check-out time
                required_check_out_time = local_check_in + minimum_duration

                # Ensure users cannot check out before the minimum duration
                if local_check_out < required_check_out_time:
                    error_msg = _("You cannot check out before {:%H:%M}. Minimum duration is {}:{:02d}.".format(
                        required_check_out_time, hours, minutes
                    ))
                    raise exceptions.UserError(error_msg)

            result = super(HrAttendance, self).write(vals)
            return result
        except Exception as e:
            raise


# For Leave Checking Emplopyeee iS Present or on Off


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    @api.model
    def is_leave_approved_today(self, employee_id, check_in_datetime):
        """
        Checks if the employee has a validated leave for today.
        Allows check-in if it's outside half-day leave or customizable leave hours.
        """
        check_in_date = check_in_datetime.date() if isinstance(check_in_datetime, datetime) else check_in_datetime

        leave = self.search([
            ('employee_id', '=', employee_id),
            ('state', '=', 'validate'),  # Only consider validated leaves
            ('date_from', '<=', check_in_datetime),
            ('date_to', '>=', check_in_datetime),
        ], limit=1)

        if not leave:
            return False  # No leave, check-in allowed

        # Check if leave is for a full day
        if leave.request_unit_half:
            # Get half-day hours (assuming morning or afternoon leave is stored)
            leave_start = leave.date_from
            leave_end = leave.date_to

            if leave_start.time() <= check_in_datetime.time() <= leave_end.time():
                return True  # Check-in not allowed during leave hours
            return False  # Check-in allowed outside leave hours

        # If it's a customizable leave with specific hours
        if leave.request_unit_hours:
            leave_start = leave.date_from
            leave_end = leave.date_to

            if leave_start.time() <= check_in_datetime.time() <= leave_end.time():
                return True  # Check-in not allowed during leave hours
            return False  # Check-in allowed outside leave hours

        return True  # Default case: full-day leave means check-in is not allowed

    def _compute_is_last_minute_leave(self):
        """Compute method to determine if a leave is last-minute"""
        for holiday in self:
            now = fields.Datetime.now()
            today_end = datetime.combine(now.date(), datetime.max.time())
            next_day = today_end + timedelta(days=1)

            holiday.is_last_minute_leave = (
                    holiday.request_date_from == now.date() or
                    holiday.request_date_from == next_day.date() or
                    (holiday.request_date_from == next_day.date() and
                     now.time() >= datetime.strptime('18:00', '%H:%M').time())
            )

    is_last_minute_leave = fields.Boolean(
        compute='_compute_is_last_minute_leave',
        store=False,
        help="Indicates if the leave request is considered last-minute"
    )

    @api.model
    def create(self, vals):
        """Prevent leave creation on public holidays, mandatory days, or non-working days."""
        record = super(HrLeave, self).create(vals)
        holiday_model = self.env['resource.calendar.leaves']
        mandatory_model = self.env['hr.leave.mandatory.day']
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)

        leave_start = record.date_from
        leave_end = record.date_to

        if not leave_start or not leave_end:
            return record

        leave_start_date = fields.Datetime.from_string(leave_start)
        leave_end_date = fields.Datetime.from_string(leave_end)

        # Check for public holidays
        public_holidays = holiday_model.search([
            ('company_id', '=', self.env.user.company_id.id),
            ('resource_id', '=', False)
        ])

        for ph in public_holidays:
            holiday_start = fields.Datetime.from_string(ph.date_from)
            holiday_end = fields.Datetime.from_string(ph.date_to)

            diff_minutes = (leave_end_date - holiday_start).total_seconds() / 60.0

            if leave_end_date <= holiday_start or (0 <= diff_minutes <= 15):
                continue

            if holiday_start <= leave_end_date and holiday_end >= leave_start_date:
                holiday_dates = (
                    f"{fields.Datetime.context_timestamp(self, ph.date_from).strftime('%Y-%m-%d %H:%M:%S')} to "
                    f"{fields.Datetime.context_timestamp(self, ph.date_to).strftime('%Y-%m-%d %H:%M:%S')}"
                )
                raise ValidationError(
                    _("It’s already a holiday! No need to apply leave (%s).") % holiday_dates
                )

        # Check for mandatory days
        mandatory_days = mandatory_model.search([
            ('start_date', '<=', leave_end),
            ('end_date', '>=', leave_start),
            ('company_id', '=', self.env.user.company_id.id)
        ])
        if mandatory_days:
            mandatory_dates = ", ".join([f"{md.start_date} to {md.end_date}" for md in mandatory_days])
            raise ValidationError(_("You cannot request leave on mandatory days: %s") % mandatory_dates)

        # Check for non-working days (based on employee's working schedule)
        if employee and employee.resource_calendar_id:
            calendar = employee.resource_calendar_id
            current_date = leave_start_date
            while current_date <= leave_end_date:
                start_dt = datetime.combine(current_date, datetime.min.time())
                end_dt = datetime.combine(current_date, datetime.max.time())

                start_dt = fields.Datetime.context_timestamp(self.with_context(tz=self.env.user.tz), start_dt)
                end_dt = fields.Datetime.context_timestamp(self.with_context(tz=self.env.user.tz), end_dt)

                intervals_dict = calendar._work_intervals_batch(start_dt, end_dt)
                intervals = list(intervals_dict.values())[0] if intervals_dict else []

                if not intervals:
                    raise ValidationError(_(
                        "You cannot apply leave for a non-working (week off) day (%s)."
                    ) % current_date)
                current_date += timedelta(days=1)

        return record

    # @api.model
    # def create(self, vals):
    #     """Prevent leave creation on public holidays, mandatory days, or non-working days (with debug prints)."""
    #     print("\n========== HR LEAVE CREATE CALLED ==========")
    #     print("Incoming vals:", vals)
    #
    #     holiday_model = self.env['resource.calendar.leaves']
    #     mandatory_model = self.env['hr.leave.mandatory.day']
    #     employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
    #     print("Employee found:", employee.name if employee else "None")
    #
    #     leave_start = vals.get('request_date_from')
    #     leave_end = vals.get('request_date_to')
    #     print("Leave Start:", leave_start, "Leave End:", leave_end)
    #
    #     if not leave_start or not leave_end:
    #         print("No leave dates found → proceeding with default create()")
    #         return super(HrLeave, self).create(vals)
    #
    #     leave_start_date = fields.Date.from_string(leave_start)
    #     leave_end_date = fields.Date.from_string(leave_end)
    #
    #     # -------------------------
    #     # 1️⃣ Check for public holidays
    #     # -------------------------
    #     print("\n--- Checking Public Holidays ---")
    #     public_holiday = holiday_model.search([
    #         ('date_from', '<=', leave_end),
    #         ('date_to', '>=', leave_start),
    #         ('company_id', '=', self.env.user.company_id.id),
    #         ('resource_id', '=', False)
    #     ], limit=1)
    #     print("Public holiday found:", public_holiday)
    #
    #     if public_holiday:
    #         holiday_dates = ", ".join([f"{ph.date_from.date()} to {ph.date_to.date()}" for ph in public_holiday])
    #         print("❌ Leave rejected due to public holiday:", holiday_dates)
    #         raise ValidationError(_("It’s already a public holiday! No need to apply leave (%s).") % holiday_dates)
    #
    #     # -------------------------
    #     # 2️⃣ Check for mandatory days
    #     # -------------------------
    #     print("\n--- Checking Mandatory Days ---")
    #     mandatory_days = mandatory_model.search([
    #         ('start_date', '<=', leave_end),
    #         ('end_date', '>=', leave_start),
    #         ('company_id', '=', self.env.user.company_id.id)
    #     ])
    #     print("Mandatory days found:", mandatory_days)
    #
    #     if mandatory_days:
    #         mandatory_dates = ", ".join([f"{md.start_date} to {md.end_date}" for md in mandatory_days])
    #         print("❌ Leave rejected due to mandatory days:", mandatory_dates)
    #         raise ValidationError(_("You cannot request leave on mandatory days: %s") % mandatory_dates)
    #
    #     # -------------------------
    #     # 3️⃣ Check for non-working days (based on employee's working schedule)
    #     # -------------------------
    #     print("\n--- Checking Working Schedule ---")
    #     if employee and employee.resource_calendar_id:
    #         calendar = employee.resource_calendar_id
    #         print("Employee Calendar:", calendar.name)
    #
    #         current_date = leave_start_date
    #         while current_date <= leave_end_date:
    #             # Create datetimes for the start and end of this date
    #             start_dt = datetime.combine(current_date, datetime.min.time())
    #             end_dt = datetime.combine(current_date, datetime.max.time())
    #
    #             # Convert to timezone-aware using Odoo context
    #             start_dt = fields.Datetime.context_timestamp(self.with_context(tz=self.env.user.tz), start_dt)
    #             end_dt = fields.Datetime.context_timestamp(self.with_context(tz=self.env.user.tz), end_dt)
    #
    #             # Get work intervals for that date
    #             intervals_dict = calendar._work_intervals_batch(start_dt, end_dt)
    #             intervals = list(intervals_dict.values())[0] if intervals_dict else []
    #
    #             print(f"Date: {current_date}, Working intervals: {intervals}")
    #
    #             if not intervals:
    #                 print(f"❌ Leave rejected — {current_date} is not part of working schedule.")
    #                 raise ValidationError(_(
    #                     "You cannot apply for leave on %s, as it is not part of your working schedule."
    #                 ) % current_date)
    #
    #             current_date += timedelta(days=1)
    #     else:
    #         print("⚠️ No working calendar found for employee. Skipping working day check.")
    #
    #     print("✅ All checks passed → Proceeding to create leave record.")
    #     record = super(HrLeave, self).create(vals)
    #     print("✅ Leave created successfully with ID:", record.id)
    #     print("=============================================\n")
    #     return record
