import pytz
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta


class AttendanceController(http.Controller):

    @http.route('/web/attendance_dashboard', type='json', auth='user')
    def get_attendance_data(self, user_id, date):
        try:
            selected_date = datetime.strptime(date, "%Y-%m-%d").date()
            today_date = datetime.now().date()

            # Show only leave data for future dates
            if selected_date > today_date:
                leave_info = []
                employees = request.env['hr.employee'].search([('parent_id.user_id', '=', user_id)])
                if not employees:
                    return {'message': 'No employees found under this user'}

                for employee in employees:
                    leave = request.env['hr.leave'].search([
                        ('employee_id', '=', employee.id),
                        ('state', '=', 'validate'),
                        ('request_date_from', '<=', selected_date),
                        ('request_date_to', '>=', selected_date)
                    ])

                    profile_picture = employee.image_1920

                    if leave:
                        for l in leave:
                            leave_info.append({
                                'leave_type': l.holiday_status_id.name,
                                'leave_status': l.state,
                                'employee': employee.name,
                                'date': selected_date.strftime('%Y-%m-%d'),
                                'work_phone': employee.work_phone,
                                'work_mobile': employee.mobile_phone,
                                'picture': profile_picture,
                            })
                return {'present': [],
                        'absent': [],
                        'late_checkin': [],
                        'early_checkout': [], 'leave': leave_info, 'all_data': leave_info}
            user = request.env['res.users'].browse(user_id)

            if not user.exists():
                return {'error': 'Invalid user ID'}

            user_timezone = pytz.timezone(user.tz or 'UTC')

            start_of_day = user_timezone.localize(
                datetime.combine(selected_date, datetime.min.time())
            ).astimezone(pytz.utc)
            end_of_day = user_timezone.localize(
                datetime.combine(selected_date, datetime.max.time())
            ).astimezone(pytz.utc)

            late_allowance_minutes = int(
                request.env['ir.config_parameter'].sudo().get_param('attendance.minute_allowed', default=0)
            )

            employees = request.env['hr.employee'].search([('parent_id.user_id', '=', user_id)])
            if not employees:
                return {'message': 'No employees found under this user'}

            results = {
                'present': [],
                'absent': [],
                'leave': [],
                'late_checkin': [],
                'early_checkout': [],
                'all_data': [],
            }

            for employee in employees:

                attendances = request.env['hr.attendance'].search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', start_of_day),
                    ('check_in', '<=', end_of_day)
                ])

                leave = request.env['hr.leave'].search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'validate'),
                    ('request_date_from', '<=', selected_date),
                    ('request_date_to', '>=', selected_date)
                ])

                resource_calendar = employee.resource_calendar_id
                work_from_hour = 9
                work_to_hour = 18

                if resource_calendar:
                    weekday = selected_date.weekday()
                    for calendar_attendance in resource_calendar.attendance_ids:
                        if int(calendar_attendance.dayofweek) == weekday and calendar_attendance.day_period == 'morning':
                            work_from_hour = int(calendar_attendance.hour_from)

                        if int(calendar_attendance.dayofweek) == weekday and calendar_attendance.day_period == 'evening':
                            work_to_hour = int(calendar_attendance.hour_to)

                profile_picture = employee.image_1920

                if attendances:
                    first_attendance = attendances[-1]
                    check_in_time_utc = first_attendance.check_in
                    check_in_time_local = check_in_time_utc.astimezone(user_timezone).time()

                    total_minutes = int(work_from_hour * 60) + late_allowance_minutes
                    allowed_time = timedelta(minutes=total_minutes)

                    if check_in_time_local > (datetime.min + allowed_time).time():
                        results['late_checkin'].append({
                            'employee': employee.name,
                            'check_in': first_attendance.check_in.astimezone(user_timezone),
                            'check_in_latitude': first_attendance.in_latitude,
                            'check_in_longitude': first_attendance.in_longitude,
                            'check_in_Address': first_attendance.check_in_address,
                            'work_phone': employee.work_phone,
                            'work_mobile': employee.mobile_phone,
                            'picture': profile_picture,

                        })

                    last_attendance = attendances[0]
                    check_out_time_utc = last_attendance.check_out
                    check_out_time_local = check_out_time_utc.astimezone(
                        user_timezone).time() if check_out_time_utc else None

                    expected_end_time = timedelta(hours=work_to_hour)

                    if check_out_time_local and datetime.min + timedelta(hours=check_out_time_local.hour,
                                                                         minutes=check_out_time_local.minute) < datetime.min + expected_end_time:
                        results['early_checkout'].append({
                            'employee': employee.name,
                            'work_phone': employee.work_phone,
                            'work_mobile': employee.mobile_phone,
                            'check_in': last_attendance.check_in.astimezone(user_timezone),
                            'check_in_latitude': last_attendance.in_latitude,
                            'check_in_longitude': last_attendance.in_longitude,
                            'check_in_Address': last_attendance.check_in_address,
                            'check_out': last_attendance.check_out and last_attendance.check_out.astimezone(
                                user_timezone),
                            'check_out_Address': last_attendance.check_out_address,
                            'check_out_latitude': last_attendance.out_latitude,
                            'check_out_longitude': last_attendance.out_longitude,
                            'picture': profile_picture,
                        })

                    for attendance in attendances:
                        results['present'].append({
                            'employee': employee.name,
                            'check_in': attendance.check_in.astimezone(user_timezone),
                            'check_out': attendance.check_out and attendance.check_out.astimezone(user_timezone),
                            'check_in_Address': attendance.check_in_address,
                            'check_out_Address': attendance.check_out_address,
                            'work_phone': employee.work_phone,
                            'work_mobile': employee.mobile_phone,
                            'check_in_latitude': attendance.in_latitude,
                            'check_in_longitude': attendance.in_longitude,
                            'check_out_latitude': attendance.out_latitude,
                            'check_out_longitude': attendance.out_longitude,
                            'picture': profile_picture,
                        })
                        results['all_data'].append({
                            'employee': employee.name,
                            'check_in': attendance.check_in.astimezone(user_timezone),
                            'check_out': attendance.check_out and attendance.check_out.astimezone(user_timezone),
                            'work_phone': employee.work_phone,
                            'work_mobile': employee.mobile_phone,
                            'check_in_latitude': attendance.in_latitude,
                            'check_in_longitude': attendance.in_longitude,
                            'check_out_latitude': attendance.out_latitude,
                            'check_out_longitude': attendance.out_longitude,
                            'check_in_Address': attendance.check_in_address,
                            'check_out_Address': attendance.check_out_address,
                            'picture': profile_picture,

                        })

                elif leave:
                    leave_info = []
                    for l in leave:
                        leave_info.append({
                            'leave_type': l.holiday_status_id.name,
                            'leave_status': l.state,
                            'employee': employee.name,
                            'date': selected_date.strftime('%Y-%m-%d'),

                            'work_phone': employee.work_phone,
                            'work_mobile': employee.mobile_phone,
                            'picture': profile_picture,
                        })
                    results['leave'].extend(leave_info)
                    results['all_data'].append({'employee': employee.name,
                                                'work_phone': employee.work_phone,
                                                'work_mobile': employee.mobile_phone, 'status': 'On Leave',
                                                'date': selected_date.strftime('%Y-%m-%d'),
                                                'picture': profile_picture,
                                                })

                else:
                    results['absent'].append({'employee': employee.name, 'work_phone': employee.work_phone,
                                              'work_mobile': employee.mobile_phone,
                                              'date': selected_date.strftime('%Y-%m-%d'), 'picture': profile_picture,

                                              })
                    results['all_data'].append({'employee': employee.name, 'work_phone': employee.work_phone,
                                                'work_mobile': employee.mobile_phone, 'status': 'Absent',
                                                'date': selected_date.strftime('%Y-%m-%d'), 'picture': profile_picture,
                                                })

            return results

        except Exception as e:
            return {'error': str(e)}