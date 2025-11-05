# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import api, models, fields, _
from odoo.tools import float_is_zero, formatLang
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = ['sale.order']

    task_id = fields.Many2one('project.task', string="Task", help="Task from which this quotation have been created")

    @api.model_create_multi
    def create(self, vals):
        orders = super().create(vals)
        for sale_order in orders:
            if sale_order.task_id:
                message = _("Extra Quotation Created: %s", sale_order._get_html_link())
                sale_order.task_id.message_post(body=message)
        return orders

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        if self.env.context.get('fsm_no_message_post'):
            return False
        return super().message_post(**kwargs)

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        self.action_auto_call_creation()
        for sale_order in self:
            if sale_order.task_id:
                message = _("This Sales Order has been created from Task: %s", sale_order.task_id._get_html_link())
                sale_order.message_post(body=message)

        return res

    def _get_product_catalog_record_lines(self, product_ids):
        """
            Accessing the catalog from the smart button of a "field service" should compute
            the content of the catalog related to that field service rather than the content
            of the catalog related to the sale order containing that "field service".
        """
        task_id = self.env.context.get('fsm_task_id')
        if task_id:
            grouped_lines = defaultdict(lambda: self.env['sale.order.line'])
            for line in self.order_line:
                if line.task_id.id == task_id and line.product_id.id in product_ids:
                    grouped_lines[line.product_id] |= line
            return grouped_lines
        return super()._get_product_catalog_record_lines(product_ids)

    # warranty dates custom ---------------------------
    order_parts_ids = fields.One2many('sale.order.parts', 'sale_order_id', string='Parts List')

    warranty_start_date = fields.Date(
        string='Warranty Start Date',
        default=fields.Date.context_today,
        required=True
    )

    warranty_end_date = fields.Date(
        string='Warranty End Date',
        compute='_compute_warranty_end_date',
        store=True
    )

    @api.depends('warranty_start_date', 'order_line.warranty_period')
    def _compute_warranty_end_date(self):
        for order in self:
            max_warranty_months = max(order.order_line.mapped('warranty_period') or [0])
            if order.warranty_start_date and max_warranty_months:
                order.warranty_end_date = order.warranty_start_date + relativedelta(months=max_warranty_months)
            else:
                order.warranty_end_date = False

    def _prepare_invoice(self):
        """Inherit to add warranty information when creating invoice"""
        invoice_vals = super()._prepare_invoice()
        invoice_vals.update({
            'warranty_start_date': self.warranty_start_date,
        })
        return invoice_vals

    def action_auto_call_creation(self):
        for order in self:
            print(f"Order state: {order.state}")
            if order.state == 'sale':
                for line in order.order_line:
                    if line.number_of_month and line.number_of_call:
                        if line.number_of_month > 0:
                            next_task_date = order.warranty_start_date + relativedelta(
                                months=line.number_of_month)
                        else:
                            next_task_date = False
                        line.next_call_date = next_task_date
                        line.call_counter = line.number_of_call
                        print(f"Setting next task date to {next_task_date} for line {line.id}")

    # warranty dates custom ---------------------------

    extended_warranty_amount = fields.Float(string="Extended Warranty Amount", default=0.0)

    extended_warranty_start_date = fields.Date(string="Extended Warranty Start Date")
    extended_warranty_end_date = fields.Date(string="Extended Warranty End Date")

    # Computed field for extended warranty total from lines
    amount_extended_warranty = fields.Monetary(
        string="Extended Warranty",
        compute='_compute_amount_extended_warranty',
        store=True
    )

    @api.depends('order_line.is_extended_warranty', 'order_line.extended_warranty_amount')
    def _compute_amount_extended_warranty(self):
        """Calculate total extended warranty from all warranty lines"""
        for order in self:
            warranty_amount = sum(
                line.extended_warranty_amount
                for line in order.order_line
                if line.is_extended_warranty
            )
            order.amount_extended_warranty = warranty_amount

    @api.depends('order_line.tax_id', 'order_line.price_unit', 'order_line.price_subtotal',
                 'order_line.price_total', 'order_line.price_tax', 'amount_extended_warranty')
    def _compute_tax_totals(self):
        """Override to include warranty_amount in tax calculation base"""
        super()._compute_tax_totals()

        for order in self:
            if not order.tax_totals:
                continue

            warranty_amount = order.amount_extended_warranty

            if warranty_amount <= 0:
                tax_totals = dict(order.tax_totals)
                tax_totals['warranty_amount'] = 0
                order.tax_totals = tax_totals
                continue

            # Make a copy
            tax_totals = dict(order.tax_totals)

            # Get tax configuration from first taxable line
            taxable_lines = order.order_line.filtered(
                lambda l: l.tax_id and not l.is_extended_warranty and l.price_unit > 0
            )

            if not taxable_lines:
                tax_totals['warranty_amount'] = warranty_amount
                tax_totals['amount_total'] = tax_totals.get('amount_total', 0) + warranty_amount
                tax_totals['formatted_amount_total'] = formatLang(
                    self.env, tax_totals['amount_total'], currency_obj=order.currency_id
                )
                order.tax_totals = tax_totals
                continue

            # Calculate tax on warranty
            first_line = taxable_lines[0]

            tax_results = first_line.tax_id.compute_all(
                warranty_amount,
                order.currency_id,
                1.0,
                product=first_line.product_id,
                partner=order.partner_shipping_id
            )

            warranty_tax_amount = sum(t.get('amount', 0.0) for t in tax_results.get('taxes', []))

            # Update tax groups by matching tax IDs instead of tax_group_id
            for tax_detail in tax_results.get('taxes', []):
                tax_id = tax_detail.get('id')

                if tax_id:
                    # Search through all subtotals and groups to find matching tax
                    for subtotal_name, groups in tax_totals.get('groups_by_subtotal', {}).items():
                        for group in groups:
                            # Match by tax_group_id OR by checking if this tax belongs to this group
                            # Since tax_group might be None, we need to match by the tax amounts/names
                            group_name = group.get('tax_group_name', '')
                            tax_name = tax_detail.get('name', '')

                            # Check if the tax names match (like "5% IGST S")
                            if tax_name and (tax_name in group_name or group_name in tax_name):
                                old_amount = group.get('tax_group_amount', 0)
                                group['tax_group_amount'] = old_amount + tax_detail.get('amount', 0)
                                group['tax_group_base_amount'] = group.get('tax_group_base_amount', 0) + warranty_amount

                                group['formatted_tax_group_amount'] = formatLang(
                                    self.env, group['tax_group_amount'], currency_obj=order.currency_id
                                )
                                group['formatted_tax_group_base_amount'] = formatLang(
                                    self.env, group['tax_group_base_amount'], currency_obj=order.currency_id
                                )
                                break

            # Store warranty amount
            tax_totals['warranty_amount'] = warranty_amount

            # Update final total
            tax_totals['amount_total'] = tax_totals.get('amount_total', 0) + warranty_amount + warranty_tax_amount
            tax_totals['formatted_amount_total'] = formatLang(
                self.env, tax_totals['amount_total'], currency_obj=order.currency_id
            )

            order.tax_totals = tax_totals

    def action_open_warranty_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Extended Warranty",
            "res_model": "extended.warranty.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }

class SaleOrderLine(models.Model):
    _inherit = ['sale.order.line']

    delivered_price_subtotal = fields.Monetary(compute='_compute_delivered_amount', string='Delivered Subtotal')
    delivered_price_tax = fields.Float(compute='_compute_delivered_amount', string='Delivered Total Tax')
    delivered_price_total = fields.Monetary(compute='_compute_delivered_amount', string='Delivered Total')
    is_extended_warranty = fields.Boolean(string="Is Extended Warranty", default=False)
    extended_warranty_amount = fields.Float(string="Extended Warranty Amount", default=0.0)
    extended_warranty_years = fields.Integer(string="Extended Warranty Years", default=0)


    warranty_product_line_id = fields.Many2one(
        'sale.order.line',
        string="Original Product Line",
        help="Links extended warranty to its original product line for tax calculation"
    )

    @api.depends('qty_delivered', 'discount', 'price_unit', 'tax_id')
    def _compute_delivered_amount(self):
        """
        Compute the amounts of the SO line for delivered quantity.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.qty_delivered,
                                            product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.delivered_price_tax = sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
            line.delivered_price_total = taxes['total_included']
            line.delivered_price_subtotal = taxes['total_excluded']

    def _timesheet_create_task_prepare_values(self, project):
        res = super(SaleOrderLine, self)._timesheet_create_task_prepare_values(project)
        if project.is_fsm:
            res.update({'partner_id': self.order_id.partner_shipping_id.id})
        return res

    def _timesheet_create_project_prepare_values(self):
        """Generate project values"""
        values = super(SaleOrderLine, self)._timesheet_create_project_prepare_values()
        if self.product_id.project_template_id.is_fsm:
            values.pop('sale_line_id', False)
        return values

    def _compute_invoice_status(self):
        sol_from_task_without_amount = self.filtered(
            lambda sol: sol.task_id.is_fsm and float_is_zero(sol.price_unit, precision_digits=sol.currency_id.rounding))
        sol_from_task_without_amount.invoice_status = 'no'
        super(SaleOrderLine, self - sol_from_task_without_amount)._compute_invoice_status()

    @api.depends('price_unit')
    def _compute_qty_to_invoice(self):
        sol_from_task_without_amount = self.filtered(
            lambda sol: sol.task_id.is_fsm and float_is_zero(sol.price_unit, precision_digits=sol.currency_id.rounding))
        sol_from_task_without_amount.qty_to_invoice = 0.0
        super(SaleOrderLine, self - sol_from_task_without_amount)._compute_qty_to_invoice()

    def action_add_from_catalog(self):
        if len(self.task_id) == 1 and self.task_id.allow_material:
            return self.task_id.action_fsm_view_material()
        return super().action_add_from_catalog()

    # custom code for warranty -----------------------------------------------------------------

    warranty_period = fields.Integer(
        string="Warranty Period",
        help="Warranty period in months for this product"
    )

    line_warranty_end_date = fields.Date(
        string='Warranty End Date',
        compute='_compute_line_warranty_end_date',
        store=True
    )

    @api.onchange('product_id')
    def _onchange_product_id_warranty(self):
        if self.product_id:
            # Access product template through product.product relation
            product_tmpl = self.product_id.product_tmpl_id
            if not self.warranty_period and product_tmpl:
                self.warranty_period = product_tmpl.minimum_warranty_period

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('product_id') and not vals.get('warranty_period'):
                product = self.env['product.product'].browse(vals['product_id'])
                if product and product.product_tmpl_id:
                    vals['warranty_period'] = product.product_tmpl_id.minimum_warranty_period
        return super().create(vals_list)

    @api.depends('order_id.warranty_start_date', 'warranty_period')
    def _compute_line_warranty_end_date(self):
        for line in self:
            if line.order_id.warranty_start_date and line.warranty_period:
                line.line_warranty_end_date = line.order_id.warranty_start_date + relativedelta(
                    months=line.warranty_period)
            else:
                line.line_warranty_end_date = False

    def _prepare_invoice_line(self, **optional_values):
        """Inherit to add warranty information when creating invoice lines"""
        res = super()._prepare_invoice_line(**optional_values)
        res.update({
            'warranty_period': self.warranty_period,
        })
        return res

        # custom code for warranty -----------------------------------------------------------------

    # Computed field to fetch the part list
    def _prepare_parts_data(self):
        self.ensure_one()
        parts_commands = []
        product_tmpl = self.product_id.product_tmpl_id

        if product_tmpl.part_ids:
            for part in product_tmpl.part_ids:
                parts_commands.append((0, 0, {
                    'sale_order_id': self.order_id.id,
                    'product_id': product_tmpl.id,
                    'part_data_id': part.id,
                    'quantity': int(self.product_uom_qty or 1)
                }))
        return parts_commands

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            # Only process if product has parts feature enabled in your DB
            if "part_ids" in line.product_id._fields:
                if line.product_id.part_ids:
                    parts_commands = line._prepare_parts_data()
                    if parts_commands:
                        line.order_id.write({'order_parts_ids': parts_commands})
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'product_id' in vals or 'product_uom_qty' in vals:
            for line in self:
                # Delete existing parts for this product
                existing_parts = self.env['sale.order.parts'].search([
                    ('sale_order_id', '=', line.order_id.id),
                    ('product_id', '=', line.product_id.product_tmpl_id.id)
                ])
                if existing_parts:
                    existing_parts.unlink()

                # Create new parts
                if line.product_id and line.product_id.part_ids:
                    parts_commands = line._prepare_parts_data()
                    if parts_commands:
                        line.order_id.write({'order_parts_ids': parts_commands})
        return res

    # custom code for unit status and service count----------------------

    unit_status = fields.Selection([
        ('warranty', 'Warranty'),
        ('amc', 'AMC'),
        ('chargeable', 'Chargeable'),
        ('free', 'Free'),
        ('project', 'Project')], string="Unit Status", store=True)

    number_of_call = fields.Integer(
        string="Number of Calls"
    )
    number_of_month = fields.Integer(string="Number of Months",
                                     help="Number of months after which a call should be created.")

    @api.onchange('product_id', 'unit_status')
    def _onchange_product_id_service_record(self):
        if self.product_id:
            product_tmpl = self.product_id.product_tmpl_id
            if product_tmpl:
                if self.unit_status in ['warranty', 'amc']:
                    # Keep the values from the product template
                    self.number_of_call = product_tmpl.number_of_call
                    self.number_of_month = product_tmpl.number_of_month
                else:
                    # Reset the fields to zero for other statuses
                    self.number_of_call = 0
                    self.number_of_month = 0

    # @api.onchange('product_id')
    # def _onchange_product_id_service_record(self):
    #     if self.product_id:
    #         # Access product template through product.product relation
    #         product_tmpl = self.product_id.product_tmpl_id
    #         if not self.number_of_call and product_tmpl:
    #             self.number_of_call = product_tmpl.number_of_call

    next_call_date = fields.Date(string="Next Date")
    call_counter = fields.Integer(string="Task Count")

    # @api.model
    # def _create_field_service_tasks(self):
    #     today = fields.Date.context_today(self)
    #     sale_order_lines = self.search([
    #         ('order_id.state', '=', 'sale'),
    #         ('call_counter', '>', 0),
    #         ('next_call_date', '=', today),
    #     ])
    #     print(sale_order_lines)
    #     for line in sale_order_lines:
    #         task_vals = {
    #             'name': f"Service call for {line.order_id.name} - {line.product_id.display_name}",
    #             'project_id': 33,
    #             'partner_id': line.order_id.partner_id.id
    #         }
    #         self.env['project.task'].create(task_vals)
    #         print("task done")
    #         line.call_counter = line.call_counter - 1
    #
    #         print(line.call_counter)
    #         if line.number_of_month:
    #             line.next_call_date = today + relativedelta(months=line.number_of_month)
    #             print(line.next_call_date)
    #
    #     return True
    @api.model
    def _create_field_service_tasks(self):
        today = fields.Date.context_today(self)

        # Search sale order lines that meet the condition
        sale_order_lines = self.search([
            ('order_id.state', '=', 'sale'),
            ('call_counter', '>', 0),
            ('next_call_date', '=', today),
        ])

        print(sale_order_lines)

        for line in sale_order_lines:
            # Dynamically find the project based on the current company and is_fsm=True
            project = self.env['project.project'].search([
                ('company_id', '=', self.env.company.id),
                ('is_fsm', '=', True)
            ], limit=1)  # Assuming only one project with is_fsm=True per company

            if not project:
                print("No FSM project found for the current company")
                continue  # Skip this iteration if no project is found

            task_vals = {
                'name': f"Service call for {line.order_id.name} - {line.product_id.display_name}",
                'project_id': project.id,
                'partner_id': line.order_id.partner_id.id
            }
            # Create a new task for each sale order line
            self.env['project.task'].create(task_vals)
            print("task done")

            # Decrease the call counter
            line.call_counter = line.call_counter - 1
            print(line.call_counter)

            # Update the next call date if applicable
            if line.number_of_month:
                line.next_call_date = today + relativedelta(months=line.number_of_month)
                print(line.next_call_date)

        return True


class SaleOrderParts(models.Model):
    _name = 'sale.order.parts'
    _description = 'Sale Order Parts'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.template', string='Main Product', required=True)
    part_data_id = fields.Many2one('product.part_data', string='Part', required=True)
    part_name = fields.Char(related='part_data_id.display_name.name', string='Part Name', store=True, readonly=True)
    quantity = fields.Integer(string='Quantity', default=1)
    minimum_warranty_period = fields.Integer(related='part_data_id.minimum_warranty_period', readonly=True)
    description = fields.Text(related='part_data_id.description')


# class ExtendedWarrantyWizard(models.TransientModel):
#     _name = "extended.warranty.wizard"
#     _description = "Extended Warranty Wizard"
#
#     order_id = fields.Many2one("sale.order", string="Sale Order", required=True)
#     line_ids = fields.One2many("extended.warranty.wizard.line", "wizard_id", string="Warranty Lines")
#
#     def default_get(self, fields_list):
#         res = super().default_get(fields_list)
#         order_id = self.env.context.get("default_order_id")
#         if order_id:
#             order = self.env["sale.order"].browse(order_id)
#             lines = []
#             for line in order.order_line.filtered(lambda l: l.unit_status == "warranty"):
#                 _logger.info(f"Adding product to wizard: {line.product_id.name}, ID: {line.product_id.id}")
#
#                 # check if extended warranty previously added for same product
#                 # FIX: Handle cases where w.name might be False/None
#                 existing_warranty = order.order_line.filtered(
#                     lambda w: w.is_extended_warranty and w.name and
#                               line.product_id.name and
#                               line.product_id.name in (w.name or "")
#                 )
#                 prev_months = 0
#                 prev_rate = 0.0
#                 prev_end_date = False
#
#                 if existing_warranty:
#                     # extract months if present in name text
#                     import re
#                     match = re.search(r'(\d+)\s*Month', existing_warranty[-1].name or '')
#                     if match:
#                         prev_months = int(match.group(1))
#
#                     # Extract rate from extended_warranty_amount field or name
#                     if hasattr(existing_warranty[-1], 'extended_warranty_amount'):
#                         prev_rate = existing_warranty[-1].extended_warranty_amount
#                     else:
#                         # Try to extract from name if field doesn't exist
#                         rate_match = re.search(r'Price:\s*([\d.]+)', existing_warranty[-1].name or '')
#                         if rate_match:
#                             prev_rate = float(rate_match.group(1))
#
#                     # Extract end date from name or compute it
#                     date_match = re.search(r'End Date:\s*(\d{4}-\d{2}-\d{2})', existing_warranty[-1].name or '')
#                     if date_match:
#                         from datetime import datetime
#                         prev_end_date = datetime.strptime(date_match.group(1), '%Y-%m-%d').date()
#                     elif line.line_warranty_end_date and prev_months:
#                         prev_end_date = line.line_warranty_end_date + relativedelta(months=prev_months, days=1)
#
#                 # Calculate extended start and end dates
#                 extended_start = (line.line_warranty_end_date + relativedelta(
#                     days=1)) if line.line_warranty_end_date else False
#                 extended_end = False
#                 if extended_start and prev_months:
#                     extended_end = extended_start + relativedelta(months=prev_months) - relativedelta(days=1)
#                 elif prev_end_date:
#                     extended_end = prev_end_date
#
#                 lines.append((0, 0, {
#                     "product_id": line.product_id.id,
#                     "warranty_end_date": line.line_warranty_end_date,
#                     "extended_start_date": extended_start,
#                     "extended_months": prev_months,
#                     "extended_end_date": extended_end,
#                     "rate": prev_rate,
#                 }))
#             res["line_ids"] = lines
#         return res
#
#     def action_confirm_warranty(self):
#         """Confirm warranty for each product line with user-entered values"""
#         self.ensure_one()
#         order = self.order_id
#         total_ext_amount = 0
#
#         for wiz_line in self.line_ids:
#             if not wiz_line.extended_months or not wiz_line.rate:
#                 continue
#
#             # Get the product name - use display_name directly
#             product_name = wiz_line.product_id.display_name or wiz_line.product_id.name or "Unknown Product"
#
#             duration_text = f"{wiz_line.extended_months} Month{'s' if wiz_line.extended_months > 1 else ''}"
#             start_date_str = f"{wiz_line.extended_start_date.strftime('%d-%m-%Y') if wiz_line.extended_start_date else 'N/A'}"
#             # Format end date
#             end_date_str = f"{wiz_line.extended_end_date.strftime('%d-%m-%Y') if wiz_line.extended_end_date else 'N/A'}"
#             # Find the original product line to insert after
#             base_line = order.order_line.filtered(lambda l: l.product_id == wiz_line.product_id)[:1]
#
#             # Remove existing warranty note for this product if exists
#             # FIX: Handle cases where w.name might be False/None
#             existing_warranty = order.order_line.filtered(
#                 lambda w: w.is_extended_warranty and w.name and
#                           wiz_line.product_id.name and
#                           wiz_line.product_id.name in (w.name or "")
#             )
#             if existing_warranty:
#                 existing_warranty.unlink()
#
#             # Create note with product name, duration, end date, and rate
#             note_vals = {
#                 "order_id": order.id,
#                 "display_type": "line_note",
#                 "name": f"{product_name} - Extended Warranty ({duration_text}) - Start Date: {start_date_str} - End Date: {end_date_str} - Price: {wiz_line.rate:.2f}",
#                 "price_unit": 0,
#                 "product_uom_qty": 0,
#                 "is_extended_warranty": True,
#                 "extended_warranty_amount": wiz_line.rate,
#                 "extended_warranty_years": 0,
#                 "sequence": (base_line.sequence + 1) if base_line else 9999,
#             }
#             self.env["sale.order.line"].create(note_vals)
#
#             total_ext_amount += wiz_line.rate
#
#         # Safe totals
#         valid_starts = [l.extended_start_date for l in self.line_ids if l.extended_start_date]
#         valid_ends = [l.extended_end_date for l in self.line_ids if l.extended_end_date]
#         vals = {'extended_warranty_amount': total_ext_amount}
#         if valid_starts:
#             vals['extended_warranty_start_date'] = min(valid_starts)
#         if valid_ends:
#             vals['extended_warranty_end_date'] = max(valid_ends)
#         order.write(vals)
#
#         order.invalidate_recordset(['amount_extended_warranty', 'tax_totals'])
#         order._compute_amount_extended_warranty()
#         order._compute_tax_totals()
#
#         return {
#             'type': 'ir.actions.act_window',
#             'res_model': 'sale.order',
#             'res_id': order.id,
#             'view_mode': 'form',
#             'target': 'current',
#         }
#
# class ExtendedWarrantyWizardLine(models.TransientModel):
#     _name = "extended.warranty.wizard.line"
#     _description = "Extended Warranty Wizard Line"
#
#     wizard_id = fields.Many2one("extended.warranty.wizard", string="Wizard", ondelete="cascade")
#     product_id = fields.Many2one("product.product", string="Product")
#     warranty_end_date = fields.Date(string="Warranty End Date", readonly=True)
#     extended_start_date = fields.Date(string="Extended Start Date",store=True)
#     extended_months = fields.Integer(string="Extended Warranty (Months)")
#     extended_end_date = fields.Date(string="Extended End Date", store=True)
#     rate = fields.Float(string="Rate")
#
#     @api.onchange("extended_start_date", "extended_months")
#     def _onchange_extended_end_date(self):
#         for line in self:
#             if line.extended_start_date and line.extended_months:
#                 line.extended_end_date = (
#                         line.extended_start_date
#                         + relativedelta(months=line.extended_months)
#                         - relativedelta(days=1)
#                 )
#             else:
#                 line.extended_end_date = False