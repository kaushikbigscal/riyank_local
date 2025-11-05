from odoo import api, models, _, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def action_open_delete_wizard(self):
        self.ensure_one()
        return {
            'name': _('Employee Termination'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.departure.wizard',
            'views': [[False, 'form']],
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'toggle_active': True,
            }
        }