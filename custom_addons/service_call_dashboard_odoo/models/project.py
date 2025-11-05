import random
from odoo import models


class Project(models.Model):
    """This class inherits from 'project.project' and adds custom functionality
    to it.It provides methods to work with project data."""
    _inherit = 'project.project'

    def get_color_code(self):
        """Generate a random color code in hexadecimal format.
        :return: A random color code in the format '#RRGGBB.'"""
        color = f"#{random.randint(0, 0xFFFFFF):06x}"
        return color

# from odoo import models, fields, api
#
# class HrDepartment(models.Model):
#     _inherit = 'hr.department'
#
#     total_employee_count = fields.Integer(string="Total Employees (incl. subdepartments)",
#                                           compute='_compute_total_employee_count')
#
#     @api.depends('child_ids', 'member_ids')
#     def _compute_total_employee_count(self):
#         for department in self:
#             all_departments = department._get_all_subdepartments()
#             employees = self.env['hr.employee'].search([('department_id', 'in', all_departments.ids)])
#             department.total_employee_count = len(employees)
#         print("all_departments ",all_departments)
#         print("employees ",employees)
#         print("department.total_employee_count ", department.total_employee_count)
#
#
#     def _get_all_subdepartments(self):
#         all_depts = self.browse()
#         to_check = self
#         print("all_depts ", all_depts)
#         print("to_check ", to_check)
#         while to_check:
#             current = to_check
#             all_depts |= current
#             to_check = self.env['hr.department'].search([('parent_id', 'in', current.ids)])
#             print("current ", current)
#             print("all_depts ", all_depts)
#             print("to_check ", to_check)
#         return all_depts

