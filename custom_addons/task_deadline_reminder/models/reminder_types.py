from odoo import models, fields, _, api
from odoo.exceptions import UserError


class ReminderTypes(models.Model):
    _name = 'reminder.types'
    _description = 'Reminder types'

    name = fields.Char(string="Reminder Types")
    reminder_minutes = fields.Integer(string="Reminder Offset (in minutes)")


    # helper to get protected record ids
    @api.model
    def _get_protected_type_ids(self):
        xml_ids = [
            'task_deadline_reminder.reminder_type_10m',
            'task_deadline_reminder.reminder_type_1h',
            'task_deadline_reminder.reminder_type_1d',
            'task_deadline_reminder.reminder_type_custom',
        ]
        return [self.env.ref(x).id for x in xml_ids if self.env.ref(x, raise_if_not_found=False)]

    def unlink(self):
        protected_ids = self._get_protected_type_ids()
        for rec in self:
            if rec.id in protected_ids:
                raise UserError(_("Default reminder type '%s' cannot be deleted.") % rec.name)

            used_in_tasks = self.env['project.task'].search_count([('reminder_type_ids', 'in', rec.id)])
            used_in_activities = self.env['mail.activity'].search_count([('reminder_type_ids', 'in', rec.id)])

            if used_in_tasks or used_in_activities:
                raise UserError(
                    _("Reminder type '%s' is being used in tasks or activities and cannot be deleted.") % rec.name
                )
        return super().unlink()

    def write(self, vals):
        # Allow updates if not changing protected fields
        protected_fields = ['name', 'reminder_minutes']
        for rec in self:
            if rec.name in ['10 Minutes Before', '1 Hour Before', '1 Day Before', 'Custom']:
                # Check if any protected field is being modified
                if any(field in vals for field in protected_fields):
                    raise UserError(_("You cannot modify the default reminder type '%s'.") % rec.name)
        return super(ReminderTypes, self).write(vals)
