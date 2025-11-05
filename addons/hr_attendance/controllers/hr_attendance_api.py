from odoo import http
from odoo.http import request

class EmployeeSubordinatesController(http.Controller):

    @http.route('/api/employee/subordinates', type='json', auth='user', methods=['GET'])
    def get_employee_subordinates(self):
        employee = request.env.user.employee_id
        if not employee:
            return {'error': 'No employee linked to the current user.'}

        subordinates = employee.all_subordinate_ids
        result = []
        for sub in subordinates:
            result.append({
                'id': sub.id,
                'name': sub.name,
                'work_email': sub.work_email,
                'job_title': sub.job_title,
                'manager_id': sub.parent_id.id if sub.parent_id else False,
                'manager_name': sub.parent_id.name if sub.parent_id else '',
            })

        return {'subordinates': result}
