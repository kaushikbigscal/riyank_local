from odoo import models, api, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    service_dashboard_planned_card = fields.Boolean(string='Show Planned Card',
                                            help='when Enabled Then ShowDashboard Planned Card.')

    service_dashboard_resolved_card = fields.Boolean(string='Show Resolved Card',
                                                    help='when Enabled Then ShowDashboard Resolved Card.')





class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    service_planned_stage = fields.Boolean(string="Enabled planned Stage",
                                           config_parameter="service_call_dashboard_odoo.service_planned_stage")
    service_resolved_stage = fields.Boolean(string="Enabled Resolved Stage",
                                            config_parameter="service_call_dashboard_odoo.service_resolved_stage")

