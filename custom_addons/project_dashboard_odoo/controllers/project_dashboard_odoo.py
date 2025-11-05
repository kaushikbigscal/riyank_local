from datetime import datetime, timedelta, date
from odoo import http
from odoo.http import request


class ProjectFilter(http.Controller):
    """The ProjectFilter class provides the filter option to the js.
    When applying the filter returns the corresponding data."""

    @http.route('/get/departments', auth='public', type='json')
    def get_departments(self):
        current_company = request.env.company
        departments = request.env['hr.department'].search([])
        return [{
            'id': dept.id,
            'name': dept.name
        } for dept in departments]

    @http.route('/get/tiles/data', auth='public', type='json')
    def get_tiles_data(self, department_id=None):
        """Fetch various project and task metrics for the dashboard."""
        user_employee = request.env.user.partner_id

        project_domain = []

        # Add department filter if specified
        if department_id:
            project_domain.append(('x_department', '=', int(department_id)))

        # Add user filter if not project manager
        if not user_employee.user_has_groups('project.group_project_manager'):
            project_domain.append(('user_id', '=', request.env.uid))

        # Get filtered projects
        all_projects = request.env['project.project'].search(project_domain)

        # Get tasks only for the filtered projects
        task_domain = [('project_id', 'in', all_projects.ids)]
        all_tasks = request.env['project.task'].search(task_domain)

        # Calculate counts using the filtered tasks
        running_tasks = all_tasks.filtered(
            lambda t: t.state in ['01_in_progress', '02_changes_requested', '03_approved'])
        done_tasks = all_tasks.filtered(lambda t: t.state == '1_done')
        canceled_tasks = all_tasks.filtered(lambda t: t.state == '1_canceled')

        # Calculate project counts
        active_projects = all_projects.filtered(lambda p: p.stage_id.name not in ['Done', 'Canceled'])
        running_projects = all_projects.filtered(lambda p: p.stage_id.name in ['In Progress'])
        done_projects = all_projects.filtered(lambda p: p.stage_id.name == 'Done')
        canceled_projects = all_projects.filtered(lambda p: p.stage_id.name == 'Canceled')

        # Dates for expiration checks
        today = datetime.today().date()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        expired_projects = all_projects.filtered(lambda p: p.date and p.date < today and p.stage_id.name != 'Done')
        expired_yesterday = all_projects.filtered(lambda p: p.date == yesterday and p.stage_id.name != 'Done')
        will_expire_tomorrow = all_projects.filtered(lambda p: p.date == tomorrow)
        expired_today = all_projects.filtered(lambda p: p.date == today)

        return {
            'total_projects': len(all_projects),
            'total_tasks': len(all_tasks),
            'active_projects': len(active_projects),
            'running_projects': len(running_projects),
            'canceled_projects': len(canceled_projects),
            'canceled_tasks': len(canceled_tasks),
            'done_projects': len(done_projects),
            'running_tasks': len(running_tasks),
            'done_tasks': len(done_tasks),
            'expired_yesterday': len(expired_yesterday),
            'will_expire_tomorrow': len(will_expire_tomorrow),
            'expired_today': len(expired_today),
            'expired_projects': len(expired_projects),
            'flag': 1
        }

    @http.route('/project/task/by_tags', auth='public', type='json')
    def get_task_by_tags(self, department_id=None):
        """Fetch task counts grouped by tags."""
        user_employee = request.env.user.partner_id
        project_domain = []

        if department_id:
            project_domain.append(('x_department', '=', int(department_id)))

        if not user_employee.user_has_groups('project.group_project_manager'):
            project_domain.append(('user_id', '=', request.env.uid))

        # Get filtered projects first
        projects = request.env['project.project'].search(project_domain)

        if not projects:
            return {
                'labels': [],
                'data': [],
                'colors': []
            }

        # Use SQL to count tasks by tags directly
        query = '''
             SELECT tag.name, COUNT(task.id) as count
            FROM project_task task
            JOIN project_tags_project_task_rel rel ON task.id = rel.project_task_id  -- Correct table name
            JOIN project_tags tag ON rel.project_tags_id = tag.id
            WHERE task.project_id IN (SELECT id FROM project_project WHERE id IN %s)
            GROUP BY tag.name
            ORDER BY count DESC
            LIMIT 10
        '''
        request._cr.execute(query, (tuple(projects.ids),))
        tag_counts = request._cr.fetchall()

        # Prepare data for chart
        labels = [row[0]['en_US'] for row in tag_counts]
        data = [row[1] for row in tag_counts]
        colors = [
                     '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
                     '#FF9F40', '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0'
                 ][:len(labels)]  # Assign colors based on number of tags

        return {
            'labels': labels,
            'data': data,
            'colors': colors
        }

    @http.route('/project/task/by_employee', auth='public', type='json')
    def get_task_by_employee(self, department_id=None):
        """Fetch task counts grouped by employees."""
        user_employee = request.env.user.partner_id

        project_domain = []

        if department_id:
            project_domain.append(('x_department', '=', int(department_id)))

        if not user_employee.user_has_groups('project.group_project_manager'):
            project_domain.append(('user_id', '=', request.env.uid))

        # Get filtered projects first
        projects = request.env['project.project'].search(project_domain)

        # Only proceed with a query if there are projects
        if not projects:
            return {
                'labels': [],
                'data': [],
                'colors': []
            }

        # Use SQL to count tasks by employee directly
        query = '''
            SELECT 
            partner.name as user_name, 
            COUNT(task.id) as task_count
        FROM 
            project_task task
        JOIN 
            project_task_user_rel rel ON task.id = rel.task_id
        JOIN 
            res_users users ON users.id = rel.user_id
        JOIN 
            res_partner partner ON partner.id = users.partner_id
        WHERE 
            task.project_id IN (SELECT id FROM project_project WHERE id IN %s)
        GROUP BY 
            partner.name
        ORDER BY 
            task_count DESC
        LIMIT 10;
        '''
        request._cr.execute(query, (tuple(projects.ids),))
        employee_counts = request._cr.fetchall()

        # Prepare data for chart
        labels = [row[0] for row in employee_counts]
        data = [row[1] for row in employee_counts]
        colors = [
                     '#2ecc71', '#3498db', '#9b59b6', '#f1c40f', '#e67e22',
                     '#e74c3c', '#1abc9c', '#34495e', '#95a5a6', '#16a085'
                 ][:len(labels)]

        return {
            'labels': labels,
            'data': data,
            'colors': colors
        }
