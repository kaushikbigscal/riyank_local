from datetime import datetime, timedelta
import re
import pytz
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MailActivitySchedule(models.TransientModel):
    _inherit = 'mail.activity.schedule'

    set_reminder = fields.Boolean(string="Reminder")
    reminder_type_ids = fields.Many2many(
        'reminder.types', 'activity_schedule_reminder_type_rel', 'schedule_id', 'reminder_type_id',
        string="Reminder Types"
    )
    custom_reminder_datetime = fields.Datetime(string="Custom Reminder Time")
    is_custom_selected = fields.Boolean(compute='_compute_is_custom_selected')
    char_time = fields.Char("Time (HH:MM)")
    datetime_combined = fields.Datetime("Combined Datetime", compute="_compute_datetime_combined", store=True)
    name = fields.Char(string="Reminder Types")

    is_meeting_type = fields.Boolean(string="Is Meeting Type", compute="_compute_is_meeting_type")

    # Add helper field to detect time format
    is_12h_format = fields.Boolean(compute='_compute_time_format')
    time_period = fields.Selection([
        ('AM', 'AM'),
        ('PM', 'PM')
    ], string="AM/PM", default='AM')

    @api.depends('activity_user_id.lang')  # Use activity_user_id for the wizard
    def _compute_time_format(self):
        for rec in self:
            user = rec.activity_user_id or self.env.user
            lang = self.env['res.lang'].search([('code', '=', user.lang)], limit=1)
            rec.is_12h_format = lang and lang.time_format and '%p' in lang.time_format

    @api.depends('activity_type_id')
    def _compute_is_meeting_type(self):
        for rec in self:
            rec.is_meeting_type = rec.activity_type_id.name == "Meeting"

    def _parse_time_string(self, time_str, is_12h_format):
        """Parse time string based on company format"""
        try:
            if is_12h_format:
                # Handle 12-hour format with AM/PM
                return datetime.strptime(time_str, '%I:%M %p').time()
            else:
                # Handle 24-hour format
                return datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return False

    @api.onchange('is_12h_format')
    def _onchange_time_format(self):
        """Reset time period when format changes"""
        for rec in self:
            if not rec.is_12h_format:
                rec.time_period = False
            elif not rec.time_period:
                rec.time_period = 'AM'

    # Update in both MailActivity and MailActivitySchedule
    @api.depends('char_time', 'date_deadline', 'time_period', 'is_12h_format')
    def _compute_datetime_combined(self):
        for rec in self:
            if rec.char_time and rec.date_deadline:
                try:
                    # Format time string based on company format
                    time_str = rec.char_time
                    if rec.is_12h_format and rec.time_period:
                        time_str = f"{rec.char_time} {rec.time_period}"

                    time_obj = self._parse_time_string(time_str, rec.is_12h_format)
                    if not time_obj:
                        rec.datetime_combined = False
                        continue

                    # Create naive datetime and convert to UTC
                    naive_dt = datetime.combine(rec.date_deadline, time_obj)
                    user_tz = pytz.timezone(rec.user_id.tz or self.env.user.tz or 'UTC')
                    local_dt = user_tz.localize(naive_dt)
                    rec.datetime_combined = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

                except (ValueError, Exception):
                    rec.datetime_combined = False
            else:
                rec.datetime_combined = False

    # @api.depends('char_time', 'date_deadline')
    # def _compute_datetime_combined(self):
    #     for rec in self:
    #         if rec.char_time and rec.date_deadline:
    #             try:
    #                 # Convert char to time object
    #                 time_obj = datetime.strptime(rec.char_time, '%H:%M').time()
    #                 # Combine with date
    #                 rec.datetime_combined = datetime.combine(rec.date_deadline, time_obj)
    #             except ValueError:
    #                 rec.datetime_combined = False
    #         else:
    #             rec.datetime_combined = False

    def _action_schedule_activities(self):
        return self._get_applied_on_records().activity_schedule(
            set_reminder=self.set_reminder,
            reminder_type_ids=self.reminder_type_ids,
            date_deadline=self.date_deadline,
            char_time=self.char_time,
            is_custom_selected=self.is_custom_selected,
            custom_reminder_datetime=self.custom_reminder_datetime,
            activity_type_id=self.activity_type_id.id,
            summary=self.summary,
            automated=False,
            note=self.note,
            user_id=self.activity_user_id.id,
            name=self.name,
            time_period=self.time_period
        )

    @api.depends('reminder_type_ids')
    def _compute_is_custom_selected(self):
        for schedule in self:
            schedule.is_custom_selected = any(
                rt.name.lower() == 'custom' for rt in schedule.reminder_type_ids
            )

    @api.onchange('reminder_type_ids')
    def _onchange_reminder_type_ids(self):
        for record in self:
            if not any(rt.name.lower() == 'custom' for rt in record.reminder_type_ids):
                record.custom_reminder_datetime = False

    @api.onchange('set_reminder')
    def _onchange_set_reminder(self):
        """Clear reminder_type_ids when set_reminder is disabled"""
        if not self.set_reminder:
            self.reminder_type_ids = [(5, 0, 0)]  # Clear all records

    def write(self, vals):
        """Override write method to clear reminder_type_ids when set_reminder is disabled"""
        if 'set_reminder' in vals and not vals['set_reminder']:
            vals['reminder_type_ids'] = [(5, 0, 0)]  # Clear all records
        return super(MailActivitySchedule, self).write(vals)


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    set_reminder = fields.Boolean(string="Reminder")
    reminder_type_ids = fields.Many2many(
        'reminder.types', 'activity_reminder_type_rel', 'activity_id', 'reminder_type_id',
        string="Reminder Types")
    custom_reminder_datetime = fields.Datetime(string="Custom Reminder Time")
    is_custom_selected = fields.Boolean(compute="_compute_is_custom_selected")
    user_id = fields.Many2one('res.users', string='Activity User')
    char_time = fields.Char("Time (HH:MM)")
    datetime_combined = fields.Datetime("Combined Datetime", compute="_compute_datetime_combined", store=True)
    name = fields.Char(string="Reminder Types")

    is_meeting_type = fields.Boolean(string="Is Meeting Type", compute="_compute_is_meeting_type")

    is_12h_format = fields.Boolean(compute='_compute_time_format')
    time_period = fields.Selection([
        ('AM', 'AM'),
        ('PM', 'PM')
    ], string="AM/PM", default='AM')

    @api.depends('user_id.lang')  # Only depend on user_id.lang
    def _compute_time_format(self):
        for rec in self:
            lang_code = rec.user_id.lang if rec.user_id else self.env.user.lang
            lang = self.env['res.lang'].search([('code', '=', lang_code)], limit=1)
            rec.is_12h_format = lang and lang.time_format and '%p' in lang.time_format

    @api.depends('activity_type_id')
    def _compute_is_meeting_type(self):
        for rec in self:
            rec.is_meeting_type = rec.activity_type_id.name == "Meeting"


    def unlink(self):
        queue_model = self.env['reminder.task.queue']
        for activity in self:
            queue_model.search([
                ('activity_id', '=', activity.id)
            ]).unlink()
        return super(MailActivity, self).unlink()

    @api.onchange('is_12h_format')
    def _onchange_time_format(self):
        """Reset time period when format changes"""
        for rec in self:
            if not rec.is_12h_format:
                rec.time_period = False
            elif not rec.time_period:
                rec.time_period = 'AM'

    def action_done(self):
        res = super().action_done()
        self.env['reminder.task.queue'].search([
            ('activity_id', 'in', self.ids)
        ]).unlink()
        return res

    def _parse_time_string(self, time_str, is_12h_format):
        """Parse time string based on company format"""
        try:
            if is_12h_format:
                # Handle 12-hour format with AM/PM
                return datetime.strptime(time_str, '%I:%M %p').time()
            else:
                # Handle 24-hour format
                return datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return False

    # @api.depends('char_time', 'date_deadline')
    # def _compute_datetime_combined(self):
    #     for rec in self:
    #         if rec.char_time and rec.date_deadline:
    #             try:
    #                 time_obj = datetime.strptime(rec.char_time, '%H:%M').time()
    #                 # Create naive datetime
    #                 naive_dt = datetime.combine(rec.date_deadline, time_obj)
    #
    #                 # Get user's timezone
    #                 user_tz = pytz.timezone(rec.user_id.tz or self.env.user.tz or 'UTC')
    #
    #                 # Localize to user's timezone, then convert to UTC
    #                 local_dt = user_tz.localize(naive_dt)
    #                 rec.datetime_combined = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
    #             except ValueError:
    #                 rec.datetime_combined = False
    #         else:
    #             rec.datetime_combined = False

    # Update in both MailActivity and MailActivitySchedule
    @api.depends('char_time', 'date_deadline', 'time_period', 'is_12h_format')
    def _compute_datetime_combined(self):
        for rec in self:
            if rec.char_time and rec.date_deadline:
                try:
                    # Format time string based on company format
                    time_str = rec.char_time
                    if rec.is_12h_format and rec.time_period:
                        time_str = f"{rec.char_time} {rec.time_period}"

                    time_obj = self._parse_time_string(time_str, rec.is_12h_format)
                    if not time_obj:
                        rec.datetime_combined = False
                        continue

                    # Create naive datetime and convert to UTC
                    naive_dt = datetime.combine(rec.date_deadline, time_obj)
                    user_tz = pytz.timezone(rec.user_id.tz or self.env.user.tz or 'UTC')
                    local_dt = user_tz.localize(naive_dt)
                    rec.datetime_combined = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

                except (ValueError, Exception):
                    rec.datetime_combined = False
            else:
                rec.datetime_combined = False

    @api.depends('reminder_type_ids')
    def _compute_is_custom_selected(self):
        for activity in self:
            activity.is_custom_selected = any(
                rt.name.lower() == 'custom' for rt in activity.reminder_type_ids
            )

    @api.onchange('reminder_type_ids')
    def _onchange_reminder_type_ids(self):
        for record in self:
            if not any(rt.name.lower() == 'custom' for rt in record.reminder_type_ids):
                record.custom_reminder_datetime = False

    @api.constrains('char_time')
    def _check_char_time_format(self):
        for rec in self:
            if rec.char_time:
                is_12h = rec.is_12h_format
                # Validation for 24-hour format
                if not is_12h and not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', rec.char_time):
                    raise ValidationError("Time must be in HH:MM format (e.g., 14:30)")
                # Validation for 12-hour format
                if is_12h and not re.match(r'^([0]?[1-9]|1[0-2]):[0-5][0-9]$', rec.char_time):
                    raise ValidationError("Time must be in HH:MM format (e.g., 02:30)")

    # @api.constrains('char_time')
    # def _check_char_time_format(self):
    #     for rec in self:
    #         if rec.char_time:
    #             try:
    #                 datetime.strptime(rec.char_time, '%H:%M')
    #             except ValueError:
    #                 raise ValidationError("Time must be in HH:MM format only (e.g., 09:30).")

    @api.model
    def create(self, vals):
        activity = super().create(vals)
        activity._generate_reminder_queue()
        return activity

    def write(self, vals):
        result = super().write(vals)
        if any(key in vals for key in ['set_reminder', 'reminder_type_ids','char_time','date_deadline','datetime_combined','custom_reminder_datetime']):
            self._generate_reminder_queue()
        return result

    def _generate_reminder_queue(self):
        queue_model = self.env['reminder.task.queue']
        for activity in self:
            # Delete old reminders
            queue_model.search([('activity_id', '=', activity.id)]).unlink()

            if not (activity.set_reminder and activity.date_deadline and activity.reminder_type_ids):
                continue

            for rt in activity.reminder_type_ids:
                if rt.name.lower() == 'custom' and activity.custom_reminder_datetime:
                    reminder_dt = activity.custom_reminder_datetime
                else:
                    if rt.reminder_minutes is None or not activity.char_time:
                        continue

                    # Parse time based on user/company format
                    time_str = activity.char_time.strip()

                    # Normalize: if in 24h mode, strip AM/PM accidentally typed in UI
                    if not activity.is_12h_format:
                        time_str = re.sub(r'\s*(AM|PM)$', '', time_str, flags=re.IGNORECASE)

                    if activity.is_12h_format and activity.time_period:
                        time_str = f"{time_str} {activity.time_period}"

                    time_obj = activity._parse_time_string(time_str, activity.is_12h_format)
                    if not time_obj:
                        continue

                    # Create datetime and convert to UTC
                    naive_dt = datetime.combine(activity.date_deadline, time_obj)
                    user_tz = pytz.timezone(activity.user_id.tz or self.env.user.tz or 'UTC')
                    local_dt = user_tz.localize(naive_dt)
                    deadline_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
                    reminder_dt = deadline_dt - timedelta(minutes=rt.reminder_minutes)

                # Create queue entry
                self.env['reminder.task.queue'].create({
                    'activity_id': activity.id,
                    'task_id': activity.res_model == 'project.task' and activity.res_id or False,
                    'user_id': activity.user_id.id,
                    'reminder_datetime': reminder_dt,
                })
    # def _generate_reminder_queue(self):
    #     queue_model = self.env['reminder.task.queue']
    #     for activity in self:
    #         # Delete old reminders
    #         queue_model.search([('activity_id', '=', activity.id)]).unlink()
    #
    #         if not (activity.set_reminder and activity.date_deadline and activity.reminder_type_ids):
    #             continue
    #
    #         for rt in activity.reminder_type_ids:
    #             if rt.name.lower() == 'custom' and activity.custom_reminder_datetime:
    #                 reminder_dt = activity.custom_reminder_datetime
    #             else:
    #                 if rt.reminder_minutes is None or not activity.char_time:
    #                     continue
    #
    #                 # Parse time based on company format
    #                 time_str = activity.char_time
    #                 if activity.is_12h_format and activity.time_period:
    #                     time_str = f"{activity.char_time} {activity.time_period}"
    #
    #                 time_obj = self._parse_time_string(time_str, activity.is_12h_format)
    #                 if not time_obj:
    #                     continue
    #
    #                 # Create datetime and convert to UTC
    #                 naive_dt = datetime.combine(activity.date_deadline, time_obj)
    #                 user_tz = pytz.timezone(activity.user_id.tz or self.env.user.tz or 'UTC')
    #                 local_dt = user_tz.localize(naive_dt)
    #                 deadline_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
    #                 reminder_dt = deadline_dt - timedelta(minutes=rt.reminder_minutes)
    #
    #             # Create queue entry
    #             self.env['reminder.task.queue'].create({
    #                 'activity_id': activity.id,
    #                 'task_id': activity.res_model == 'project.task' and activity.res_id or False,
    #                 'user_id': activity.user_id.id,
    #                 'reminder_datetime': reminder_dt,
    #             })

    # def _generate_reminder_queue(self):
    #     queue_model = self.env['reminder.task.queue']
    #     for activity in self:
    #         # Delete old reminders
    #         queue_model.search([('activity_id', '=', activity.id)]).unlink()
    #
    #         # Skip invalid cases
    #         if not (activity.set_reminder and activity.date_deadline and activity.reminder_type_ids):
    #             continue
    #
    #         for rt in activity.reminder_type_ids:
    #             # Handle custom
    #             if rt.name.lower() == 'custom' and activity.custom_reminder_datetime:
    #                 reminder_dt = activity.custom_reminder_datetime
    #             else:
    #                 if rt.reminder_minutes is None or not activity.char_time:
    #                     continue
    #                 try:
    #                     time_obj = datetime.strptime(activity.char_time, '%H:%M').time()
    #                 except ValueError:
    #                     continue
    #
    #                 # Create naive datetime
    #                 naive_dt = datetime.combine(activity.date_deadline, time_obj)
    #
    #                 # Get user's timezone and convert properly
    #                 user_tz = pytz.timezone(activity.user_id.tz or self.env.user.tz or 'UTC')
    #                 local_dt = user_tz.localize(naive_dt)
    #                 deadline_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
    #
    #                 reminder_dt = deadline_dt - timedelta(minutes=rt.reminder_minutes)
    #
    #             # Create queue entry
    #             self.env['reminder.task.queue'].create({
    #                 'activity_id': activity.id,
    #                 'task_id': activity.res_model == 'project.task' and activity.res_id or False,
    #                 'user_id': activity.user_id.id,
    #                 'reminder_datetime': reminder_dt,
    #             })













































    #
    # @api.model
    # def create(self, vals):
    #     activity = super().create(vals)
    #     activity._generate_reminder_queue()
    #     return activity

    # def write(self, vals):
    #     result = super().write(vals)
    #     if any(key in vals for key in ['set_reminder', 'reminder_type_ids', 'date_deadline','time_deadline']):
    #         self._generate_reminder_queue()
    #     return result

    # def _generate_reminder_queue(self):
    #     for activity in self:
    #         # Remove old reminders
    #         self.env['reminder.task.queue'].search([('task_id', '=', activity.id)]).unlink()
    #
    #         if not (activity.set_reminder and activity.date_deadline and activity.time_deadline and activity.reminder_type_ids):
    #             continue
    #
    #         for rt in activity.reminder_type_ids:
    #             # Handle custom reminders
    #             if rt.name.lower() == 'custom' and activity.custom_reminder_datetime:
    #                 reminder_dt = activity.custom_reminder_datetime
    #                 print("0",reminder_dt)
    #             else:
    #                 if rt.reminder_minutes is None:
    #                     continue  # Skip if no minute value
    #                 print("1",activity.time_deadline)
    #                 reminder_dt = activity.time_deadline - timedelta(minutes=rt.reminder_minutes)
    #                 print("2",reminder_dt)
    #
    #             # Store in queue
    #             self.env['reminder.task.queue'].create({
    #                 'task_id': activity.id,
    #                 'user_id': activity.user_ids and activity.user_ids[0].id or None,
    #                 'reminder_datetime': reminder_dt,
    #             })






    # def _generate_activity_reminders(self):
    #     queue_model = self.env['reminder.task.queue']
    #     for activity in self:
    #         queue_model.search([('activity_id', '=', activity.id)]).unlink()
    #
    #         if not (activity.set_reminder and activity.date_deadline and activity.reminder_type_ids):
    #             continue
    #
    #         # Parse '12:55' from time_deadline field
    #         try:
    #             time_parts = activity.time_deadline.strip().split(':')
    #             hour = int(time_parts[0])
    #             minute = int(time_parts[1])
    #         except Exception:
    #             continue  # skip if invalid time format
    #
    #         # Construct full deadline datetime
    #         deadline_dt = datetime(
    #             year=activity.date_deadline.year,
    #             month=activity.date_deadline.month,
    #             day=activity.date_deadline.day,
    #             hour=hour,
    #             minute=minute
    #         )
    #
    #         for rt in activity.reminder_type_ids:
    #             if rt.name.lower() == 'custom' and activity.custom_reminder_datetime:
    #                 reminder_dt = activity.custom_reminder_datetime
    #             elif rt.reminder_minutes is not None:
    #                 reminder_dt = deadline_dt - timedelta(minutes=rt.reminder_minutes)
    #             else:
    #                 continue
    #
    #             queue_model.create({
    #                 'activity_id': activity.id,
    #                 'task_id': activity.res_id if activity.res_model == 'project.task' else False,
    #                 'reminder_datetime': reminder_dt,
    #                 'user_id': activity.user_id.id if activity.user_id else False,
    #             })

