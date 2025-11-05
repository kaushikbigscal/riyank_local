from odoo import models, fields, api
from odoo.addons.calendar.models.calendar_recurrence import (
    BYDAY_SELECTION,
    MONTH_BY_SELECTION,
    RRULE_TYPE_SELECTION,
    WEEKDAY_SELECTION,
)
from datetime import datetime, timedelta
from odoo.exceptions import UserError
import calendar


class RouteAssignment(models.Model):
    _name = "route.assignment"
    _description = "Route Assignment"
    _rec_name = "route_id"

    employee_ids = fields.Many2many('res.users', string="Employees", required=True)
    route_id = fields.Many2one('route.management', string="Select Route", required=True)
    start_date = fields.Date(string="Start Date", required=True, default=fields.Date.today)

    # Recurrence fields
    rrule_type = fields.Selection(
        selection=lambda self: [option for option in RRULE_TYPE_SELECTION if option[0] != 'yearly'],
        string="Recurrence",
        default="daily",
        required=True
    )
    interval = fields.Integer(string="Repeat Every", default=1, required=True)
    END_TYPE_SELECTION = [('count', 'Number of Repetitions'), ('end_date', 'End Date')]
    end_type = fields.Selection(END_TYPE_SELECTION, string="Recurrence Termination", default="end_date", required=True)
    count = fields.Integer(string="Repeat", default=1)
    until = fields.Date(string="End Date")

    # Weekly recurrence
    mon = fields.Boolean("Monday")
    tue = fields.Boolean("Tuesday")
    wed = fields.Boolean("Wednesday")
    thu = fields.Boolean("Thursday")
    fri = fields.Boolean("Friday")
    sat = fields.Boolean("Saturday")
    sun = fields.Boolean("Sunday")

    # Monthly recurrence
    month_by = fields.Selection(MONTH_BY_SELECTION, string="Monthly Option")
    # month_by = fields.Selection(
    #     [('date', 'Date of Month'), ('week', 'Week of Month')],
    #     string="Monthly Option",
    # )
    for i in range(1, 32):
        locals()[f'day_{i}'] = fields.Boolean(string=str(i))
    first = fields.Boolean("First")
    second = fields.Boolean("Second")
    third = fields.Boolean("Third")
    fourth = fields.Boolean("Fourth")
    last = fields.Boolean("Last")
    weekday = fields.Selection(WEEKDAY_SELECTION)

    # Visit fields
    visit_ids = fields.One2many('field.visit', 'route_assignment_id', string="Generated Visits")
    visit_count = fields.Integer(string="Visit Count", compute="_compute_visit_count")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.depends('visit_ids')
    def _compute_visit_count(self):
        for record in self:
            record.visit_count = len(record.visit_ids)

    @api.onchange("end_type")
    def _onchange_end_type(self):
        if self.end_type == "count":
            self.until = False
        elif self.end_type == "end_date":
            self.count = 0

    @api.onchange("rrule_type")
    def _onchange_rrule_type(self):
        if self.rrule_type != "monthly":
            self.month_by = False
            self.weekday = False
            self.first = self.second = self.third = self.fourth = self.last = False
            for i in range(1, 32):
                setattr(self, f'day_{i}', False)

    # Helpers for monthly recurrence
    def _get_selected_month_days(self):
        return [i for i in range(1, 32) if getattr(self, f'day_{i}', False)]

    def _get_selected_weeks(self):
        week_map = [(self.first, 1), (self.second, 2), (self.third, 3), (self.fourth, 4), (self.last, -1)]
        return [num for flag, num in week_map if flag]

    def _get_selected_weekdays(self):
        weekday_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        return [weekday_map[w] for w, val in [('mon', self.mon), ('tue', self.tue), ('wed', self.wed),
                                              ('thu', self.thu), ('fri', self.fri), ('sat', self.sat),
                                              ('sun', self.sun)] if val]

    # Generate recurrence dates
    def _get_calendar_recurrence_dates(self, start_from=None, limit_days=None):
        dates = []
        start = (start_from or self.start_date)
        if isinstance(start, datetime):
            start = start.date()
        end = (self.until or (start + timedelta(days=limit_days or 365)))
        if isinstance(end, datetime):
            end = end.date()

        if self.rrule_type == 'daily':
            current = start
            while current <= end:
                dates.append(current)
                current += timedelta(days=self.interval)

        elif self.rrule_type == 'weekly':
            weekdays = self._get_selected_weekdays() or [start.weekday()]
            current = start
            while current <= end:
                for wd in weekdays:
                    diff = wd - current.weekday()
                    visit_date = current + timedelta(days=diff if diff >= 0 else diff + 7)
                    if start <= visit_date <= end:
                        dates.append(visit_date)
                current += timedelta(weeks=self.interval)

        elif self.rrule_type == 'monthly':
            current = start.replace(day=1)
            while current <= end:
                year, month = current.year, current.month
                if self.month_by == 'date':
                    selected_days = self._get_selected_month_days() or [start.day]
                    for day in selected_days:
                        try:
                            visit_date = current.replace(day=day)
                            if start <= visit_date <= end:
                                dates.append(visit_date)
                        except ValueError:
                            continue
                elif self.month_by == 'day':
                    selected_weeks = self._get_selected_weeks() or [1]
                    selected_weekdays = self._get_selected_weekdays() or [start.weekday()]
                    cal = calendar.Calendar()
                    month_days = list(cal.itermonthdays2(year, month))
                    for week_num in selected_weeks:
                        for wd in selected_weekdays:
                            days_in_month = [d for d, w in month_days if d != 0 and w == wd]
                            if not days_in_month:
                                continue
                            if week_num == -1:
                                day = days_in_month[-1]
                            elif week_num <= len(days_in_month):
                                day = days_in_month[week_num - 1]
                            else:
                                continue
                            try:
                                visit_date = current.replace(day=day)
                                if start <= visit_date <= end:
                                    dates.append(visit_date)
                            except ValueError:
                                continue
                month = current.month + self.interval
                year = current.year + (month - 1) // 12
                month = (month - 1) % 12 + 1
                current = current.replace(year=year, month=month, day=1)

        return sorted(list(set(dates)))

    def _get_last_visit_date(self):
        return max(self.visit_ids.mapped('date_start') or [self.start_date])

    def _get_new_visit_dates(self, limit=30):
        """Return only the next 'limit' dates after the last visit, excluding existing ones."""
        last_date = self._get_last_visit_date()
        # get all possible future dates
        all_dates = self._get_calendar_recurrence_dates(
            start_from=last_date + timedelta(days=1),
            limit_days=3650,  # far enough into the future
        )
        # exclude already created dates
        existing_dates = set(self.visit_ids.mapped('date'))
        new_dates = [d for d in all_dates if d not in existing_dates]
        # return only the first 'limit' new dates
        return new_dates[:limit]

    def _prepare_visit_values(self, dates):
        vals = []
        for date in dates:
            for emp in self.employee_ids:
                for cust in self.route_id.partner_id:
                    vals.append({
                        'name': f"{self.route_id.name} - {emp.name} - {cust.name} - {date}",
                        'user_id': emp.id,
                        'partner_id': cust.id,
                        'date': date,
                        'date_start': date,
                        'route_assignment_id': self.id,
                        'company_id': self.company_id.id,
                        'field_visit_plan_type': 'customer_wise',
                        'allday': True,
                        'visit_origin': 'route_wise',
                    })
        return vals

    # def create_visits(self, days=7):
    #     """Create field visits based on recurrence rules."""
    #     new_dates = self._get_new_visit_dates(days)
    #     if not new_dates:
    #         return self.env['field.visit']
    #
    #     visit_vals = self._prepare_visit_values(new_dates)
    #     visits = self.env['field.visit'].create(visit_vals)
    #     return visits
    def create_visits(self, days=7):
        """Create field visits based on recurrence rules.
           Each run will create 'days' new visits without duplicates.
        """
        FieldVisit = self.env['field.visit']

        # compute next block of dates after last created visit
        new_dates = self._get_new_visit_dates(days)
        if not new_dates:
            return FieldVisit  # nothing new

        # prepare all potential visit values
        visit_vals = self._prepare_visit_values(new_dates)

        # collect all existing keys for this assignment (emp + partner + date)
        existing_keys = set(
            (v.user_id.id, v.partner_id.id, v.date)
            for v in FieldVisit.search([('route_assignment_id', '=', self.id)])
        )

        # filter only new ones
        to_create = []
        for vals in visit_vals:
            key = (vals['user_id'], vals['partner_id'], vals['date'])
            if key not in existing_keys:
                to_create.append(vals)

        if not to_create:
            return FieldVisit  # nothing to create

        visits = FieldVisit.create(to_create)
        return visits

    def action_view_visits(self):
        return {
            'name': 'Generated Visits',
            'type': 'ir.actions.act_window',
            'res_model': 'field.visit',
            'view_mode': 'tree,form',
            'domain': [('route_assignment_id', '=', self.id)],
        }

    @api.model
    def cron_create_visits(self):
        for assignment in self.search([]):
            assignment.create_visits(7)


class RouteAssignmentCreateVisitsWizard(models.TransientModel):
    _name = 'route.assignment.create.visits.wizard'
    _description = 'Create Visits Wizard for Route Assignment'

    route_assignment_id = fields.Many2one('route.assignment', string='Route Assignment',
                                          required=True,
                                          default=lambda self: self.env.context.get('active_id'))
    days = fields.Integer(string='Days Ahead', default=7, required=True)
    preview_dates = fields.Text(string='Dates to Create', compute='_compute_preview_info', readonly=True)
    visits_to_create = fields.Integer(string='Total Visits to Create', compute='_compute_preview_info', readonly=True)
    employee_count = fields.Integer(string='Employees', compute='_compute_employee_count', readonly=True)

    @api.depends('route_assignment_id.employee_ids')
    def _compute_employee_count(self):
        for rec in self:
            rec.employee_count = len(rec.route_assignment_id.employee_ids)

    @api.depends('route_assignment_id', 'days')
    def _compute_preview_info(self):
        for wizard in self:
            if wizard.route_assignment_id and wizard.days > 0:
                new_dates = wizard.route_assignment_id._get_new_visit_dates(wizard.days)
                wizard.visits_to_create = len(new_dates) * len(wizard.route_assignment_id.employee_ids)
                if new_dates:
                    dates_str = [str(d) for d in new_dates[:10]]
                    if len(new_dates) > 10:
                        dates_str.append(f"... and {len(new_dates)-10} more")
                    wizard.preview_dates = '\n'.join(dates_str)
                else:
                    wizard.preview_dates = "No new visits to create."
            else:
                wizard.preview_dates = "Please select a valid route assignment and days."
                wizard.visits_to_create = 0

    def action_create_visits(self):
        if not self.route_assignment_id:
            raise UserError("Please select a route assignment.")
        if self.days <= 0:
            raise UserError("Days must be greater than 0.")
        if not self.route_assignment_id.employee_ids:
            raise UserError("No employees assigned.")

        visits = self.route_assignment_id.create_visits(self.days)
        if visits:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Created Visits ({len(visits)})',
                'res_model': 'field.visit',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', visits.ids)],
                'target': 'current',
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'No Visits Created',
                'message': 'No new visits to create. All visits may already exist.',
                'type': 'warning',
                'sticky': False,
            }
        }

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
