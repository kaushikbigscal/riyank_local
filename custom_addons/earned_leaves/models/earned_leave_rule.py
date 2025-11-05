from odoo import models, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def apply_earned_leave_rule(self):
        earned_leave_type = self.env['hr.leave.type'].search([('name', '=', 'Earned Leaves')], limit=1)
        encash_leave_type = self.env['hr.leave.type'].search([('name', '=', 'Encash Leaves')], limit=1)

        if not earned_leave_type or not encash_leave_type:
            raise UserError("Earned Leaves or Encash Leaves types not found.")

        max_earned_leaves = 10

        # Get all employees
        employees = self.search([])

        for employee in employees:
            _logger.info(f"Processing employee ID: {employee.id}")

            earned_allocations_records = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', earned_leave_type.id),
                ('state', '=', 'validate')
            ])
            earned_allocations = sum(earned_allocations_records.mapped('number_of_days'))
            _logger.info(f"Earned Allocations for Employee ID {employee.id}: {earned_allocations}")

            leaves_taken = sum(self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', earned_leave_type.id),
                ('state', '=', 'validate')
            ]).mapped('number_of_days'))

            net_earned_leaves = earned_allocations - leaves_taken
            _logger.info(f"Net Earned Leaves for Employee ID {employee.id}: {net_earned_leaves}")

            if net_earned_leaves > max_earned_leaves:
                excess_leaves = net_earned_leaves - max_earned_leaves
                _logger.info(f"Excess Leaves for Employee ID {employee.id}: {excess_leaves}")
            else:
                _logger.info(f"No excess leaves to adjust for Employee ID {employee.id}.")
                continue

            # Add excess to Encash Leaves
            encash_allocation = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', encash_leave_type.id),
                ('state', '=', 'validate')
            ], limit=1)
            _logger.info(f"Encash Allocation found: {encash_allocation}")

            if encash_allocation:
                _logger.info(f"Updating Encash Allocation with excess leaves: {excess_leaves}")
                encash_allocation.write({'number_of_days': encash_allocation.number_of_days + excess_leaves})
            else:
                _logger.info(f"Creating new Encash Allocation with excess leaves: {excess_leaves}")
                self.env['hr.leave.allocation'].create({
                    'name': 'Automatic Encash Allocation',
                    'employee_id': employee.id,
                    'holiday_status_id': encash_leave_type.id,
                    'number_of_days': excess_leaves,
                    'state': 'confirm',
                })

            # Unlink existing earned leave allocations
            _logger.info("Unlinking existing Earned Leave Allocations.")
            earned_allocations_records.write({'state': 'confirm'})
            earned_allocations_records.unlink()
            max_earned = int(max_earned_leaves + leaves_taken)
            #max_earned = 10
            # Allocate new earned leave with maximum limit
            _logger.info(f"Allocating new Earned Leave Allocation with limit: {max_earned_leaves}")
            new_allocation = self.env['hr.leave.allocation'].create({
                'name': 'Reallocated Earned Leave',
                'employee_id': employee.id,
                'holiday_status_id': earned_leave_type.id,
                'number_of_days': max_earned,
                'state': 'confirm',
            })
            new_allocation.action_validate()

            _logger.info(f"Earned Leave Allocation updated successfully for Employee ID {employee.id}.")

        _logger.info("Earned Leave Allocation process completed for all employees.")