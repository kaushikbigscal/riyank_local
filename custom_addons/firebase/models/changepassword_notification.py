from odoo import models


class ChangePasswordOwn(models.TransientModel):
    _inherit = 'change.password.own'

    def change_password(self):
        # Call the original change_password method to update the password
        result = super(ChangePasswordOwn, self).change_password()

        # Get the current user
        user = self.env.user

        # Check if the user has a device token
        if user.device_token:
            # Prepare the notification payload
            payload = {
                'model': 'res.users',
                'record_id': str(user.id),
                'action': 'password_changed',
                'silent': 'true'
            }

            # Send FCM notification
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=[user.id],
                title=None,
                body=None,
                payload=payload
            )

            user.write({'device_token': False})

        return result
