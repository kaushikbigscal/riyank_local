# import logging
# from odoo import fields, models
#
# _logger = logging.getLogger(__name__)
#
# class PaymentTransaction(models.Model):
#     _inherit = 'payment.transaction'
#
#     def write(self, vals):
#         _logger.info("write() called on payment.transaction with vals: %s", vals)
#
#         old_states = {tx.id: tx.state for tx in self}
#         res = super().write(vals)
#
#         for tx in self:
#             old = old_states.get(tx.id)
#             new = tx.state
#             if old not in ('done', 'authorized') and new in ('done', 'authorized'):
#                 _logger.info(f"Transaction DONE detected → processing sale orders. tx={tx.reference}")
#
#                 # Journal
#                 journal = tx.provider_id.journal_id or self.env['account.journal'].search([
#                     ('company_id', '=', tx.company_id.id),
#                     ('type', 'in', ['bank', 'cash']),
#                 ], limit=1)
#
#                 for order in tx.sale_order_ids:
#                     try:
#                         if order.state in ('draft', 'sent'):
#                             order.with_context(send_email=False).action_confirm()
#
#                         # 1) Create full invoice (full sale order amount)
#                         invoice = order._create_invoices()
#                         invoice.action_post()
#
#                         # 2) Register payment (partial)
#                         pay_reg = self.env['account.payment.register'].with_context(
#                             active_model='account.move',
#                             active_ids=invoice.ids,
#                         ).create({
#                             'payment_date': fields.Date.context_today(self),
#                             'journal_id': journal.id if journal else False,
#                             'amount': tx.amount,  # partial payment
#                         })
#                         payment_moves = pay_reg._create_payments()
#
#                         # 3) Update sale order
#                         order.invoice_ids = [(4, inv.id) for inv in invoice]
#                         order.write({'state': 'sale'})
#                         if sum(invoice.mapped('amount_residual')) == 0:
#                             order.write({'invoice_status': 'invoiced'})
#                         else:
#                             order.write({'invoice_status': 'to invoice'})
#
#                         _logger.info(f"SO {order.name} updated with invoice {invoice.ids}, partial payment {tx.amount}")
#
#                     except Exception as e:
#                         _logger.exception("Failed processing SO %s", order.name)
#
#         return res

#
#
# # -*- coding: utf-8 -*-
# import logging
# from odoo import api, fields, models
# from odoo.exceptions import UserError
#
# _logger = logging.getLogger(__name__)
#
# class PaymentTransaction(models.Model):
#     _inherit = 'payment.transaction'
#
#     def write(self, vals):
#         print(">>> WRITE called on payment.transaction ids=%s vals=%s", self.ids, vals)
#         old_states = {tx.id: tx.state for tx in self}
#         res = super().write(vals)
#
#         for tx in self:
#             old_state = old_states.get(tx.id)
#             new_state = tx.state
#             print(">>> TX %s state changed %s → %s", tx.id, old_state, new_state)
#
#             # Trigger invoice creation when payment is authorized or done
#             if old_state not in ('done', 'authorized') and new_state in ('done', 'authorized'):
#                 print(">>> Payment finalized for tx=%s (state=%s)", tx.id, new_state)
#                 self._create_invoice_from_payment(tx)
#         return res
#
#     def _create_invoice_from_payment(self, tx):
#         print(">>> _create_invoice_from_payment called for tx=%s", tx.id)
#
#         # Use journal from payment provider or fallback
#         journal = tx.provider_id.journal_id or self.env['account.journal'].search([
#             ('company_id', '=', tx.company_id.id),
#             ('type', 'in', ['bank', 'cash']),
#         ], limit=1)
#         print(">>> Using journal id=%s name=%s", journal.id if journal else None, journal.name if journal else None)
#
#         # Loop through related sale orders
#         for order in tx.sale_order_ids:
#             try:
#                 print(">>> Handling SO %s (state=%s)", order.name, order.state)
#
#                 # Confirm quotation if still draft or sent
#                 if order.state in ('draft', 'sent'):
#                     print(">>> Confirming quotation for SO %s", order.name)
#                     order.with_context(send_email=False).action_confirm()
#                     print(">>> SO confirmed: %s", order.name)
#
#                 # Create invoice normally (full amount)
#                 print(">>> Creating invoice for SO %s", order.name)
#                 invoices = order._create_invoices()
#                 if not invoices:
#                     print(">>> No invoice created for SO %s (nothing to invoice)", order.name)
#                     continue
#
#                 # Post invoices
#                 for inv in invoices:
#                     if not inv.invoice_line_ids:
#                         print(">>> Invoice %s has no lines, skipping", inv.name)
#                         continue
#
#                     print(">>> Posting invoice %s (total=%s)", inv.name, inv.amount_total)
#                     inv.action_post()
#                     print(">>> Invoice %s posted", inv.name)
#
#                     # Register payment **partial amount**
#                     if tx.amount > 0 and inv.amount_residual > 0:
#                         payment_amount = min(tx.amount, inv.amount_residual)
#                         print(">>> Registering payment %s on invoice %s (residual=%s)", payment_amount, inv.name, inv.amount_residual)
#                         pay_reg = self.env['account.payment.register'].with_context(
#                             active_model='account.move',
#                             active_ids=[inv.id],
#                         ).create({
#                             'payment_date': fields.Date.context_today(self),
#                             'journal_id': journal.id if journal else False,
#                             'amount': payment_amount,
#                         })
#                         payment_moves = pay_reg._create_payments()
#                         print(">>> Payment registered for invoice %s: %s", inv.name, payment_moves.ids)
#
#                     inv._compute_amount()
#                     print(">>> Invoice %s residual after payment: %s", inv.name, inv.amount_residual)
#
#             except Exception as e:
#                 _logger.exception(">>> Failed processing SO %s", order.name)

# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def write(self, vals):
        print(">>> WRITE called on payment.transaction ids=%s vals=%s" % (self.ids, vals))
        old_states = {tx.id: tx.state for tx in self}
        res = super().write(vals)

        for tx in self:
            old_state = old_states.get(tx.id)
            new_state = tx.state
            print(">>> TX %s state changed %s → %s" % (tx.id, old_state, new_state))

            # Trigger invoice creation when payment is authorized or done
            if old_state not in ('done', 'authorized') and new_state in ('done', 'authorized'):
                print(">>> Payment finalized for tx=%s (state=%s)" % (tx.id, new_state))
                self._create_invoice_from_payment(tx)
        return res

    def _create_invoice_from_payment(self, tx):
        print(">>> _create_invoice_from_payment called for tx=%s" % tx.id)

        # Use journal from payment provider or fallback
        journal = tx.provider_id.journal_id or self.env['account.journal'].search([
            ('company_id', '=', tx.company_id.id),
            ('type', 'in', ['bank', 'cash']),
        ], limit=1)
        print(">>> Using journal id=%s name=%s" % (journal.id if journal else None, journal.name if journal else None))

        # Loop through related sale orders
        for order in tx.sale_order_ids:
            try:
                print(">>> Handling SO %s (state=%s)" % (order.name, order.state))

                # Confirm quotation if still draft or sent
                if order.state in ('draft', 'sent'):
                    print(">>> Confirming quotation for SO %s" % order.name)
                    order.with_context(send_email=False).action_confirm()
                    print(">>> SO confirmed: %s" % order.name)

                # Create invoice normally (full amount)
                print(">>> Creating invoice for SO %s" % order.name)
                invoices = order._create_invoices()
                if not invoices:
                    print(">>> No invoice created for SO %s (nothing to invoice)" % order.name)
                    continue

                # Post invoices
                for inv in invoices:
                    if not inv.invoice_line_ids:
                        print(">>> Invoice %s has no lines, skipping" % inv.name)
                        continue

                    print(">>> Posting invoice %s (total=%s)" % (inv.name, inv.amount_total))
                    inv.action_post()
                    print(">>> Invoice %s posted" % inv.name)

                # Instead of manually creating payments, just reconcile transaction
                print(">>> Reconciling transaction %s with invoices %s" % (tx.id, invoices.ids))
                tx._reconcile_after_done()

                # Debug residual amounts
                for inv in invoices:
                    inv._compute_amount()
                    print(">>> Invoice %s residual after reconcile: %s" % (inv.name, inv.amount_residual))

            except Exception as e:
                _logger.exception(">>> Failed processing SO %s" % order.name)
