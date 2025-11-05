from odoo import models, fields, api, _


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def action_feedback(self, **kwargs):
        for activity in self:
            if activity.create_uid and activity.create_uid != self.env.user:
                try:
                    if activity.res_model and activity.res_id:
                        record = self.env[activity.res_model].browse(activity.res_id)
                        record.message_notify(
                            subject="Activity Marked as Done",
                            body=f" The Activity {activity.summary or activity.activity_type_id.name} assigned to {activity.user_id.name} was marked as Done.",
                            partner_ids=[activity.create_uid.partner_id.id],
                        )
                except Exception:
                    pass
        # Set context flag to skip unlink notification
        return super(MailActivity, self.with_context(skip_unlink_notify=True)).action_feedback(**kwargs)

    def unlink(self):
        skip_notify = self.env.context.get('skip_unlink_notify')
        for activity in self:
            if not skip_notify and activity.create_uid and activity.create_uid != self.env.user:
                try:
                    record = self.env[activity.res_model].browse(activity.res_id)
                    record.message_notify(
                        subject="Activity Cancelled",
                        body=f"The activity {activity.summary or activity.activity_type_id.name} assigned to {activity.user_id.name} was Cancelled.",
                        partner_ids=[activity.create_uid.partner_id.id],
                    )
                except Exception:
                    pass
        return super().unlink()