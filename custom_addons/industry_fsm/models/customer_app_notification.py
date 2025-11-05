
from odoo import models, fields, api
import logging

from odoo.tools import format_datetime

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def unlink(self):

        portal_notification_installed = self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'notification'),
            ('state', '=', 'installed')
        ]) > 0

        for task in self:
            if portal_notification_installed:
                notifications = self.env['portal.notification'].sudo().search([
                    ('res_model', '=', 'project.task'),
                    ('res_id', '=', task.id)
                ])

                if notifications:
                    print(f"[DELETE] Found {len(notifications)} notification(s) for task ID {task.id} - deleting now...")
                    notifications.unlink()
                    print(f"[DELETE] Notifications for task ID {task.id} removed successfully.")
                else:
                    print(f"[DELETE] No notifications found for task ID {task.id}.")

                print(f"[DELETE] Deleting project.task record ID {task.id} - {task.name}")

            return super().unlink() 

    def _send_customer_notification(self, partner, subject, message, url='/my/ticket'):
        if not partner:
            return

        # Check if customer_app module is installed
        customer_app_installed = self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'customer_app'),
            ('state', '=', 'installed')
        ]) > 0

        # Check if portal_notification module is installed
        portal_notification_installed = self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'notification'),
            ('state', '=', 'installed')
        ]) > 0

        # Send webpush only if customer_app is installed
        if portal_notification_installed:
            success = self.env['mail.partner.device'].send_webpush_to_partner(
                partner=partner,
                title=subject,
                body=message,
                url=url
            )
            if success:
                _logger.info("Webpush notification sent successfully")
            else:
                _logger.warning("Webpush notification failed to send")

        if customer_app_installed:
            self.env['portal.notification'].sudo().create_for_partner(
                partner=partner,
                title=subject,
                message=message,
                url=url or "/my/home",
                res_model=self._name,
                res_id=self.id
            )


    @api.model
    def create(self, vals):

        task = super().create(vals)

        if self.env.user.has_group('base.group_portal'):
            return task

        if task.is_fsm:
            customer = task.partner_id
            ticket_no = task.sequence_fsm or 'Undefined'
            task_name = task.name

            if customer:
                msg = f"Service ticket {ticket_no} / {task_name} has been created."
                url = f"/my/ticket/{task.id}"
                task._send_customer_notification(customer, "New Service Ticket Created", msg, url)

                if task.user_ids:
                    assignees = ", ".join(task.user_ids.mapped('name'))
                    planned_dt = task.planned_date_begin or fields.Datetime.now()

                    tz = customer.tz or 'Asia/Kolkata'  # fallback if not set
                    planned_str = format_datetime(task.env, planned_dt, tz=tz, dt_format='%d/%m/%Y %H:%M:%S')

                    msg = (
                        f"Ticket {ticket_no} has been assigned to {assignees} "
                        f"with planned date-time {planned_str}."
                    )
                    url = f"/my/ticket/{task.id}"
                    task._send_customer_notification(customer, "Ticket Assigned", msg, url)
        return task

    def write(self, vals):
        res = super().write(vals)

        for task in self:
            if not task.is_fsm:
                continue

            if self.env.user.has_group('base.group_portal'):
                return task

            customer = task.partner_id
            if not customer:
                continue

            ticket_no = task.sequence_fsm or task.name

            if 'user_ids' in vals:
                assignees = ", ".join(task.user_ids.mapped('name'))
                planned_dt = task.planned_date_begin or fields.Datetime.now()

                # Convert UTC to customer's timezone
                tz = customer.tz or 'Asia/Kolkata'  # fallback to your default timezone
                planned_dt_local = fields.Datetime.context_timestamp(task.with_context(tz=tz), planned_dt)

                formatted_date = planned_dt_local.strftime("%d/%m/%Y %H:%M:%S")

                msg = (
                    f"Ticket {ticket_no} has been assigned to {assignees} "
                    f"with planned date-time {formatted_date}."
                )
                url = f"/my/ticket/{task.id}"
                task._send_customer_notification(customer, "Ticket Assigned", msg, url)

            if 'stage_id' in vals:
                stage_name = task.stage_id.name.lower()

                if stage_name == 'in progress':
                    assignees = ", ".join(task.user_ids.mapped('name'))
                    msg = f"{assignees} has checked-in at your place and started work on ticket {ticket_no}."
                    url = f"/my/ticket/{task.id}"
                    task._send_customer_notification(customer, "Work Started", msg, url)

                elif stage_name in ['done', 'resolved']:
                    url = f"/my/ticket/{task.id}"
                    if stage_name == 'resolved':
                        msg = f"Service ticket {ticket_no} has been resolved."
                        title = "Ticket Resolved"
                    else:
                        msg = f"Service ticket {ticket_no} has been completed."
                        title = "Ticket Completed"
                    task._send_customer_notification(customer, title, msg, url)

        return res

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)

        # detect once if the field exists on res.partner
        has_webpush = 'webpush_subscription' in self.env['res.partner']._fields

        for task in self:
            if not task.is_fsm:
                continue
            if kwargs.get('message_type') != 'comment':
                continue

            author = self.env.user
            is_portal_user = author.has_group('base.group_portal')

            ticket_no = task.sequence_fsm or task.name
            message_body = kwargs.get('body', '')

            if is_portal_user:
                # portal user commented, notify assignees
                for user in task.user_ids:
                    partner = user.partner_id
                    if has_webpush and partner.webpush_subscription:
                        msg = f"Customer update on ticket {ticket_no}: {message_body}"
                        url = f"/my/ticket/{task.id}"
                        task._send_customer_notification(partner, "Customer Reply", msg, url)
            else:
                # internal user commented, notify customer
                customer = task.partner_id
                if has_webpush and customer.webpush_subscription:
                    msg = f"Update on ticket {ticket_no}: {message_body}"
                    url = f"/my/ticket/{task.id}"
                    task._send_customer_notification(customer, "Service Ticket Update", msg, url)

        return message


