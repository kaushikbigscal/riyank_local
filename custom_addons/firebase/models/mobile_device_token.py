from odoo import models, fields, api
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = 'res.users'

    # user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    device_token = fields.Char(string='Device Token')
    last_used = fields.Datetime(string='Last Used')

    _sql_constraints = [
        ('unique_user_device_token', 'unique(user_id, device_token)', 'Device token must be unique per user')
    ]

    def write(self, vals):
        allowed_fields = ['device_token', 'last_used']

        # If user is NOT an Administrator
        if not self.env.user.has_group('base.group_system'):
            # If user is Portal or Internal
            if self.env.user.has_group('base.group_portal') or self.env.user.has_group('base.group_user'):
                for field in vals.keys():
                    if field not in allowed_fields:
                        raise AccessError(
                            "You are only allowed to update the fields: device_token and last_used."
                        )

        return super(ResUsers, self).write(vals)

    @api.model
    def register_device_token(self, user_id, device_token, platform):
        """
        Register or update device token for a user
        """
        try:
            existing_token = self.search([
                ('id', '=', user_id),
                ('device_token', '=', device_token)
            ])

            if existing_token:
                existing_token.write({
                    'last_used': fields.Datetime.now(),
                    'active': True
                })
                return existing_token.id

            return self.create({
                'user_id': user_id,
                'device_token': device_token,
                'platform': platform,
                'last_used': fields.Datetime.now()
            }).id

        except Exception as e:
            self.env['notification.log'].create_log(
                'device_token_registration',
                f'Error registering device token: {str(e)}'
            )
            return False