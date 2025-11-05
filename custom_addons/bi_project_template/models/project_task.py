from datetime import timedelta
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ProjectTask(models.Model):
    _inherit = 'project.task'

    allocated_days_template = fields.Integer(string='Task Duration', help="Enter the Task Duration in Days")
    is_project_template = fields.Boolean(
        related='project_id.is_project_template',
        store=False
    )
    date_deadline = fields.Datetime(
        string='Deadline',
        compute='_compute_date_deadline',
        store=True,
        readonly=False
    )

    def _compute_date_deadline(self):
        for task in self:
            if not task.is_fsm:
                if task.state and task.state == '1_done':
                    # Do not change deadline if task is in Done state
                    continue
                start_date = task.project_id.date_start
                days = task.allocated_days_template or 0
                if start_date and days > 0:
                    task.date_deadline = start_date + timedelta(days=days)
                else:
                    task.date_deadline = False

    @api.onchange('allocated_days_template')
    def _onchange_allocated_days_template(self):
        self._compute_date_deadline()

    def _update_project_end_date(self):
        _logger.info("Starting _update_project_end_date for %s tasks", len(self))
        projects = self.mapped('project_id').filtered(lambda p: p.date_start)
        if not projects:
            return

        task_model = self.env['project.task']
        for project in projects:
            # Filter only tasks of this project
            last_task = task_model.search([
                ('project_id', '=', project.id)
            ], order='sequence desc', limit=1)

            new_date = project.date_start
            if last_task and last_task.allocated_days_template > 0:
                new_date += timedelta(days=last_task.allocated_days_template)

            # Only write if the date is actually different to avoid triggering chatter/tracking
            if project.date != new_date:
                project.sudo().write({'date': new_date})
                
        _logger.info("Finished _update_project_end_date")


    @api.model
    def create(self, vals):
        task = super().create(vals)
        if not self.env.context.get('import_file'):
            task._update_project_end_date()
        return task
