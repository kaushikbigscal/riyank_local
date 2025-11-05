from odoo import models, fields
from random import randint


class ComplaintType(models.Model):
    _name = 'complaint.type'
    _description = 'Complaint Type'
    _order = 'name'

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string='Name', required=True)
    color = fields.Integer(string='Color', default=_get_default_color)
    reason_code_ids = fields.One2many('reason.code', 'complaint_type_id', string='Reason Codes')

    show_in_portal = fields.Boolean(string="Show in Customer Portal")
    show_portal_field = fields.Boolean(compute='_compute_show_portal_field')

    def _compute_show_portal_field(self):
        module_installed = self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'customer_app'),
            ('state', '=', 'installed')
        ]) > 0
        for rec in self:
            rec.show_portal_field = module_installed

    attachment_on_out = fields.Boolean(string="Attachment Required on Check-out", default=True)
    report_id = fields.Many2one(
        'xml.upload',
        string='Report',
        domain="[('report_action', '=', 'data_recycle.action_xml_upload_custom_report_format_for_all_service_call')]"
    )
    resolved_required_fields = fields.Many2many(
        'ir.model.fields',
        string="Required Fields for Resolved Stage",
        domain=[('model', '=', 'project.task')],
        help="Select the fields that must be filled before moving to the 'Resolved' stage."
    )
    signed_required = fields.Boolean(string="signed required", default=True)


class ReasonCode(models.Model):
    _name = 'reason.code'
    _description = 'Reason Code'

    name = fields.Char(string='Reason Code', required=True)
    complaint_type_id = fields.Many2one('complaint.type', string='Complaint Type', ondelete='cascade')
