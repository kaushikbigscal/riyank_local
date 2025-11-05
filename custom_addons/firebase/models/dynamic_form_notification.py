from odoo import fields, models, api

class DynamicField(models.Model):
    _inherit = 'dynamic.fields'

    def action_create_dynamic_field(self):
        # Call your logic to create the field (assuming that's done here)
        res = super(DynamicField, self).action_create_dynamic_field()

        # Notify users
        users = self.env['res.users'].search([])
        user_ids = [user.id for user in users if user.device_token]

        if user_ids:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=user_ids,
                title=None,
                body=None,
                payload={
                    'model': 'dynamic.fields',
                    'record_id': str(self.id),
                    'action': 'dynamic_field_creation',
                    'silent': "true"
                }
            )
            

        return res

    def unlink(self):
        for record in self:
            # Fetch all users with a registered device token
            users = self.env['res.users'].search([])
            user_ids = [user.id for user in users if user.device_token]

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'dynamic.fields',
                        'record_id':str(record.id),
                        'action': 'dynamic_field_deletion',
                        'silent': "true"
                    }
                )

        return super(DynamicField, self).unlink()



class FormConfig(models.Model):
    _inherit = 'ir.model.fields.mobile'

    def write(self, vals):
        # Only proceed if 'for_mobile' is being changed
        if 'for_mobile' not in vals:
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
                    'silent': "true"
                })
        return result

