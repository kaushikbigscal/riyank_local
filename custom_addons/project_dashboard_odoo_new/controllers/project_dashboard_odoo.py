from collections import defaultdict
from datetime import datetime, timedelta, date
from odoo import http
from odoo.http import request
from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class ProjectFilter(http.Controller):
    """The ProjectFilter class provides the filter option to the js.
    When applying the filter returns the corresponding data."""



    @http.route('/get/project_template', type='json', auth='user')
    def get_project_template(self):
        """Fetch project templates where the current user is assigned to non-blocked tasks or is a PM."""
        try:
            user_id = request.env.user.id
            lang = request.env.lang or 'en_US'

            is_admin = request.env.user.has_group('base.group_system')

            templates = set()

            if is_admin:
                query_admin = """
                    SELECT DISTINCT pp.x_template
                    FROM project_project pp
                    WHERE pp.active = TRUE
                      AND pp.is_fsm = FALSE
                      AND pp.x_template IS NOT NULL
                    ORDER BY pp.x_template;
                """
                request.env.cr.execute(query_admin)
                result = request.env.cr.fetchall()
                templates.update(row[0] for row in result if row[0])
            else:
                # Project Manager templates
                query_pm = """
                    SELECT DISTINCT pp.x_template
                    FROM project_project pp
                    WHERE pp.active = TRUE
                      AND pp.is_fsm = FALSE
                      AND pp.x_template IS NOT NULL
                      AND pp.user_id = %s
                    ORDER BY pp.x_template;
                """
                request.env.cr.execute(query_pm, (user_id,))
                result_pm = request.env.cr.fetchall()
                templates.update(row[0] for row in result_pm if row[0])

                # Assigned task user templates
                query_user = """
                    SELECT DISTINCT pp.x_template
                    FROM project_project pp
                    WHERE pp.active = TRUE
                      AND pp.is_fsm = FALSE
                      AND pp.x_template IS NOT NULL
                      AND pp.id IN (
                          SELECT pt.project_id
                          FROM project_task pt
                          JOIN project_task_user_rel rel ON pt.id = rel.task_id
                          WHERE rel.user_id = %s
                            AND pt.active = TRUE
                            AND pt.state NOT IN ('1_done', '1_canceled', '04_waiting_normal')
                      )
                    ORDER BY pp.x_template;
                """
                request.env.cr.execute(query_user, (user_id,))
                result_user = request.env.cr.fetchall()
                templates.update(row[0] for row in result_user if row[0])

            # Format and return the unique template list
            return [{'id': t, 'name': t} for t in sorted(templates)]

        except Exception as e:
            _logger.error(f"Error fetching project templates: {e}", exc_info=True)
            return []



    @http.route('/get/departments', auth='public', type='json')
    def get_departments(self):
        try:
            lang = request.env.lang or 'en_US'
            user_id = request.env.user.id

            # Check if the user is an admin
            is_admin = request.env.user.has_group('base.group_system')
            params = [lang]
            departments = {}

            # Admin Query - Admin sees all departments
            if is_admin:
                query = """
                    SELECT DISTINCT hd.id,
                           COALESCE(hd.name->>%s, hd.name->>'en_US') AS name
                    FROM hr_department hd
                    JOIN project_project pp ON pp.x_department = hd.id
                    WHERE pp.active = TRUE
                      AND pp.is_fsm = FALSE
                    ORDER BY name;
                """
                request.env.cr.execute(query, tuple(params))
                result = request.env.cr.fetchall()
            else:
                # Project Manager Query - Project manager sees departments for their managed projects
                query_pm = """
                    SELECT DISTINCT hd.id,
                           COALESCE(hd.name->>%s, hd.name->>'en_US') AS name
                    FROM hr_department hd
                    JOIN project_project pp ON pp.x_department = hd.id
                    WHERE pp.active = TRUE
                      AND pp.is_fsm = FALSE
                      AND pp.user_id = %s 
                    ORDER BY name;
                """
                request.env.cr.execute(query_pm, (lang, user_id))
                result_pm = request.env.cr.fetchall()

                # Normal User Query - Normal user sees departments based on assigned tasks
                query_user = """
                    SELECT DISTINCT hd.id,
                           COALESCE(hd.name->>%s, hd.name->>'en_US') AS name
                    FROM hr_department hd
                    JOIN project_project pp ON pp.x_department = hd.id
                    JOIN project_task pt ON pt.project_id = pp.id
                    JOIN project_task_user_rel rel ON rel.task_id = pt.id
                    WHERE pp.active = TRUE
                      AND pp.is_fsm = FALSE
                      AND rel.user_id = %s  
                      AND pt.state NOT IN ('1_done', '1_canceled', '04_waiting_normal')  
                    ORDER BY name;
                """
                request.env.cr.execute(query_user, (lang, user_id))
                result_user = request.env.cr.fetchall()

                # Combine results of Project Manager and Normal User
                for dept_id, dept_name in result_pm + result_user:
                    if dept_id not in departments:
                        departments[dept_id] = dept_name

                result = [(dept_id, name) for dept_id, name in departments.items()]

            return [{'id': dept_id, 'name': dept_name} for dept_id, dept_name in result if dept_name]

        except Exception as e:
            _logger.error(f"Error fetching departments: {e}", exc_info=True)
            return []


    @http.route('/get/tiles/data', auth='public', type='json')
    def get_tiles_data(self, department_id=None, x_template=None, start_date=None, end_date=None):
        try:
            user = request.env.user
            user_id = user.id
            today = fields.Date.today()
            yesterday = today - timedelta(days=1)
            tomorrow = today + timedelta(days=1)

            if start_date and end_date:
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                except ValueError:
                    return {'error': 'Invalid date format. Use YYYY-MM-DD.'}

            project_model = request.env['project.project'].sudo()
            task_model = request.env['project.task'].sudo()

            is_admin = user.has_group('project.group_project_manager')
            pm_project_ids = project_model.search([('user_id', '=', user_id)]).ids

            user_task_ids = task_model.search([
                ('user_ids', 'in', [user_id]),
                ('active', '=', True),
                ('state', 'in', ['01_in_progress', '02_changes_requested', '03_approved', '05_not_started'])
            ])
            user_task_project_ids = user_task_ids.mapped('project_id').ids

            combined_project_ids = list(set(pm_project_ids + user_task_project_ids))

            base_domain = [
                ('is_fsm', '=', False),
                ('is_project_template', '=', False),
                ('active', '=', True),
            ]
            # Department filter
            if department_id:
                department_ids = (
                    [int(d) for d in department_id] if isinstance(department_id, list)
                    else [int(d) for d in str(department_id).split(",") if d.isdigit()]
                )
                if department_ids:
                    base_domain.append(('x_department', 'in', department_ids))

            # Template filter
            if x_template:
                templates = x_template if isinstance(x_template, list) else x_template.split(",")
                if templates:
                    if len(templates) == 1:
                        base_domain.append(('x_template', '=', templates[0]))
                    else:
                        base_domain.extend(['|'] * (len(templates) - 1))
                        base_domain.extend([('x_template', '=', t) for t in templates])

            # Date range filter
            if start_date and end_date:
                base_domain.extend([
                    ('date', '>=', start_date),
                    ('date', '<=', end_date)
                ])

            if not is_admin:
                base_domain.append(('id', 'in', combined_project_ids or [0]))

            projects = project_model.search(base_domain)
            project_ids = projects.ids

            stage_counts = {s: 0 for s in ['Done', 'Canceled', 'In Progress']}
            for proj in projects:
                stage = proj.stage_id.name
                if stage in stage_counts:
                    stage_counts[stage] += 1

            done_projects = stage_counts['Done']
            canceled_projects = stage_counts['Canceled']
            running_projects = stage_counts['In Progress']
            active_projects = len(project_ids) - done_projects - canceled_projects

            expired_projects = len(projects.filtered(lambda p: p.date and p.date < today and p.stage_id.name not in ['Done', 'Canceled']))
            expired_yesterday = len(projects.filtered(lambda p: p.date == yesterday and p.stage_id.name not in ['Done', 'Canceled']))
            expired_today = len(projects.filtered(lambda p: p.date == today and p.stage_id.name not in ['Done', 'Canceled']))
            will_expire_tomorrow = len(projects.filtered(lambda p: p.date == tomorrow and p.stage_id.name not in ['Done', 'Canceled']))

            # Task filtering
            task_domain = [('project_id', 'in', project_ids), ('active', '=', True)]

            if not is_admin:
                role_domain = []
                if pm_project_ids:
                    role_domain.append(('project_id', 'in', pm_project_ids))
                if user_task_project_ids:
                    role_domain.append(('user_ids', 'in', [user_id]))
                if role_domain:
                    if len(role_domain) > 1:
                        task_domain += ['|'] * (len(role_domain) - 1) + role_domain
                    else:
                        task_domain += role_domain
                else:
                    task_domain.append(('id', '=', 0))

            if is_admin or pm_project_ids:
                visible_states = ['01_in_progress', '02_changes_requested', '03_approved', '1_done', '1_canceled','04_waiting_normal','04_waiting_for_customer', '05_not_started']
            else:
                visible_states = ['01_in_progress', '02_changes_requested', '03_approved', '05_not_started']


            task_domain.append(('state', 'in', visible_states))

            all_tasks = task_model.search(task_domain)

            # Count running tasks excluding blocked ones

            running_tasks = sum(
                1 for t in all_tasks if t.state in ['01_in_progress', '02_changes_requested', '03_approved','04_waiting_normal','04_waiting_for_customer'])

            not_started = sum(1 for t in all_tasks if t.state == '05_not_started')

            done_tasks = sum(1 for t in all_tasks if t.state == '1_done')
            canceled_tasks = sum(1 for t in all_tasks if t.state == '1_canceled')

            excluded_project_stages = ['Done', 'Canceled']
            expired_tasks = sum(
                1 for t in all_tasks
                if t.project_id.date
                and t.project_id.date < today
                and t.state not in ['1_done', '1_canceled']
                and t.project_id.stage_id
                and t.project_id.stage_id.name not in excluded_project_stages
            )
            expired_yesterday_tasks = sum(
                1 for t in all_tasks
                if t.project_id.date == yesterday
                and t.state not in ['1_done', '1_canceled']
                and t.project_id.stage_id
                and t.project_id.stage_id.name not in excluded_project_stages
            )
            expired_today_tasks = sum(
                1 for t in all_tasks
                if t.project_id.date == today
                and t.state not in ['1_done', '1_canceled']
                and t.project_id.stage_id
                and t.project_id.stage_id.name not in excluded_project_stages
            )
            will_expire_tomorrow_tasks = sum(
                1 for t in all_tasks
                if t.project_id.date == tomorrow
                and t.state not in ['1_done', '1_canceled']
                and t.project_id.stage_id
                and t.project_id.stage_id.name not in excluded_project_stages
            )

            return {
                'total_projects': len(project_ids),
                'active_projects': active_projects,
                'running_projects': running_projects,
                'done_projects': done_projects,
                'canceled_projects': canceled_projects,
                'expired_projects': expired_projects,
                'expired_yesterday': expired_yesterday,
                'expired_today': expired_today,
                'will_expire_tomorrow': will_expire_tomorrow,
                'not_started': not_started,
                'total_tasks': len(all_tasks),
                'running_tasks': running_tasks,
                'done_tasks': done_tasks,
                'canceled_tasks': canceled_tasks,
                'expired_tasks': expired_tasks,
                'expired_yesterday_tasks': expired_yesterday_tasks,
                'expired_today_tasks': expired_today_tasks,
                'will_expire_tomorrow_tasks': will_expire_tomorrow_tasks,
                'has_project_admin_rights': is_admin,
            }

        except Exception as e:
            _logger.exception("Error in /get/tiles/data")
            return {'error': str(e)}



    @http.route('/project/task/by_employee', auth='user', type='json')
    def get_task_by_employee(self, department_id=None, x_template=None, start_date=None, end_date=None):
        try:
            user = request.env.user
            is_admin = user.has_group('base.group_system')

            # Base project domain
            project_domain = [
                ('is_fsm', '=', False),
                ('is_project_template', '=', False),
                ('active', '=', True),
            ]

            if department_id:
                dept_ids = [int(d) for d in department_id] if isinstance(department_id, list) else \
                    [int(d) for d in str(department_id).split(',') if d.isdigit()]
                if dept_ids:
                    project_domain.append(('x_department', 'in', dept_ids))

            if x_template:
                templates = x_template if isinstance(x_template, list) else str(x_template).split(',')
                if len(templates) == 1:
                    project_domain.append(('x_template', '=', templates[0]))
                else:
                    template_domain = ['|'] * (len(templates) - 1)
                    for t in templates:
                        template_domain.append(('x_template', '=', t))
                    project_domain.extend(template_domain)

            if start_date and end_date:
                project_domain += [('date', '>=', start_date), ('date', '<=', end_date)]

            # all_projects = request.env['project.project'].search(project_domain)
            all_projects = request.env['project.project'].sudo().search(project_domain)
            if not all_projects:
                return {'labels': [], 'data': [], 'colors': []}

            # Task domain
            task_domain = [
                ('project_id', 'in', all_projects.ids),
                # ('depend_on_ids', '=', False),
                ('active', '=', True),
                ('state', 'in', ['01_in_progress', '02_changes_requested', '03_approved', '1_done', '1_canceled','04_waiting_normal','04_waiting_for_customer', '05_not_started']),
            ]

            if is_admin:
                # Admin sees everything, including done and canceled
                pass
            else:
                # Identify PM-managed projects
                managed_projects = all_projects.filtered(lambda p: p.user_id.id == user.id)
                if managed_projects:
                    # PM sees all tasks (including done/canceled) in their projects
                    task_domain.append(('|')),
                    task_domain.append(('project_id', 'in', managed_projects.ids)),
                    task_domain.append(('user_ids', 'in', [user.id]))
                else:
                    # Regular user: only see own tasks, excluding done/canceled
                    task_domain.append(('user_ids', 'in', [user.id]))
                    task_domain.append(('state', 'in', ['01_in_progress', '02_changes_requested', '03_approved', '05_not_started']))

            tasks = request.env['project.task'].sudo().search(task_domain)
            if not tasks:
                return {'labels': [], 'data': [], 'colors': []}

            # Count tasks by assigned user
            user_task_map = {}
            for task in tasks:
                for assigned_user in task.user_ids:
                    # Regular user: skip others
                    if not is_admin and not managed_projects and assigned_user.id != user.id:
                        continue
                    user_task_map[assigned_user] = user_task_map.get(assigned_user, 0) + 1

            sorted_users = sorted(user_task_map.items(), key=lambda x: x[1], reverse=True)
            sorted_users = sorted_users[:10]
            labels = [u.name for u, _ in sorted_users]
            data = [count for _, count in sorted_users]
            colors = [
                         '#2ecc71', '#3498db', '#9b59b6', '#f1c40f', '#e67e22',
                         '#e74c3c', '#1abc9c', '#34495e', '#95a5a6', '#16a085'
                     ][:len(labels)]

            return {'labels': labels, 'data': data, 'colors': colors}

        except Exception as e:
            _logger.error(f"[get_task_by_employee] Error: {e}")
            return {'labels': [], 'data': [], 'colors': []}

    @http.route('/project/task/by_tags', auth='user', type='json')
    def get_task_by_tags(self, department_id=None, x_template=None, start_date=None, end_date=None):
        try:
            user = request.env.user
            is_admin = user.has_group('base.group_system')

            # Base project domain
            project_domain = [
                ('active', '=', True),
                ('is_fsm', '=', False),
                ('is_project_template', '=', False),
            ]

            if department_id:
                dept_ids = [int(d) for d in department_id] if isinstance(department_id, list) else \
                    [int(d) for d in str(department_id).split(',') if d.isdigit()]
                if dept_ids:
                    project_domain.append(('x_department', 'in', dept_ids))

            if x_template:
                templates = x_template if isinstance(x_template, list) else str(x_template).split(',')
                if len(templates) == 1:
                    project_domain.append(('x_template', '=', templates[0]))
                else:
                    template_domain = ['|'] * (len(templates) - 1)
                    for t in templates:
                        template_domain.append(('x_template', '=', t))
                    project_domain.extend(template_domain)

            if start_date and end_date:
                project_domain += [
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                ]

            all_projects = request.env['project.project'].sudo().search(project_domain)
            if not all_projects:
                return {'labels': [], 'data': [], 'colors': []}

            # Determine visible projects and task domain
            managed_projects = all_projects.filtered(lambda p: p.user_id.id == user.id)
            task_domain = [
                ('active', '=', True),
                ('state', 'in', ['01_in_progress', '02_changes_requested', '03_approved','1_done','1_canceled','04_waiting_normal','04_waiting_for_customer', '05_not_started'])
                # ('depend_on_ids', '=', False),
            ]


            if is_admin:
                task_domain.append(('project_id', 'in', all_projects.ids))

            elif managed_projects:
                # Project Manager: tasks from managed projects + tasks assigned to them
                task_domain.append('|')
                task_domain += [
                    ('project_id', 'in', managed_projects.ids),
                    ('user_ids', 'in', [user.id]),
                    ('state', 'in', ['01_in_progress', '02_changes_requested', '03_approved','1_done','1_canceled','04_waiting_normal','04_waiting_for_customer', '05_not_started'])
                ]
            else:
                # Normal user
                task_domain += [
                    ('project_id', 'in', all_projects.ids),
                    ('user_ids', 'in', [user.id]),
                    ('state', 'in', ['01_in_progress', '02_changes_requested', '03_approved', '05_not_started']),
                ]

            tasks = request.env['project.task'].sudo().search(task_domain)
            if not tasks:
                return {'labels': [], 'data': [], 'colors': []}

            # Tag aggregation
            query = '''
                SELECT
                    COALESCE(tag.name->>%s, tag.name->>'en_US',tag.name->>0) as tag_name,
                    COUNT(DISTINCT task.id) as count
                FROM
                    project_task task
                JOIN
                    project_tags_project_task_rel rel ON task.id = rel.project_task_id
                JOIN
                    project_tags tag ON rel.project_tags_id = tag.id
                WHERE
                    task.id IN %s
                GROUP BY
                    tag_name
                ORDER BY
                    count DESC
                LIMIT 10
            '''

            lang = request.env.lang or 'en_US'
            request.env.cr.execute(query, (lang, tuple(tasks.ids)))
            tag_counts = request.env.cr.fetchall()
            tag_counts.sort(key=lambda x: x[1], reverse=True)

            labels = [row[0] for row in tag_counts if row[0]]
            data = [row[1] for row in tag_counts if row[0]]
            colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
                      '#FF9F40', '#8B0000', '#2E8B57', '#8A2BE2', '#00CED1'][:len(labels)]

            return {
                'labels': labels,
                'data': data,
                'colors': colors,
            }

        except Exception as e:
            _logger.error(f"[get_task_by_tags] Error: {e}")
            return {'labels': [], 'data': [], 'colors': []}


    # Summary Dashboard By Company Level

    @http.route('/get/companies', auth='public', type='json')
    def get_companies(self):
        companies = request.env['res.company'].search([])
        return [{
            'id': company.id,
            'name': company.name
        } for company in companies]


    @http.route('/get/departments/by_company', auth='user', type='json')
    def get_departments_by_company(self, company_id=None):
        try:
            if not company_id:
                return []

            company_id = int(company_id)
            user = request.env.user
            has_project_admin_rights = user.has_group('project.group_project_manager')

            if has_project_admin_rights:
                # Admin: return all root departments in the company
                departments = request.env['hr.department'].search([
                    ('company_id', '=', company_id),
                    ('parent_id', '=', False)
                ])
            else:
                # Regular user: return only departments from projects where the user has assigned tasks
                assigned_project_ids = request.env['project.task'].search([
                    ('user_ids', 'in', [user.id]),
                    ('project_id.company_id', '=', company_id),
                    ('active', '=', True)
                ]).mapped('project_id')

                departments = assigned_project_ids.mapped('x_department').filtered(lambda d: d.parent_id is False)

            return [{
                'id': dept.id,
                'name': dept.name
            } for dept in departments]

        except Exception as e:
            _logger.error("Error fetching departments: %s", e)
            return []

    @http.route('/get/sub_departments', auth='public', type='json')
    def get_sub_departments(self, department_id):
        """Fetch sub-departments for a given department."""
        sub_departments = request.env['hr.department'].search([
            ('parent_id', '=', int(department_id))  # Assuming 'parent_id' is the field linking subdepartments to
            # their parent
        ])
        return [{
            'id': sub_dept.id,
            'name': sub_dept.name
        } for sub_dept in sub_departments]

    @http.route('/get/departments/used', auth='public', type='json')
    def get_used_departments(self):
        """Fetch only departments that are used in projects."""
        try:
            # Get departments that are used in projects
            query = """
                SELECT DISTINCT d.id, d.name
                FROM hr_department d
                JOIN project_project p ON p.x_department = d.id
                WHERE p.is_project_template = False
                ORDER BY d.name
            """
            request.env.cr.execute(query)
            departments = request.env.cr.dictfetchall()

            return [{
                'id': dept['id'],
                'name': dept['name']
            } for dept in departments]
        except Exception as e:
            _logger.error("Error fetching used departments: %s", str(e))
            return []
