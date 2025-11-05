from odoo import models


class IrHttpInherited(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        info["user_group"] = self.env.user.has_group('oe_restrict_debug_mode''.group_oe_restrict_debug_mode'),
        return info