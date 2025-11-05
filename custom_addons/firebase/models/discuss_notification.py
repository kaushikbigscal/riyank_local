#discuss model(channel,chat,update,pin,unpin)
from odoo import models, api, tools

class ChannelNotification(models.Model):
    _inherit = 'discuss.channel'

    @api.model
    def create(self, vals_list):
        record = super(ChannelNotification, self).create(vals_list)
        users = self.env['res.users'].search([])
        user_ids = [user.id for user in users if user.device_token]

        if user_ids:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=user_ids,
                title=None,
                body=None,
                payload={
                    'model': 'discuss.channel',
                    'record_id': str(record.id),
                    'action': 'channel_creation',
                    'silent': "true"
                }
            )
        return record

    def write(self, vals):
        result = super(ChannelNotification, self).write(vals)
        for record in self:
            # Skip notification if write_date == create_date (i.e., fresh after creation)
            if record.create_date and record.write_date and record.create_date == record.write_date:
                continue

            users = self.env['res.users'].search([])
            user_ids = [user.id for user in users if user.device_token]

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'discuss.channel',
                        'record_id': str(record.id),
                        'action': 'channel_update',
                        'silent': "true"
                    }
                )
        return result

    def unlink(self):
        for record in self:
            # Fetch all users with a registered device token
            users = self.env['res.users'].search([])
            user_ids = [user.id for user in users if user.device_token]

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'discuss.channel',
                        'record_id': str(record.id),
                        'action': 'channel_deletion',
                        'silent': "true"
                    }
                )
        return super(ChannelNotification, self).unlink()

    def message_post(self, **kwargs):
        # Check for skip_notification context, including the pin action flag
        if self.env.context.get('skip_notification'):
            return super(ChannelNotification, self).message_post(**kwargs)

        message = super(ChannelNotification, self).message_post(**kwargs)
        current_user = self.env.user

        for channel in self:
            participants = channel.channel_partner_ids
            users = self.env['res.users'].search([
                ('partner_id', 'in', participants.ids),
                ('id', '!=', current_user.id),
                ('device_token', '!=', False)
            ])

            user_ids = [user.id for user in users]

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'mail.channel',
                        'record_id': str(channel.id),
                        'action': 'message_sent',
                        'silent': "true"
                    }
                )

        return message

    def set_message_pin(self, **kwargs):
        # Set the context flag to skip notifications in message_post
        context = dict(self.env.context, skip_notification=True)
        self = self.with_context(context)

        message = super(ChannelNotification, self).set_message_pin(**kwargs)

        current_user = self.env.user

        for channel in self:
            # Get channel participants
            participants = channel.channel_partner_ids

            # Get all users linked to those partners, excluding the sender
            users = self.env['res.users'].search([
                ('partner_id', 'in', participants.ids),
                ('id', '!=', current_user.id),
                ('device_token', '!=', False)
            ])

            user_ids = [user.id for user in users]

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'mail.channel',
                        'record_id': str(channel.id),
                        'action': 'message_pin_unpin',
                        'silent': "true"
                    }
                )


        return message

    def _message_update_content(self, message, body, attachment_ids=None, partner_ids=None,
                                strict=True, **kwargs):

        result = super()._message_update_content(
            message, body, attachment_ids, partner_ids,
            strict=strict, **kwargs
        )

        if message.model == "discuss.channel" and message.res_id:
            channel = self.env["discuss.channel"].browse(message.res_id)
            current_user = self.env.user

            participants = channel.channel_partner_ids
            users = self.env['res.users'].search([
                ('partner_id', 'in', participants.ids),
                ('id', '!=', current_user.id),
                ('device_token', '!=', False)
            ])

            user_ids = [user.id for user in users]

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'discuss.channel',
                        'record_id': str(channel.id),
                        'action': 'message_edited',
                        'silent': "true"
                    }
                )

        return result

#message reaction notification
class MailMessage(models.Model):
    _inherit = 'mail.message'

    def _message_reaction(self, emoji, action):
        result = super()._message_reaction(emoji, action)

        if self.model == "discuss.channel" and self.res_id:
            channel = self.env["discuss.channel"].browse(self.res_id)
            current_user = self.env.user

            participants = channel.channel_partner_ids
            users = self.env['res.users'].search([
                ('partner_id', 'in', participants.ids),
                ('id', '!=', current_user.id),
                ('device_token', '!=', False)
            ])

            user_ids = [user.id for user in users]

            if user_ids:
                self.env['mobile.notification.service'].send_fcm_notification(
                    user_ids=user_ids,
                    title=None,
                    body=None,
                    payload={
                        'model': 'discuss.channel',
                        'record_id': str(channel.id),
                        'action': 'reaction_added_deleted',
                        'silent': "true"
                    }
                )

        return result

#inbox notification
class MailThreadFCMInboxOnly(models.AbstractModel):
    _inherit = 'mail.thread'

    def _notify_thread(self, message, msg_vals=False, **kwargs):

        # Call the original _notify_thread to retain default behavior
        result = super()._notify_thread(message, msg_vals=msg_vals, **kwargs)

        # Fetch inbox-type mail notifications related to this message
        inbox_notifications = self.env['mail.notification'].search([
            ('mail_message_id', '=', message.id),
            ('notification_type', '=', 'inbox'),
            ('res_partner_id.user_ids', '!=', False),
            ('res_partner_id.user_ids.device_token', '!=', False),
            ('is_read', '=', False)
        ])

        if not inbox_notifications:
            return result

        # Extract recipient users
        users_to_notify = inbox_notifications.mapped('res_partner_id.user_ids')
        users_to_notify = users_to_notify.filtered(lambda u: u.active and u.device_token)

        # Remove sender from recipient list
        author_user = message.author_id.user_ids[:1]
        users_to_notify = users_to_notify - author_user

        if not users_to_notify:
            return result

        # Build payload
        author_name = message.author_id.name
        fcm_payload = {
            'title': None,
            'body': None,
            'data': {
                'message_id': str(message.id),
                'model': str(message.model or ''),
                'res_id': str(message.res_id or ''),
                'record_name': str(message.record_name or ''),
                'author_name': str(author_name),
                'type': "inbox",
                'silent':"true"

            }
        }

        device_tokens = [
            str(u.device_token).strip()
            for u in users_to_notify if u.device_token
        ]

        if device_tokens:
            self.env['mobile.notification.service'].send_fcm_notification(
                user_ids=users_to_notify.ids,
                title=None,
                body=None,
                payload=fcm_payload['data']
            )

        return result
