# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, time, date, timedelta
import pytz
from odoo.tools import format_date
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

# Batch size for processing employees
BATCH_SIZE = 100


class HrAttendance(models.Model):
    """Extend HR Attendance to add notes field"""
    _inherit = 'hr.attendance'

    attendance_note = fields.Text(string='Note', tracking=True)

    def write(self, vals):
        """Override write to handle attendance corrections after manual edits"""
        result = super(HrAttendance, self).write(vals)

        # Check if this write came from correction editing
        if self.env.context.get('from_correction'):
            # Add note for manual adjustment if not already present
            if 'attendance_note' not in vals or not vals.get('attendance_note'):
                vals_with_note = {'attendance_note': 'Short hours manual adjustment'}
                super(HrAttendance, self).write(vals_with_note)

            # Re-evaluate corrections for affected records
            for record in self:
                if record.check_in:
                    check_date = record.check_in.date()
                    self._handle_correction_after_edit(record.employee_id.id, check_date)

        return result

    def _handle_correction_after_edit(self, employee_id, check_date):
        """Handle correction record updates/deletion after attendance edit"""
        AttendanceCorrection = self.env['temp.attendance.correction']

        # Get all attendance records for this employee on this date
        date_start = datetime.combine(check_date, time.min)
        date_end = datetime.combine(check_date, time.max)

        day_attendances = self.search([
            ('employee_id', '=', employee_id),
            ('check_in', '>=', date_start),
            ('check_in', '<=', date_end),
            ('check_out', '!=', False)  # Only completed attendances
        ])

        # Calculate total worked hours
        total_worked_hours = sum(day_attendances.mapped('worked_hours') or [0.0])

        # Get expected hours for this employee
        employee = self.env['hr.employee'].browse(employee_id)
        correction_model = AttendanceCorrection.sudo()
        expected_hours = correction_model._get_expected_hours(employee, check_date)

        # Get grace minutes
        minute_allowed = correction_model._get_minute_allowed()

        # Find existing correction records for this employee and date
        existing_corrections = AttendanceCorrection.search([
            ('employee_id', '=', employee_id),
            ('date', '=', check_date),
            ('reason_code', 'in', ['SHORT_HOURS', 'NO_SHOW'])
        ])

        # Calculate effective expected hours (considering grace for late check-in)
        effective_expected_hours = expected_hours

        if day_attendances:
            # Apply grace period logic
            earliest_check_in = min(day_attendances.mapped('check_in'))
            earliest_start = self._get_scheduled_start_time(employee, check_date)

            if earliest_start and earliest_check_in:
                delay_minutes = max(0, int((earliest_check_in - earliest_start).total_seconds() // 60))
                discount_minutes = min(delay_minutes, minute_allowed)
                effective_expected_hours = max(0.0, expected_hours - (discount_minutes / 60.0))

        # Decision logic
        if not day_attendances:
            # Still no attendance - keep/create NO_SHOW
            no_show_correction = existing_corrections.filtered(lambda r: r.reason_code == 'NO_SHOW')
            if not no_show_correction:
                # Create NO_SHOW if it doesn't exist
                schedule_hours = correction_model._get_schedule_time_range(employee, check_date)
                AttendanceCorrection.create({
                    'employee_id': employee_id,
                    'date': check_date,
                    'reason_code': 'NO_SHOW',
                    'worked_hours': 0.0,
                    'expected_hours': expected_hours,
                    'shortfall': expected_hours,
                    'check_in': None,
                    'check_out': None,
                    'schedule_hours': schedule_hours,
                    'department_id': employee.department_id.id if employee.department_id else None,
                    'company_id': employee.company_id.id if employee.company_id else None,
                })
            # Remove any SHORT_HOURS records
            existing_corrections.filtered(lambda r: r.reason_code == 'SHORT_HOURS').unlink()

        elif total_worked_hours >= effective_expected_hours:
            # Working hours now meet expectations - remove all corrections
            existing_corrections.unlink()
            _logger.info(
                f"Removed correction records for employee {employee.name} on {check_date} - hours now sufficient")

        else:
            # Still has shortfall - update SHORT_HOURS record
            short_hours_correction = existing_corrections.filtered(lambda r: r.reason_code == 'SHORT_HOURS')

            # Remove NO_SHOW if exists (since we now have attendance)
            existing_corrections.filtered(lambda r: r.reason_code == 'NO_SHOW').unlink()

            # Get latest attendance times
            check_in_times = day_attendances.mapped('check_in')
            check_out_times = day_attendances.mapped('check_out')

            correction_vals = {
                'worked_hours': total_worked_hours,
                'expected_hours': expected_hours,
                'shortfall': effective_expected_hours - total_worked_hours,
                'check_in': min(check_in_times) if check_in_times else None,
                'check_out': max(check_out_times) if check_out_times else None,
            }

            if short_hours_correction:
                # Update existing SHORT_HOURS record
                short_hours_correction.write(correction_vals)
                _logger.info(f"Updated SHORT_HOURS correction for employee {employee.name} on {check_date}")
            else:
                # Create new SHORT_HOURS record
                schedule_hours = correction_model._get_schedule_time_range(employee, check_date)
                correction_vals.update({
                    'employee_id': employee_id,
                    'date': check_date,
                    'reason_code': 'SHORT_HOURS',
                    'schedule_hours': schedule_hours,
                    'department_id': employee.department_id.id if employee.department_id else None,
                    'company_id': employee.company_id.id if employee.company_id else None,
                })
                AttendanceCorrection.create(correction_vals)
                _logger.info(f"Created new SHORT_HOURS correction for employee {employee.name} on {check_date}")

    def _get_scheduled_start_time(self, employee, check_date):
        """Get the scheduled start time for an employee on a given date"""
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', check_date),
            '|', ('date_end', '=', False), ('date_end', '>=', check_date)
        ], limit=1)

        calendar = None
        if contract and contract.resource_calendar_id:
            calendar = contract.resource_calendar_id
        elif employee.resource_calendar_id:
            calendar = employee.resource_calendar_id
        elif employee.company_id.resource_calendar_id:
            calendar = employee.company_id.resource_calendar_id

        if not calendar:
            return None

        weekday = check_date.weekday()
        attendance_lines = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == weekday)

        if not attendance_lines:
            return None

        earliest_start = min(attendance_lines.mapped('hour_from'))

        # Convert to datetime
        scheduled_start = datetime.combine(
            check_date,
            time(int(earliest_start), int((earliest_start % 1) * 60))
        )

        # Convert to UTC if needed
        user_tz = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)
        scheduled_start_local = local_tz.localize(scheduled_start)

        return scheduled_start_local.astimezone(pytz.UTC).replace(tzinfo=None)


class AttendanceCorrection(models.Model):
    _name = 'temp.attendance.correction'
    _description = 'Attendance Shortfall Correction'
    _order = 'date desc, employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    date = fields.Date(string='Date', required=True)
    reason_code = fields.Selection([
        ('SHORT_HOURS', 'Short Hours'),
        ('NO_SHOW', 'No Show')
    ], string='Reason Code', required=True)
    worked_hours = fields.Float(string='Worked Hours')
    expected_hours = fields.Float(string='Expected Hours')
    shortfall = fields.Float(string='Shortfall')
    check_in = fields.Datetime(string='In Time')
    check_out = fields.Datetime(string='Out Time')
    schedule_hours = fields.Char(string='Work Schedule')
    department_id = fields.Many2one('hr.department', string='Department')
    company_id = fields.Many2one('res.company', string='Company')

    @api.model
    def check_attendance_for_date(self, check_date=None, employee_ids=None):
        """
        Optimized attendance checking with bulk operations and batch processing
        """
        if not check_date:
            check_date = date.today()

        _logger.info(f"Checking attendance for date: {check_date}")

        # Filter employees if employee_ids provided
        domain = [('active', '=', True)]
        if employee_ids:
            domain.append(('id', 'in', employee_ids))

        # Get all active employees with required fields only
        employee_fields = ['id', 'name', 'resource_calendar_id', 'department_id', 'company_id']
        employees_data = self.env['hr.employee'].sudo().search_read(domain, employee_fields)

        if not employees_data:
            return 0

        total_employees = len(employees_data)
        created_records = 0

        # Process employees in batches to manage memory and performance
        for i in range(0, total_employees, BATCH_SIZE):
            batch_employees = employees_data[i:i + BATCH_SIZE]
            employee_ids = [emp['id'] for emp in batch_employees]

            _logger.info(
                f"Processing batch {i // BATCH_SIZE + 1}: employees {i + 1}-{min(i + BATCH_SIZE, total_employees)}")

            # Bulk fetch all required data for this batch
            batch_data = self._bulk_fetch_batch_data(employee_ids, check_date)

            # Process this batch
            batch_corrections = self._process_employee_batch(batch_employees, check_date, batch_data)

            # Bulk create correction records
            if batch_corrections:
                self.create(batch_corrections)
                created_records += len(batch_corrections)

        _logger.info(f"Created {created_records} attendance correction records for {check_date}")
        return created_records

    def _bulk_fetch_batch_data(self, employee_ids, check_date):
        """
        Bulk fetch all required data for a batch of employees to minimize database queries
        """
        date_start = datetime.combine(check_date, time.min)
        date_end = datetime.combine(check_date, time.max)

        # Bulk fetch attendance records
        attendance_data = self.env['hr.attendance'].search_read([
            ('employee_id', 'in', employee_ids),
            ('check_in', '>=', date_start),
            ('check_in', '<=', date_end)
        ], ['employee_id', 'check_in', 'check_out', 'worked_hours'])

        # Group attendance by employee_id
        attendance_by_employee = {}
        for att in attendance_data:
            emp_id = att['employee_id'][0]
            if emp_id not in attendance_by_employee:
                attendance_by_employee[emp_id] = []
            attendance_by_employee[emp_id].append(att)

        # Bulk fetch active contracts
        contract_data = self.env['hr.contract'].search_read([
            ('employee_id', 'in', employee_ids),
            ('state', '=', 'open'),
            ('date_start', '<=', check_date),
            '|', ('date_end', '=', False), ('date_end', '>=', check_date)
        ], ['employee_id', 'resource_calendar_id'])

        # Group contracts by employee_id
        contracts_by_employee = {}
        for contract in contract_data:
            emp_id = contract['employee_id'][0]
            contracts_by_employee[emp_id] = contract

        # Bulk fetch leave records
        leave_data = self.env['hr.leave'].search_read([
            ('employee_id', 'in', employee_ids),
            ('state', '=', 'validate'),
            ('request_date_from', '<=', check_date),
            ('request_date_to', '>=', check_date)
        ], ['employee_id'])

        # Create set of employees on leave
        employees_on_leave = {leave['employee_id'][0] for leave in leave_data}

        # Fetch existing correction records to avoid duplicates
        existing_corrections = self.search_read([
            ('employee_id', 'in', employee_ids),
            ('date', '=', check_date)
        ], ['employee_id', 'reason_code'])

        # Group existing corrections by employee and reason
        existing_by_employee = {}
        for correction in existing_corrections:
            emp_id = correction['employee_id'][0]
            reason = correction['reason_code']
            if emp_id not in existing_by_employee:
                existing_by_employee[emp_id] = set()
            existing_by_employee[emp_id].add(reason)

        # Bulk fetch calendar data
        calendar_ids = set()
        for emp in employee_ids:
            contract = contracts_by_employee.get(emp)
            if contract and contract['resource_calendar_id']:
                calendar_ids.add(contract['resource_calendar_id'][0])

        # Also get employee calendars
        employee_calendar_data = self.env['hr.employee'].search_read([
            ('id', 'in', employee_ids),
            ('resource_calendar_id', '!=', False)
        ], ['id', 'resource_calendar_id'])

        for emp_cal in employee_calendar_data:
            if emp_cal['resource_calendar_id']:
                calendar_ids.add(emp_cal['resource_calendar_id'][0])

        # Get company calendars
        company_ids = self.env['hr.employee'].search_read([
            ('id', 'in', employee_ids)
        ], ['company_id'])

        for comp in company_ids:
            if comp['company_id']:
                company_calendar = self.env['res.company'].browse(comp['company_id'][0]).resource_calendar_id
                if company_calendar:
                    calendar_ids.add(company_calendar.id)

        # Bulk fetch calendar data
        calendar_data = {}
        if calendar_ids:
            calendars = self.env['resource.calendar'].search_read([
                ('id', 'in', list(calendar_ids))
            ], ['id', 'hours_per_day'])

            for cal in calendars:
                calendar_data[cal['id']] = cal

            # Fetch attendance lines for working day calculation
            weekday = check_date.weekday()
            attendance_lines_data = self.env['resource.calendar.attendance'].search_read([
                ('calendar_id', 'in', list(calendar_ids)),
                ('dayofweek', '=', str(weekday))
            ], ['calendar_id', 'hour_from', 'hour_to'])

            # Group attendance lines by calendar
            attendance_lines_by_calendar = {}
            for line in attendance_lines_data:
                cal_id = line['calendar_id'][0]
                if cal_id not in attendance_lines_by_calendar:
                    attendance_lines_by_calendar[cal_id] = []
                attendance_lines_by_calendar[cal_id].append(line)

            # Add attendance lines to calendar data
            for cal_id, lines in attendance_lines_by_calendar.items():
                if cal_id in calendar_data:
                    calendar_data[cal_id]['attendance_lines'] = lines

        return {
            'attendance_by_employee': attendance_by_employee,
            'contracts_by_employee': contracts_by_employee,
            'employees_on_leave': employees_on_leave,
            'existing_by_employee': existing_by_employee,
            'calendar_data': calendar_data
        }

    def _process_employee_batch(self, employees_data, check_date, batch_data):
        """
        Process a batch of employees and return correction records to create
        """
        corrections_to_create = []
        minute_allowed = self._get_minute_allowed()  # grace minutes for late check-in

        for employee_data in employees_data:
            employee_id = employee_data['id']

            # Skip if employee is on leave
            if employee_id in batch_data['employees_on_leave']:
                continue

            # Get employee's attendance for the date
            employee_attendance = batch_data['attendance_by_employee'].get(employee_id, [])

            # Check if it's a working day
            if not self._is_working_day_optimized(employee_data, check_date, batch_data):
                continue

            # Get expected hours and schedule
            expected_hours = self._get_expected_hours_optimized(employee_data, batch_data)
            schedule_hours = self._get_schedule_time_range_optimized(employee_data, check_date, batch_data)

            if not employee_attendance:
                # NO_SHOW case
                if 'NO_SHOW' not in batch_data['existing_by_employee'].get(employee_id, set()):
                    corrections_to_create.append({
                        'employee_id': employee_id,
                        'date': check_date,
                        'reason_code': 'NO_SHOW',
                        'worked_hours': 0.0,
                        'expected_hours': expected_hours,
                        'shortfall': expected_hours,
                        'check_in': None,
                        'check_out': None,
                        'schedule_hours': schedule_hours,
                        'department_id': employee_data['department_id'][0] if employee_data['department_id'] else None,
                        'company_id': employee_data['company_id'][0] if employee_data['company_id'] else None,
                    })
            else:
                # Check for SHORT_HOURS
                completed_attendance = [att for att in employee_attendance if att['check_out']]
                if completed_attendance:
                    total_worked_hours = sum(att['worked_hours'] or 0 for att in completed_attendance)

                    if total_worked_hours < expected_hours:
                        # Apply grace only against late check-in vs scheduled start
                        # Resolve earliest scheduled start from calendar lines
                        calendar_id = None
                        contract = batch_data['contracts_by_employee'].get(employee_id)
                        if contract and contract['resource_calendar_id']:
                            calendar_id = contract['resource_calendar_id'][0]
                        elif employee_data.get('resource_calendar_id'):
                            calendar_id = employee_data['resource_calendar_id'][0]

                        earliest_start = None
                        if calendar_id and calendar_id in batch_data['calendar_data']:
                            cal = batch_data['calendar_data'][calendar_id]
                            lines = cal.get('attendance_lines', []) or []
                            if lines:
                                earliest_start = min(line['hour_from'] for line in lines)

                        check_in_times = [att['check_in'] for att in completed_attendance if att['check_in']]
                        check_out_times = [att['check_out'] for att in completed_attendance if att['check_out']]

                        effective_expected_hours = expected_hours
                        if earliest_start is not None and check_in_times:
                            scheduled_start_dt = datetime.combine(
                                check_date,
                                time(int(earliest_start), int((earliest_start % 1) * 60))
                            )
                            actual_first_check_in = min(check_in_times)
                            delay_minutes = max(0,
                                                int((actual_first_check_in - scheduled_start_dt).total_seconds() // 60))
                            discount_minutes = min(delay_minutes, minute_allowed)
                            effective_expected_hours = max(0.0, expected_hours - (discount_minutes / 60.0))

                        if total_worked_hours < effective_expected_hours:
                            if 'SHORT_HOURS' not in batch_data['existing_by_employee'].get(employee_id, set()):
                                corrections_to_create.append({
                                    'employee_id': employee_id,
                                    'date': check_date,
                                    'reason_code': 'SHORT_HOURS',
                                    'worked_hours': total_worked_hours,
                                    'expected_hours': expected_hours,
                                    'shortfall': effective_expected_hours - total_worked_hours,
                                    'check_in': min(check_in_times) if check_in_times else None,
                                    'check_out': max(check_out_times) if check_out_times else None,
                                    'schedule_hours': schedule_hours,
                                    'department_id': employee_data['department_id'][0] if employee_data[
                                        'department_id'] else None,
                                    'company_id': employee_data['company_id'][0] if employee_data[
                                        'company_id'] else None,
                                })

        return corrections_to_create

    @api.model
    def _get_minute_allowed(self) -> int:
        # Grace minutes allowed (global setting)
        return int(self.env['ir.config_parameter'].sudo().get_param('hr_attendance.minute_allowed', 15))

    def _get_expected_hours_optimized(self, employee_data, batch_data):
        """
        Optimized version using pre-fetched data
        """
        employee_id = employee_data['id']

        # Try contract calendar first
        contract = batch_data['contracts_by_employee'].get(employee_id)
        if contract and contract['resource_calendar_id']:
            calendar_id = contract['resource_calendar_id'][0]
            calendar = batch_data['calendar_data'].get(calendar_id)
            if calendar and calendar.get('hours_per_day'):
                return calendar['hours_per_day']

        # Try employee calendar
        if employee_data['resource_calendar_id']:
            calendar_id = employee_data['resource_calendar_id'][0]
            calendar = batch_data['calendar_data'].get(calendar_id)
            if calendar and calendar.get('hours_per_day'):
                return calendar['hours_per_day']

        # Default to 8 hours (company calendar lookup omitted for simplicity)
        return 8.0

    def _get_schedule_time_range_optimized(self, employee_data, check_date, batch_data):
        """
        Optimized version using pre-fetched calendar data
        """
        employee_id = employee_data['id']

        # Get calendar ID
        calendar_id = None
        contract = batch_data['contracts_by_employee'].get(employee_id)
        if contract and contract['resource_calendar_id']:
            calendar_id = contract['resource_calendar_id'][0]
        elif employee_data['resource_calendar_id']:
            calendar_id = employee_data['resource_calendar_id'][0]

        if not calendar_id or calendar_id not in batch_data['calendar_data']:
            return "No Schedule"

        calendar = batch_data['calendar_data'][calendar_id]
        attendance_lines = calendar.get('attendance_lines', [])

        if not attendance_lines:
            return "No Schedule"

        # Find earliest start time and latest end time
        earliest_start = min(line['hour_from'] for line in attendance_lines)
        latest_end = max(line['hour_to'] for line in attendance_lines)

        # Format as HH:MM-HH:MM
        start_time = f"{int(earliest_start):02d}:{int((earliest_start % 1) * 60):02d}"
        end_time = f"{int(latest_end):02d}:{int((latest_end % 1) * 60):02d}"

        return f"{start_time}-{end_time}"

    def _is_working_day_optimized(self, employee_data, check_date, batch_data):
        """
        Optimized working day check using pre-fetched data,
        but allows Sunday/holiday work if company and employee rules permit.
        """
        employee_id = employee_data['id']

        # Get calendar ID
        calendar_id = None
        contract = batch_data['contracts_by_employee'].get(employee_id)
        if contract and contract['resource_calendar_id']:
            calendar_id = contract['resource_calendar_id'][0]
        elif employee_data['resource_calendar_id']:
            calendar_id = employee_data['resource_calendar_id'][0]

        # Get company record for this employee (needed for company rule check)
        company_id = employee_data['company_id'][0] if employee_data['company_id'] else None
        company_rule_enabled = False
        if company_id:
            company = self.env['res.company'].browse(company_id)
            company_rule_enabled = bool(company.Enable_Sunday_Rule)

        # Check if employee allows work on non-working days
        allow_on_non_working_day = False
        emp_record = self.env['hr.employee'].browse(employee_id)
        if emp_record.Allow_work_on_sunday:
            allow_on_non_working_day = True

        # If no calendar data
        if not calendar_id or calendar_id not in batch_data['calendar_data']:
            # If company+employee allow work on non-working day, treat as working day
            if company_rule_enabled and allow_on_non_working_day:
                return True
            return False

        calendar = batch_data['calendar_data'][calendar_id]
        attendance_lines = calendar.get('attendance_lines', [])

        if attendance_lines:
            return True

        # No attendance lines (non-working day) but rule applies
        if company_rule_enabled and allow_on_non_working_day:
            return True

        return False

    # Keep the original methods for backward compatibility and individual operations
    def _get_expected_hours(self, employee, check_date):
        """Original method - kept for backward compatibility"""
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', check_date),
            '|', ('date_end', '=', False), ('date_end', '>=', check_date)
        ], limit=1)

        if contract and contract.resource_calendar_id:
            return contract.resource_calendar_id.hours_per_day

        if employee.resource_calendar_id:
            return employee.resource_calendar_id.hours_per_day

        if employee.company_id.resource_calendar_id:
            return employee.company_id.resource_calendar_id.hours_per_day

        return 8.0

    def _get_schedule_time_range(self, employee, check_date):
        """Original method - kept for backward compatibility"""
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', check_date),
            '|', ('date_end', '=', False), ('date_end', '>=', check_date)
        ], limit=1)

        calendar = None
        if contract and contract.resource_calendar_id:
            calendar = contract.resource_calendar_id
        elif employee.resource_calendar_id:
            calendar = employee.resource_calendar_id
        elif employee.company_id.resource_calendar_id:
            calendar = employee.company_id.resource_calendar_id

        if not calendar:
            return "No Schedule"

        weekday = check_date.weekday()
        attendance_lines = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == weekday)
        if not attendance_lines:
            return "No Schedule"

        earliest_start = min(attendance_lines.mapped('hour_from'))
        latest_end = max(attendance_lines.mapped('hour_to'))

        start_time = f"{int(earliest_start):02d}:{int((earliest_start % 1) * 60):02d}"
        end_time = f"{int(latest_end):02d}:{int((latest_end % 1) * 60):02d}"

        return f"{start_time}-{end_time}"

    def _is_working_day(self, employee, check_date):
        """Original method - kept for backward compatibility"""
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', check_date),
            '|', ('date_end', '=', False), ('date_end', '>=', check_date)
        ], limit=1)

        calendar = None
        if contract and contract.resource_calendar_id:
            calendar = contract.resource_calendar_id
        elif employee.resource_calendar_id:
            calendar = employee.resource_calendar_id
        elif employee.company_id.resource_calendar_id:
            calendar = employee.company_id.resource_calendar_id

        if not calendar:
            return False

        day_of_week = check_date.weekday()
        return calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == day_of_week)

    @api.model
    def scheduled_attendance_check(self):
        """
        Scheduled action method to check attendance for the previous day
        """
        yesterday = date.today() - timedelta(days=1)
        _logger.info(f"Scheduled attendance check running at {datetime.now()}")
        _logger.info(f"Checking attendance for previous day: {yesterday}")

        records_created = self.check_attendance_for_date(yesterday)
        _logger.info(f"Scheduled check completed. Created {records_created} records for {yesterday}")
        return records_created

    @api.model
    def manual_attendance_check(self, check_date=None, employee_ids=None):
        if not check_date:
            check_date = date.today()
        _logger.info(f"Manual attendance check for date: {check_date}, employees: {employee_ids or 'ALL'}")
        return self.check_attendance_for_date(check_date, employee_ids=employee_ids)

    def action_bulk_no_show_create(self):
        """
        Optimized bulk create attendance for selected NO_SHOW corrections
        """
        Attendance = self.env['hr.attendance']
        no_show_records = self.sudo().filtered(lambda r: r.reason_code == 'NO_SHOW')

        if not no_show_records:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("No Records"),
                    'message': _("Please select at least one record."),
                    'sticky': False,
                    'type': 'info',
                }
            }

        created = 0
        errors = []
        attendance_to_create = []
        records_to_delete = []

        # Bulk fetch existing attendance data to avoid N+1 queries
        employee_ids = no_show_records.mapped('employee_id.id')
        dates = list(set(no_show_records.mapped('date')))

        # Create date ranges for bulk query
        existing_attendance = {}
        for check_date in dates:
            date_start = datetime.combine(check_date, time.min)
            date_end = datetime.combine(check_date, time.max)

            attendance_data = Attendance.sudo().search_read([
                ('employee_id', 'in', employee_ids),
                ('check_in', '>=', date_start),
                ('check_in', '<=', date_end)
            ], ['employee_id', 'worked_hours'])

            for att in attendance_data:
                key = (att['employee_id'][0], check_date)
                if key not in existing_attendance:
                    existing_attendance[key] = []
                existing_attendance[key].append(att)

        for rec in no_show_records:
            # Check if employee already has sufficient attendance for this date
            key = (rec.employee_id.id, rec.date)
            existing_att = existing_attendance.get(key, [])

            if existing_att:
                total_worked_hours = sum(att['worked_hours'] or 0 for att in existing_att)
                expected_hours = rec.expected_hours or 8.0

                if total_worked_hours >= (expected_hours * 0.8):
                    errors.append(
                        f"Employee {rec.employee_id.name} already has {total_worked_hours:.1f}h attendance on {rec.date}")
                    records_to_delete.append(rec.id)
                    continue

            # Get work schedule start and end times
            check_in, check_out = self._get_workday_start_end_times(rec.employee_id, rec.date)
            if not check_in or not check_out:
                errors.append(f"No work schedule found for {rec.employee_id.name} on {rec.date}")
                continue

            # Prepare attendance record for bulk creation
            attendance_to_create.append({
                'employee_id': rec.employee_id.id,
                'check_in': check_in,
                'check_out': check_out,
                'attendance_note': 'No show manual adjustment',
            })
            records_to_delete.append(rec.id)
            created += 1

        # Bulk create attendance records
        if attendance_to_create:
            try:
                Attendance.sudo().create(attendance_to_create)
            except Exception as e:
                raise UserError(f"Failed to create attendance records: {str(e)}")

        # Bulk delete correction records
        if records_to_delete:
            self.browse(records_to_delete).unlink()

        # === Sticky Notification Response ===
        message = f"Created {created} attendance records."
        if errors:
            message += f"\n{len(errors)} issues encountered."
            for error in errors[:3]:
                message += f"\n- {error}"
            if len(errors) > 3:
                message += f"\n... and {len(errors) - 3} more"

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Attendance Bulk Update"),
                'message': message,
                'sticky': False,
                'type': 'success' if created else 'warning',
                "next": {
                    "type": "ir.actions.act_window_close",
                }
            }
        }

    def _get_workday_start_end_times(self, employee, work_date):
        """Get the earliest start time and latest end time for the employee's workday."""
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', work_date),
            '|', ('date_end', '=', False), ('date_end', '>=', work_date)
        ], limit=1)

        calendar = None
        if contract and contract.resource_calendar_id:
            calendar = contract.resource_calendar_id
        elif employee.resource_calendar_id:
            calendar = employee.resource_calendar_id
        elif employee.company_id.resource_calendar_id:
            calendar = employee.company_id.resource_calendar_id

        if not calendar:
            return (None, None)

        weekday = work_date.weekday()
        attendance_lines = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == weekday)

        # Fallback: if no schedule found for this day (holiday/week off), pick first available working day
        if not attendance_lines:
            # All attendance lines sorted by dayofweek
            all_days_with_attendance = calendar.attendance_ids.sorted(key=lambda a: a.dayofweek)

            if all_days_with_attendance:
                # Get the earliest dayofweek in the schedule
                first_day = all_days_with_attendance[0].dayofweek

                # Filter lines for just that first day
                first_day_lines = all_days_with_attendance.filtered(lambda l: l.dayofweek == first_day)

                earliest_start = min(first_day_lines.mapped('hour_from'))
                latest_end = max(first_day_lines.mapped('hour_to'))
            else:
                return (None, None)
        else:
            earliest_start = min(attendance_lines.mapped('hour_from'))
            latest_end = max(attendance_lines.mapped('hour_to'))

        # Get user timezone
        user_tz = self.env.user.tz or 'UTC'
        check_in_local = datetime.combine(work_date, time(int(earliest_start), int((earliest_start % 1) * 60)))
        check_out_local = datetime.combine(work_date, time(int(latest_end), int((latest_end % 1) * 60)))

        local_tz = pytz.timezone(user_tz)
        utc_tz = pytz.UTC

        check_in_local = local_tz.localize(check_in_local)
        check_out_local = local_tz.localize(check_out_local)

        check_in_utc = check_in_local.astimezone(utc_tz).replace(tzinfo=None)
        check_out_utc = check_out_local.astimezone(utc_tz).replace(tzinfo=None)

        return (check_in_utc, check_out_utc)

    def action_add_attendance(self):
        """For NO_SHOW: Create a single attendance record for this employee/date and remove the correction."""
        self.ensure_one()
        if self.reason_code != 'NO_SHOW':
            raise UserError("This action is only for NO SHOW records.")

        check_in, check_out = self._get_workday_start_end_times(self.employee_id, self.date)
        if not check_in or not check_out:
            raise UserError("No work schedule found for this employee on this date.")

        self.env['hr.attendance'].create({
            'employee_id': self.employee_id.id,
            'check_in': check_in,
            'check_out': check_out,
            'attendance_note': 'No show manual adjustment',
        })
        self.unlink()
        return True

    def action_edit_attendance(self):
        """For SHORT_HOURS: Open the related attendance record(s) for editing."""
        self.ensure_one()

        if self.reason_code != 'SHORT_HOURS':
            raise UserError("This action is only for SHORT HOURS records.")

        return {
            'name': _('Edit Attendance'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.attendance',
            'view_mode': 'tree,form',
            'domain': [
                ('employee_id', '=', self.employee_id.id),
                ('check_in', '>=', datetime.combine(self.date, time.min)),
                ('check_in', '<=', datetime.combine(self.date, time.max))
            ],
            'context': {
                'default_employee_id': self.employee_id.id,
                'default_check_in': self.date,
                'from_correction': True,  # Important flag for the write override
                'correction_record_id': self.id,  # Optional: track which correction triggered this
            },
            'target': 'current',
        }


class AttendanceCheckWizard(models.TransientModel):
    _name = 'attendance.check.wizard'
    _description = 'Manual Attendance Check Wizard'

    check_date_from = fields.Date(string="From Date", required=True, default=fields.Date.today)
    check_date_to = fields.Date(string="To Date", required=True, default=fields.Date.today)
    employee_ids = fields.Many2many(
        'hr.employee',
        string="Employees",
        help="Select employees to check. Leave empty to check all employees."
    )

    @api.constrains('check_date_from', 'check_date_to')
    def _check_date_range(self):
        for record in self:
            if record.check_date_from > record.check_date_to:
                raise ValidationError("From Date must be earlier than or equal to To Date.")

            # Optional: limit range to prevent performance issues
            date_diff = (record.check_date_to - record.check_date_from).days
            if date_diff > 31:  # More than 31 days
                raise ValidationError("Date range cannot exceed 31 days.")

    def action_run_manual_check(self):
        """Run attendance check for date range"""
        AttendanceCorrection = self.env['temp.attendance.correction']
        total_records = 0

        current_date = self.check_date_from
        while current_date <= self.check_date_to:
            daily_records = AttendanceCorrection.manual_attendance_check(
                current_date,
                employee_ids=self.employee_ids.ids if self.employee_ids else None
            )
            # daily_records = AttendanceCorrection.manual_attendance_check(current_date)
            total_records += daily_records
            _logger.info(f"Processed {daily_records} records for {current_date}")
            current_date += timedelta(days=1)

        _logger.info(f"Manual attendance check completed. Total records created: {total_records}")

        # Format dates in user’s language
        lang = self.env.user.lang or "en_US"
        date_from_str = format_date(self.env, self.check_date_from, lang_code=lang)
        date_to_str = format_date(self.env, self.check_date_to, lang_code=lang)

        # Return notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Attendance Check Completed',
                'message': f'Created {total_records} correction records from {date_from_str} to {date_to_str}',
                'type': 'success',
                'sticky': False,
                "next": {
                    "type": "ir.actions.act_window_close",
                }
            }
        }
