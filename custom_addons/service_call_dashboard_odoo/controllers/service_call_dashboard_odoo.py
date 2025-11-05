from datetime import datetime, timedelta
from odoo import http
from odoo.http import request
from odoo import api, fields
import pytz
import logging

_logger = logging.getLogger(__name__)


class ProjectFilter(http.Controller):
    @http.route('/calls/filter', auth='public', type='json')
    def project_filter(self):
        project_list = []
        employee_list = []
        project_ids = request.env['project.task'].search([])
        employee_ids = request.env['hr.employee'].search([])
        # getting partner data
        for employee_id in employee_ids:
            dic = {'name': employee_id.name,
                   'id': employee_id.id}
            employee_list.append(dic)

        for project_id in project_ids:
            dic = {'name': project_id.name,
                   'id': project_id.id}
            project_list.append(dic)

        return [project_list, employee_list]

    @http.route('/calls/filter-apply', auth='public', type='json')
    def project_filter_apply(self, **kw):
        data = kw['data']
        # checking the employee selected or not
        if data['employee'] == 'null':
            emp_selected = [employee.id for employee in
                            request.env['hr.employee'].search([])]
        else:
            emp_selected = [int(data['employee'])]
        start_date = data['start_date']
        end_date = data['end_date']
        # checking the dates are selected or not
        if start_date != 'null' and end_date != 'null':
            start_date = datetime.datetime.strptime(start_date,
                                                    "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            if data['project'] == 'null':
                pro_selected = [project.id for project in
                                request.env['project.project'].search(
                                    [('date_start', '>', start_date),
                                     ('date_start', '<', end_date)])]
            else:
                pro_selected = [int(data['project'])]
        elif start_date == 'null' and end_date != 'null':
            end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            if data['project'] == 'null':
                pro_selected = [project.id for project in
                                request.env['project.project'].search(
                                    [('date_start', '<', end_date)])]
            else:
                pro_selected = [int(data['project'])]
        elif start_date != 'null' and end_date == 'null':
            start_date = datetime.datetime.strptime(start_date,
                                                    "%Y-%m-%d").date()
            if data['project'] == 'null':
                pro_selected = [project.id for project in
                                request.env['project.project'].search(
                                    [('date_start', '>', start_date)])]
            else:
                pro_selected = [int(data['project'])]
        else:
            if data['project'] == 'null':
                pro_selected = [project.id for project in
                                request.env['project.project'].search([])]
            else:
                pro_selected = [int(data['project'])]
        report_project = request.env['timesheets.analysis.report'].search(
            [('project_id', 'in', pro_selected),
             ('employee_id', 'in', emp_selected)])
        analytic_project = request.env['account.analytic.line'].search(
            [('project_id', 'in', pro_selected),
             ('employee_id', 'in', emp_selected)])
        margin = round(sum(report_project.mapped('margin')), 2)
        sale_orders = []
        for rec in analytic_project:
            if rec.order_id.id and rec.order_id.id not in sale_orders:
                sale_orders.append(rec.order_id.id)
        total_time = sum(analytic_project.mapped('unit_amount'))
        return {
            'total_project': pro_selected,
            'total_emp': emp_selected,
            'total_task': [rec.id for rec in request.env['project.task'].search(
                [('project_id', 'in', pro_selected)])],
            'hours_recorded': total_time,
            'list_hours_recorded': [rec.id for rec in analytic_project],
            'total_margin': margin,
            'total_so': sale_orders
        }

    @http.route('/get/call/tiles/data', auth='public', type='json')
    def get_tiles_data(self):
        try:
            # Debug: Check total FSM tasks
            all_fsm_tasks = request.env['project.task'].search_count([('is_fsm', '=', True)])
            _logger.info(f"Total FSM tasks: {all_fsm_tasks}")

            # Debug: Check active FSM tasks with projects
            active_fsm_tasks = request.env['project.task'].search_count([
                ('is_fsm', '=', True),
                ('active', '=', True),
                ('project_id', '!=', False)
            ])
            _logger.info(f"Active FSM tasks with projects: {active_fsm_tasks}")

            user_employee = request.env.user.partner_id
            domain = [('is_fsm', '=', True)]

            if not user_employee.user_has_groups('project.group_project_manager'):
                domain.append(('user_id', '=', request.env.uid))

            all_projects = request.env['project.project'].search(domain)

            all_tasks = request.env['project.task'].search([
                ('project_id', 'in', all_projects.ids)])

            un_assigned_task = request.env['project.task'].search([
                ('project_id', 'in', all_projects.ids),
                ('user_ids', '=', False)])


            total_closed_task = request.env['project.task'].search([
                ('project_id', 'in', all_projects.ids),
                ('stage_id.name', '=', 'Done')])

            # Calculate counts for FSM projects and tasks
            active_projects = all_projects.filtered(lambda p: p.stage_id.name not in ['Done', 'Canceled'])

            running_projects = all_projects.filtered(lambda p: p.stage_id.name == 'In Progress')
            done_projects = all_projects.filtered(lambda p: p.stage_id.name == 'Done')
            running_tasks = all_tasks.filtered(lambda t: t.state == '01_in_progress')
            # done_tasks = all_tasks.filtered(lambda t: t.state == '1_done')

            done_tasks = all_tasks.filtered(lambda t: t.stage_id.name == 'Done')
            # old code commented


            today = datetime.today() + timedelta(hours=5, minutes=30)
            yesterday = today - timedelta(days=1)
            tomorrow = today + timedelta(days=1)

            # Set time to end of day (23:59:59) for each date
            today_end = today.replace(hour=23, minute=59, second=59)
            yesterday_end = yesterday.replace(hour=23, minute=59, second=59)
            tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59)

            # Set time to start of day (00:00:00) for each date
            today_start = today.replace(hour=0, minute=0, second=0)
            yesterday_start = yesterday.replace(hour=0, minute=0, second=0)
            tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0)

            # Filter tasks based on deadline ranges
            expired_yesterday = all_tasks.filtered(
                lambda t: t.date_deadline and
                          yesterday_start <= t.date_deadline <= yesterday_end
            )

            expired_today = all_tasks.filtered(
                lambda t: t.date_deadline and
                          today_start <= t.date_deadline <= today_end
            )

            will_expire_tomorrow = all_tasks.filtered(
                lambda t: t.date_deadline and
                          tomorrow_start <= t.date_deadline <= tomorrow_end
            )

            # Get a valid task ID - modified query
            sample_task = request.env['project.task'].search([
                ('is_fsm', '=', True),
                ('active', '=', True),
                ('project_id', '!=', False)  # Ensure task has a project
            ], limit=1)

            # Debug logging
            _logger.info(f"Found task: {sample_task.name if sample_task else 'None'}")
            sample_task_id = sample_task.id if sample_task else None

            result = {
                'total_projects': len(all_projects),
                'active_projects': len(active_projects),
                'running_projects': len(running_projects),
                'done_projects': len(done_projects),
                'running_tasks': len(running_tasks),
                'done_tasks': len(done_tasks),
                'total_tasks': len(all_tasks),
                'un_assigned_task': len(un_assigned_task),
                'total_closed_task': len(total_closed_task),
                'expired_yesterday': len(expired_yesterday),
                'will_expire_tomorrow': len(will_expire_tomorrow),
                'expired_today': len(expired_today),
                'flag': 1,
            }

            return result

        except Exception as e:
            _logger.error(f"Error in get_tiles_data: {e}")
            return {
                'error': str(e),
                'flag': 0
            }

    @http.route('/get/call/data', auth='public', type='json')
    def get_task_data(self):
        user_employee = request.env.user.partner_id
        if user_employee.user_has_groups('project.group_project_manager'):
            request._cr.execute('''select project_task.name as task_name,
            pro.name as project_name from project_task
            Inner join project_project as pro on project_task.project_id
            = pro.id ORDER BY project_name ASC''')
            data = request._cr.fetchall()
            project_name = []
            for rec in data:
                project_name.append(list(rec))
            return {
                'project': project_name
            }
        else:
            all_project = request.env['project.project'].search(
                [('user_id', '=', request.env.uid)]).ids

            # print(" get_task_data all_project",all_project)
            all_tasks = request.env['project.task'].search(
                [('project_id', 'in', all_project)])
            task_project = [[task.name, task.project_id.name] for task in
                            all_tasks]
            return {
                'project': task_project
            }

    @http.route('/call/task/by_tags', auth='public', type='json')
    # def get_task_by_tags(self, company_id=None, department_id=None, subdepartment_id=None):
    def get_task_by_tags(self, company_id=None, department_id=None, subdepartment_id=None, state_id=None, city=None):
        user_employee = request.env.user.partner_id
        domain = [('is_fsm', '=', True)]
        # Add company filter
        if company_id:
            domain.append(('company_id', '=', int(company_id)))

        # Add department/subdepartment filter
        if subdepartment_id:
            domain.append(('department_id', '=', int(subdepartment_id)))
        elif department_id:
            department = request.env['hr.department'].browse(int(department_id))
            if department.exists():
                if department.name == 'Service Division':
                    subdepartments = request.env['hr.department'].search([
                        ('parent_id', '=', department.id)
                    ])
                    if subdepartments:
                        domain.append(('department_id', 'in', subdepartments.ids))
                else:
                    domain.append(('department_id', '=', department.id))

        if state_id:
            # print(f"Processing state_id: {state_id}")
            try:
                state_id_int = int(state_id)
                partner_ids = request.env['res.partner'].search([('state_id', '=', state_id_int)]).ids
                # print(f"Found {len(partner_ids)} partners matching state_id {state_id_int}")
                if partner_ids:
                    domain.append(('partner_id', 'in', partner_ids))
                    # print("Meeeeeeeeeee",base_task_domain)
            except Exception as e:
                print(f"Error processing state_id: {e}")

        if city:
            try:

                city_names = [cities.strip() for cities in city]
                print(city)
                print("city name", city_names)
                partner_ids = request.env['res.partner'].search([('city', 'in', city_names)]).ids
                print("partner name",partner_ids)
                # If no partners match the city filter, return zeros immediately
                if not partner_ids:
                    return {
                        'new_stage_tasks_today': 0,
                        'calls_assigned_today': 0,
                        'calls_unassigned_today': 0,
                        'calls_closed_today': 0,
                        'calls_on_hold_today': 0,
                        'applied_domain': domain,
                        'info': f"No partners found in city: {city}"
                    }

                # If we have partners with this city, continue with filtering
                for i, condition in enumerate(domain):
                    if condition[0] == 'partner_id' and condition[1] == 'in':
                        # Find intersection of both partner sets
                        existing_ids = condition[2]
                        intersection = list(set(existing_ids) & set(partner_ids))

                        # If the intersection is empty, return zeros immediately
                        if not intersection:
                            return {
                                'new_stage_tasks_today': 0,
                                'calls_assigned_today': 0,
                                'calls_unassigned_today': 0,
                                'calls_closed_today': 0,
                                'calls_on_hold_today': 0,
                                'applied_domain': domain,
                                'info': f"No partners found matching both state and city: {city}"
                            }

                        domain[i] = ('partner_id', 'in', intersection)
                        break
                else:
                    # If there was no existing partner filter, add one
                    domain.append(('partner_id', 'in', partner_ids))
            except Exception as e:
                print(f"Error processing city: {e}")

            # print("After partner filtering")


        # Get all tasks with tags
        tasks = request.env['project.task'].search(domain)
        tag_count = {}
        # Count tasks for each tag
        for task in tasks:
            for tag in task.tag_ids:
                tag_count[tag.name] = tag_count.get(tag.name, 0) + 1

        # Prepare data for chart
        return {
            'labels': list(tag_count.keys()),
            'data': list(tag_count.values()),
            'colors': [
                          '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
                          '#FF9F40', '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0'
                      ][:len(tag_count)]
        }

    # this code only  Emplopyee Task Distribution
    @http.route('/call/task/by_employee', auth='public', type='json')
    def get_task_by_employee(self, company_id=None, department_id=None, subdepartment_id=None, state_id=None,
                             city=None):
        user_employee = request.env.user.partner_id
        domain = [('is_fsm', '=', True)]

        # Add company filter
        if company_id:
            domain.append(('company_id', '=', int(company_id)))

        # Add department/subdepartment filter
        if subdepartment_id:
            domain.append(('department_id', '=', int(subdepartment_id)))
        elif department_id:
            department = request.env['hr.department'].browse(int(department_id))
            if department:
                if department.name == 'Service Division':
                    subdepartments = request.env['hr.department'].search([
                        ('parent_id', '=', department.id)
                    ])
                    if subdepartments:
                        domain.append(('department_id', 'in', subdepartments.ids))
                else:
                    domain.append(('department_id', '=', department.id))

        if state_id:
            # print(f"Processing state_id: {state_id}")
            try:
                state_id_int = int(state_id)
                partner_ids = request.env['res.partner'].search([('state_id', '=', state_id_int)]).ids
                # print(f"Found {len(partner_ids)} partners matching state_id {state_id_int}")
                if partner_ids:
                    domain.append(('partner_id', 'in', partner_ids))

            except Exception as e:
                print(f"Error processing state_id: {e}")

            # In the city filter section:
        if city:
            try:
                partner_ids = request.env['res.partner'].search([('city', 'ilike', city)]).ids

                # If no partners match the city filter, return zeros immediately
                if not partner_ids:
                    return {
                        'new_stage_tasks_today': 0,
                        'calls_assigned_today': 0,
                        'calls_unassigned_today': 0,
                        'calls_closed_today': 0,
                        'calls_on_hold_today': 0,
                        'applied_domain': domain,
                        'info': f"No partners found in city: {city}"
                    }

                # If we have partners with this city, continue with filtering
                for i, condition in enumerate(domain):
                    if condition[0] == 'partner_id' and condition[1] == 'in':
                        # Find intersection of both partner sets
                        existing_ids = condition[2]
                        intersection = list(set(existing_ids) & set(partner_ids))

                        # If the intersection is empty, return zeros immediately
                        if not intersection:
                            return {
                                'new_stage_tasks_today': 0,
                                'calls_assigned_today': 0,
                                'calls_unassigned_today': 0,
                                'calls_closed_today': 0,
                                'calls_on_hold_today': 0,
                                'applied_domain': domain,
                                'info': f"No partners found matching both state and city: {city}"
                            }

                        domain[i] = ('partner_id', 'in', intersection)
                        break
                else:
                    # If there was no existing partner filter, add one
                    domain.append(('partner_id', 'in', partner_ids))
            except Exception as e:
                print(f"Error processing city: {e}")

        # Get all tasks with assigned users
        tasks = request.env['project.task'].search(domain)
        employee_count = {}

        # Count tasks for each employee
        for task in tasks:
            for user in task.user_ids:
                employee_name = user.name
                employee_count[employee_name] = employee_count.get(employee_name, 0) + 1

        # Sort by task count in descending order and limit to top 10
        sorted_data = dict(sorted(employee_count.items(), key=lambda x: x[1], reverse=True)[:10])
        colors_base = [
            '#2ecc71', '#3498db', '#9b59b6', '#f1c40f', '#e67e22',
            '#e74c3c', '#1abc9c', '#34495e', '#95a5a6', '#16a085'
        ]

        data_labels = list(sorted_data.keys())
        data_values = list(sorted_data.values())
        colors = colors_base[:len(data_labels)]

        return {
            'labels': data_labels,
            'data': data_values,
            'colors': colors
        }

    @http.route('/call/stage/wise_chart', auth='public', type='json')
    def get_task_by_stages(self, company_id=None, department_id=None, subdepartment_id=None, state_id=None, city=None):
        user_employee = request.env.user.partner_id
        domain = [('is_fsm', '=', True)]

        # Add company filter
        if company_id:
            domain.append(('company_id', '=', int(company_id)))

        # Add department/subdepartment filter
        if subdepartment_id:
            domain.append(('department_id', '=', int(subdepartment_id)))
        elif department_id:
            department = request.env['hr.department'].browse(int(department_id))
            if department.exists():
                if department.name == 'Service Division':
                    subdepartments = request.env['hr.department'].search([
                        ('parent_id', '=', department.id)
                    ])
                    if subdepartments:
                        domain.append(('department_id', 'in', subdepartments.ids))
                else:
                    domain.append(('department_id', '=', department.id))

        if state_id:
            # print(f"Processing state_id: {state_id}")
            try:
                state_id_int = int(state_id)
                partner_ids = request.env['res.partner'].search([('state_id', '=', state_id_int)]).ids
                # print(f"Found {len(partner_ids)} partners matching state_id {state_id_int}")
                if partner_ids:
                    domain.append(('partner_id', 'in', partner_ids))
                    # print("Meeeeeeeeeee",base_task_domain)
            except Exception as e:
                print(f"Error processing state_id: {e}")

            # In the city filter section:
        if city:
            try:
                partner_ids = request.env['res.partner'].search([('city', 'ilike', city)]).ids

                # If no partners match the city filter, return zeros immediately
                if not partner_ids:
                    return {
                        'new_stage_tasks_today': 0,
                        'calls_assigned_today': 0,
                        'calls_unassigned_today': 0,
                        'calls_closed_today': 0,
                        'calls_on_hold_today': 0,
                        'applied_domain': domain,
                        'info': f"No partners found in city: {city}"
                    }

                # If we have partners with this city, continue with filtering
                for i, condition in enumerate(domain):
                    if condition[0] == 'partner_id' and condition[1] == 'in':
                        # Find intersection of both partner sets
                        existing_ids = condition[2]
                        intersection = list(set(existing_ids) & set(partner_ids))

                        # If the intersection is empty, return zeros immediately
                        if not intersection:
                            return {
                                'new_stage_tasks_today': 0,
                                'calls_assigned_today': 0,
                                'calls_unassigned_today': 0,
                                'calls_closed_today': 0,
                                'calls_on_hold_today': 0,
                                'applied_domain': domain,
                                'info': f"No partners found matching both state and city: {city}"
                            }

                        domain[i] = ('partner_id', 'in', intersection)
                        break
                else:
                    # If there was no existing partner filter, add one
                    domain.append(('partner_id', 'in', partner_ids))
            except Exception as e:
                print(f"Error processing city: {e}")

            # print("After partner filtering")
        # print("city, state customer wise data employee", domain)

        # Get all tasks
        tasks = request.env['project.task'].search(domain)

        # Count tasks for each stage
        stage_count = {}
        for task in tasks:
            stage_name = task.stage_id.name if task.stage_id else 'Undefined'
            stage_count[stage_name] = stage_count.get(stage_name, 0) + 1

        # Prepare data for chart
        return {
            'labels': list(stage_count.keys()),
            'data': list(stage_count.values()),
            'colors': [
                          '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
                          '#FF9F40', '#FF5733', '#33FF57', '#3357FF', '#FF33F1'
                      ][:len(stage_count)]
        }

    @http.route('/call/customer/wise_chart', auth='public', type='json')
    def get_task_by_customers(self, company_id=None, department_id=None, subdepartment_id=None, state_id=None,
                              city=None):
        user_employee = request.env.user.partner_id
        domain = [('is_fsm', '=', True)]

        # Add company filter
        if company_id:
            domain.append(('company_id', '=', int(company_id)))

        # Add department/subdepartment filter
        if subdepartment_id:
            domain.append(('department_id', '=', int(subdepartment_id)))
        elif department_id:
            department = request.env['hr.department'].browse(int(department_id))
            if department.exists():
                if department.name == 'Service Division':
                    subdepartments = request.env['hr.department'].search([
                        ('parent_id', '=', department.id)
                    ])
                    if subdepartments:
                        domain.append(('department_id', 'in', subdepartments.ids))
                else:
                    domain.append(('department_id', '=', department.id))

        if state_id:
            # print(f"Processing state_id: {state_id}")
            try:
                state_id_int = int(state_id)
                partner_ids = request.env['res.partner'].search([('state_id', '=', state_id_int)]).ids
                # print(f"Found {len(partner_ids)} partners matching state_id {state_id_int}")
                if partner_ids:
                    domain.append(('partner_id', 'in', partner_ids))
                    # print("Meeeeeeeeeee",base_task_domain)
            except Exception as e:
                print(f"Error processing state_id: {e}")

            # In the city filter section:
        if city:
            try:
                partner_ids = request.env['res.partner'].search([('city', 'ilike', city)]).ids

                # If no partners match the city filter, return zeros immediately
                if not partner_ids:
                    return {
                        'new_stage_tasks_today': 0,
                        'calls_assigned_today': 0,
                        'calls_unassigned_today': 0,
                        'calls_closed_today': 0,
                        'calls_on_hold_today': 0,
                        'applied_domain': domain,
                        'info': f"No partners found in city: {city}"
                    }

                # If we have partners with this city, continue with filtering
                for i, condition in enumerate(domain):
                    if condition[0] == 'partner_id' and condition[1] == 'in':
                        # Find intersection of both partner sets
                        existing_ids = condition[2]
                        intersection = list(set(existing_ids) & set(partner_ids))

                        # If the intersection is empty, return zeros immediately
                        if not intersection:
                            return {
                                'new_stage_tasks_today': 0,
                                'calls_assigned_today': 0,
                                'calls_unassigned_today': 0,
                                'calls_closed_today': 0,
                                'calls_on_hold_today': 0,
                                'applied_domain': domain,
                                'info': f"No partners found matching both state and city: {city}"
                            }

                        domain[i] = ('partner_id', 'in', intersection)
                        break
                else:
                    # If there was no existing partner filter, add one
                    domain.append(('partner_id', 'in', partner_ids))
            except Exception as e:
                print(f"Error processing city: {e}")

        # Check if user is not a manager, filter projects by user
        if not user_employee.user_has_groups('industry_fsm.group_fsm_manager'):
            projects = request.env['project.project'].search([('user_id', '=', request.env.uid)])
            domain.append(('project_id', 'in', projects.ids))

        # Get all tasks
        tasks = request.env['project.task'].search(domain)

        customer_count = {}
        for task in tasks:
            if task.partner_id:  # Skip tasks with undefined customer
                customer_name = task.partner_id.name
                # customer_name = task.partner_id.name if task.partner_id else 'Undefined'

                # customer_name = task.partner_id.name if task.partner_id else 'Undefined'
                customer_count[customer_name] = customer_count.get(customer_name, 0) + 1

        # Prepare data for chart
        return {
            'labels': list(customer_count.keys()),
            'data': list(customer_count.values()),
            'colors': [
                          '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
                          '#FF9F40', '#FF5733', '#33FF57', '#3357FF', '#FF33F1'
                      ][:len(customer_count)]
        }

    @http.route('/call/task/customer_internal_external_chart', auth='user', type='json')
    def get_task_by_internal_external_wise(self, company_id=None, department_id=None, subdepartment_id=None,
                                           state_id=None, city=None):
        user_employee = request.env.user.partner_id
        domain = [('is_fsm', '=', True)]  # Filter FSM tasks only
        # Add company filter
        if company_id:
            domain.append(('company_id', '=', int(company_id)))

        # Add department/subdepartment filter
        if subdepartment_id:
            domain.append(('department_id', '=', int(subdepartment_id)))
        elif department_id:
            department = request.env['hr.department'].browse(int(department_id))
            if department.exists():
                if department.name == 'Service Division':
                    subdepartments = request.env['hr.department'].search([
                        ('parent_id', '=', department.id)
                    ])
                    if subdepartments:
                        domain.append(('department_id', 'in', subdepartments.ids))
                else:
                    domain.append(('department_id', '=', department.id))

        if state_id:
            # print(f"Processing state_id: {state_id}")
            try:
                state_id_int = int(state_id)
                partner_ids = request.env['res.partner'].search([('state_id', '=', state_id_int)]).ids
                # print(f"Found {len(partner_ids)} partners matching state_id {state_id_int}")
                if partner_ids:
                    domain.append(('partner_id', 'in', partner_ids))

            except Exception as e:
                print(f"Error processing state_id: {e}")

            # In the city filter section:
        if city:
            try:
                partner_ids = request.env['res.partner'].search([('city', 'ilike', city)]).ids

                # If no partners match the city filter, return zeros immediately
                if not partner_ids:
                    return {
                        'new_stage_tasks_today': 0,
                        'calls_assigned_today': 0,
                        'calls_unassigned_today': 0,
                        'calls_closed_today': 0,
                        'calls_on_hold_today': 0,
                        'applied_domain': domain,
                        'info': f"No partners found in city: {city}"
                    }

                # If we have partners with this city, continue with filtering
                for i, condition in enumerate(domain):
                    if condition[0] == 'partner_id' and condition[1] == 'in':
                        # Find intersection of both partner sets
                        existing_ids = condition[2]
                        intersection = list(set(existing_ids) & set(partner_ids))

                        # If the intersection is empty, return zeros immediately
                        if not intersection:
                            return {
                                'new_stage_tasks_today': 0,
                                'calls_assigned_today': 0,
                                'calls_unassigned_today': 0,
                                'calls_closed_today': 0,
                                'calls_on_hold_today': 0,
                                'applied_domain': domain,
                                'info': f"No partners found matching both state and city: {city}"
                            }

                        domain[i] = ('partner_id', 'in', intersection)
                        break
                else:
                    # If there was no existing partner filter, add one
                    domain.append(('partner_id', 'in', partner_ids))
            except Exception as e:
                print(f"Error processing city: {e}")

            # print("After partner filtering")
        print("city, state customer wise data employee", domain)

        # Apply project filter for non-managers
        if not request.env.user.has_group('industry_fsm.group_fsm_manager'):
            projects = request.env['project.project'].search([('user_id', '=', request.env.uid)])
            domain.append(('project_id', 'in', projects.ids))

        # Get tasks
        tasks = request.env['project.task'].search(domain)

        # Initialize counts
        internal_task_count = 0
        external_task_count = 0

        # Iterate through tasks and count internal & external types
        for task in tasks:
            task_type = task.call_allocation  # Ensure this field exists in your model
            if task_type == 'internal':
                internal_task_count += 1
            elif task_type == 'external':
                external_task_count += 1

        # Return correct data structure
        return {
            'labels': ['Internal Tasks', 'External Tasks'],
            'data': [internal_task_count, external_task_count],
            'colors': ['#FF6384', '#36A2EB']  # Colors for visualization
        }

    @http.route('/call/today', auth='public', type='json')
    def get_calls_today(self, company_id=None, department_id=None, subdepartment_id=None, state_id=None, city=None):
        try:
            base_task_domain = [('is_fsm', '=', True)]
            user = request.env.user
            is_admin = user.has_group('industry_fsm.group_fsm_manager')
            employee = user.employee_id

            base_dept_ids = []
            if employee.department_id:
                base_dept_ids.append(employee.department_id.id)

            # Departments from call.visibility
            visibility_dept_ids = request.env['call.visibility'].search([
                ('employee_id', '=', user.employee_id.id)
            ]).mapped('department_id.id')


            # Combine and remove duplicates - User's accessible departments
            user_accessible_dept_ids = list(set(base_dept_ids + visibility_dept_ids))

            # Only filter by supervisor's department if no department/subdepartment filter is provided
            if not is_admin and not (department_id or subdepartment_id):

                base_task_domain.append(('department_id', 'in', user_accessible_dept_ids))

            # Company filter
            if company_id:
                company_id = int(company_id)
                base_task_domain.append(('company_id', '=', company_id))

            # Get the "Service Division" department and its children
            service_division_dept = request.env['hr.department'].search([('name', '=', 'Service Division')], limit=1)
            if service_division_dept:
                # Check if user is admin
                if is_admin:
                    # Admin sees ALL Service Division departments
                    all_dept_ids = request.env['hr.department'].search(
                        [('id', 'child_of', service_division_dept.id)]).ids
                else:
                    # Non-admin sees only their accessible departments
                    all_dept_ids = user_accessible_dept_ids

                base_task_domain.append(('department_id', 'in', all_dept_ids))

            # Department filtering
            if subdepartment_id:
                base_task_domain.append(('department_id', '=', int(subdepartment_id)))
            elif department_id:
                department = request.env['hr.department'].browse(int(department_id))
                if department.exists():
                    all_dept_ids = request.env['hr.department'].search([('id', 'child_of', department.id)]).ids
                    base_task_domain.append(('department_id', 'in', all_dept_ids))

            # Filter by customer city and state - with more debug info
            # print("Before partner filtering")
            if state_id:
                # print(f"Processing state_id: {state_id}")
                try:
                    state_id_int = int(state_id)
                    partner_ids = request.env['res.partner'].search([('state_id', '=', state_id_int)]).ids
                    print("partner_ids", partner_ids)
                    # print(f"Found {len(partner_ids)} partners matching state_id {state_id_int}")
                    if partner_ids:
                        base_task_domain.append(('partner_id', 'in', partner_ids))
                        # print("Meeeeeeeeeee",base_task_domain)
                except Exception as e:
                    print(f"Error processing state_id: {e}")

            # In the city filter section:
            if city:
                try:
                    print(" Abhi Abhi City", city)
                    partner_ids = request.env['res.partner'].search([('city', 'in', city)]).ids
                    base_task_domain.append(('partner_id', 'in', partner_ids))
                    print("Abhi Partner", partner_ids)
                    # If no partners match the city filter, return zeros immediately
                    if not partner_ids:
                        return {
                            'total_stage_tasks_today':0,
                            'new_stage_tasks_today': 0,
                            'calls_assigned_today': 0,
                            'calls_unassigned_today': 0,
                            'calls_closed_today': 0,
                            'calls_on_hold_today': 0,
                            'applied_domain': base_task_domain,
                            'info': f"No partners found in city: {city}"
                        }

                    # If we have partners with this city, continue with filtering
                    for i, condition in enumerate(base_task_domain):
                        if condition[0] == 'partner_id' and condition[1] == 'in':
                            # Find intersection of both partner sets
                            existing_ids = condition[2]
                            intersection = list(set(existing_ids) & set(partner_ids))

                            # If the intersection is empty, return zeros immediately
                            if not intersection:
                                return {
                                    'total_stage_tasks_today': 0,
                                    'new_stage_tasks_today': 0,
                                    'calls_assigned_today': 0,
                                    'calls_unassigned_today': 0,
                                    'calls_closed_today': 0,
                                    'calls_on_hold_today': 0,
                                    'applied_domain': base_task_domain,
                                    'info': f"No partners found matching both state and city: {city}"
                                }

                            base_task_domain[i] = ('partner_id', 'in', intersection)
                            break
                    else:
                        # If there was no existing partner filter, add one
                        base_task_domain.append(('partner_id', 'in', partner_ids))
                except Exception as e:
                    print(f"Error processing city: {e}")

                # print("After partner filtering")
                # print("city, state customer wise data", base_task_domain)

            # Date filter for today
            user_tz = pytz.timezone(request.env.user.tz or 'UTC')
            today = datetime.now(user_tz).date()
            today_domain = base_task_domain + [
                ('create_date', '>=', datetime.combine(today, datetime.min.time())),
                ('create_date', '<=', datetime.combine(today, datetime.max.time()))
            ]

            print(today_domain)
            task_model = request.env['project.task']
            total_calls = task_model.search_count(today_domain)
            new_tasks = task_model.search_count(today_domain + [('stage_id.name', '=', 'In Progress')])
            assigned_tasks = task_model.search_count(today_domain + [('stage_id.name', '=', "Assigned")])
            unassigned_tasks = task_model.search_count(today_domain + [('user_ids', '=', False)])
            on_hold_tasks = task_model.search_count(today_domain + [('stage_id.name', '=', 'Pending')])
            closed_tasks = task_model.search_count(today_domain + [('stage_id.name', 'in', ['Done', 'Cancelled'])])
            planned_today_tasks = task_model.search_count(today_domain + [('stage_id.name', '=', "Planned")])
            return {
                'total_stage_tasks_today': total_calls,
                'new_stage_tasks_today': new_tasks,
                'calls_assigned_today': assigned_tasks,
                'calls_unassigned_today': unassigned_tasks,
                'calls_closed_today': closed_tasks,
                'calls_on_hold_today': on_hold_tasks,
                'applied_domain': base_task_domain,
                'planned_today_tasks': planned_today_tasks
            }

        except Exception as e:
            _logger.error(f"Error in get_calls_today: {e}")
            return {
                'total_stage_tasks_today': 0,
                'new_stage_tasks_today': 0,
                'calls_assigned_today': 0,
                'calls_unassigned_today': 0,
                'calls_closed_today': 0,
                'calls_on_hold_today': 0,
                'error': str(e)
            }

    @http.route('/previous/total', auth='public', type='json')
    def get_previous_total(self, **kw):
        try:
            # Base domain for tasks
            task_domain = [('is_fsm', '=', True)]
            department_id = kw.get('department_id')
            subdepartment_id = kw.get('subdepartment_id')
            user = request.env.user
            is_admin = user.has_group('industry_fsm.group_fsm_manager')
            employee = user.employee_id

            base_dept_ids = []
            if employee.department_id:
                base_dept_ids.append(employee.department_id.id)


            visibility_dept_ids = request.env['call.visibility'].search([
                ('employee_id', '=', user.employee_id.id)
            ]).mapped('department_id.id')


            # Combine and remove duplicates - User's accessible departments
            user_accessible_dept_ids = list(set(base_dept_ids + visibility_dept_ids))

            # Only filter by supervisor's department if no department/subdepartment filter is provided
            if not is_admin and not (department_id or subdepartment_id):

                task_domain.append(('department_id', 'in', user_accessible_dept_ids))

            # Add company filter
            if kw.get('company_id'):
                task_domain.append(('company_id', '=', int(kw['company_id'])))

                # Get the "Service Division" department and its children
                service_division_dept = request.env['hr.department'].search([('name', '=', 'Service Division')],
                                                                            limit=1)
                if service_division_dept:
                    if is_admin:
                        # Admin sees ALL Service Division departments
                        all_dept_ids = request.env['hr.department'].search(
                            [('id', 'child_of', service_division_dept.id)]).ids
                    else:
                        # Non-admin sees only their accessible departments
                        all_dept_ids = user_accessible_dept_ids
                    # Get all subdepartments including the parent
                    # all_dept_ids = request.env['hr.department'].search(
                    #     [('id', 'child_of', service_division_dept.id)]).ids
                    task_domain.append(('department_id', 'in', all_dept_ids))

            # Add department/subdepartment filter
            if kw.get('subdepartment_id'):
                # Only the selected subdepartment
                task_domain.append(('department_id', '=', int(kw['subdepartment_id'])))

            elif kw.get('department_id'):
                department = request.env['hr.department'].browse(int(kw['department_id']))
                if department.exists():
                    # Get department and all subdepartments
                    all_dept_ids = request.env['hr.department'].search([('id', 'child_of', department.id)]).ids
                    task_domain.append(('department_id', 'in', all_dept_ids))

            # Filter by customer city and state - with more debug info
            state_id = kw.get('state_id')
            city = kw.get('city')

            # print("Before partner filtering")
            if state_id:
                # print(f"Processing state_id: {state_id}")
                try:
                    state_id_int = int(state_id)
                    partner_ids = request.env['res.partner'].search([('state_id', '=', state_id_int)]).ids
                    # print(f"Found {len(partner_ids)} partners matching state_id {state_id_int}")
                    if partner_ids:
                        task_domain.append(('partner_id', 'in', partner_ids))
                        # print("Meeeeeeeeeee", task_domain)
                except Exception as e:
                    print(f"Error processing state_id: {e}")

            if city:
                try:
                    partner_ids = request.env['res.partner'].search([('city', 'in', city)]).ids
                    print("Mukesh Partner ids", partner_ids)
                    # If no partners match the city filter, return zeros immediately
                    if not partner_ids:
                        return {
                            'new_stage_tasks_today': 0,
                            'calls_assigned_today': 0,
                            'calls_unassigned_today': 0,
                            'calls_closed_today': 0,
                            'calls_on_hold_today': 0,
                            'applied_domain': task_domain,
                            'info': f"No partners found in city: {city}"
                        }

                    # If we have partners with this city, continue with filtering
                    for i, condition in enumerate(task_domain):
                        if condition[0] == 'partner_id' and condition[1] == 'in':
                            # Find intersection of both partner sets
                            existing_ids = condition[2]
                            intersection = list(set(existing_ids) & set(partner_ids))

                            # If the intersection is empty, return zeros immediately
                            if not intersection:
                                return {
                                    'new_stage_tasks_today': 0,
                                    'calls_assigned_today': 0,
                                    'calls_unassigned_today': 0,
                                    'calls_closed_today': 0,
                                    'calls_on_hold_today': 0,
                                    'applied_domain': task_domain,
                                    'info': f"No partners found matching both state and city: {city}"
                                }

                            task_domain[i] = ('partner_id', 'in', intersection)
                            break
                    else:
                        # If there was no existing partner filter, add one
                        task_domain.append(('partner_id', 'in', partner_ids))
                except Exception as e:
                    print(f"Error processing city: {e}")

            # Add date filters
            start_date = kw.get('start_date')
            end_date = kw.get('end_date')
            if start_date and end_date:
                try:
                    start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                    end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                    task_domain += [
                        ('create_date', '>=', start_datetime),
                        ('create_date', '<', end_datetime)
                    ]
                except ValueError as e:
                    _logger.error(f"Date parsing error: {e}")

            # Add user access rights filter
            if not request.env.user.has_group('project.group_project_manager'):
                task_domain.append(('user_id', '=', request.env.uid))

            # Search tasks with complete domain
            tasks = request.env['project.task'].search(task_domain)

            # Count tasks by different criteria
            assigned_tasks = tasks.filtered(lambda t: t.stage_id.name == 'Assigned')
            unassigned_tasks = tasks.filtered(lambda t: not t.user_ids)
            on_hold_tasks = tasks.filtered(lambda t: t.stage_id.name == 'Pending')
            # closed_tasks = tasks.filtered(lambda t: t.stage_id.name == 'Done')
            closed_tasks = tasks.filtered(lambda t: t.stage_id.name in ['Done', 'Cancelled'])
            in_progress_tasks = tasks.filtered(lambda t: t.stage_id.name == 'In Progress')
            planned_tasks = tasks.filtered(lambda t: t.stage_id.name == 'Planned')
            resolved_tasks = tasks.filtered(lambda t: t.stage_id.name == 'Resolved')
            return {
                'all_previous_tasks_total': len(tasks),
                'all_assigned_tasks_total': len(assigned_tasks),
                'all_unassigned_tasks_total': len(unassigned_tasks),
                'all_on_hold_tasks_total': len(on_hold_tasks),
                'all_closed_tasks_total': len(closed_tasks),
                'in_progress_count': len(in_progress_tasks),
                'in_planned_count': len(planned_tasks),
                'in_resolved_count': len(resolved_tasks),
                'date_range': {
                    'start': start_date,
                    'end': end_date
                },
                'applied_filters': {
                    'company_id': kw.get('company_id'),
                    'department_id': kw.get('department_id'),
                    'subdepartment_id': kw.get('subdepartment_id'),

                    'state_id': kw.get('state_id'),
                    'city': kw.get('city')
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_previous_total: {e}")
            return {
                'all_previous_tasks_total': 0,
                'all_assigned_tasks_total': 0,
                'all_unassigned_tasks_total': 0,
                'all_on_hold_tasks_total': 0,
                'all_closed_tasks_total': 0,
                'in_progress_count': 0,
                'in_planned_count': 0,
                'in_resolved_count': 0,
                'date_range': {'start': None, 'end': None},
                'applied_filters': {}
            }

    @http.route('/get/task/details', auth='public', type='json')
    def get_task_details(self, task_id):
        try:
            if not task_id:
                return {'error': 'No task ID provided'}

            task = request.env['project.task'].browse(int(task_id))
            # print("task ", task)
            if not task.exists():
                return {'error': 'Task not found'}

            return {
                'id': task.id,
                'name': task.name,
                'exists': True,
                'project': task.project_id.name if task.project_id else None
            }
        except Exception as e:
            _logger.error(f"Error fetching task details: {e}")
            return {'error': str(e)}

    @http.route('/get/fsm/project', auth='user', type='json')
    def get_fsm_project(self):
        try:
            current_user = request.env.user
            user_company = current_user.company_id

            # Switch to user and their company context
            env = request.env(user=current_user,
                              context=dict(request.env.context, allowed_company_ids=[user_company.id]))

            fsm_project = env['project.project'].search([
                ('is_fsm', '=', True),
                ('name', '=', 'Service Call')
            ], limit=1)

            return {
                'id': fsm_project.id,
                'name': fsm_project.name,
                'user_id': current_user.id,
                'user_name': current_user.name
            }

        except Exception as e:
            _logger.error(f"Error getting FSM project: {e}")
            return False


    # @http.route('/get/company/settings', type='json', auth="user")
    # def get_company_settings(self):
    #     company = request.env.company
    #     return {
    #         "service_dashboard_planned_card": bool(company.service_dashboard_planned_card),
    #         "service_dashboard_resolved_card": bool(company.service_dashboard_resolved_card),
    #     }

    @http.route('/get/company/settings', type='json', auth="user")
    def get_company_settings(self):
        config = request.env['ir.config_parameter'].sudo()
        planned_stage = config.get_param('industry_fsm.service_planned_stage', 'False') == 'True'
        resolved_stage = config.get_param('industry_fsm.service_resolved_stage', 'False') == 'False'
        print("Planned", planned_stage)
        print("Resolved", resolved_stage)
        return {
            "service_dashboard_planned_card": planned_stage,
            "service_dashboard_resolved_card": resolved_stage,
            "service_dashboard_today_planned_card": planned_stage,
            "service_dashboard_today_resolved_card": resolved_stage,
        }

    # company level settings

    @http.route('/get/service_companies', auth='public', type='json')
    def get_companies(self):
        # Search departments named "Service Division"
        service_departments = request.env['hr.department'].sudo().search([
            ('name', '=', 'Service Division')
        ])

        # Extract unique company IDs from these departments
        company_ids = service_departments.mapped('company_id.id')

        # Now fetch only those companies
        companies = request.env['res.company'].sudo().search([
            ('id', 'in', company_ids)
        ])

        return [{
            'id': company.id,
            'name': company.name
        } for company in companies]

    @http.route('/get/service_departments/by_company', auth='public', type='json')
    def get_departments_by_company(self, company_id):
        try:
            # print(company_id)
            departments = request.env['hr.department'].search([
                ('company_id', '=', int(company_id)),
                ('parent_id', '=', False),
            ])
            print("oooo",departments)
            # print("departments 1", departments)
            return [{
                'id': dept.id,
                'name': dept.name
            } for dept in departments]
        except Exception as e:
            _logger.error("Error fetching departments: %s", e)
            return []

    @http.route('/get/service_sub_departments', auth='user', type='json')
    def get_sub_departments(self, department_id):
        try:
            user = request.env.user
            Department = request.env['hr.department']
            department_id = int(department_id)

            # Superuser / Admin
            if user.has_group('industry_fsm.group_fsm_manager'):
                sub_departments = Department.search([
                    ('parent_id', '=', department_id)
                ])
                print("sub", sub_departments)

            # Supervisor group logic
            elif user.has_group('industry_fsm.group_fsm_supervisor'):
                employee = request.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)

                base_dept_ids = []
                if employee.department_id:
                    base_dept_ids.append(employee.department_id.id)


                # Departments from call.visibility
                visibility_dept_ids = request.env['call.visibility'].search([
                    ('employee_id', '=', user.employee_id.id)
                ]).mapped('department_id.id')


                # Combine and remove duplicates
                all_dept_ids = list(set(base_dept_ids + visibility_dept_ids))


                # Find sub-departments of all allowed departments
                sub_departments = Department.search([
                    ('id', 'in', all_dept_ids)
                ])


                # if employee and employee.department_id:
                #     sub_departments = Department.search([
                #         ('parent_id', '=', department_id),
                #         ('id', '=', employee.department_id.id)
                #     ])
                #     print("super", sub_departments)

            return [{
                'id': sub_dept.id,
                'name': sub_dept.name,
            } for sub_dept in sub_departments]

        except Exception as e:
            _logger.error("Error fetching sub-departments: %s", e)
            return []

    @http.route('/get/states/by_subdepartment', auth='public', type='json')
    def get_states_by_subdepartment(self, subdepartment_id):
        """Fetch all states for a given sub-department."""
        try:
            # print(f"Fetching states for subdepartment_id: {subdepartment_id}")

            subdepartment_id = int(subdepartment_id)  # Convert to integer
            # If sub_department is not directly in department.service,
            # you might need to use a different approach
            # Option 1: Use domain filtering with a related field
            records = request.env['department.service'].sudo().search([
                # Adjust this domain based on your actual model relationships
                ('department_id', '=', subdepartment_id)
            ])
            # Collect unique states
            states = records.mapped('state_id')

            # Returning properly formatted response
            return [{
                'id': state.id,
                'name': state.name,
                'subdepartment_id': subdepartment_id
            } for state in states]

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'error': str(e), 'details': traceback.format_exc()}

    @http.route('/get/cities/by_state', auth='public', type='json')
    def get_cities_by_state(self, subdepartment_id, state_id):
        """Fetch all cities for a given state."""
        try:
            _logger.info(f"Fetching cities for subdepartment_id: {subdepartment_id} and state_id: {state_id}")

            subdepartment_id = int(subdepartment_id)
            state_id = int(state_id)

            # Search for cities in department.service model
            records = request.env['department.service'].sudo().search([
                ('department_id', '=', subdepartment_id),
                ('state_id', '=', state_id)
            ])

            _logger.info(f"Found {len(records)} records")

            # Get unique cities using mapped function
            cities = records.mapped('city_id')
            print("Citiesss", cities)
            _logger.info(f"Found {len(cities)} unique cities")

            # Format the response
            result = []
            for city in cities:
                try:
                    result.append({
                        'id': city.id,
                        'name': city.name,
                        'state_id': state_id
                    })
                    _logger.info(f"Added city: {city.name}")
                except Exception as city_error:
                    _logger.warning(f"Error processing city record: {city_error}")
                    continue

            _logger.info(f"Returning {len(result)} formatted cities")
            return result

        except Exception as e:
            _logger.error(f"Error fetching cities: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
            return {'error': str(e), 'details': traceback.format_exc()}

    from odoo import http, fields
    from odoo.http import request
    import logging

    _logger = logging.getLogger(__name__)

    class EmployeeStatsController(http.Controller):

        @http.route('/call/employee/click', type='json', auth='user')
        def get_filtered_employee_ids(self, employee_type=None, company_id=None, department_id=None,
                                      subdepartment_id=None, state_id=None, city=None):
            try:
                user = request.env.user
                employee = user.employee_id
                today = fields.Date.today()
                domain = []
                base_dept_ids = []
                is_admin = user.has_group('industry_fsm.group_fsm_manager')

                if employee.department_id:
                    base_dept_ids.append(employee.department_id.id)

                # Departments from call.visibility
                visibility_dept_ids = request.env['call.visibility'].search([
                    ('employee_id', '=', user.employee_id.id)
                ]).mapped('department_id.id')

                # Combine and remove duplicates - User's accessible departments
                user_accessible_dept_ids = list(set(base_dept_ids + visibility_dept_ids))

                # Company filter
                if company_id:
                    domain.append(('company_id', '=', int(company_id)))
                # Get the "Service Division" department and its children
                service_division_dept = request.env['hr.department'].search([('name', '=', 'Service Division')],
                                                                            limit=1)
                if service_division_dept:

                    # Get all subdepartments including the parent
                    if is_admin:
                        # Admin sees ALL Service Division departments
                        all_dept_ids = request.env['hr.department'].search(
                            [('id', 'child_of', service_division_dept.id)]).ids
                    else:
                        # Non-admin sees only their accessible departments
                        all_dept_ids = user_accessible_dept_ids
                    domain.append(('department_id', 'in', all_dept_ids))

                # Department/Subdepartment filter
                if subdepartment_id:
                    print("Me goes here")
                    domain.append(('department_id', '=', int(subdepartment_id)))
                elif department_id:
                    print("Me goes in departmenrt")
                    department = request.env['hr.department'].browse(int(department_id))
                    child_ids = request.env['hr.department'].search([('id', 'child_of', department.id)]).ids
                    domain.append(('department_id', 'in', child_ids))

                # Supervisor logic if filters not passed
                if not is_admin and not (department_id or subdepartment_id):
                    print("Bhai i am hereeeeeeeeeee")
                    domain.append(('department_id', 'in', user_accessible_dept_ids))

                employees = request.env['hr.employee'].search(domain)
                print("My Employees",employees)
                print("This is a domain",domain)
                employee_ids = employees.ids
                user_ids = employees.mapped('user_id').ids

                result_ids = []

                if employee_type == 'total':
                    result_ids = employee_ids

                elif employee_type == 'on_leave':
                    result_ids = employees.filtered(lambda e: e.is_absent).ids

                elif employee_type == 'occupied':
                    # Find employees with running timers in account.analytic.line
                    running_timers = request.env['account.analytic.line'].sudo().search([
                        ('is_timer_running', '=', True),
                        ('employee_id', 'in', employee_ids),
                    ])
                    # Get employee IDs who have running timers
                    result_ids = running_timers.mapped('employee_id.id')

                    return {'employee_ids': result_ids}

                elif employee_type == 'stop_and_delete':
                    # Find and stop running timers, then delete entries
                    running_timers = request.env['account.analytic.line'].sudo().search([
                        ('is_timer_running', '=', True),
                        ('employee_id', 'in', employee_ids),
                    ])

                    if running_timers:
                        # Stop all running timers first
                        running_timers.write({'is_timer_running': False})

                        # Delete the timer entries
                        running_timers.unlink()

                        return {
                            'employee_ids': [],
                            'deleted_count': len(running_timers),
                            'message': f'Stopped and deleted {len(running_timers)} timer entries'
                        }

                    return {
                        'employee_ids': [],
                        'deleted_count': 0,
                        'message': 'No running timers found to delete'
                    }

                    # tasks = request.env['project.task'].search([
                    #     ('is_fsm', '=', True),
                    #     ('user_ids', 'in', user_ids)
                    # ])
                    # occupied_user_ids = tasks.mapped('user_ids.id')
                    # result_ids = request.env['hr.employee'].search([
                    #     ('user_id', 'in', occupied_user_ids)
                    # ]).ids

                elif employee_type == 'free':
                    tasks = request.env['project.task'].search([
                        ('is_fsm', '=', True),
                        ('user_ids', 'in', user_ids)
                    ])
                    occupied_user_ids = tasks.mapped('user_ids.id')
                    on_leave_ids = employees.filtered(lambda e: e.is_absent).ids
                    occupied_ids = request.env['hr.employee'].search([
                        ('user_id', 'in', occupied_user_ids)
                    ]).ids
                    result_ids = list(set(employee_ids) - set(occupied_ids) - set(on_leave_ids))

                elif employee_type == 'running_overdue':
                    tasks = request.env['project.task'].search([
                        ('is_fsm', '=', True),
                        ('user_ids', 'in', user_ids),
                        ('date_deadline', '<', today),
                        ('stage_id.name', 'not in', ['Done', 'Cancelled'])
                    ])
                    overdue_user_ids = tasks.mapped('user_ids.id')
                    result_ids = request.env['hr.employee'].search([
                        ('user_id', 'in', overdue_user_ids)
                    ]).ids

                return {'employee_ids': result_ids}

            except Exception as e:
                _logger.error(f"Error in /call/employee/click: {e}")
                return {'employee_ids': []}

    # @http.route('/call/employee/click', type='json', auth='user')
    # def click_employee_filter(self, employee_type=None, **kwargs):
    #     Employee = request.env['hr.employee'].sudo()
    #     Department = request.env['hr.department'].sudo()
    #
    #     domain = []
    #
    #     company_id = kwargs.get('company_id')
    #     department_id = kwargs.get('department_id')
    #     subdepartment_id = kwargs.get('subdepartment_id')
    #
    #     if company_id:
    #         domain.append(('company_id', '=', int(company_id)))
    #
    #     # Get Service Division department
    #     service_division = Department.search([('name', '=', 'Service Division')], limit=1)
    #
    #     # Department filtering
    #     if subdepartment_id:
    #         domain.append(('department_id', '=', int(subdepartment_id)))
    #     elif department_id:
    #         domain.append(('department_id', 'child_of', int(department_id)))
    #     elif service_division:
    #         domain.append(('department_id', 'child_of', service_division.id))
    #
    #     # On Leave filtering
    #     if employee_type == 'on_leave':
    #         domain.append(('is_absent', '=', True))
    #     print("My leave Domain",domain)
    #     employees = Employee.search(domain)
    #     return {'employee_ids': employees.ids}

    @http.route('/get/team/stats', auth='public', type='json')
    def get_team_stats(self, company_id=None, department_id=None, subdepartment_id=None, state_id=None, city=None):
        # def get_team_stats(self, company_id=None, department_id=None, subdepartment_id=None):
        try:
            employee_domain = []
            user = request.env.user
            is_admin = user.has_group('industry_fsm.group_fsm_manager')
            employee = user.employee_id

            base_dept_ids = []
            if employee.department_id:
                base_dept_ids.append(employee.department_id.id)

            # Departments from call.visibility
            visibility_dept_ids = request.env['call.visibility'].search([
                ('employee_id', '=', user.employee_id.id)
            ]).mapped('department_id.id')

            # Combine and remove duplicates - User's accessible departments
            user_accessible_dept_ids = list(set(base_dept_ids + visibility_dept_ids))

            # Supervisor restriction (only if no dept/subdept selected)
            if not is_admin and not (department_id or subdepartment_id):
                employee_domain.append(('department_id', 'in', user_accessible_dept_ids))

            # Ensure company_id is passed and valid
            if company_id:
                company_id = int(company_id)
                employee_domain.append(('company_id', '=', company_id))

            # Get the "Service Division" department and its children
            service_division_dept = request.env['hr.department'].search([('name', '=', 'Service Division')], limit=1)
            if service_division_dept:
                is_admin = user.has_group('industry_fsm.group_fsm_manager')
                # Get all subdepartments including the parent
                if is_admin:
                    # Admin sees ALL Service Division departments
                    all_dept_ids = request.env['hr.department'].search(
                        [('id', 'child_of', service_division_dept.id)]).ids
                else:
                    # Non-admin sees only their accessible departments
                    all_dept_ids = user_accessible_dept_ids

                employee_domain.append(('department_id', 'in', all_dept_ids))

            # Add department and subdepartment logic
            if subdepartment_id:
                # Just the selected subdepartment â€” not the parent
                employee_domain.append(('department_id', '=', int(subdepartment_id)))

            elif department_id:
                # Include the department and all its children
                department = request.env['hr.department'].browse(int(department_id))
                if department:
                    all_dept_ids = request.env['hr.department'].search([('id', 'child_of', department.id)]).ids
                    employee_domain.append(('department_id', 'in', all_dept_ids))

            employees = request.env['hr.employee'].search(employee_domain)

            if not employees:
                return {
                    'total_team': 0,
                    'free_team': 0,
                    'running_overdue': 0,
                    'occupied': 0,
                    'on_leave': 0
                }
            # Build task domain for filtered employees
            task_domain = [
                ('is_fsm', '=', True),
                ('user_ids', 'in', employees.mapped('user_id').ids)
            ]
            # Add company filter to tasks if provided
            if company_id:
                task_domain.append(('company_id', '=', int(company_id)))

            tasks = request.env['project.task'].search(task_domain)
            today = fields.Date.today()

            # Calculate statistics
            total_team = len(employees)

            # occupied_employee_ids = set()
            # for task in tasks:
            #     for emp in employees:
            #         if emp.user_id and emp.user_id in task.user_ids:
            #             occupied_employee_ids.add(emp.id)
            running_timers = request.env['account.analytic.line'].sudo().search([
                ('is_timer_running', '=', True),
                ('employee_id', 'in', [emp.id for emp in employees]),
            ])
            occupied_employee_ids = set(running_timers.mapped('employee_id.id'))

            # Calculate metrics
            occupied = len(occupied_employee_ids)
            # Calculate employees on leave
            on_leave = len(employees.filtered(lambda e: e.is_absent))
            print("Leave", on_leave)
            # free_team = total_team - occupied - on_leave
            free_employees = employees.filtered(
                lambda emp: emp.id not in occupied_employee_ids and not emp.is_absent
            )
            free_team = len(free_employees)

            running_overdue = tasks.filtered(
                lambda t: t.date_deadline and
                          t.date_deadline.date() < today and  # Convert to date
                          t.stage_id.name not in ['Done', 'Cancelled']
            )
            running_overdue = len(running_overdue.user_ids)

            return {
                'total_team': total_team,
                'free_team': free_team,
                'running_overdue': running_overdue,
                'occupied': occupied,
                'on_leave': on_leave
            }
        except Exception as e:
            _logger.error(f"Error in get_team_stats: {e}")
            return {
                'total_team': 0,
                'free_team': 0,
                'running_overdue': 0,
                'occupied': 0,
                'on_leave': 0
            }

    @http.route('/call/task/click', auth='public', type='json')
    def handle_task_click(self, task_type, company_id=None, department_id=None, subdepartment_id=None, start_date=None,
                          end_date=None):
        try:
            # Base domain with FSM filter
            domain = [('is_fsm', '=', True)]
            user = request.env.user
            is_admin = user.has_group('industry_fsm.group_fsm_manager')
            employee = user.employee_id

            base_dept_ids = []
            if employee.department_id:
                base_dept_ids.append(employee.department_id.id)

            # Departments from call.visibility
            visibility_dept_ids = request.env['call.visibility'].search([
                ('employee_id', '=', user.employee_id.id)
            ]).mapped('department_id.id')

            # Combine and remove duplicates - User's accessible departments
            user_accessible_dept_ids = list(set(base_dept_ids + visibility_dept_ids))
            if not is_admin and not (department_id or subdepartment_id):

                domain.append(('department_id', 'in', user_accessible_dept_ids))

            if company_id:
                company_id = int(company_id)
                domain.append(('company_id', '=', company_id))

            # Get the "Service Division" department and its children
            service_division_dept = request.env['hr.department'].search([('name', '=', 'Service Division')], limit=1)
            if service_division_dept:
                # Check if user is admin
                if is_admin:
                    # Admin sees ALL Service Division departments
                    all_dept_ids = request.env['hr.department'].search(
                        [('id', 'child_of', service_division_dept.id)]).ids
                else:
                    # Non-admin sees only their accessible departments
                    all_dept_ids = user_accessible_dept_ids
                domain.append(('department_id', 'in', all_dept_ids))

            if subdepartment_id:
                # Just the selected subdepartment â€” not the parent
                domain.append(('department_id', '=', int(subdepartment_id)))

            elif department_id:
                # Include the department and all its children
                department = request.env['hr.department'].browse(int(department_id))
                if department.exists():
                    all_dept_ids = request.env['hr.department'].search([('id', 'child_of', department.id)]).ids
                    domain.append(('department_id', 'in', all_dept_ids))

            # Add date filters if provided
            if start_date and end_date:
                domain.extend([
                    ('create_date', '>=', f"{start_date} 00:00:00"),
                    ('create_date', '<=', f"{end_date} 23:59:59")
                ])
            else:
                # Only apply today's filter if no specific date range is provided
                user_tz = pytz.timezone(request.env.user.tz or 'UTC')
                today = datetime.now(user_tz).date()
                domain.extend([
                    ('create_date', '>=', datetime.combine(today, datetime.min.time())),
                    ('create_date', '<=', datetime.combine(today, datetime.max.time()))
                ])
            # Add specific task type filter
            if task_type == 'new':
                domain.append(('stage_id.name', '=', 'New'))
            elif task_type == 'total':
                pass
            elif task_type == 'assigned':
                domain.append(('stage_id.name', '=', 'Assigned'))
            elif task_type == 'unassigned':
                domain.append(('user_ids', '=', False))
            elif task_type == 'on_hold':
                domain.append(('stage_id.name', '=', 'Pending'))
            elif task_type == 'in_progress':
                domain.append(('stage_id.name', '=', 'In Progress'))
            elif task_type == 'today_planned':
                domain.append(('stage_id.name', '=', 'Planned'))
            elif task_type == 'in_resolved':
                domain.append(('stage_id.name', '=', 'Resolved'))
            elif task_type == 'closed':
                domain.append(('stage_id.name', 'in', ['Done', 'Cancelled']))

            tasks = request.env['project.task'].search(domain)
            # print(tasks)
            return {
                'count': len(tasks),
                'task_ids': tasks.ids
            }
        except Exception as e:
            _logger.error(f"Error in handle_task_click: {e}")
            return {'error': str(e)}