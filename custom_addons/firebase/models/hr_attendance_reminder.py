from datetime import timedelta
from pytz import timezone, UTC
from odoo import fields, api, models


class HrAttendanceReminder(models.Model):
    _inherit = 'hr.employee'

    def send_checkin_reminder(self):
        """
        Send check-in reminders to employees who haven't checked in
        within a defined time window after their standard start time.
        """
        config = self.env['ir.config_parameter'].sudo()
        allow_reminder = config.get_param('hr_attendance.allow_notification_reminder_attendance')
        reminder_time_limit = config.get_param('hr_attendance.attendance_checkin_reminder_time_limit',
                                               '00:15')  # Default 15 min

        if not allow_reminder:
            return

        try:
            reminder_hours, reminder_minutes = map(int, reminder_time_limit.split(':'))
        except ValueError:
            return

        # Hardcoded expiry limit (e.g., 1 hour after expected check-in time)
        expiry_hours, expiry_minutes = 1, 0  # 1 hour

        # Get IST timezone
        ist_tz = timezone('Asia/Kolkata')

        # Get current datetime in UTC and convert to IST
        current_datetime_utc = fields.Datetime.now()
        print(current_datetime_utc)
        current_datetime_ist = UTC.localize(current_datetime_utc).astimezone(ist_tz)
        print(current_datetime_ist)
        # Get today's date in IST
        current_date = current_datetime_ist.date()
        print(current_date)
        # Find employees with active contracts
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('contract_id', '!=', False)
        ])
        print(employees)
        for employee in employees:
            if not employee.user_id or not employee.contract_id:
                continue

            leave_check = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                ('date_from', '<=', current_date),
                ('date_to', '>=', current_date)
            ])

            if leave_check:
                continue

            weekday = str(current_date.weekday())

            attendance = employee.contract_id.resource_calendar_id.attendance_ids.filtered(
                lambda a: a.dayofweek == weekday
            )
            if attendance:
                standard_start_time = attendance[0].hour_from
            else:
                continue  # No attendance rule for today

            start_hours = int(standard_start_time)
            start_minutes = int((standard_start_time - start_hours) * 60)

            # Expected check-in time is already in IST from UI
            expected_checkin_time_str = f"{current_date} {start_hours:02}:{start_minutes:02}:00"
            expected_checkin_time = ist_tz.localize(fields.Datetime.from_string(expected_checkin_time_str))
            print(expected_checkin_time)
            reminder_start_time = expected_checkin_time + timedelta(hours=reminder_hours, minutes=reminder_minutes)
            reminder_end_time = expected_checkin_time + timedelta(hours=expiry_hours,
                                                                  minutes=expiry_minutes)  # Hardcoded 1 hour

            # If current time is past the reminder expiry time, stop sending reminders
            if current_datetime_ist > reminder_end_time:
                continue

            # If current time is within the reminder window and user hasn't checked in
            if current_datetime_ist >= reminder_start_time:
                attendance_record = self.env['hr.attendance'].search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', fields.Datetime.to_string(current_date)),
                ], limit=1)

                if not attendance_record:
                    payload = {
                        'model': 'hr.attendance',
                        'action': 'check_in_reminder'
                    }

                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=employee.user_id.id,
                        title='Check-in Reminder',
                        body=f'Your shift started at {expected_checkin_time_str}. Please check in.',
                        payload=payload
                    )



    def send_checkout_reminder(self):
        """
        Send check-out reminders to employees who haven't checked out
        within a defined time window before/after their standard shift end.
        """
        config = self.env['ir.config_parameter'].sudo()
        allow_reminder = config.get_param('hr_attendance.allow_notification_reminder_attendance')
        reminder_time_limit = config.get_param('hr_attendance.attendance_checkout_reminder_time_limit', '00:15')  # Default 15 min

        if not allow_reminder:
            return

        try:
            reminder_hours, reminder_minutes = map(int, reminder_time_limit.split(':'))
        except ValueError:
            return

        # Hardcoded expiry limit (e.g., reminders stop 1 hour after shift end)
        expiry_hours, expiry_minutes = 1, 0  # 1 hour

        # Get IST timezone
        ist_tz = timezone('Asia/Kolkata')

        # Get current datetime in UTC and convert to IST
        current_datetime_utc = fields.Datetime.now()
        current_datetime_ist = UTC.localize(current_datetime_utc).astimezone(ist_tz)
        print(current_datetime_ist)
        # Get today's date in IST
        current_date = current_datetime_ist.date()
        print(current_date)
        # Find employees with active contracts
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('contract_id', '!=', False)
        ])

        for employee in employees:
            if not employee.user_id or not employee.contract_id:
                continue

            leave_check = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                ('date_from', '<=', current_date),
                ('date_to', '>=', current_date)
            ])

            if leave_check:
                continue

            weekday = str(current_date.weekday())

            attendance = employee.contract_id.resource_calendar_id.attendance_ids.filtered(
                lambda a: a.dayofweek == weekday
            )
            if attendance:
                standard_end_time = attendance[0].hour_to
                print(standard_end_time) # Shift end time
            else:
                continue  # No attendance rule for today

            end_hours = int(standard_end_time)
            end_minutes = int((standard_end_time - end_hours) * 60)

            # Expected check-out time in IST
            expected_checkout_time_str = f"{current_date} {end_hours:02}:{end_minutes:02}:00"
            expected_checkout_time = ist_tz.localize(fields.Datetime.from_string(expected_checkout_time_str))
            print(expected_checkout_time)
            reminder_start_time = expected_checkout_time - timedelta(hours=reminder_hours, minutes=reminder_minutes)
            reminder_end_time = expected_checkout_time + timedelta(hours=expiry_hours, minutes=expiry_minutes)  # Hardcoded 1 hour after
            print(reminder_end_time)
            # If current time is past the reminder expiry time, stop sending reminders
            if current_datetime_ist > reminder_end_time:
                continue

            # If current time is within the reminder window and user hasn't checked out
            if current_datetime_ist >= reminder_start_time:
                attendance_record = self.env['hr.attendance'].search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', fields.Datetime.to_string(current_date)),
                    ('check_out', '=', False)
                ], limit=1)

                if attendance_record:
                    payload = {
                        'model': 'hr.attendance',
                        'action': 'check_out_reminder'
                    }

                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=employee.user_id.id,
                        title='Check-out Reminder',
                        body=f'Your shift ended at {expected_checkout_time_str}. Please check out.',
                        payload=payload
                    )
