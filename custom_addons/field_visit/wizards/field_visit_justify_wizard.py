from odoo import api, fields, models, _
from odoo.exceptions import UserError
#
# class FieldVisitJustificationWizard(models.TransientModel):
#     _name = "field.visit.justification.wizard"
#     _description = "Add Justification"
#
#     message = fields.Text(string="Justification")
#
#     visit_id = fields.Many2one('field.visit', string="Visit")
#     attachment = fields.Many2many(
#         'ir.attachment',
#         string="Attachment",
#     )
#
#     def action_add_justification(self):
#         self.ensure_one()
#         visit = self.visit_id
#         user = self.env.user.name
#         date = fields.Datetime.now().strftime("%d/%m/%Y %H:%M:%S")
#
#         # New entry wrapped in <p>
#         new_entry = f"<p><b>{user} [{date}]</b>: {self.message}</p>"
#
#         # Normalize previous justification: wrap in <p> if missing
#         if visit.justification:
#             existing = visit.justification.strip()
#             if not existing.startswith("<p>"):
#                 existing = f"<p>{existing}</p>"
#             # Append new entry with a horizontal line for separation
#             visit.justification = f"{existing}{new_entry}"
#         else:
#             visit.justification = new_entry
#
#
#
# class FieldVisitJustificationWizard(models.TransientModel):
#     _name = "field.visit.justification.wizard"
#     _description = "Add Justification"
#
#     message = fields.Text(string="Justification")
#     visit_id = fields.Many2one('field.visit', string="Visit")
#     attachment = fields.Many2many('ir.attachment', string="Attachment")
#
#     def action_add_justification(self):
#         self.ensure_one()
#         self.env['field.visit.justification'].create({
#             'visit_id': self.visit_id.id,
#             'user_id': self.env.user.id,
#             'datetime': fields.Datetime.now(),
#             'message': self.message,
#             'attachment_ids': [(6, 0, self.attachment.ids)],
#         })

#
# class FieldVisitJustificationWizard(models.TransientModel):
#     _name = "field.visit.justification.wizard"
#     _description = "Add Justification"
#
#     message = fields.Text(string="Justification", required=True)
#     visit_id = fields.Many2one('field.visit', string="Visit", required=True)
#     attachment = fields.Many2many('ir.attachment', string="Attachment")
#     parent_id = fields.Many2one('field.visit.justification', string="Reply To")
#
#     def action_add_justification(self):
#         self.ensure_one()
#         visit = self.visit_id
#         sender = self.env.user
#         employee = visit.user_id.employee_ids
#         first_approver = employee.field_visit_first_approval if employee else False
#         second_approver = employee.field_visit_second_approval if employee else False
#
#         # Determine recipient type
#         if sender.id == visit.user_id.id:  # Salesperson sending
#             if self.parent_id:
#                 # Replying to an approver
#                 if self.parent_id.user_id.id == first_approver.id:
#                     recipient_type = 'first_approver'
#                 elif self.parent_id.user_id.id == second_approver.id:
#                     recipient_type = 'second_approver'
#                 else:
#                     recipient_type = 'salesperson'
#             else:
#                 recipient_type = 'first_approver'
#         elif first_approver and sender.id == first_approver.id:
#             recipient_type = 'salesperson'
#         elif second_approver and sender.id == second_approver.id:
#             recipient_type = 'salesperson'
#         else:
#             raise UserError("You cannot send justification for this visit.")
#
#         justification = self.env['field.visit.justification'].create({
#             'visit_id': visit.id,
#             'user_id': sender.id,
#             'datetime': fields.Datetime.now(),
#             'message': self.message,
#             'attachment_ids': [(6, 0, self.attachment.ids)],
#             'recipient_type': recipient_type,
#             'parent_id': self.parent_id.id if self.parent_id else False
#         })
#
#         # Send notification to the recipient
#         if recipient_type == 'first_approver':
#             recipient_user = first_approver
#         elif recipient_type == 'second_approver':
#             recipient_user = second_approver
#         else:
#             recipient_user = visit.user_id
#
#         if recipient_user:
#             recipient_user.partner_id.message_post(
#                 subject=f'New justification from {sender.name}',
#                 body=self.message,
#                 message_type='notification',
#                 subtype_xmlid='mail.mt_comment',
#                 partner_ids=[recipient_user.partner_id.id]
#             )
class FieldVisitJustificationWizard(models.TransientModel):
    _name = "field.visit.justification.wizard"
    _description = "Add Justification"

    message = fields.Text(string="Justification", required=True)
    visit_id = fields.Many2one('field.visit', string="Visit", required=True)
    attachment = fields.Many2many('ir.attachment', string="Attachment")
    parent_id = fields.Many2one('field.visit.justification', string="Reply To")

    def action_add_justification(self):
        self.ensure_one()
        visit = self.visit_id
        sender = self.env.user
        employee = visit.user_id.employee_ids
        first_approver = employee.field_visit_first_approval if employee else False
        second_approver = employee.field_visit_second_approval if employee else False

        recipient_user = False
        recipient_type = False

        if self.parent_id:
            # Replying to a justification
            parent_sender = self.parent_id.user_id
            recipient_user = parent_sender  # Always reply to the sender of parent
            recipient_type = self.parent_id.recipient_type
        else:
            # Top-level justification
            if sender == visit.user_id:
                # Salesperson sends: go to the last approver who sent any justification
                last_just = visit.justification_ids.sorted(lambda j: j.datetime, reverse=True)[:1]
                if last_just:
                    last_sender = last_just[0].user_id
                    if last_sender in (first_approver, second_approver):
                        recipient_user = last_sender
                        recipient_type = 'first_approver' if last_sender == first_approver else 'second_approver'
                    else:
                        recipient_user = first_approver or second_approver
                        recipient_type = 'first_approver' if first_approver else 'second_approver'
                else:
                    # No previous justification, default to first approver
                    recipient_user = first_approver
                    recipient_type = 'first_approver'
            elif sender in (first_approver, second_approver):
                # Approver sends: always goes to salesperson
                recipient_user = visit.user_id
                recipient_type = 'salesperson'
            else:
                raise UserError("You cannot send justification for this visit.")

        # Debug print
        print("=== Justification Debug ===")
        print(f"Sender: {sender.name} (ID: {sender.id})")
        print(f"Recipient: {recipient_user.name if recipient_user else 'None'}")
        print(f"Recipient Type: {recipient_type}")
        print(f"Parent Justification: {self.parent_id.id if self.parent_id else 'None'}")
        print("===========================")

        # Create justification
        justification = self.env['field.visit.justification'].create({
            'visit_id': visit.id,
            'user_id': sender.id,
            'datetime': fields.Datetime.now(),
            'message': self.message,
            'attachment_ids': [(6, 0, self.attachment.ids)],
            'recipient_type': recipient_type,
            'parent_id': self.parent_id.id if self.parent_id else False
        })

        # Send notification
        if recipient_user:
            recipient_user.partner_id.message_post(
                subject=f'New justification from {sender.name}',
                body=self.message,
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
                partner_ids=[recipient_user.partner_id.id]
            )
