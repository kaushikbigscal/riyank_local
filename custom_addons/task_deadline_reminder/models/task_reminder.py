import html
import logging
from collections import defaultdict

from odoo import models, fields, api, _
from datetime import datetime, time, timedelta
import pytz
from odoo.tools import html_escape, json

_logger = logging.getLogger(__name__)


class TaskReminder(models.Model):
    _name = 'task.reminder'
    _description = 'Task Reminder'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_datetime desc, id desc'

    name = fields.Char(string="Reminder Title", required=True)
    task_id = fields.Many2one('project.task', string="Task")
    user_ids = fields.Many2many('res.users', string="Users", required=True)
    deadline = fields.Datetime(string="Task Deadline")
    is_read = fields.Boolean(string="Is_Read")
    notified = fields.Boolean(default=False)
    author_id = fields.Many2one('res.users', string='Author', default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Related Partner')
    related_model = fields.Char(string='Related Document Model')
    related_id = fields.Integer(string='Related Document ID')
    body = fields.Html(string='Body')
    scheduled_datetime = fields.Datetime(string='Scheduled Datetime', default=fields.Datetime.now)
    activity_id = fields.Many2one('mail.activity', string='Activity')
    project_id = fields.Many2one('project.project')
    action_domain = fields.Char(string="Action Domain")

    summary = fields.Text(string="Summary")
    date_deadline = fields.Date(string="Due Date")
    char_time = fields.Char("Time (HH:MM)")

    time_str = fields.Char(string='Formatted Time', help='Formatted time string for display')
    today_formatted = fields.Char(string='Formatted Date', help='Formatted date string for display')



    read_by_user_ids = fields.Many2many(
        'res.users',
        'task_reminder_read_users_rel',
        'reminder_id',
        'user_ids',
        string="Read by Users"
    )

    def is_read_by_current_user(self):
        """Check if current reminder is read by the current user"""
        return self.env.user.id in self.read_by_user_ids.ids

    @api.model
    def get_user_reminders(self):
        """Get reminders for current user with user-specific read status"""
        current_user = self.env.user

        # Get all reminders where current user is in user_ids
        reminders = self.search([
            ('user_ids', 'in', [current_user.id])
        ])

        result = []
        for reminder in reminders:
            reminder_data = {
                'id': reminder.id,
                'name': reminder.name,
                'task_id': [reminder.task_id.id, reminder.task_id.name] if reminder.task_id else False,
                'task_name': reminder.task_id.name if reminder.task_id else '',
                'deadline': reminder.deadline,
                'activity_id': reminder.activity_id.id if reminder.activity_id else False,
                'project_id': reminder.project_id.id if reminder.project_id else False,
                'project_name': reminder.project_id.name if reminder.project_id else '',
                'is_overdue_reminder': reminder.is_overdue_reminder,
                'action_domain': reminder.action_domain,
                'is_read': current_user.id in reminder.read_by_user_ids.ids,  # User-specific read status
                'notified': reminder.notified,
                'task_deadline': reminder.task_id.date_deadline if reminder.task_id else False,
                'summary': reminder.summary,
                'date_deadline': reminder.date_deadline,
                'char_time': reminder.activity_id.char_time if reminder.activity_id else False,
                'time_str': reminder.time_str or 'No TimeSet',
                'today_formatted': reminder.today_formatted or 'No DateSet',

            }
            result.append(reminder_data)

        return result

    @api.model
    def mark_as_read_for_user(self, reminder_ids, user_ids=None):
        """Mark reminders as read for specific user"""
        if user_ids is None:
            user_ids = self.env.user.id

        reminders = self.browse(reminder_ids)
        for reminder in reminders:
            # Add current user to read_by_user_ids if not already there
            if user_ids not in reminder.read_by_user_ids.ids:
                reminder.write({
                    'read_by_user_ids': [(4, user_ids)]  # Add user to many2many
                })
            if user_ids == self.env.user.id:
                reminder.is_read = True
        return True

    @api.model
    def mark_as_read(self, ids):
        """Legacy method - now marks as read for current user only"""
        return self.mark_as_read_for_user(ids)

    @api.model
    def get_unread_count_for_user(self, user_ids=None):
        """Get count of unread reminders for specific user"""
        if user_ids is None:
            user_ids = self.env.user.id

        # Count reminders where user is assigned but hasn't read yet
        unread_count = self.search_count([
            ('user_ids', 'in', [user_ids]),
            ('read_by_user_ids', 'not in', [user_ids])  # Not in read_by_user_ids
        ])
        return unread_count

    @api.model
    def create_task_reminders(self):
        now = fields.Datetime.now()
        _logger.info("Running Task Reminder Cron at %s", now)

        queue_items = self.env['reminder.task.queue'].search([
            ('reminder_datetime', '<=', now),
        ])
        reminders_to_create = []
        messages_to_post = defaultdict(list)  # Grouped by record
        processed_queue_ids = []

        for queue in queue_items:
            reminder_time = queue.reminder_datetime

            # Skip & delete if reminder is expired more than 1 minute ago
            if (now - reminder_time) > timedelta(minutes=1):
                _logger.info("Reminder too old (missed): %s — deleting without notification", reminder_time)
                processed_queue_ids.append(queue.id)
                continue

            if queue.task_id:
                task = queue.task_id
                for user in task.user_ids:
                    reminders_to_create.append({
                        'name': f'Task Reminder: {task.name}',
                        'task_id': task.id,
                        'deadline': reminder_time,
                        'user_ids': [(6, 0, [user.id])],  # Per-user reminder
                    })

                    tz = user.tz or 'UTC'
                    local_time = fields.Datetime.context_timestamp(task.with_context(tz=tz), reminder_time)
                    messages_to_post[task].append((user, local_time, 'Task Reminder'))

            elif queue.activity_id:
                activity = queue.activity_id
                user = activity.user_id
                datetime_combined = queue.datetime_combined

                if not reminder_time or not isinstance(reminder_time, datetime):
                    processed_queue_ids.append(queue.id)
                    continue

                reminders_to_create.append({
                    'name': f'Activity Reminder: {activity.activity_type_id.name or "No Type"}',
                    'activity_id': activity.id,
                    'deadline': reminder_time,
                    'user_ids': [(6, 0, [user.id])],
                    'summary': activity.summary or activity.activity_type_id.name,  # Add summary from activity
                    'date_deadline': activity.date_deadline,
                    'char_time': activity.char_time,
                })

                tz = user.tz or 'UTC'
                local_time = fields.Datetime.context_timestamp(activity.with_context(tz=tz), reminder_time)

                # Format time based on user preference
                lang = self.env['res.lang'].search([('code', '=', user.lang)], limit=1)
                is_12h = lang and lang.time_format and '%p' in lang.time_format
                formatted_time = local_time.strftime('%I:%M %p' if is_12h else '%H:%M')

                messages_to_post[activity].append((user, local_time, 'Activity Reminder'))

            processed_queue_ids.append(queue.id)
 

        # ✅ Create reminders for systray
        if reminders_to_create:
            self.env['task.reminder'].create(reminders_to_create)

        # ✅ Post chatter notifications only once per record
        self._post_grouped_chatter_messages(messages_to_post)
        # Clean up processed queue items
        if processed_queue_ids:
            self.env['reminder.task.queue'].browse(processed_queue_ids).unlink()
            print(f"Deleted {len(processed_queue_ids)} processed queue items")

        # ✅ Clean up processed queue items
        if processed_queue_ids:
            self.env['reminder.task.queue'].browse(processed_queue_ids).unlink()
            _logger.info("Deleted %d processed/expired reminders", len(processed_queue_ids))

        _logger.info("Reminder cron execution complete.")

    def _post_grouped_chatter_messages(self, messages_to_post):
        """Post grouped chatter messages for task/activity by redirecting activity messages to their parent model"""
        for record, entries in messages_to_post.items():
            # Determine the actual record where the message should be posted
            target_record = record
            if record._name == 'mail.activity':
                try:
                    target_record = self.env[record.res_model].browse(record.res_id)
                except Exception as e:
                    print("Failed to resolve parent model for activity %s: %s", record.id, e)
                    continue

            if not hasattr(target_record, 'message_post'):
               print("Skipping chatter post for model '%s' — no message_post", target_record._name)
               continue

            partners = []
            time_lines = set()
            subject = ''

            for user, local_time, sub in entries:
                partners.append(user.partner_id.id)
                time_lines.add(f"{local_time.strftime('%d-%m-%Y %H:%M:%S')} ({user.tz})")
                subject = sub

            time_lines = sorted(time_lines)

            target_record.message_post(
                body=_("Reminder: %s is scheduled at:\n%s") % (
                    target_record.name or target_record.display_name,
                    "\n".join(time_lines)
                ),
                subject=_(subject),
                partner_ids=list(set(partners)),
                message_type="notification",
                subtype_xmlid="mail.mt_comment"
            )

    is_overdue_reminder = fields.Boolean("Is Overdue Reminder", default=False)

    def get_formview_action(self):
        """Enhanced method to handle different types of reminders"""
        self.ensure_one()
        # Check if this is an AMC contract reminder and module is installed
        if self.related_model == 'amc.contract' and self.related_id:
            amc_installed = self.env['ir.module.module'].search_count([
                ('name', '=', 'inventory_custom_tracking_installation_delivery'),
                ('state', '=', 'installed')
            ])
            if amc_installed:
                return {
                    'type': 'ir.actions.act_window',
                    'name': f"AMC Contract: {self.name}",
                    'view_mode': 'form',
                    'res_model': 'amc.contract',
                    'res_id': self.related_id,
                    'target': 'current',
                    'views': [(False, 'form')],
                }
            return {'type': 'ir.actions.act_window_close'}

        # Check if this is an overdue task reminder
        if self.name == 'Overdue Task Reminder' or self.is_overdue_reminder or self.action_domain:
            return self.get_overdue_tasks_action()

        # Regular task reminder - open task form
        if self.task_id:
            return {
                'type': 'ir.actions.act_window',
                'name': self.task_id.name,
                'view_mode': 'form',
                'res_model': 'project.task',
                'res_id': self.task_id.id,
                'target': 'current',
                'views': [(False, 'form')],
            }

        # Activity reminder - open activity form or related record
        if self.activity_id:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Activity: {self.activity_id.summary}',
                'view_mode': 'form',
                'res_model': self.activity_id.res_model,
                'res_id': self.activity_id.res_id,
                'target': 'current',
                'views': [(False, 'form')],
            }
        # Default fallback
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def create(self, vals):
        vals['notified'] = False
        return super().create(vals)

    def write(self, vals):
        if 'deadline' in vals:
            vals['notified'] = False
        return super().write(vals)


####### Overdue task reminders ##########

    @api.model
    def cron_send_overdue_reminders(self):
        """Cron job method to send overdue task reminders"""
        config = self.env['ir.config_parameter'].sudo()

        # Check if overdue reminders are enabled
        if config.get_param('task_deadline_reminder.enable_overdue_reminder') != 'True':
            return

        # Get reminder times
        allowed_times = [
            t.strip() for t in config.get_param('overdue_task_reminder.times', '').split(',') if t.strip()
        ]
        if not allowed_times:
            return

        # Handle UTC timezone conversion
        user_tz = pytz.timezone('Asia/Kolkata')
        now_utc = fields.Datetime.now()
        now_local_str = now_utc.astimezone(user_tz).strftime('%H:%M')

        if now_local_str not in allowed_times:
            return

        CLOSED_STATES = ['1_done', '1_canceled']

        today = fields.Date.today()

        # Find overdue tasks (exclude ToDos - only Tasks with deadlines)
        overdue_tasks = self.env['project.task'].search([
            ('date_deadline', '<', today),
            ('state', 'not in', CLOSED_STATES),
            ('active', '=', True),
            ('user_ids', '!=', False),
            '|',  # Start OR
            ('project_id', '=', False),  # private tasks
            ('project_id.is_fsm', '=', False),  # non-FSM normal tasks
        ])
        if not overdue_tasks:
            return

        # Group tasks by responsible user
        tasks_by_user = {}
        for task in overdue_tasks:
            for user in task.user_ids:
                tasks_by_user.setdefault(user.id, []).append(task)

        for user_id, user_tasks in tasks_by_user.items():
            user = self.env['res.users'].browse(user_id)

            task_count = len(user_tasks)
            task_list_text = f"You have {task_count} overdue tasks. Please complete them as soon as possible."

            task_recordset = self.env['project.task'].browse([t.id for t in user_tasks])

            domain = [('id', 'in', task_recordset.ids)]

            sample_task = user_tasks[0]

            if 'mail.thread' in self.env:
                self.env['mail.thread'].with_context(mail_notify_force_send=True).message_notify(
                    partner_ids=[user.partner_id.id],
                    subject="Overdue Tasks Reminder",
                    body=task_list_text,
                    model='project.task',
                    res_id=sample_task.id
                )
            else:
                _logger.warning("mail.thread model not found in registry. Skipping notification.")

            self.env['task.reminder'].create({
                'name': f'Overdue Task Reminder-({task_count})',
                'user_ids': [(6, 0, [user.id])],
                'deadline': fields.Datetime.now(),
                'is_overdue_reminder': True,
                'body': task_list_text,
                'action_domain': str(domain),
            })

    def get_overdue_tasks_action(self):
        """Return action to open real-time tree view of overdue tasks"""
        self.ensure_one()

        CLOSED_STATES = ['1_done', '1_canceled']

        today = fields.Date.today()

        domain = [
            ('date_deadline', '<', today),
            ('state', 'not in', CLOSED_STATES),
            ('active', '=', True),
            ('user_ids', 'in', self.user_ids.ids),
            '|',  # Start OR
            ('project_id', '=', False),  # private tasks
            ('project_id.is_fsm', '=', False),  # non-FSM normal tasks
        ]
        return {
            'type': 'ir.actions.act_window',
            'name': 'Overdue Tasks',
            'view_mode': 'tree,form',
            'res_model': 'project.task',
            'domain': domain,
            'target': 'current',
            'views': [
                (self.env.ref('project.view_task_tree2').id, 'tree'),
                (self.env.ref('project.view_task_form2').id, 'form')
            ],
            'context': {
                'default_user_ids': self.user_ids.ids,
                'search_default_overdue': 1,
                'search_default_user_id': self.env.user.id,
                'create': False,
            }
        }

############## amc reminder ############

    stage_id = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('not_renewed', 'Not Renewed'),
    ])

    @api.model
    def generate_amc_end_reminders(self):

        # Check if required module is installed
        module_installed = self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'inventory_custom_tracking_installation_delivery'),
            ('state', '=', 'installed')
        ])
        if not module_installed:
            print("Module 'inventory_custom_tracking_installation_delivery' not installed. Skipping reminder generation.")
            return


        now = fields.Datetime.now()

        print("=== Running AMC Reminder Cron at %s ===" % now)

        config = self.env['ir.config_parameter'].sudo()

        # Get the parameter value, if not set or None, skip processing
        days_before_param = config.get_param('reminder.amc_days_limit')

        if days_before_param is None:
            print("Parameter 'reminder.amc_days_limit' not set - skipping reminder processing")
            return

        days_before = int(days_before_param)  # Use the actual value including 0
        print("Reminder days before end date from settings (reminder.amc_days_limit): %s" % days_before)

        today = fields.Date.today()

        print("Searching for contracts that need reminders today...")

        # Find contracts where (end_date - days_before) equals today
        # This means we should send reminder today for contracts ending in 'days_before' days
        contracts = self.env['amc.contract'].search([
            ('stage_id', '=', 'active'),
            ('end_date', '!=', False)
        ])

        print("Total active contracts found: %s" % len(contracts))

        # Debug: Print all contract end dates
        for contract in contracts:
            # Calculate reminder date (today when the reminder is created)
            reminder_date = contract.end_date - timedelta(days=days_before)

            # Create datetime with 11:00 AM in IST
            local_datetime = datetime.combine(reminder_date, time(11, 0, 0))

            # Set timezone to IST first
            ist_tz = pytz.timezone('Asia/Kolkata')
            ist_datetime = ist_tz.localize(local_datetime)

            # Convert to UTC for storage in Odoo
            utc_reminder_datetime = ist_datetime.astimezone(pytz.UTC).replace(tzinfo=None)

            print(
                f"Contract: {contract.name} | End Date: {contract.end_date} | Reminder Date (UTC): {utc_reminder_datetime} | Today: {today}")

        # Filter contracts that need reminders today
        contracts_to_remind = contracts.filtered(
            lambda c: c.end_date and (c.end_date - timedelta(days=days_before)) == today
        )

        print("Contracts found that need reminders: %s" % len(contracts_to_remind))

        for contract in contracts_to_remind:
            print(f"Processing contract: {contract.name} (ID: {contract.id}) - Ends on: {contract.end_date}")

            if not contract.user_ids:
                print(f"No user assigned to contract: {contract.name} (Skipping)")
                continue

            # Calculate reminder date with proper timezone conversion
            reminder_date = contract.end_date - timedelta(days=days_before)

            # Create datetime with 11:00 AM in IST
            local_datetime = datetime.combine(reminder_date, time(11, 0, 0))

            # Set timezone to IST first
            ist_tz = pytz.timezone('Asia/Kolkata')
            ist_datetime = ist_tz.localize(local_datetime)

            # Convert to UTC for storage in Odoo
            utc_reminder_datetime = ist_datetime.astimezone(pytz.UTC).replace(tzinfo=None)

            # ✅ Check if a reminder already exists for this contract and deadline
            existing_reminder = self.env['task.reminder'].search([
                ('related_model', '=', 'amc.contract'),
                ('related_id', '=', contract.id),
                ('deadline', '=', utc_reminder_datetime),
            ], limit=1)

            if existing_reminder:
                print(
                    f"Reminder already exists for contract '{contract.name}' ending on {contract.end_date} — Skipping.")
                continue

            # Calculate days remaining
            days_remaining = (contract.end_date - today).days

            reminder_vals = {
                'name': f"AMC Contract \"{contract.name}\" Expired in {days_remaining} days.",
                'task_id': False,
                'deadline': utc_reminder_datetime,  # Use UTC datetime
                'user_ids': [(6, 0, contract.user_ids.ids)],
                'related_model': 'amc.contract',
                'related_id': contract.id,
            }

            reminder = self.env['task.reminder'].create(reminder_vals)
            print(
                f"Reminder created for contract '{contract.name}' and users {[u.name for u in contract.user_ids]} at {utc_reminder_datetime} UTC")

            # Post a message for each user
            for user in contract.user_ids:
                body_msg = _("Reminder: AMC Contract %s is ending in %s days on %s.") % (
                    html_escape(contract.name),
                    days_remaining,
                    contract.end_date.strftime('%d-%m-%Y')
                )
                contract.message_post(
                    body=body_msg,
                    subject=_("AMC Contract Reminder"),
                    partner_ids=[user.partner_id.id],
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                )
                print(f"Notification posted to user '{user.name}'")

        print("=== AMC Reminder Cron Completed ===")

    def get_user_amc_reminders(self):
        """Fetch AMC reminders for current user"""
        user_id = self.env.user.id
        today = fields.Date.today()

        return self.search_read([
            ('user_ids', 'in', [user_id]),
            ('end_date', '>=', today),
            ('stage_id', '=', 'active'),
        ], ['id', 'name', 'end_date', 'is_read'])


