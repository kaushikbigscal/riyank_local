from odoo import models, fields, api

class EmployeeLeaveReport(models.Model):
    _name = 'employee.leave.report'
    _description = 'All Approved Employee Leaves (All Companies)'
    _auto = False  # It's a SQL view

    employee_id = fields.Many2one('hr.employee', string="Employee")
    department_id = fields.Many2one('hr.department', string="Department")
    date_from = fields.Datetime(string="Start Date")
    date_to = fields.Datetime(string="End Date")
    company_id = fields.Many2one('res.company', string="Company")

    def init(self):
        self._cr.execute("""
            CREATE OR REPLACE VIEW employee_leave_report AS (
                SELECT
                    l.id as id,
                    l.employee_id,
                    e.department_id,
                    l.date_from,
                    l.date_to,
                    e.company_id
                FROM hr_leave l
                JOIN hr_employee e ON l.employee_id = e.id
                WHERE l.state = 'validate'
            )
        """)
