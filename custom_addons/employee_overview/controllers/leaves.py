from odoo import http
from odoo.http import request


class LeaveController(http.Controller):

    @http.route('/web/employee/leaves/json', type='json', auth='user')
    def get_approved_leaves(self):
        # Remove company filter from context completely to fetch all companies' leaves
        leaves = request.env['hr.leave'].sudo().search([('state', '=', 'validate')])
        return [{
            'employee': l.employee_id.name,
            'department': l.department_id.name,
            'date_from': str(l.date_from),
            'date_to': str(l.date_to),
            'company': l.employee_id.company_id.name,
        } for l in leaves]