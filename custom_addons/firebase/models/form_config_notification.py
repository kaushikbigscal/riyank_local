from odoo import fields, models, api

class FormConfig(models.Model):
    _inherit = 'ir.model.fields.mobile'

    def write(self, vals):
        # Only proceed if 'for_mobile' is being changed
        if 'for_mobile' not in vals :
            return super(FormConfig, self).write(vals)

        result = super(FormConfig, self).write(vals)

        for record in self:
            # Skip notification if it's a fresh creation
            if record.create_date and record.write_date and record.create_date == record.write_date:
                continue

            users = self.env['res.users'].search([])
            user_ids = [user.id for user in users if user.device_token]

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title=None,
                    body=None,
                    payload={
                    'model': record.model_id.model if record.model_id else None,
                    'record_id': str(record.id),
                    'action': 'form_config_update',
                    'silent': "true",
                })
        return result
