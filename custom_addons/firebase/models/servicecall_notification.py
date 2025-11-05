# Service call setting changes
from odoo import models, api
import logging
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def set_values(self):
        config = self.env['ir.config_parameter'].sudo()

        old_planned = config.get_param('industry_fsm.service_planned_stage', 'False') == 'True'
        old_resolved = config.get_param('industry_fsm.service_resolved_stage', 'False') == 'True'

        super(ResConfigSettings, self).set_values()

        new_planned = config.get_param('industry_fsm.service_planned_stage', 'False') == 'True'
        new_resolved = config.get_param('industry_fsm.service_resolved_stage', 'False') == 'True'

        if old_planned != new_planned or old_resolved != new_resolved:
            users = self.env['res.users'].search([('device_token', '!=', False)])
            user_ids = users.ids

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'res.config.settings',
                        'action': 'settings_update',
                        'silent': "true"
                    }
                )


