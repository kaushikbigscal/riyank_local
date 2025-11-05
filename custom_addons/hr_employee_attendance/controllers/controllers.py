from odoo import http
from odoo.http import request
from odoo.service import security
import werkzeug.wrappers
from datetime import datetime, time
from pytz import timezone
from lxml import etree
import pytz
import json
from odoo import models, fields, api, _, exceptions, http
from odoo.exceptions import ValidationError


class AllAccessRightsController(http.Controller):
    @http.route('/web/check_all_access_rights', type='json', auth='user')
    def check_all_access_rights(self, model_name):
        """
        API to check a user's access rights on a given model.

        :param model_name: Odoo model name (e.g., 'res.partner')
        :return: Dictionary containing access rights for CRUD operations
        """
        if not model_name:
            return {"status": False, "error": "Model name is required"}

        # Validate if the model exists
        if model_name not in request.env:
            return {"status": False, "error": f"Invalid model name: {model_name}"}

        result = {}
        operations = ["create", "read", "write", "unlink"]

        for operation in operations:
            try:
                result[operation] = request.env[model_name].check_access_rights(operation, raise_exception=False)
            except Exception as e:
                result[operation] = False  # Instead of exposing raw errors, return False

        return {"status": True, "access_rights": result}


class MenuAPIController(http.Controller):
    @http.route('/web/get_user_menus', type='json', auth='user')
    def get_user_menus(self):
        try:
            user = request.env.user
            user_groups = user.groups_id.ids

            # Define allowed top-level menu names
            allowed_menu_names = ['CRM', 'Project', 'To-do', 'Attendances', 'Leave', 'Service Call', 'Contacts',
                                  'Discuss']

            # Explicitly exclude menus under Settings/Technical path
            Menu = request.env['ir.ui.menu']

            # Get top-level menus matching our list, but exclude those under Settings/Technical
            top_menus = Menu.search([
                ('name', 'in', allowed_menu_names),
                '|', ('groups_id', 'in', user_groups), ('groups_id', '=', False)
            ])

            if not top_menus:
                return {
                    'user_groups': user_groups,
                    'menus': []
                }

            # Get all children of the allowed top menus
            all_menu_ids = []
            for menu in top_menus:
                all_menu_ids.append(menu.id)

                # Get all child menus using Odoo's domain operator
                child_menus = Menu.search([
                    ('id', 'child_of', menu.id),
                    ('id', '!=', menu.id),  # Exclude the parent itself
                ])
                all_menu_ids.extend(child_menus.ids)

            # Check each menu's actual accessibility
            accessible_menu_ids = []
            for menu_id in all_menu_ids:
                menu = Menu.browse(menu_id)

                # Skip menus under Settings/Technical
                if 'Settings/Technical' in menu.complete_name:
                    continue

                # Check group restrictions
                if menu.groups_id and not set(menu.groups_id.ids).intersection(set(user_groups)):
                    continue

                # If menu has an action, verify model access
                if menu.action and menu.action._name == 'ir.actions.act_window' and menu.action.res_model:
                    model_name = menu.action.res_model
                    if model_name not in request.env:
                        continue

                    try:
                        # Check read permission
                        model = request.env[model_name]
                        model.check_access_rights('read')
                    except Exception:
                        continue

                # Menu is accessible
                accessible_menu_ids.append(menu_id)

            # Get menu data
            if accessible_menu_ids:
                menus = Menu.search_read(
                    [('id', 'in', accessible_menu_ids)],
                    fields=['name', 'id', 'parent_id', 'child_id', 'action', 'sequence',
                            'complete_name', 'web_icon', 'is_quick', 'is_for_mobile'],
                    order='parent_path, sequence'
                )

                # Final filter to remove any Settings/Technical menus that might have slipped through
                menus = [menu for menu in menus if 'Settings/Technical' not in menu['complete_name']]
            else:
                menus = []

            return {
                'user_groups': user_groups,
                'menus': menus,
            }

        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(f"Error in get_user_menus: {str(e)}")
            return {
                'error': str(e),
                'menus': []
            }


# class MenuAPIController(http.Controller):
#     @http.route('/web/get_user_menus', type='json', auth='user')
#     def get_user_menus(self):
#         try:
#             user = request.env.user
#             user_groups = user.groups_id.ids  # Get user's group IDs
#
#             # Fetch menus visible to the user's groups or globally accessible
#             menus = request.env['ir.ui.menu'].search_read(
#                 ['|', ('groups_id', 'in', user_groups), ('groups_id', '=', False)],
#                 fields=['name', 'id', 'parent_id', 'child_id', 'action', 'sequence',
#                         'complete_name', 'web_icon', 'is_quick', 'is_for_mobile'],
#                 order='parent_path, sequence'
#             )
#
#             # Create a dictionary for faster parent lookups
#             menu_dict = {menu['id']: menu for menu in menus}
#             allowed_menus = ['CRM', 'Project', 'To-do', 'Attendances', 'Leave', 'Service Call', 'Contacts', 'Discuss']
#             filtered_menus = []
#
#             # Filter menus with proper parent checking
#             for menu in menus:
#                 # Include if it's an allowed top menu
#                 if menu['name'] in allowed_menus:
#                     filtered_menus.append(menu)
#                     continue
#
#                 # Include if it's a child of an allowed menu
#                 if menu['parent_id']:
#                     parent_id = menu['parent_id'][0]
#                     current_parent = menu_dict.get(parent_id)
#
#                     # Check parent chain until we find an allowed menu or reach the top
#                     while current_parent:
#                         if current_parent['name'] in allowed_menus:
#                             filtered_menus.append(menu)
#                             break
#                         if not current_parent.get('parent_id'):
#                             break
#                         parent_id = current_parent['parent_id'][0]
#                         current_parent = menu_dict.get(parent_id)
#
#             return {
#                 'user_groups': user_groups,
#                 'menus': filtered_menus,
#             }
#
#         except Exception as e:
#             return {
#                 'error': str(e),
#                 'menus': []
#             }

class FormAPI(http.Controller):

    @http.route('/web/relation_data', type='json', auth='user')
    def get_relation_data(self):
        """
        Fetch data from a related model.

        :return: JSON response with related data or error message.
        """
        try:
            # Parse JSON data from the request body
            request_data = request.httprequest.get_json()

            # Extract parameters
            model_name = request_data.get('model_name')
            fields_to_fetch = request_data.get('fields_to_fetch', ['id', 'name', 'display_name'])

            if not model_name:
                return {'status': 'error', 'message': 'Parameter "model_name" is required.'}

            # Check if the model exists
            if model_name not in request.env:
                return {'status': 'error', 'message': f'Model {model_name} does not exist.'}

            # Fetch records
            records = request.env[model_name].search([])
            data = records.read(fields_to_fetch)

            return {'status': 'success', 'data': data}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

 
class AttendanceAPI(http.Controller):

    @http.route('/web/attendance/validate', type='json', auth='user')
    def validate_attendance(self, employee_id, check_in):
        check_in_date = fields.Datetime.from_string(check_in)
        user_tz = request.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)
        check_in_date = pytz.UTC.localize(check_in_date).astimezone(local_tz)

        attendance_count = request.env['hr.attendance'].sudo().search_count([
            ('employee_id', '=', employee_id),
            ('check_in', '>=', check_in_date.replace(hour=0, minute=0, second=0, microsecond=0)),
            ('check_in', '<', check_in_date.replace(hour=23, minute=59, second=59, microsecond=999999))
        ])

        if attendance_count == 1:
            weekday = check_in_date.weekday()
            employee = request.env['hr.employee'].sudo().browse(employee_id)
            resource_calendar = employee.resource_calendar_id
            if resource_calendar:
                for attendance in resource_calendar.attendance_ids:
                    if int(attendance.dayofweek) == weekday and attendance.day_period == 'morning':
                        work_from_time = attendance.hour_from
            else:
                return {'message': 'resource calender not found.'}

            allowed_minutes = int(
                request.env['ir.config_parameter'].sudo().get_param('hr_attendance.minute_allowed', default=0)
            )
            total_minutes = int(work_from_time * 60) + allowed_minutes
            allowed_time = f"{total_minutes // 60:02}:{total_minutes % 60:02}"
            check_in_time = check_in_date.strftime('%H:%M')

            notify_late = bool(
                request.env['ir.config_parameter'].sudo().get_param('hr_attendance.notification_late_day_in',
                                                                    default=False)
            )
            if notify_late and check_in_time > allowed_time:
                return {
                    'message': 'You are reporting late for work your pay might be impacted.'}

        else:
            return {'message': 'Attendance validated successfully.'}

class GetSessionController(http.Controller):

    @http.route('/web/get_session_id', type='json', auth='user')
    def get_session_id(self):
        session_id = request.httprequest.cookies.get('session_id')
        csrf_token = request.csrf_token()
        return {'session_id': session_id,
                'csrf_token': csrf_token}

class CustomAuthController(http.Controller):

    @http.route('/web/session/authenticate', type='json', auth="none", csrf=False)
    def authenticate(self, db, login, password):
        try:
            # Call the original authentication method
            uid = request.session.authenticate(db, login, password)
            if uid:
                # Get the default response
                default_response = request.env['ir.http'].session_info()

                # Add attendance records if the user is an employee
                user = request.env['res.users'].sudo().browse(uid)
                image_data = user.image_1920
                if image_data:
                    default_response['profile_image'] = image_data
                # -------------------------------------------------------------------------------------
                company_id = user.company_id.id if user.company_id else False

                # Fetch the company details using the dynamic company ID
                company = request.env['res.company'].sudo().search([('id', '=', company_id)],
                                                                   limit=1) if company_id else None

                if company:
                    # Fetch the fields like enable_geofence, latitude, longitude, allowed_distance, etc.
                    default_response['company_geofence_info'] = {
                        'enable_geofence': company.enable_geofence,
                        'company_latitude': company.company_latitude,
                        'company_longitude': company.company_longitude,
                        'allowed_distance': company.allowed_distance,
                        'display_name': company.display_name
                    }
                # Fetch user-specific geofencing settings
                if user:
                    default_response['user_geofence_info'] = {
                        'enable_geofence': user.enable_geofence
                    }

                # -------------------------------------------------------------------------------------

                employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)

                if employee:
                    # Get the user's timezone
                    user_tz = timezone(user.tz or 'UTC')

                    # Get the current date in the user's timezone
                    current_date = datetime.now(user_tz).date()

                    # Define the start and end of the current day in the user's timezone
                    day_start = user_tz.localize(datetime.combine(current_date, time.min))
                    day_end = user_tz.localize(datetime.combine(current_date, time.max))

                    # Convert to UTC for the database query
                    day_start_utc = day_start.astimezone(timezone('UTC'))
                    day_end_utc = day_end.astimezone(timezone('UTC'))

                    attendance_records = request.env['hr.attendance'].sudo().search_read(
                        [
                            ('employee_id', '=', employee.id),
                            ('check_in', '>=', day_start_utc),
                            ('check_in', '<=', day_end_utc)
                        ],
                        ['check_in', 'check_out'],
                        order='check_in desc'
                    )

                    # Convert times back to user's timezone for display
                    for record in attendance_records:
                        if record['check_in']:
                            record['check_in'] = timezone('UTC').localize(record['check_in']).astimezone(
                                user_tz).strftime('%Y-%m-%d %H:%M:%S')
                        if record['check_out']:
                            record['check_out'] = timezone('UTC').localize(record['check_out']).astimezone(
                                user_tz).strftime('%Y-%m-%d %H:%M:%S')

                    default_response['attendance_records'] = attendance_records

                    # -------------------for department name and id -------------------

                    user = request.env['res.users'].sudo().browse(uid)
                    employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
                    if not employee:
                        return None

                    employee_info = {
                        'department_id': employee.department_id.id if employee.department_id else False,
                        'department_name': employee.department_id.name if employee.department_id else False
                    }
                    default_response['department_info'] = employee_info
                # ---------------------------------------------------------------------------
                return default_response
            else:
                return werkzeug.wrappers.Response(status=401, content_type='application/json')
        except Exception as e:
            return werkzeug.wrappers.Response(status=500, content_type='application/json')


class EmployeeActivityController(http.Controller):

    @http.route('/web/employee/activities', type='json', auth='user')
    def get_employee_activities(self, parent_employee_id):
        """
        Fetch all activities related to the parent employee and their assigned employees.
        Activities can be from any model (CRM, Sale, Project, etc.).
        """
        try:
            # Find the parent employee
            parent_employee = request.env['hr.employee'].browse(parent_employee_id)
            if not parent_employee.exists():
                return {'error': f"Parent Employee with ID {parent_employee_id} not found."}

            # Get all employees under the parent employee (using parent_id)
            assigned_employees = request.env['hr.employee'].search([('parent_id', '=', parent_employee.id)])

            all_employee_ids = assigned_employees.ids + [parent_employee.id]  # Include parent employee

            # Fetch all activities related to these employees
            activities = request.env['mail.activity'].search([
                ('user_id.employee_id', 'in', all_employee_ids)
            ])

            # Extract relevant data
            activities_data = activities.read(
                ['summary', 'activity_type_id', 'res_model', 'res_id', 'date_deadline', 'user_id'])
            activities_result = []

            for activity in activities_data:
                # For each activity, retrieve model details (CRM, Sale, Project, etc.)
                activity_details = {
                    'summary': activity['summary'],
                    'activity_type': activity['activity_type_id'][1] if activity['activity_type_id'] else None,
                    'model': activity['res_model'],
                    'res_id': activity['res_id'],
                    'date_deadline': activity['date_deadline'],
                    'assigned_user': activity['user_id']
                }
                activities_result.append(activity_details)

            result = {
                'parent_employee': parent_employee.name,
                'assigned_employees': assigned_employees.mapped('name'),
                'activities': activities_result,
            }
            return {
                'status': 'success',
                'result': result
            }

        except Exception as e:
            message = {str(e)}
            return {
                'status': 'false',
                'error': message
            }



class CustomAPIController(http.Controller):
    # original
    @http.route('/web/user_dashboard_counts', type='json', auth='user')
    def get_user_dashboard_counts(self):
        try:
            try:
                request_data = json.loads(request.httprequest.data.decode('utf-8'))
                params = request_data.get('params', {})
                args = params.get('args', [])
                user_data = args[0] if args else {}
                user_id = user_data.get('user_id')

                # Validate user_id
                if not user_id:
                    raise ValueError("Missing 'user_id' in the request parameters.")
            except Exception as parse_error:
                return parse_error

            # Fetch counts with error handling
            try:
                lead_count = request.env['crm.lead'].sudo().search_count([
                    ('user_id', '=', user_id),
                    ('type', '=', 'lead'),
                    ("active", "=", True),
                ])

                task_count = request.env['project.task'].sudo().search_count([
                    ('user_ids', 'in', [user_id]),
                    ("display_in_project", "=", True),
                    ("is_fsm", "=", False),
                    ("active", "=", True),
                    ("project_id.is_project_template", "=", False),
                    ("state", "in", ["01_in_progress", "02_changes_requested", "03_approved", "05_not_started"]),
                ])

                opportunity_count = request.env['crm.lead'].sudo().search_count([
                    ('type', '=', 'opportunity'),
                    ('user_id', '=', user_id),
                    ("active", "=", True),
                ])

                project_count = request.env['project.project'].sudo().search_count([
                    ('user_id', '=', user_id),
                    ("is_fsm", "=", False),
                    ("active", "=", True),
                    ("is_internal_project", "=", False),
                    ("is_project_template", "=", False),
                ])

                todo_count = request.env['project.task'].sudo().search_count([
                    ('user_ids', 'in', [user_id]),
                    ('project_id', '=', False),
                    ("parent_id", "=", False),
                    ("active", "=", True),
                    ("state", "in", ['01_in_progress', "05_not_started"]),
                ])

                call_count = request.env['project.task'].sudo().search_count([
                    ('user_ids', 'in', [user_id]),
                    ("project_id", "!=", False),
                    ("display_in_project", "=", True),
                    ("is_fsm", "=", True),
                    ("active", "=", True),
                    ("stage_id", "not in", ['Done', 'Canceled']),

                ])
            except Exception as query_error:
                message = {str(query_error)}
                return {
                    'status': 'false',
                    'error': message
                }

            result = {
                'lead_count': lead_count,
                'opportunity_count': opportunity_count,
                'project_count': project_count,
                'task_count': task_count,
                'todo_count': todo_count,
                'call_count': call_count
            }

            return {
                'status': 'success',
                'result': result

            }

        except Exception as e:
            # Catch any unexpected errors
            message = {str(e)}
            return {
                'status': 'false',
                'error': message
            }

# class CustomApiController(http.Controller):
# 
#     @http.route('/web/user_data', type='json', auth='user', csrf=False)
#     def handle_combined_api(self, date_start, user_id):
#         ist_tz = pytz.timezone('Asia/Kolkata')
# 
#         start_date_utc = datetime.strptime(date_start, '%Y-%m-%d').replace(hour=0, minute=0, second=0,
#                                                                            tzinfo=ist_tz).astimezone(pytz.UTC)
#         end_date_utc = datetime.strptime(date_start, '%Y-%m-%d').replace(hour=23, minute=59, second=59,
#                                                                          tzinfo=ist_tz).astimezone(pytz.UTC)
# 
#         start_date_query_utc = start_date_utc.strftime('%Y-%m-%d %H:%M:%S')
#         end_date_query_utc = end_date_utc.strftime('%Y-%m-%d %H:%M:%S')
# 
#         def rename_fields(records, field_map):
#             for record in records:
#                 for old_field, new_field in field_map.items():
#                     if old_field in record:
#                         record[new_field] = record.pop(old_field)
#             return records
# 
#         response = {}
# 
#         def fetch_model_data(model, domain, fields, field_map, category_name):
#             try:
#                 records = request.env[model].search_read(domain, fields)
#                 response[category_name] = rename_fields(records, field_map)
#             except Exception as e:
#                 response[category_name] = []  # Return empty if no access
#                 # Optionally log or capture the error if needed
# 
#         # Fetch each module separately
#         fetch_model_data(
#             'project.task',
#             [["user_ids", "in", [user_id]], ["create_date", ">=", start_date_query_utc],
#              ["create_date", "<=", end_date_query_utc], ["is_fsm", "=", False]],
#             ["name", "create_date", "create_uid", "user_ids", "tag_ids", "state", "description"],
#             {'state': 'status'},
#             'tasks'
#         )
# 
#         fetch_model_data(
#             'crm.lead',
#             [["user_id", "=", user_id], ["create_date", ">=", start_date_query_utc],
#              ["create_date", "<=", end_date_query_utc], ["type", "=", "lead"]],
#             ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#             {'stage_id': 'status'},
#             'leads'
#         )
# 
#         fetch_model_data(
#             'project.task',
#             [["user_ids", "in", [user_id]], ["create_date", ">=", start_date_query_utc],
#              ["create_date", "<=", end_date_query_utc], ["is_fsm", "=", True]],
#             ["name", "create_date", "create_uid", "user_ids", "tag_ids", "stage_id", "description"],
#             {'stage_id': 'status'},
#             'service_calls'
#         )
# 
#         fetch_model_data(
#             'project.task',
#             [["user_ids", "in", [user_id]], ["create_date", ">=", start_date_query_utc],
#              ["create_date", "<=", end_date_query_utc], ["project_id", "=", False], ["parent_id", "=", False]],
#             ["name", "create_date", "create_uid", "user_ids", "tag_ids", "state", "description"],
#             {'state': 'status'},
#             'todo_tasks'
#         )
# 
#         fetch_model_data(
#             'crm.lead',
#             [["user_id", "=", user_id], ["create_date", ">=", start_date_query_utc],
#              ["create_date", "<=", end_date_query_utc], ["type", "=", "opportunity"], ["active", "=", True]],
#             ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#             {'stage_id': 'status'},
#             'opportunities'
#         )
# 
#         fetch_model_data(
#             'project.project',
#             [["user_id", "=", user_id], ["create_date", ">=", start_date_query_utc],
#              ["create_date", "<=", end_date_query_utc], ['is_internal_project', '=', False]],
#             ["name", "create_date", "create_uid", "user_id", "tag_ids", "stage_id", "description"],
#             {'stage_id': 'status'},
#             'projects'
#         )
# 
#         # Process user_ids and tag_ids for records
#         for category in ['tasks', 'leads', 'service_calls', 'todo_tasks', 'opportunities', 'projects']:
#             for record in response.get(category, []):
#                 if 'user_ids' in record and isinstance(record['user_ids'], list):
#                     users = request.env['res.users'].browse(record['user_ids'])
#                     record['user_ids'] = [{'id': user.id, 'name': user.name} for user in users]
# 
#                 if category in ['tasks', 'todo_tasks', 'projects', 'service_calls']:
#                     if 'tag_ids' in record and isinstance(record['tag_ids'], list):
#                         tags = request.env['project.tags'].browse(record['tag_ids'])
#                         record['tag_ids'] = [{'id': tag.id, 'name': tag.name} for tag in tags]
# 
#                 elif category in ['leads', 'opportunities']:
#                     if 'tag_ids' in record and isinstance(record['tag_ids'], list):
#                         tags = request.env['crm.tag'].browse(record['tag_ids'])
#                         record['tag_ids'] = [{'id': tag.id, 'name': tag.name} for tag in tags]
# 
#         return {
#             'status': 'success',
#             'result': response,
#         }


class ProjectCountAPI(http.Controller):

    @http.route('/web/project/count', type='json', auth='user')
    def project_count(self, user_id=None, tag_ids=None, company_id=None, last_update_status=None):
        try:
            domain = [("is_internal_project", "=", False), ("is_fsm", "=", False)]

            if user_id:
                if isinstance(user_id, list):
                    if None in user_id:  # Check for None (unassigned projects)
                        user_id = [uid for uid in user_id if uid is not None]  # Filter out None
                        if user_id:
                            domain = ['|', ('user_id', 'in', user_id), ('user_id', '=', False)]
                        else:
                            domain.append(('user_id', '=', False))
                    else:
                        domain.append(('user_id', 'in', user_id))
                elif isinstance(user_id, str):
                    try:
                        user_ids = [int(uid.strip()) if uid.strip() != 'null' else None for uid in user_id.split(',')]
                        if None in user_ids:  # Check for None (unassigned projects)
                            user_ids = [uid for uid in user_ids if uid is not None]
                            if user_ids:
                                domain = ['|', ('user_id', 'in', user_ids), ('user_id', '=', False)]
                            else:
                                domain.append(('user_id', '=', False))
                        else:
                            domain.append(('user_id', 'in', user_ids))
                    except ValueError:
                        return {'status': 'false',
                                'error': 'Invalid user_id format. Must be a list of integers or a comma-separated string.'}
                else:
                    return {'status': 'false', 'error': 'Invalid user_id format. Must be a list or string.'}

            if tag_ids:
                if isinstance(tag_ids, list):
                    non_null_tag_ids = [tid for tid in tag_ids if isinstance(tid, int)]
                    include_untagged = any(tid is False for tid in tag_ids)

                    # If both non-null tag IDs and include_untagged are true, use the OR condition
                    if non_null_tag_ids and include_untagged:
                        domain += ['|', ('tag_ids', 'in', non_null_tag_ids), ('tag_ids', '=', False)]
                    elif non_null_tag_ids:
                        domain.append(('tag_ids', 'in', non_null_tag_ids))
                    elif include_untagged:
                        domain.append(('tag_ids', '=', False))
                else:
                    return {
                        'status': 'false',
                        'error': 'Invalid tag_ids format. Must be a list of integers or False.'
                    }

            if company_id:
                if isinstance(company_id, list):
                    domain.append(('company_id', 'in', company_id))
                else:
                    return {'status': 'false', 'error': 'Invalid company_id format. Must be a list.'}

            if last_update_status:
                if isinstance(last_update_status, list):
                    domain.append(('last_update_status', 'in', last_update_status))
                else:
                    return {'status': 'false', 'error': 'Invalid last_update_status format. Must be a list.'}

            task_data = request.env['project.project'].sudo().read_group(
                domain=domain,
                fields=['stage_id'],
                groupby=['stage_id']
            )

            response_data = [
                {
                    'stage_id': group['stage_id'][0],
                    'stage_name': group['stage_id'][1],
                    'count': group['stage_id_count']
                } for group in task_data
            ]

            return {
                'status': 'success',
                'data': response_data
            }

        except Exception as query_error:
            message = str(query_error)
            return {
                'status': 'false',
                'error': message
            }



class ProjectTodoAPI(http.Controller):
    @http.route('/web/todo/count', type='json', auth='user')
    def todo_count(self, user_ids=None, tag_ids=None):
        try:
            # Get current user's personal stages
            current_user = request.env.user
            personal_stages = request.env['project.task.type'].sudo().search([
                ('user_id', '=', current_user.id)
            ])

            # Base domain that always applies
            domain = [
                ('project_id', '=', False),
                ('parent_id', '=', False),
                ('active', '=', True),
                ('state', 'in', (
                    '01_in_progress',
                    '02_changes_requested',
                    '03_approved',
                    '04_waiting_normal',
                    '1_done',
                    '1_canceled'
                ))
            ]

            # Helper function to safely convert and validate IDs
            def parse_id_list(ids, field_name):
                if not ids:
                    return []
                try:
                    return [int(id) for id in ids]
                except ValueError:
                    raise ValueError(
                        f'Invalid {field_name} format. Must be a list of integers.'
                    )

            # If no user_ids provided, use current user
            if not user_ids:
                domain.append(('user_ids', '=', current_user.id))
            else:
                # Add specified user conditions
                parsed_user_ids = parse_id_list(user_ids, 'user_ids')
                if len(parsed_user_ids) > 1:
                    domain.append('&')
                domain.extend(('user_ids', '=', uid) for uid in parsed_user_ids)

            # Add tag conditions if specified
            if tag_ids:
                parsed_tag_ids = parse_id_list(tag_ids, 'tag_ids')
                if len(parsed_tag_ids) > 1:
                    domain.append('&')
                domain.extend(('tag_ids', '=', tid) for tid in parsed_tag_ids)

            # Fetch task counts for each personal stage
            result = []
            for stage in personal_stages:
                stage_domain = domain + [('personal_stage_type_id', '=', stage.id)]
                count = request.env['project.task'].sudo().search_count(stage_domain)

                result.append({
                    'stage_id': stage.id,
                    'stage_name': stage.name,
                    'count': count
                })

            return {
                'status': 'success',
                'result': result
            }

        except ValueError as ve:
            return {
                'status': 'false',
                'error': str(ve)
            }
        except Exception as e:
            return {
                'status': 'false',
                'error': str(e)
            }

class ProjectTaskCountAPI(http.Controller):

    @http.route('/web/task/count', type='json', auth='user')
    def task_count(self, user_ids=None, tag_ids=None, company_id=None, milestone_id=None, project_id=None):
        def process_field(field, field_name):
            """Process list fields (user_ids, tag_ids) for domains."""
            if isinstance(field, list):
                non_null_ids = [fid for fid in field if isinstance(fid, int)]
                include_false = any(fid is False for fid in field)

                if non_null_ids and include_false:
                    return ['|', (field_name, 'in', non_null_ids), (field_name, '=', False)]
                elif non_null_ids:
                    return [(field_name, 'in', non_null_ids)]
                elif include_false:
                    return [(field_name, '=', False)]
            return None

        try:
            domain = [("display_in_project", "=", True)]
            if not project_id:
                return {
                    'status': 'false',
                    'error': 'project_id is required.'
                }

            try:
                project_id = int(project_id)
                domain.append(("project_id", "=", project_id))
            except (ValueError, TypeError):
                return {
                    'status': 'false',
                    'error': 'Invalid project_id format. Must be a valid integer.'
                }

            if user_ids:
                if isinstance(user_ids, list):
                    # Separate valid IDs and False/None
                    non_null_user_ids = [uid for uid in user_ids if isinstance(uid, int)]
                    include_unassigned = any(uid is False for uid in user_ids)

                    if non_null_user_ids and include_unassigned:
                        # Combine assigned users and unassigned tasks
                        domain += ['|', ('user_ids', 'in', non_null_user_ids), ('user_ids', '=', False)]
                    elif non_null_user_ids:
                        # Only assigned users
                        domain.append(('user_ids', 'in', non_null_user_ids))
                    elif include_unassigned:
                        # Only unassigned tasks
                        domain.append(('user_ids', '=', False))
                else:
                    return {
                        'status': 'false',
                        'error': 'Invalid user_ids format. Must be a list of integers or False.'
                    }

            if tag_ids:
                if isinstance(tag_ids, list):
                    non_null_tag_ids = [tid for tid in tag_ids if isinstance(tid, int)]
                    include_untagged = any(tid is False for tid in tag_ids)

                    if non_null_tag_ids and include_untagged:
                        domain += ['|', ('tag_ids', 'in', non_null_tag_ids), ('tag_ids', '=', False)]
                    elif non_null_tag_ids:
                        domain.append(('tag_ids', 'in', non_null_tag_ids))
                    elif include_untagged:
                        domain.append(('tag_ids', '=', False))
                else:
                    return {
                        'status': 'false',
                        'error': 'Invalid tag_ids format. Must be a list of integers or False.'
                    }

            if company_id is not None:
                try:
                    domain += process_field(company_id, 'company_id')
                except ValueError as e:
                    return {'status': 'false', 'error': str(e)}

            if milestone_id is not None:
                try:
                    domain += process_field(milestone_id, 'milestone_id')
                except ValueError as e:
                    return {'status': 'false', 'error': str(e)}

            stage_domain = [('project_ids', '=', project_id)] if project_id else []
            all_stages = request.env['project.task.type'].sudo().search(stage_domain)

            task_data = request.env['project.task'].sudo().read_group(
                domain=domain,
                fields=['stage_id'],
                groupby=['stage_id']
            )

            task_counts = {group['stage_id'][0]: group['stage_id_count'] for group in task_data}

            response = {
                'status': 'success',
                'data': [
                    {
                        'stage_id': stage.id,
                        'stage_name': stage.name,
                        'count': task_counts.get(stage.id, 0)
                    } for stage in all_stages
                ]
            }

            return response
        except Exception as query_error:
            return {
                'status': 'false',
                'error': str(query_error)
            }