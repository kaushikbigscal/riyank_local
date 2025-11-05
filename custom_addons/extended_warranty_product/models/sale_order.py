# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
import logging
from odoo.tools.misc import formatLang
import json
import re

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = ['sale.order']

    extended_warranty_amount = fields.Float(string="Extended Warranty Amount", default=0.0)
    extended_warranty_start_date = fields.Date(string="Extended Warranty Start Date")
    extended_warranty_end_date = fields.Date(string="Extended Warranty End Date")

    # Computed field for extended warranty total from lines
    amount_extended_warranty = fields.Monetary(
        string="Extended Warranty",
        compute='_compute_amount_extended_warranty',
        store=True
    )

    # @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total',
    #              'amount_extended_warranty')
    # def _compute_amounts(self):
    #     """Override to include extended warranty in total amount with individual product taxes"""
    #     # Call super to calculate standard amounts
    #     super()._compute_amounts()
    #
    #     for order in self:
    #         if order.amount_extended_warranty <= 0:
    #             continue
    #
    #         total_warranty_tax = 0.0
    #
    #         # Process each warranty line individually to get its corresponding tax
    #         warranty_lines = order.order_line.filtered(lambda l: l.is_extended_warranty)
    #
    #         for warranty_line in warranty_lines:
    #             # Use the stored reference to original product line
    #             matching_product_line = warranty_line.warranty_product_line_id
    #
    #             # Calculate tax for this specific warranty amount
    #             if matching_product_line and matching_product_line.tax_id:
    #                 tax_results = matching_product_line.tax_id.compute_all(
    #                     warranty_line.extended_warranty_amount,
    #                     order.currency_id,
    #                     1.0,
    #                     product=matching_product_line.product_id,
    #                     partner=order.partner_shipping_id
    #                 )
    #                 warranty_tax = sum(t.get('amount', 0.0) for t in tax_results.get('taxes', []))
    #                 total_warranty_tax += warranty_tax
    #
    #         # Add warranty and its tax to totals
    #         order.amount_tax += total_warranty_tax
    #         order.amount_total += order.amount_extended_warranty + total_warranty_tax

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

    # @api.depends('order_line.tax_id', 'order_line.price_unit', 'order_line.price_subtotal',
    #              'order_line.price_total', 'order_line.price_tax', 'amount_extended_warranty',
    #              'amount_total', 'amount_tax')
    # def _compute_tax_totals(self):
    #     """Override to include warranty_amount in tax calculation with individual product taxes"""
    #     super()._compute_tax_totals()
    #
    #     for order in self:
    #         if not order.tax_totals:
    #             continue
    #
    #         warranty_amount = order.amount_extended_warranty
    #
    #         if warranty_amount <= 0:
    #             tax_totals = dict(order.tax_totals)
    #             tax_totals['warranty_amount'] = 0
    #             order.tax_totals = tax_totals
    #             continue
    #
    #         # Make a copy
    #         tax_totals = dict(order.tax_totals)
    #
    #         # Process each warranty line individually
    #         warranty_lines = order.order_line.filtered(lambda l: l.is_extended_warranty)
    #         total_warranty_tax = 0.0
    #
    #         for warranty_line in warranty_lines:
    #             matching_product_line = warranty_line.warranty_product_line_id
    #
    #             if not matching_product_line or not matching_product_line.tax_id:
    #                 continue
    #
    #             # Calculate tax on this warranty amount
    #             tax_results = matching_product_line.tax_id.compute_all(
    #                 warranty_line.extended_warranty_amount,
    #                 order.currency_id,
    #                 1.0,
    #                 product=matching_product_line.product_id,
    #                 partner=order.partner_shipping_id
    #             )
    #
    #             warranty_tax_amount = sum(t.get('amount', 0.0) for t in tax_results.get('taxes', []))
    #             total_warranty_tax += warranty_tax_amount
    #
    #             # Update tax groups for this warranty's taxes
    #             for tax_detail in tax_results.get('taxes', []):
    #                 tax_id = tax_detail.get('id')
    #
    #                 if tax_id:
    #                     # Search through all subtotals and groups to find matching tax
    #                     for subtotal_name, groups in tax_totals.get('groups_by_subtotal', {}).items():
    #                         for group in groups:
    #                             group_name = group.get('tax_group_name', '')
    #                             tax_name = tax_detail.get('name', '')
    #
    #                             # Check if the tax names match
    #                             if tax_name and (tax_name in group_name or group_name in tax_name):
    #                                 old_amount = group.get('tax_group_amount', 0)
    #                                 group['tax_group_amount'] = old_amount + tax_detail.get('amount', 0)
    #                                 group['tax_group_base_amount'] = group.get('tax_group_base_amount',
    #                                                                            0) + warranty_line.extended_warranty_amount
    #
    #                                 group['formatted_tax_group_amount'] = formatLang(
    #                                     self.env, group['tax_group_amount'], currency_obj=order.currency_id
    #                                 )
    #                                 group['formatted_tax_group_base_amount'] = formatLang(
    #                                     self.env, group['tax_group_base_amount'], currency_obj=order.currency_id
    #                                 )
    #                                 break
    #
    #         # Store warranty amount
    #         tax_totals['warranty_amount'] = warranty_amount
    #
    #         # Update final total
    #         tax_totals['amount_total'] = tax_totals.get('amount_total', 0) + warranty_amount + total_warranty_tax
    #         tax_totals['formatted_amount_total'] = formatLang(
    #             self.env, tax_totals['amount_total'], currency_obj=order.currency_id
    #         )
    #
    #         order.tax_totals = tax_totals

    def action_open_warranty_wizard(self):
        """Open the extended warranty wizard - This is the button action"""
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

    # EXTENDED WARRANTY FIELDS
    is_extended_warranty = fields.Boolean(string="Is Extended Warranty", default=False)
    extended_warranty_amount = fields.Float(string="Extended Warranty Amount", default=0.0)
    extended_warranty_years = fields.Integer(string="Extended Warranty Years", default=0)




class ExtendedWarrantyWizard(models.TransientModel):
    _name = "extended.warranty.wizard"
    _description = "Extended Warranty Wizard"

    order_id = fields.Many2one("sale.order", string="Sale Order", required=True)
    line_ids = fields.One2many("extended.warranty.wizard.line", "wizard_id", string="Warranty Lines")

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        order_id = self.env.context.get("default_order_id")
        if order_id:
            order = self.env["sale.order"].browse(order_id)
            lines = []
            for line in order.order_line.filtered(lambda l: l.unit_status == "warranty"):
                _logger.info(f"Adding product to wizard: {line.product_id.name}, ID: {line.product_id.id}")

                # check if extended warranty previously added for same product
                existing_warranty = order.order_line.filtered(
                    lambda w: w.is_extended_warranty and w.name and
                              line.product_id.name and
                              line.product_id.name in (w.name or "")
                )
                prev_months = 0
                prev_rate = 0.0
                prev_end_date = False

                if existing_warranty:
                    # extract months if present in name text
                    match = re.search(r'(\d+)\s*Month', existing_warranty[-1].name or '')
                    if match:
                        prev_months = int(match.group(1))

                    # Extract rate from extended_warranty_amount field or name
                    if hasattr(existing_warranty[-1], 'extended_warranty_amount'):
                        prev_rate = existing_warranty[-1].extended_warranty_amount
                    else:
                        # Try to extract from name if field doesn't exist
                        rate_match = re.search(r'Price:\s*([\d.]+)', existing_warranty[-1].name or '')
                        if rate_match:
                            prev_rate = float(rate_match.group(1))

                    # Extract end date from name or compute it
                    date_match = re.search(r'End Date:\s*(\d{4}-\d{2}-\d{2})', existing_warranty[-1].name or '')
                    if date_match:
                        prev_end_date = datetime.strptime(date_match.group(1), '%Y-%m-%d').date()
                    elif line.line_warranty_end_date and prev_months:
                        prev_end_date = line.line_warranty_end_date + relativedelta(months=prev_months, days=1)

                # Calculate extended start and end dates
                extended_start = (line.line_warranty_end_date + relativedelta(
                    days=1)) if line.line_warranty_end_date else False
                extended_end = False
                if extended_start and prev_months:
                    extended_end = extended_start + relativedelta(months=prev_months) - relativedelta(days=1)
                elif prev_end_date:
                    extended_end = prev_end_date

                lines.append((0, 0, {
                    "product_id": line.product_id.id,
                    "warranty_start_date": line.order_id.warranty_start_date,
                    "warranty_end_date": line.line_warranty_end_date,
                    "extended_start_date": extended_start,
                    "extended_months": prev_months,
                    "extended_end_date": extended_end,
                    "rate": prev_rate,
                }))
            res["line_ids"] = lines
        return res

    def action_confirm_warranty(self):
        """Confirm warranty for each product line with user-entered values."""
        self.ensure_one()
        order = self.order_id
        total_ext_amount = 0

        # Store lines to create with their proper sequence
        lines_to_create = []

        for wiz_line in self.line_ids:
            if not wiz_line.extended_months or not wiz_line.rate:
                continue
            if not wiz_line.warranty_product_id:
                raise ValidationError(
                    _("Please select an Extended Warranty product for %s.") % wiz_line.product_id.display_name)

            # Find base product line
            base_line = order.order_line.filtered(
                lambda l: l.product_id == wiz_line.product_id and not l.is_extended_warranty
            )[:1]

            # If warranty already exists for this base product, remove it first
            existing_warranty = order.order_line.filtered(
                lambda w: w.is_extended_warranty and
                          w.warranty_product_line_id == base_line.id
            )
            if existing_warranty:
                existing_warranty.unlink()

            # Compute sequence so warranty line comes right after base line
            if base_line:
                warranty_sequence = base_line.sequence + 0.1
            else:
                warranty_sequence = (order.order_line and max(order.order_line.mapped('sequence')) or 0) + 10

            # Tax from warranty product
            # taxes = wiz_line.warranty_product_id.taxes_id.filtered(
            #     lambda t: t.company_id == order.company_id
            # )

            taxes = base_line.tax_id if base_line else self.env['account.tax']

            product_name = wiz_line.product_id.display_name if wiz_line.product_id else "Product"

            # Prepare line values
            line_vals = {
                "order_id": order.id,
                "product_id": wiz_line.warranty_product_id.id,
                "name": f"Extended Warranty for {product_name} ({wiz_line.extended_months} Months) "
                        f"from {wiz_line.extended_start_date.strftime('%d-%m-%Y') if wiz_line.extended_start_date else ''} "
                        f"to {wiz_line.extended_end_date.strftime('%d-%m-%Y') if wiz_line.extended_end_date else ''}",
                "product_uom_qty": 1,
                "price_unit": wiz_line.rate,
                "tax_id": [(6, 0, taxes.ids)],
                "is_extended_warranty": True,
                "extended_warranty_amount": wiz_line.rate,
                "extended_warranty_years": 0,
                "warranty_product_line_id": base_line.id if base_line else False,
                "sequence": warranty_sequence,
            }

            lines_to_create.append(line_vals)
            total_ext_amount += wiz_line.rate

        # Create all warranty lines
        for line_vals in lines_to_create:
            self.env["sale.order.line"].create(line_vals)

        # Re-sequence cleanly to ensure proper ordering
        # Group lines by base product to maintain warranty lines right after their products
        seq = 10
        for line in order.order_line.sorted(key=lambda l: (l.sequence, l.is_extended_warranty)):
            line.sequence = seq
            seq += 10

        # Update warranty summary info on the order
        valid_starts = [l.extended_start_date for l in self.line_ids if l.extended_start_date]
        valid_ends = [l.extended_end_date for l in self.line_ids if l.extended_end_date]
        vals = {'extended_warranty_amount': total_ext_amount}
        if valid_starts:
            vals['extended_warranty_start_date'] = min(valid_starts)
        if valid_ends:
            vals['extended_warranty_end_date'] = max(valid_ends)
        order.write(vals)

        # Recompute totals
        order._compute_amount_extended_warranty()
        # order._amount_all() if hasattr(order, '_amount_all') else order._compute_amounts()
        # order._compute_tax_totals()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': order.id,
            'view_mode': 'form',
            'target': 'current',
        }

class ExtendedWarrantyWizardLine(models.TransientModel):
    _name = "extended.warranty.wizard.line"
    _description = "Extended Warranty Wizard Line"

    wizard_id = fields.Many2one("extended.warranty.wizard", string="Wizard", ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Base Product")
    warranty_product_id = fields.Many2one(
        "product.product",
        string="Extended Warranty Product",
        domain="[('product_tmpl_id.is_extended_warranty', '=', True)]",
        required=True,
        help="Select the product created from your extended warranty product template",
        store=True
    )
    warranty_start_date = fields.Date(string="Warranty Start Date", readonly=True)
    warranty_end_date = fields.Date(string="Warranty End Date", readonly=True)
    extended_start_date = fields.Date(string="Extended Warranty Start Date", store=True)
    extended_months = fields.Integer(string="Extended Warranty (Months)")
    extended_end_date = fields.Date(string="Extended Warranty End Date", store=True)
    rate = fields.Float(string="Rate")

    @api.onchange("extended_start_date", "extended_months")
    def _onchange_extended_end_date(self):
        for line in self:
            if line.extended_start_date and line.extended_months:
                line.extended_end_date = (
                        line.extended_start_date
                        + relativedelta(months=line.extended_months)
                        - relativedelta(days=1)
                )
            else:
                line.extended_end_date = False


