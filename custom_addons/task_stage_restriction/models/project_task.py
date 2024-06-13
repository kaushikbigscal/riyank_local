# task_stage_restriction/models/project_task.py
from odoo import models, fields, api
from odoo.exceptions import AccessError

class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model
    def write(self, vals):
        if 'stage_id' in vals:
            if not self.env.user.has_group('project.group_project_manager'):
                raise AccessError("You do not have the necessary permissions to change the task stage.")
        return super(ProjectTask, self).write(vals)
