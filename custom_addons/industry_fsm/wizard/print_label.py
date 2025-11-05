from odoo import models, fields, api
from odoo.exceptions import UserError

class QuantityWizard(models.TransientModel):
    _name = "print.label.wizard"
    _description = "Wizard to print label"

    quantity = fields.Integer(string="Quantity", default=1, required=True)
    move_quantity = fields.Selection([
        ('move', 'Operation Quantities'),
        ('custom', 'Custom')], string="Quantity to print", required=True, default='move')
    mapping_id = fields.Many2one('customer.product.mapping', string="Customer Product Mapping")
    format = fields.Selection([('2x7','2 x 7 label'),
                               ('4x7','4 x 7 label'),('4x12','4 x 12 label'),('dymo','Dymo label')],string="Format", default="2x7")
    extra_html = fields.Char('Extra Content', default='')

    def action_confirm(self):
        """Generate PDF with quantity of labels based on selected format"""
        if not self.mapping_id:
            return

        # Determine which report to use based on the selected format
        if self.format == 'dymo':
            report_ref = 'industry_fsm.action_report_customer_product_dymo'
        elif self.format == '2x7':
            report_ref = 'industry_fsm.action_report_customer_asset_2x7'
        elif self.format == '4x7':
            report_ref = 'industry_fsm.action_report_customer_asset_4x7'
        elif self.format == '4x12':
            report_ref = 'industry_fsm.action_report_customer_asset_4x12'
        else:
            report_ref = 'industry_fsm.action_report_customer_product_dymo'

        report_action = self.env.ref(report_ref).with_context(
            quantity=self.quantity,
            wizard_extra_html=self.extra_html,  # Pass extra_html through context
            wizard_type='single'  # Identify wizard type
        ).report_action(self.mapping_id)

        report_action.update({'close_on_report_download': True})
        return report_action

# models/bulk_quantity_wizard.py


class BulkQuantityWizard(models.TransientModel):
    _name = "bulk.print.label.wizard"
    _description = "Wizard to bulk label printing"

    quantity = fields.Integer(string="Quantity", default=1, required=True)
    move_quantity = fields.Selection([
        ('move', 'Operation Quantities'),
        ('custom', 'Custom')], string="Quantity to print", required=True, default='move')
    format = fields.Selection([('2x7','2 x 7 label'),
                               ('4x7','4 x 7 label'),('4x12','4 x 12 label'),('dymo','Dymo label')],string="Format", default="2x7")

    mapping_ids = fields.Many2many(
        'customer.product.mapping',
        string="Customer Product Mappings",
        help="Records to print labels for"
    )
    extra_html = fields.Char('Extra Content', default='')


    @api.model
    def default_get(self, fields_list):
        res = super(BulkQuantityWizard, self).default_get(fields_list)
        # populate mapping_ids from active_ids if present
        active_ids = self.env.context.get('active_ids') or []
        if 'mapping_ids' in fields_list and active_ids:
            res['mapping_ids'] = [(6, 0, active_ids)]
        return res

    def action_confirm(self):
        """Generate PDF with labels for selected mapping_ids"""
        self.ensure_one()
        if not self.mapping_ids:
            raise UserError("No mappings selected to print.")

        # Determine which report to use based on the selected format
        if self.format == 'dymo':
            report_ref = 'industry_fsm.action_report_customer_product_dymo'
        elif self.format == '2x7':
            report_ref = 'industry_fsm.action_report_customer_asset_2x7'
        elif self.format == '4x7':
            report_ref = 'industry_fsm.action_report_customer_asset_4x7'
        elif self.format == '4x12':
            report_ref = 'industry_fsm.action_report_customer_asset_4x12'
        else:
            report_ref = 'industry_fsm.action_report_customer_product_dymo'

        report_action = self.env.ref(report_ref).with_context(
            quantity=self.quantity,
            wizard_extra_html=self.extra_html,  # Pass extra_html through context
            wizard_type='bulk'  # Identify wizard type
        ).report_action(self.mapping_ids)

        report_action.update({'close_on_report_download': True})
        return report_action