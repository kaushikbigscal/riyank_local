from odoo import models, fields, api, _

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    def write(self, vals):
        res = super(HrLeave, self).write(vals)

        # Check if state is being changed
        if 'state' in vals and vals['state'] == 'validate1':
            for leave in self:
                leave.message_notify(
                    body=_('Your %(leave_type)s planned on %(date)s has been approved first approval', leave_type=leave.holiday_status_id.display_name, date=leave.date_from),
                    partner_ids=[leave.employee_id.user_id.partner_id.id] if leave.employee_id.user_id else [],
                )
        return res