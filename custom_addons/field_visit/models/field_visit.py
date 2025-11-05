from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime, time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import pytz


class Partner(models.Model):
    _inherit = ['res.partner']

    employee_ids = fields.One2many(
        'hr.employee', 'work_contact_id', string='Employees', groups="hr.group_hr_user",
        help="Related employees based on their private address")
    employees_count = fields.Integer(compute='_compute_employees_count', groups="hr.group_hr_user")

    def _compute_employees_count(self):
        for partner in self:
            partner.employees_count = len(partner.employee_ids.filtered(lambda e: e.company_id in self.env.companies))

    # *vruti*
    def action_open_visits(self):
        self.ensure_one()
        return {
            'name': _('Related Visits'),
            'type': 'ir.actions.act_window',
            'res_model': 'field.visit',
            'view_mode': 'form',
            **({'domain': [('partner_id', '=', self.id)]} if self.employees_count > 1 else {
                'context': {'default_partner_id': self.id}}),
        }


# *vruti*

class FieldVisitTimesheet(models.Model):
    _name = "field.visit.timesheet"
    _description = "Timesheet Entry"

    visit_id = fields.Many2one(
        comodel_name="field.visit",
        string="Visit",
        required=True,
        ondelete='cascade',
    )
    start_time = fields.Datetime(string="Start Time", required=True)
    end_time = fields.Datetime(string="End Time")
    total_working_time = fields.Float(string="Total Working Time", compute="_compute_total_working_time", store=True)

    start_address = fields.Char(string="Start Address")
    end_address = fields.Char(string="End Address")
    start_latitude = fields.Float(string="Start Latitude", digits=(16, 8))
    start_longitude = fields.Float(string="Start Longitude", digits=(16, 8))
    end_latitude = fields.Float(string="End Latitude", digits=(16, 8))
    end_longitude = fields.Float(string="End Longitude", digits=(16, 8))
    visit_name = fields.Char(
        string="Visit Name",
        related='visit_id.name',
        store=True
    )

    customer_line_id = fields.Many2one(
        'field.visit.customer.line',
        string="Customer Visit Line",
        ondelete='cascade',
    )

    analytic_line_id = fields.Many2one('account.analytic.line', string="Analytic Line", ondelete='cascade')

    customer_id = fields.Many2one(
        'res.partner',
        string="Customer",
        help="Customer for this timesheet (only required for city-wise visits)."
    )

    # Add this method to handle deletion
    def unlink(self):
        # Delete associated analytic lines first
        analytic_lines = self.mapped('analytic_line_id')
        result = super().unlink()
        if analytic_lines:
            analytic_lines.unlink()
        return result

    actual_user_id = fields.Many2one(
        'res.users',
        string="Actual User",
        default=lambda self: self.env.user,
        required=True
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        compute='_compute_employee_id',
        store=True
    )

    is_manual = fields.Boolean(
        string="Manual Entry",
        default=False,
        help="Checked if this timesheet was created manually by an admin instead of normal start/stop work."
    )

    @api.depends('actual_user_id')
    def _compute_employee_id(self):
        for record in self:
            if record.actual_user_id:
                employee = self.env['hr.employee'].search([
                    ('user_id', '=', record.actual_user_id.id)
                ], limit=1)
                record.employee_id = employee.id if employee else False
            else:
                record.employee_id = False

    @api.depends('start_time', 'end_time')
    def _compute_total_working_time(self):
        for record in self:
            if record.start_time and record.end_time:
                record.total_working_time = (record.end_time - record.start_time).total_seconds() / 3600.0
            else:
                record.total_working_time = 0.0

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("manual_timesheet_entry"):
            res["is_manual"] = True
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # detect manual entry by context
            if self.env.context.get("manual_timesheet_entry", False):
                vals["is_manual"] = True

        records = super().create(vals_list)

        for rec in records:

            visit = rec.visit_id
            enable_flag = self.env.company.enable_planned_approval

            # 🔹 State validation
            if enable_flag and visit.state != 'approved':
                raise ValidationError(_("You can only create timesheet entries when the visit is approved."))
            elif not enable_flag and visit.state not in ['draft', 'approved']:
                raise ValidationError(
                    _("You can only create timesheet entries when the visit is in Draft or Approved state.")
                )

            # 🔹 If parent is city-wise, move timesheet to a child visit
            if visit.field_visit_plan_type == 'city_wise' and rec.customer_id:
                customer = rec.customer_id

                # 1. Find or create child visit for this customer
                child_visit = self.env['field.visit'].search([
                    ('parent_visit_id', '=', visit.id),
                    ('partner_id', '=', customer.id),
                    ('field_visit_plan_type', '=', 'customer_wise'),
                ], limit=1)

                if not child_visit:
                    child_visit = self.env['field.visit'].create({
                        'parent_visit_id': visit.id,
                        'field_visit_plan_type': 'customer_wise',
                        'state_id': visit.state_id.id,
                        'city_id': visit.city_id.id,
                        'user_id': visit.user_id.id,
                        'partner_id': customer.id,
                        'state': 'approved',  # Admin override
                        'visit_origin': 'city_wise',
                        # 🔹 Copy objectives and sub-objectives
                        'visit_objective': [(6, 0, visit.visit_objective.ids)],
                        'sub_objective_ids': [(6, 0, visit.sub_objective_ids.ids)],

                        # 🔹 Copy joint visit users
                        'joint_visit_user_ids': [(6, 0, visit.joint_visit_user_ids.ids)],
                        # 🔹 Planned date/time if needed
                        # 'date_start': visit.date_start,
                        # 'date': visit.date,

                    })

                    # Also create customer line in parent
                    self.env['field.visit.customer.line'].create({
                        'visit_id': visit.id,
                        'partner_id': customer.id,
                        'child_visit_id': child_visit.id,
                    })

                # 2. Move timesheet to child visit
                rec.visit_id = child_visit.id

            # 🔹 Create Analytic Line if not exists
            if not rec.analytic_line_id and rec.start_time and rec.end_time:
                default_category = self.env['custom.timesheet.category'].search([('code', '=', 'FIELD_VISIT')], limit=1)
                if not default_category:
                    raise ValidationError("Please define a timesheet category with code 'FIELD_VISIT'.")

                duration = (rec.end_time - rec.start_time).total_seconds() / 3600

                analytic_line = self.env['account.analytic.line'].create({
                    'name': f'Visit: {rec.visit_id.name} - {rec.actual_user_id.name}',
                    'user_id': rec.actual_user_id.id,
                    'category_id': default_category.id,
                    'source_model': 'field.visit.timesheet',
                    'source_record_id': rec.id,
                    'start_address': rec.start_address,
                    'end_address': rec.end_address,
                    'date_time': rec.start_time,
                    'end_date_time': rec.end_time,
                    'unit_amount': duration,
                })
                rec.analytic_line_id = analytic_line.id

        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            enable_flag = self.env.company.enable_planned_approval
            if enable_flag and rec.visit_id.state != 'approved':
                raise ValidationError(_("You can only update timesheet entries when the visit is approved."))
            elif not enable_flag and rec.visit_id.state not in ['draft', 'approved']:
                raise ValidationError(
                    _("You can only update timesheet entries when the visit is in Draft or Approved state."))

            if rec.analytic_line_id and rec.start_time and rec.end_time:
                duration = (rec.end_time - rec.start_time).total_seconds() / 3600
                rec.analytic_line_id.write({
                    'start_address': rec.start_address,
                    'end_address': rec.end_address,
                    'date_time': rec.start_time,
                    'end_date_time': rec.end_time,
                    'unit_amount': duration,
                })
        return res


class FieldVisitCustomerLine(models.Model):
    _name = "field.visit.customer.line"
    _description = "Field Visit Customer Line"
    _order = "sequence, id"

    visit_id = fields.Many2one('field.visit', string="City Visit", required=True, ondelete="cascade")
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    state = fields.Selection([
        ("draft", "Draft"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancel", "Cancel"),
    ], string="Status", default="draft")
    timesheet_ids = fields.One2many('field.visit.timesheet', 'customer_line_id', string="Timesheets")
    is_work_started = fields.Boolean(string="Work Started", default=False)
    show_time_control = fields.Selection([
        ('start', 'Start Work'),
        ('stop', 'Stop Work'),
    ], string="Work Control", default='start')

    child_visit_id = fields.Many2one('field.visit', string="Customer Visit")
    child_visit_name = fields.Char(
        string="Visit Name",
        related="child_visit_id.name",
        store=False,
    )

    def unlink(self):
        # Check if customer lines have timesheet entries
        for line in self:
            if line.timesheet_ids:
                raise ValidationError(_(
                    "This customer visit has timesheet entries referencing it. "
                    "Before removing this customer visit, you have to remove these timesheet entries."
                ))

        return super().unlink()

    def action_open_child_visit(self):
        self.ensure_one()
        if not self.child_visit_id:
            raise UserError(_("No linked customer visit found."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'field.visit',
            'view_mode': 'form',
            'res_id': self.child_visit_id.id,
            'target': 'current',
        }


class CityWiseStartWorkWizard(models.TransientModel):
    _name = 'city.wise.start.work.wizard'
    _description = 'City Wise Start Work Wizard'

    visit_id = fields.Many2one('field.visit', string="City Visit", required=True)
    customer_ids = fields.Many2one(
        'res.partner',
        string=" Select Customers for visit",
        domain="[('city_id', '=', city_id)]"
    )
    city_id = fields.Many2one('res.city', string="City", related="visit_id.city_id", readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            visit = self.env['field.visit'].browse(self.env.context['active_id'])
            res['visit_id'] = visit.id
        return res

    def action_start_city_work(self):
        self.ensure_one()

        if not self.customer_ids:
            raise UserError(_("Please select at least one customer to start work."))

        new_visits = self.env['field.visit']
        customer_lines = []

        for customer in self.customer_ids:
            # 1. Create child visit
            stage = self.visit_id.state if self.visit_id.state == 'approved' else 'draft'
            child_visit = self.env['field.visit'].create({
                'parent_visit_id': self.visit_id.id,
                'field_visit_plan_type': 'customer_wise',
                'state_id': self.visit_id.state_id.id,
                'city_id': self.city_id.id,
                'user_id': self.visit_id.user_id.id,
                'partner_id': customer.id,
                'state': stage,
                'visit_origin': 'city_wise',
                # 🔹 Copy objectives
                'visit_objective': [(6, 0, self.visit_id.visit_objective.ids)],
                'sub_objective_ids': [(6, 0, self.visit_id.sub_objective_ids.ids)],

                # 🔹 Copy joint visit users
                'joint_visit_user_ids': [(6, 0, self.visit_id.joint_visit_user_ids.ids)],

                # 🔹 Copy planned date range
                # 'date_start': self.visit_id.date_start,
                # 'date': self.visit_id.date,
            })
            new_visits |= child_visit

            # 2. Immediately trigger its start work button
            child_visit.button_start_work()

            timesheet = self.env['field.visit.timesheet'].search(
                [('visit_id', '=', child_visit.id)],
                order="id desc",
                limit=1
            )
            if timesheet and timesheet.start_time:
                child_visit.write({
                    'date_start': timesheet.start_time,  # Use start_time instead of check_in
                    'date': timesheet.start_time,  # Use start_time instead of check_in
                })

            # 3. Create customer line
            line = self.env['field.visit.customer.line'].create({
                'visit_id': self.visit_id.id,
                'partner_id': customer.id,
                'child_visit_id': child_visit.id,
            })
            customer_lines.append(line.id)

        # 4. Return action:
        if len(new_visits) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'field.visit',
                'res_id': new_visits.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'field.visit',
                'res_id': self.visit_id.id,
                'view_mode': 'form',
                'target': 'current',
            }


class StartWorkWizard(models.TransientModel):
    _name = 'start.work.wizard'
    _description = 'Start Work Wizard'

    visit_id = fields.Many2one('field.visit', string="Visit", required=True)

    def action_start_work(self):
        user_id = self.visit_id.user_id

        ongoing_visit = self.env['field.visit'].search([
            ('user_id', '=', user_id.id),
            ('is_work_started', '=', True),
            ('id', '!=', self.id)
        ], limit=1)

        if ongoing_visit:
            raise ValidationError(_(
                "The salesperson is already working on another visit: '%s'. Please stop work on that visit first."
            ) % ongoing_visit.name)

        timesheet = self.env['field.visit.timesheet'].create({
            'visit_id': self.visit_id.id,
            'start_time': fields.Datetime.now(),
        })

        self.visit_id.timesheet_ids = [(4, timesheet.id)]

        self.visit_id.show_time_control = 'stop'
        self.visit_id.is_work_started = True

        return {'type': 'ir.actions.act_window_close'}


class EndWorkWizard(models.TransientModel):
    _name = 'end.work.wizard'
    _description = 'End Work Wizard'

    visit_id = fields.Many2one('field.visit', string="Visit", required=True)

    # Check-out specific fields
    is_productive_call = fields.Boolean(string="Productive Call", default=False)
    is_objective_met = fields.Boolean(string="Objective Met")
    sub_objective_ids = fields.Many2many(
        'visit.subobjective',
        string="Sub-objectives Achieved",
        domain="[('visit_objective_id', 'in', visit_objective_ids)]"
    )
    product_ids = fields.Many2many(
        'product.product',
        string="Products Demonstrated"
    )

    # Sample products
    sample_product_lines = fields.One2many(
        'end.work.wizard.sample.line',
        'wizard_id',
        string="Sample Products Given"
    )

    rating = fields.Selection([
        ('0', 'Very Low'),
        ('1', 'Low'),
        ('2', 'Medium'),
        ('3', 'High'),
        ('4', 'Very High'),
        ('5', 'Outstanding')
    ], string="Visit Rating")

    schedule_next_visit = fields.Boolean(string="Schedule Next Visit")
    next_visit_datetime = fields.Datetime(string="Next Visit Date/Time")
    place_order = fields.Boolean(string="Place Order")
    call_conclusion = fields.Text(string="Call Summary & Next Steps")

    # Location fields (hidden in UI but used for geofencing)
    latitude = fields.Float(string="Latitude", digits=(10, 7))
    longitude = fields.Float(string="Longitude", digits=(10, 7))
    location_address = fields.Char(string="Current Address", readonly=True)

    visit_objective_ids = fields.Many2many(
        'visit.objective',
        related='visit_id.visit_objective',
        string="Visit Objectives"
    )

    @api.constrains('next_visit_datetime', 'schedule_next_visit')
    def _check_next_visit_datetime(self):
        for wizard in self:
            if wizard.schedule_next_visit and wizard.next_visit_datetime:
                now = fields.Datetime.now()
                if wizard.next_visit_datetime < now:
                    raise ValidationError(_("Next visit date/time must be in the future."))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_visit_id'):
            visit = self.env['field.visit'].browse(self.env.context['default_visit_id'])
            res['visit_objective_ids'] = visit.visit_objective.ids
        return res

    @api.onchange('is_productive_call')
    def _onchange_is_productive_call(self):
        """Reset fields when productive call is False"""
        if not self.is_productive_call:
            self.is_objective_met = False
            self.sub_objective_ids = [(5, 0, 0)]
            self.product_ids = [(5, 0, 0)]
            self.sample_product_lines = [(5, 0, 0)]
            self.rating = False
            self.schedule_next_visit = False
            self.next_visit_datetime = False
            self.place_order = False

    @api.onchange('schedule_next_visit')
    def _onchange_schedule_next_visit(self):
        """Reset next visit datetime when schedule_next_visit is False"""
        if not self.schedule_next_visit:
            self.next_visit_datetime = False

    def action_add_sample_line(self):
        """Helper method to add a new sample product line"""
        if not self.product_ids:
            raise ValidationError(_("Please select products first before adding sample products."))

        self.sample_product_lines = [(0, 0, {'quantity': 1.0})]
        return {
            'type': 'ir.actions.do_nothing',
        }

    def _validate_sample_products(self):
        """Validate that sample products are only from selected products"""
        if self.sample_product_lines and self.product_ids:
            for line in self.sample_product_lines:
                if line.product_id and line.product_id not in self.product_ids:
                    raise ValidationError(_(
                        "Sample product '%s' is not in the list of demonstrated products. "
                        "Please select it in the Products Demonstrated field first."
                    ) % line.product_id.name)

    def action_end_work(self):
        visit = self.visit_id
        company = self.env.company

        # Check if current user has a running timer for this visit
        user_timer = self.env['account.analytic.line'].search([
            ('source_model', '=', 'field.visit'),
            ('source_record_id', '=', visit.id),
            ('user_id', '=', self.env.user.id),
            ('is_timer_running', '=', True),
        ], limit=1)

        if not user_timer:
            raise ValidationError(_("You don't have a running timer for this visit."))

        if company.checkin_out_difference > 0 and visit.timesheet_ids:
            last_timesheet = visit.timesheet_ids[-1]
            if last_timesheet.start_time and fields.Datetime.now():
                diff_minutes = (fields.Datetime.now() - last_timesheet.start_time).total_seconds() / 60.0
                if diff_minutes < company.checkin_out_difference:
                    raise ValidationError(_(
                        "You cannot check out before %s minutes. "
                        "Please complete the minimum work duration."
                    ) % company.checkin_out_difference)

        # Validate sample products
        # self._validate_sample_products()

        # Get address from coordinates
        latitude = self.latitude or self.env.context.get("default_latitude", 0.0)
        longitude = self.longitude or self.env.context.get("default_longitude", 0.0)
        address = self.env['account.analytic.line'].get_address_from_coordinates(latitude, longitude)

        # Geofence check
        self.env['account.analytic.line']._validate_geofence_checkout_visit(visit, latitude, longitude)

        user_timer.write({
            'end_latitude': latitude,
            'end_longitude': longitude,
            'end_address': address,
        })

        # Stop the timer for this user
        user_timer.action_stop_timer()

        # Update the corresponding field visit timesheet entry
        user_timesheet = self.env['field.visit.timesheet'].search([
            ('visit_id', '=', visit.id),
            ('actual_user_id', '=', self.env.user.id),
            ('end_time', '=', False)
        ], order='id desc', limit=1)

        if user_timesheet:
            user_timesheet.write({
                'end_time': fields.Datetime.now(),
                'end_address': address,
                'end_latitude': latitude,
                'end_longitude': longitude,
            })

        # Store check-out details for this user
        checkout_vals = {
            'visit_id': visit.id,
            'user_id': self.env.user.id,  # Track which user checked out
            'is_productive_call': self.is_productive_call,
            'is_objective_met': self.is_objective_met,
            'sub_objective_ids': [(6, 0, self.sub_objective_ids.ids)],
            'product_ids': [(6, 0, self.product_ids.ids)],
            'rating': self.rating,
            'schedule_next_visit': self.schedule_next_visit,
            'next_visit_datetime': self.next_visit_datetime,
            'place_order': self.place_order,
            'call_conclusion': self.call_conclusion,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'address': self.location_address,
        }

        # Create sample product lines in checkout record
        if self.sample_product_lines:
            sample_lines = []
            for line in self.sample_product_lines:
                if line.product_id:  # Only create lines with products
                    sample_lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'quantity': line.quantity,
                    }))
            checkout_vals['sample_product_line_ids'] = sample_lines

        self.env['field.visit.checkout'].create(checkout_vals)

        if self.schedule_next_visit and self.next_visit_datetime:
            now = fields.Datetime.now()
            if self.next_visit_datetime < now:
                raise ValidationError(_("Next visit date/time must be in the future."))

            valid_sub_objectives = self.sub_objective_ids.filtered(
                lambda so: so.visit_objective_id.id in self.visit_objective_ids.ids
            )

            new_visit_vals = {
                'name': self.env['ir.sequence'].next_by_code('field.visit') or "New Visit",
                'user_id': self.env.user.id,
                'date_start': self.next_visit_datetime,
                'date': self.next_visit_datetime,
                'visit_objective': [(6, 0, self.visit_objective_ids.ids)],
                'sub_objective_ids': [(6, 0, valid_sub_objectives.ids)],
                'company_id': visit.company_id.id,
                'field_visit_plan_type': visit.field_visit_plan_type,
            }

            # Customer vs. Official work logic
            if visit.field_visit_plan_type == "customer_wise":
                new_visit_vals['partner_id'] = visit.partner_id.id
            elif visit.field_visit_plan_type == "official_work":
                new_visit_vals['partner_id'] = False

            # Copy route/team if they exist
            if hasattr(visit, 'route_id') and visit.route_id:
                new_visit_vals['route_id'] = visit.route_id.id
            if hasattr(visit, 'team_id') and visit.team_id:
                new_visit_vals['team_id'] = visit.team_id.id

            # Handle joint visit (assuming Many2many field like joint_user_ids on field.visit)
            if hasattr(visit, 'joint_visit_user_ids') and visit.joint_visit_user_ids:
                new_visit_vals['joint_visit_user_ids'] = [(6, 0, visit.joint_visit_user_ids.ids)]

            self.env['field.visit'].create(new_visit_vals)
        # Check if any other users are still working on this visit
        other_running_timers = self.env['account.analytic.line'].search([
            ('source_model', '=', 'field.visit'),
            ('source_record_id', '=', visit.id),
            ('user_id', '!=', self.env.user.id),
            ('is_timer_running', '=', True),
        ])

        # If no other users are working, update the general work status
        if not other_running_timers:
            visit.is_work_started = False
            visit.show_time_control = 'start'

        return {'type': 'ir.actions.act_window_close'}


class EndWorkWizardSampleLine(models.TransientModel):
    _name = 'end.work.wizard.sample.line'
    _description = 'End Work Wizard Sample Line'

    wizard_id = fields.Many2one('end.work.wizard', string="Wizard")
    product_id = fields.Many2one('product.product', string="Product", required=True)
    quantity = fields.Float(string="Quantity", default=1.0)


class FieldVisitCheckout(models.Model):
    _name = "field.visit.checkout"
    _description = "Field Visit Check-out Details"

    visit_id = fields.Many2one('field.visit', string="Visit", required=True, ondelete="cascade")
    is_productive_call = fields.Boolean(string="Productive Call")
    is_objective_met = fields.Boolean(string="Objective Met")
    sub_objective_ids = fields.Many2many('visit.subobjective', string="Sub-objectives")
    product_ids = fields.Many2many('product.product', string="Products Shown")
    user_id = fields.Many2one('res.users', string="User", required=True, default=lambda self: self.env.user)
    # Sample product lines
    sample_product_line_ids = fields.One2many(
        'field.visit.checkout.sample.line',
        'checkout_id',
        string="Sample Products"
    )

    rating = fields.Selection([
        ('0', 'Very Low'),
        ('1', 'Low'),
        ('2', 'Medium'),
        ('3', 'High'),
        ('4', 'Very High'),
        ('5', 'Outstanding')
    ], string="Rating")

    schedule_next_visit = fields.Boolean(string="Schedule Next Visit")
    next_visit_datetime = fields.Datetime(string="Next Visit Date/Time")
    place_order = fields.Boolean(string="Place Order")
    call_conclusion = fields.Text(string="Call Conclusion")
    latitude = fields.Float(string="Latitude", digits=(10, 7))
    longitude = fields.Float(string="Longitude", digits=(10, 7))
    address = fields.Char(string="Address")


class FieldVisitCheckoutSampleLine(models.Model):
    _name = 'field.visit.checkout.sample.line'
    _description = 'Field Visit Checkout Sample Line'

    checkout_id = fields.Many2one('field.visit.checkout', string="Checkout", required=True, ondelete="cascade")
    product_id = fields.Many2one('product.product', string="Product", required=True)
    quantity = fields.Float(string="Quantity", default=1.0, required=True)


class FieldVisit(models.Model):
    # _name = "crm.salesperson.planner.visit"
    _name = "field.visit"
    _description = "Field Visit"
    _order = "date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    _rec_name = "name"

    _systray_view = 'activity'

    name = fields.Char(
        string="Visit Number",
        required=True,
        default="Draft",
        copy=False,
    )

    # partner_id = fields.Many2one(
    #     comodel_name="res.partner",
    #     string="Customer",
    #     domain=lambda self: self.env['partner.domain.mixin']._get_partner_domain(),
    # )

    def _get_customer_domain(self):
        """Apply domain only if customer_visibility module is installed"""
        module_installed = self.env['ir.module.module'].sudo().search([
            ('name', '=', 'customer_visibility'),
            ('state', '=', 'installed')
        ], limit=1)
        if module_installed:
            return self.env['partner.domain.mixin']._get_partner_domain()
        return []

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Customer",
        domain=_get_customer_domain,
    )

    parent_visit_id = fields.Many2one('field.visit', string="Parent Visit")
    child_visit_ids = fields.One2many('field.visit', 'parent_visit_id', string="Customer Visits")

    partner_phone = fields.Char(string="Phone", related="partner_id.phone")
    partner_mobile = fields.Char(string="Mobile", related="partner_id.mobile")

    visit_origin = fields.Selection([
        ('manual', 'Manual'),
        ('city_wise', 'City Wise'),
        ('route_wise', 'Route Wise'),
    ], string="Visit Origin", default='manual', readonly=True)

    def _get_bottom_iterative(self, root_employee, children_map):
        """Return all reportees iteratively, cycle-safe."""
        result = []
        seen = set()
        stack = [root_employee.id]

        while stack:
            current_id = stack.pop()
            if current_id in seen:
                continue
            seen.add(current_id)
            if current_id != root_employee.id:  # exclude root employee
                result.append(current_id)
            stack.extend(children_map.get(current_id, []))

        return result

    date_start = fields.Datetime(string='Start Date')

    date = fields.Datetime(string='Expiration Date', index=True, tracking=True,
                           help="Date on which this project ends. The timeframe defined on the project is taken into account when viewing its planning.")

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Salesperson",
        index=True,
        tracking=True,
        default=lambda self: self.env.user,
        domain=lambda self: [
            ("groups_id", "in", self.env.ref("sales_team.group_sale_salesman").id)
        ],
    )

    joint_visit_user_ids = fields.Many2many(
        'res.users',
        string="Joint Visit Users",
        compute='_compute_joint_visit_user_ids',
        store=True,
        readonly=False,
    )

    @api.constrains('user_id')
    def _check_salesperson_permission(self):
        for rec in self:
            user = self.env.user
            # Allow only normal Field Visit Users (not managers)
            if (
                user.has_group("field_visit.group_field_visit_user")
                and not user.has_group("field_visit.group_field_visit_manager")
                and not user.has_group("field_visit.group_field_visit_managers")
            ):
                # If user selects a salesperson different than themselves → Error
                if rec.user_id and rec.user_id != user:
                    raise ValidationError(
                        "You can only assign yourself as Salesperson because you are a Field Visit User."
                    )

    @api.depends('user_id')
    def _compute_joint_visit_user_ids(self):
        for rec in self:
            rec.joint_visit_user_ids = False
            if rec.user_id:
                users = self.env['field.visit']._get_allowed_joint_visit_users(rec.user_id)
                rec.joint_visit_user_ids = users[:0]

    def _get_allowed_joint_visit_users(self, user):
        """
        Return allowed users for a given res.users record based on hierarchy:
        - 'top'         : All managers above current user
        - 'bottom'      : All subordinates below current user
        - 'top_bottom'  : Go up to top managers, then include everyone under them
                          (if already top, include all subordinates)
        - 'all'         : All users in same company
        """
        hierarchy = (
                user.joint_visit_hierarchy
                or user.company_id.joint_visit_hierarchy
                or 'all'
        )

        if hierarchy == 'top':
            allowed = self._get_top_managers_users(user)

        elif hierarchy == 'bottom':
            allowed = self._get_bottom_subordinates_users(user)

        elif hierarchy == 'top_bottom':
            # Step 1: get top managers
            top_managers = self._get_top_managers_users(user)
            if not top_managers:
                # If no top manager (e.g., CEO), use self
                top_managers = user

            # Step 2: include those managers + everyone below them
            allowed = top_managers
            for manager_user in top_managers:
                sub_users = self._get_bottom_subordinates_users(manager_user)
                allowed |= sub_users

        else:
            company = [user.company_id.id] + user.company_id.child_ids.ids + user.company_ids.ids

            allowed = self.env['res.users'].search([('company_id', 'in', company)])

        # Remove the current user
        allowed = allowed - user
        return allowed

    def _get_top_managers_users(self, user):
        """
        Walk upward from a res.users record to collect all managers (employee_id.parent_id chain).
        Return res.users recordset.
        """
        managers = self.env['res.users']
        current_user = user
        while current_user and current_user.employee_id and current_user.employee_id.parent_id:
            manager_user = current_user.employee_id.parent_id.user_id
            if manager_user and manager_user not in managers:
                managers |= manager_user
                current_user = manager_user
            else:
                break
        return managers

    def _get_bottom_subordinates_users(self, user, direct_only=False):
        """
        Get subordinates downward from a res.users record.
        - direct_only=True  => only immediate children
        - direct_only=False => all levels (recursive)
        """
        if not user.employee_id:
            return self.env['res.users']

        subordinates = user.employee_id.subordinate_ids  # recursive

        return subordinates.mapped('user_id').filtered(lambda u: u)

    # Dhruti start
    route_assignment_id = fields.Many2one(
        'route.assignment',
        string='Route Assignment',
        help='Route assignment that generated this visit'
    )

    @api.model
    def _check_plan_lock_period_for_creation(self):
        """Check if current date is within plan lock period for creation/submission"""
        company = self.env.company

        # Check if plan lock period is enabled
        if not company.plan_lock_period:
            return True  # No restrictions if disabled

        # NO EXCEPTIONS FOR ADMINISTRATORS - everyone is restricted from creating/submitting
        today = fields.Date.today()
        plan_open_date = company.plan_open_date
        plan_close_date = company.plan_close_date

        if not plan_open_date or not plan_close_date:
            return True  # No restrictions if dates not set

        # Check if today is within the lock period
        if plan_open_date <= today <= plan_close_date:
            raise ValidationError(_(
                "You cannot create new plans or submit plans during the plan lock period "
                "(from %s to %s). Please wait until the lock period is over."
            ) % (plan_open_date, plan_close_date))

        return True

    def _check_edit_permission_during_lock_period(self):
        """Check if user has permission to edit during lock period"""
        company = self.env.company

        # Check if plan lock period is enabled
        if not company.plan_lock_period:
            return True  # No restrictions if disabled

        today = fields.Date.today()
        plan_open_date = company.plan_open_date
        plan_close_date = company.plan_close_date

        if not plan_open_date or not plan_close_date:
            return True  # No restrictions if dates not set

        # Check if today is within the lock period
        if plan_open_date <= today <= plan_close_date:
            # Only administrators can edit during lock period
            if not (self.env.user.has_group('field_visit.group_field_visit_manager') or \
                    self.env.user.has_group('field_visit.group_field_visit_managers')):
                raise ValidationError(_(
                    "You cannot edit plans during the plan lock period "
                    "(from %s to %s). Only administrators can make changes."
                ) % (plan_open_date, plan_close_date))

        return True

    # Dhruti end

    description = fields.Html()
    justification = fields.Html()

    state = fields.Selection(
        string="Status",
        required=True,
        copy=False,
        tracking=True,
        selection=[
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("justify", "Justify"),
            ("validate", "Validate"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("completed", "Completed"),
            ("cancel", "Cancel"),
            ("incident", "Incident"),
        ],
        default="draft",
    )

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields=allfields, attributes=attributes)
        enable_flag = self.env.company.enable_planned_approval

        if not enable_flag:
            if 'state' in res:
                res['state']['selection'] = [
                    ("draft", "Draft"),
                    ("completed", "Completed"),
                    ("cancel", "Cancel"),
                ]
        return res

    close_reason_id = fields.Many2one(
        comodel_name="field.visit.close.reason", string="Close Reason"
    )
    close_reason_image = fields.Image(max_width=1024, max_height=1024, attachment=True)
    close_reason_notes = fields.Text()
    visit_template_id = fields.Many2one(
        comodel_name="field.visit.template", string="Visit Template"
    )
    calendar_event_id = fields.Many2one(
        comodel_name="calendar.event", string="Calendar Event"
    )

    field_visit_plan_type = fields.Selection(
        selection=lambda self: self._get_field_visit_plan_types(),
        string="Field Visit Types",
        required=True,
        default=lambda self: self._get_default_field_visit_plan_type(),
    )

    @api.model
    def _get_default_field_visit_plan_type(self):
        """Return the first available visit type based on company settings."""
        company = self.env.company
        if company.enable_city_wise:
            return 'city_wise'
        elif company.enable_customer_wise:
            return 'customer_wise'
        elif company.enable_official_work:  # Add this condition
            return 'official_work'
        return False

    @api.model
    def _get_field_visit_plan_types(self):
        """Return available selection values based on company settings."""
        company = self.env.company  # Get current user's company

        selection = []

        if company.enable_city_wise:
            selection.append(('city_wise', 'City-wise'))

        if company.enable_customer_wise:
            selection.append(('customer_wise', 'Customer-wise'))

        if company.enable_official_work:
            selection.append(('official_work', 'Official Work'))

        return selection

    state_id = fields.Many2one('res.country.state', string='State', domain=[('country_id.code', '=', 'IN')])
    city_id = fields.Many2one('res.city', string='City', domain="[('state_id', '=?', state_id)]")
    zip_code = fields.Many2many("city.zip", string='Area', domain="[('city_id', '=', [city_id])]")
    allday = fields.Boolean(string="All Day", default=True)

    # @api.constrains('date_start')
    # def _check_date_start_not_past(self):
    #     for rec in self:
    #         if rec.date_start and rec.date_start < datetime.now():
    #             raise ValidationError(_("Start Date&Time cannot be in the past. Please select correct Date&Time."))

    @api.onchange('city_id')
    def _onchange_city_id(self):
        for rec in self:
            if rec.city_id and not rec.state_id:
                rec.state_id = rec.city_id.state_id

    @api.onchange('allday')
    def _onchange_allday(self):
        if self.allday:
            # Get today's date in user's timezone
            today = fields.Date.context_today(self)

            # User timezone
            user_tz = self.env.user.tz or 'UTC'
            tz = pytz.timezone(user_tz)

            # Start and end in user's local timezone
            start_local = tz.localize(datetime.combine(today, time(hour=0, minute=0, second=0)))
            end_local = tz.localize(datetime.combine(today, time(hour=23, minute=59, second=0)))

            # Convert to UTC and assign as string
            self.date_start = start_local.astimezone(pytz.UTC).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            self.date = end_local.astimezone(pytz.UTC).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        else:
            self.date_start = False
            self.date = False

    @api.onchange('field_visit_plan_type')
    def _onchange_field_visit_plan_type(self):
        """Reset dependent fields when field_visit_plan_type changes"""
        for rec in self:
            if rec.field_visit_plan_type != 'city_wise':
                rec.state_id = False
                rec.city_id = False
                rec.zip_code = [(5, 0, 0)]

            # For official work, clear customer but keep objectives
            if rec.field_visit_plan_type == 'official_work':
                rec.partner_id = False

    @api.onchange('state_id')
    def _onchange_state(self):
        if self.state_id and self.state_id != self.city_id.state_id:
            self.city_id = False
            self.zip_code = False

    @api.onchange('city_id')
    def _onchange_city(self):
        if self.city_id and self.city_id != self.zip_code.city_id:
            self.zip_code = False

    display_name_customer_city = fields.Char(
        string="Customer / City",
        compute="_compute_display_name_customer_city"
    )

    @api.depends('field_visit_plan_type', 'partner_id', 'city_id')
    def _compute_display_name_customer_city(self):
        for record in self:
            value = ''
            if record.field_visit_plan_type == 'city_wise' and record.city_id:
                value = record.city_id.name
            elif record.field_visit_plan_type == 'customer_wise' and record.partner_id:
                value = record.partner_id.name
            elif record.field_visit_plan_type == 'official_work':
                value = _("Official Work")
            record.display_name_customer_city = value

    _sql_constraints = [
        (
            "field_visit_name",
            "UNIQUE (name)",
            "The visit number must be unique!",
        ),
    ]

    show_time_control = fields.Selection(
        selection=[
            ('start', 'Start Work'),
            ('stop', 'Stop Work'),
        ],
        string="Work Control",
        default='start',
    )

    timesheet_ids = fields.One2many(
        comodel_name="field.visit.timesheet",
        inverse_name="visit_id",
        string="Timesheets",
    )
    is_work_started = fields.Boolean(string="Work Started", default=False)
    visit_objective = fields.Many2many('visit.objective', string='Visit Objective',
                                       domain="[('visit_type', 'in', ['all', field_visit_plan_type])]")
    sub_objective_ids = fields.Many2many(
        comodel_name='visit.subobjective',
        string='Sub Objectives',
        domain="[('visit_objective_id', 'in', visit_objective)]",
    )

    customer_line_ids = fields.One2many(
        'field.visit.customer.line',
        'visit_id',
        string="Customer Visits",
        invisible="field_visit_plan_type != 'city_wise'",
        readonly=True,  # Add this line to make it read-only
    )
    is_unplanned = fields.Boolean("Is Unplanned Visit", default=False)

    # --------------------Dashboard-------------------------------
    @api.model
    def retrieve_dashboard(self, date_from=False, date_to=False):
        domain = []
        if date_from:
            domain.append(('date_start', '>=', date_from))
        if date_to:
            domain.append(('date_start', '<=', date_to))

        visits = self.search(domain)
        user = self.env.user

        # Define states (adjust to your model states)
        draft_states = ['draft']
        completed_states = ['completed']
        cancelled_states = ['cancel']

        user = self.env.user
        my_visits = visits.filtered(lambda v: v.user_id.id == user.id)

        my_visits_count = len(my_visits)
        my_completed_visits_count = len(my_visits.filtered(lambda v: v.state in completed_states))
        my_cancelled_visits_count = len(my_visits.filtered(lambda v: v.state in cancelled_states))
        my_draft_visits_count = len(my_visits.filtered(lambda v: v.state in draft_states))

        result = {
            'my_visits': my_visits_count,
            'my_draft_visits_count': my_draft_visits_count,
            'my_completed_visits_count': my_completed_visits_count,
            'my_cancelled_visits_count': my_cancelled_visits_count,
        }
        print(result)
        return result

    @api.depends('start_time', 'end_time')
    def _compute_total_working_time(self):
        for record in self:
            if record.start_time and record.end_time:
                record.total_working_time = (record.end_time - record.start_time).total_seconds() / 3600.0
            else:
                record.total_working_time = 0.0

    def button_start_work(self):
        """Direct start work without wizard"""
        self.ensure_one()

        company = self.env.company

        # Check if plan approval is required for check-in
        if company.check_in_with_plan:
            if self.state != 'approved':
                raise ValidationError(_(
                    "You can only check-in when the visit is approved. "
                    "Please wait for plan approval before checking in."
                ))

        enable_flag = self.env.company.enable_planned_approval
        if enable_flag and self.state != 'approved':
            raise ValidationError(_("You can only start work when the visit is approved."))

        if company.attendance_before_checkin:
            attendance = self.env['hr.attendance'].search([
                ('employee_id.user_id', '=', self.env.user.id),
                ('check_in', '!=', False),
                ('check_out', '=', False)
            ], limit=1)
            if not attendance:
                raise ValidationError(_(
                    "You must do attendance before starting a field visit."
                ))

        # For city-wise visits, open the customer selection wizard
        if self.field_visit_plan_type == 'city_wise':
            if not self.city_id:
                raise UserError(_("Please select a city before starting work for city-wise visits."))

            return {
                'name': _('Select Customers'),
                'type': 'ir.actions.act_window',
                'res_model': 'city.wise.start.work.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'active_id': self.id},
            }

        # Check if user already has a running timer
        running_timer = self.env['account.analytic.line'].search([
            ('user_id', '=', self.env.user.id),
            ('is_timer_running', '=', True),
            ('source_model', '=', 'field.visit')
        ], limit=1)

        if running_timer:
            raise ValidationError(
                f"You already have a running timer: {running_timer.name}"
            )

        latitude = self.env.context.get("default_latitude", 0.0)
        longitude = self.env.context.get("default_longitude", 0.0)

        # if not self.env.user.allow_without_location and (not latitude or not longitude):
        #     raise ValidationError(_("Location is required to check in / check out."))

        # Fallback: use partner geolocation if context is empty
        if not latitude or not longitude:
            if self.partner_id:
                latitude = self.partner_id.partner_latitude
                longitude = self.partner_id.partner_longitude

        # Geofence check
        self.env['account.analytic.line']._validate_geofence_checkin_visit(self, latitude, longitude)

        # Timesheet category
        default_category = self.env['custom.timesheet.category'].search([('code', '=', 'FIELD_VISIT')], limit=1)
        if not default_category:
            raise ValidationError("Please define a timesheet category with code 'FIELD_VISIT'.")

        address = self.env['account.analytic.line'].get_address_from_coordinates(latitude, longitude)

        # Create timesheet analytic line
        timesheet = self.env['account.analytic.line'].create({
            'name': f'Visit: {self.name} - {self.env.user.name}',
            'user_id': self.env.user.id,
            'category_id': default_category.id,
            'source_model': 'field.visit',
            'source_record_id': self.id,
            'start_latitude': latitude,
            'start_longitude': longitude,
            'start_address': address,
        })

        # # Register analytic line as belonging to this module
        # self.env['ir.model.data'].create({
        #     'module': 'field_visit',
        #     'name': f'analytic_line_{analytic_line.id}',
        #     'model': 'account.analytic.line',
        #     'res_id': analytic_line.id,
        #     'noupdate': False,
        # })

        # Create field visit timesheet entry for display
        if self.field_visit_plan_type in ['customer_wise', 'official_work']:
            field_visit_timesheet = self.env['field.visit.timesheet'].create({
                'visit_id': self.id,
                'start_time': fields.Datetime.now(),
                'start_address': address,
                'start_latitude': latitude,
                'start_longitude': longitude,

                # 'employee_id': self.user_id.id,
                'actual_user_id': self.env.user.id,
                'analytic_line_id': timesheet.id,
            })
            self.timesheet_ids = [(4, field_visit_timesheet.id)]

        self.is_work_started = True
        self.show_time_control = 'stop'

        return timesheet.action_start_timer()

    def button_end_work(self):

        return {

            'name': 'Stop Work',
            'type': 'ir.actions.act_window',
            'res_model': 'end.work.wizard',  # This should match the model name defined above
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_visit_id': self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        self._check_plan_lock_period_for_creation()
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        today_user = fields.Date.context_today(self)

        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("field.visit")

            if vals.get("date_start"):
                # Convert to datetime in user's timezone
                date_start_utc = fields.Datetime.to_datetime(vals["date_start"])
                date_start_user = date_start_utc.astimezone(user_tz)

                # Compare only by date for past validation
                if date_start_user.date() < today_user:
                    raise ValidationError(_("Start Date cannot be in the past. Please select a valid date."))

        visits = super().create(vals_list)

        for visit in visits:
            if visit.is_unplanned:
                visit.sudo().write({'state': 'approved'})

        for visit in visits:
            if visit.user_id and visit.date_start and visit.date:
                overlapping_visits = self.search([
                    ('id', '!=', visit.id),
                    ('user_id', '=', visit.user_id.id),
                    ('state', 'not in', ['cancel', 'completed']),
                    '|',
                    ('date_start', '<', visit.date),
                    ('date', '>', visit.date_start),
                ])
                for ov in overlapping_visits:
                    if ov.date and ov.date_start:
                        if visit.date_start < ov.date and visit.date > ov.date_start:
                            raise ValidationError(_(
                                "The salesperson already has a visit scheduled that overlaps with the proposed time."
                            ))

            partner_ids = [visit.partner_id.id]
            if self.env.user.partner_id:
                partner_ids.append(self.env.user.partner_id.id)
            visit.message_subscribe(partner_ids)

        return visits

    def action_draft(self):
        if self.state not in ["cancel", "incident", "completed"]:
            raise ValidationError(
                _("The visit must be in cancelled, incident or visited state")
            )
        if self.calendar_event_id:
            self.calendar_event_id.with_context(bypass_cancel_visit=True).unlink()
        self.write({"state": "draft"})

    def action_submitted(self):
        self._check_plan_lock_period_for_creation()
        if self.filtered(lambda a: not a.state == "draft"):
            raise ValidationError(_("The visit must be in draft state"))
        # events = self.create_calendar_event()
        # if events:
        #     self.browse(events.mapped("res_id")).write({"state": "submitted"})
        self.write({"state": "submitted"})

    show_submit_btn = fields.Boolean(compute="_compute_buttons")
    show_complete_btn = fields.Boolean(compute="_compute_buttons")
    show_justification_btn = fields.Boolean(compute="_compute_buttons")

    def _compute_buttons(self):
        for rec in self:
            flag = rec.env.company.enable_planned_approval
            rec.show_submit_btn = flag and rec.state == "draft"
            rec.show_complete_btn = (
                    (flag and rec.state in ("submitted", "approved"))
                    or (not flag and rec.state == "draft")
            )
            rec.show_justification_btn = flag

    def action_completed(self):
        enable_flag = self.env.company.enable_planned_approval

        # If approval flow is enabled, visit must be in 'approved' state
        if enable_flag:
            if self.state != "approved":
                raise ValidationError(_("The visit must be approved before marking it as completed."))
        # else:
        #     # If approval flow is disabled, visit must at least be submitted
        #     if self.state != "submitted":
        #         raise ValidationError(_("The visit must be in submitted state before completion."))

        # Check timesheets
        incomplete_timesheets = self.timesheet_ids.filtered(lambda t: not t.end_time)
        if incomplete_timesheets:
            raise ValidationError(
                _("You must stop the work before marking the visit as completed")
            )

        complete_timesheets = self.timesheet_ids.filtered(lambda t: t.start_time and t.end_time)
        if not complete_timesheets:
            raise ValidationError(
                _("At least one entry with both start and end times is required to mark the visit as completed.")
            )

        self.write({"state": "completed"})

    def action_cancel(self, reason_id, image=None, notes=None):
        if self.state not in ["draft", "submitted", "approved", "rejected", "justify"]:
            raise ValidationError(_("The visit must be in draft or submitted state"))
        if self.is_work_started:
            self.show_time_control = 'start'
            self.is_work_started = False

            if self.timesheet_ids:
                last_timesheet = self.timesheet_ids[-1]
                last_timesheet.end_time = fields.Datetime.now()
            else:
                raise ValidationError(_("No active timesheet found to end work."))

        if self.calendar_event_id:
            self.calendar_event_id.with_context(bypass_cancel_visit=True).unlink()
        self.write(
            {
                "state": "cancel",
                "close_reason_id": reason_id.id,
                "close_reason_image": image,
                "close_reason_notes": notes,
                'first_approved': False,
                'second_approved': False
            }
        )

    first_approved = fields.Boolean(string="First Approved", default=False, copy=False)
    second_approved = fields.Boolean(string="Second Approved", default=False, copy=False)

    def action_approve_first(self):
        """ First Approval """
        for visit in self:
            emp = visit.user_id.employee_ids
            current_user = self.env.user

            first_approver_users = emp.mapped('field_visit_first_approval')
            second_approver_users = emp.mapped('field_visit_second_approval')

            # Only first approver assigned → approve directly
            if first_approver_users and not second_approver_users:
                if current_user not in first_approver_users:
                    raise UserError("You are not authorized to approve this visit.")
                visit.write({'state': 'approved', 'second_approved': True})


            # Only second approver assigned → approve directly using first button
            elif second_approver_users and not first_approver_users:
                if current_user not in second_approver_users:
                    raise UserError("You are not authorized to approve this visit.")
                visit.write({'state': 'approved', 'second_approved': True})

            # Both approvers assigned → sequence enforced
            elif first_approver_users or second_approver_users:
                # if current_user not in first_approver_users:
                #     raise UserError("You are not authorized to approve this visit as first approver.")
                if visit.state not in ['submitted', 'justify']:
                    raise UserError("Visit must be in Submitted or Justify state for first approval.")
                visit.write({'state': 'validate', 'first_approved': True})

    def action_approve_second(self):
        """ Second Approval """
        for visit in self:
            emp = visit.user_id.employee_ids
            current_user = self.env.user

            first_approver = emp.field_visit_first_approval if emp else False
            second_approver = emp.field_visit_second_approval if emp else False

            # Only second approver assigned → approve directly
            if second_approver and not first_approver:
                if current_user != second_approver:
                    raise UserError("You are not authorized to approve this visit.")
                visit.write({'state': 'approved', 'second_approved': True})


            # Only first approver assigned → approve directly using second button
            elif first_approver and not second_approver:
                if current_user != first_approver:
                    raise UserError("You are not authorized to approve this visit.")
                visit.write({'state': 'approved', 'second_approved': True})


            # Both approvers assigned → sequence check
            elif first_approver and second_approver:
                if current_user != second_approver:
                    raise UserError("You are not authorized to approve as second approver.")
                if visit.state not in ['validate', 'justify']:
                    raise UserError("First approver must approve before second approver.")
                visit.write({
                    'state': 'approved',
                    'second_approved': True
                })


            # Only first approver assigned → second button not needed
            elif first_approver and not second_approver:
                raise UserError("Use 'First Approve' button. You are not second approver.")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Optionally set defaults here
        return res

    def action_reject(self):
        for rec in self:
            rec.state = 'rejected'

    def action_justify(self):
        self.write({'state': 'justify'})
        return {
            'name': 'Add Justification',
            'type': 'ir.actions.act_window',
            'res_model': 'field.visit.justification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_visit_id': self.id}
        }

    def action_bulk_cancel(self):
        for visit in self:
            if visit.state not in ['cancel', 'completed', 'incident']:
                wiz = self.env['field.visit.close.wiz'].with_context(
                    att_close_type='cancel',
                    active_id=visit.id,
                    active_ids=[visit.id]
                ).create({})
                wiz.action_close()

    def action_bulk_submitted(self):
        for visit in self:
            if visit.state == 'draft':
                visit.action_submitted()

    def action_bulk_approved(self):
        for visit in self:
            if visit.state == 'submitted':
                visit.action_completed()

    def _prepare_calendar_event_vals(self):
        partner_ids = []
        if self.partner_id:
            partner_ids.append(self.partner_id.id)
        if self.user_id and self.user_id.partner_id:
            partner_ids.append(self.user_id.partner_id.id)

        return {
            "name": self.name,
            "partner_ids": [(6, 0, partner_ids)],
            "user_id": self.user_id.id,
            "start_date": self.date_start,
            "stop_date": self.date,
            "start": self.date_start,
            "stop": self.date,
            "allday": self.allday,  # respect your allday flag
            "res_model": self._name,
            "res_model_id": self.env.ref("field_visit.model_field_visit").id,
            "res_id": self.id,
        }

    def create_calendar_event(self):
        events = self.env["calendar.event"]
        for item in self:
            event = self.env["calendar.event"].create(
                item._prepare_calendar_event_vals()
            )
            if event:
                event.activity_ids.unlink()
                item.calendar_event_id = event
            events += event
        return events

    def action_incident(self, reason_id, image=None, notes=None):
        if self.state not in ["draft", "submitted"]:
            raise ValidationError(_("The visit must be in draft or submitted state"))
        if self.is_work_started:
            self.show_time_control = 'start'
            self.is_work_started = False

            if self.timesheet_ids:
                last_timesheet = self.timesheet_ids[-1]
                last_timesheet.end_time = fields.Datetime.now()
            else:
                raise ValidationError(_("No active timesheet found to end work."))

        self.write(
            {
                "state": "incident",
                "close_reason_id": reason_id.id,
                "close_reason_image": image,
                "close_reason_notes": notes,
            }
        )

    def unlink(self):
        for visit in self:
            # 1. Restrict if visit has timesheet entries (ignore state here)
            if visit.timesheet_ids:
                raise ValidationError(_(
                    "This visit has some timesheet entries referencing it. "
                    "Before removing this visit, you have to remove these timesheet entries."
                ))

            # 2. Restrict if visit is not in draft or cancel state
            if visit.state not in ["draft", "cancel"]:
                raise ValidationError(_("Visits must be in cancelled or draft state before deletion."))

            # 3. Restrict if City Wise visit has child visits
            if visit.child_visit_ids:
                raise ValidationError(_(
                    "You cannot delete the City Wise Visit '%s' because it has Customer-wise visits attached."
                ) % visit.display_name)

        return super(FieldVisit, self).unlink()

    def write(self, values):

        self._check_edit_permission_during_lock_period()

        # Check plan lock period for state changes to submitted
        if values.get('state') == 'submitted':
            self._check_plan_lock_period_for_creation()

        # Regular permission check for editing submitted visits
        for record in self:
            if record.state == 'submitted' and self.env.user.has_group('field_visit.group_field_visit_user') \
                    and not self.env.user.has_group('field_visit.group_field_visit_manager') \
                    and not self.env.user.has_group('field_visit.group_field_visit_managers'):
                raise UserError("You cannot edit a submitted visit.")

        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        today_user = fields.Date.context_today(self)  # Today in user timezone

        for rec in self:
            new_date_start = values.get("date_start") or rec.date_start
            if new_date_start:
                date_start_utc = fields.Datetime.to_datetime(new_date_start)
                date_start_user = date_start_utc.astimezone(user_tz)

                if date_start_user.date() < today_user:
                    raise ValidationError(_("Start Date cannot be in the past. Please select a valid date."))


        ret_val = super().write(values)

        if (values.get("date") or values.get("user_id")) and not self.env.context.get("bypass_update_event"):
            for item in self.filtered(lambda a: a.calendar_event_id):
                new_vals = {}
                if values.get("date") or values.get("date_start"):
                    new_vals["start"] = values.get("date_start", item.date_start)
                    new_vals["stop"] = values.get("date", item.date)
                if values.get("user_id"):
                    new_vals["user_id"] = values["user_id"]  # Many2one is just an int ID
                if new_vals:
                    item.calendar_event_id.write(new_vals)
        return ret_val

    justification_ids = fields.One2many(
        'field.visit.justification',
        'visit_id',
        string="Justifications"
    )

    allowed_recipient_types = fields.Char(compute="_compute_allowed_recipient_types")
    is_approver_or_salesperson = fields.Boolean(compute="_compute_allowed_recipient_types")
    justification_ids_visible = fields.One2many(
        'field.visit.justification',
        'visit_id',
        string="Visible Justifications",
        compute="_compute_visible_justifications"
    )

    def _compute_allowed_recipient_types(self):
        for visit in self:
            user = self.env.user
            types = []
            employee = visit.user_id.employee_ids
            first_approver_id = employee.field_visit_first_approval.id if employee and employee.field_visit_first_approval else False
            second_approver_id = employee.field_visit_second_approval.id if employee and employee.field_visit_second_approval else False

            if user.id == visit.user_id.id:  # Salesperson
                types = ['first_approver', 'second_approver', 'salesperson']
            elif first_approver_id and user.id == first_approver_id:
                types = ['first_approver', 'salesperson']
            elif second_approver_id and user.id == second_approver_id:
                types = ['second_approver', 'salesperson']

            visit.allowed_recipient_types = types
            visit.is_approver_or_salesperson = bool(types)

    @api.depends('justification_ids', 'state')
    def _compute_visible_justifications(self):
        for visit in self:
            user = self.env.user
            employee = visit.user_id.employee_ids
            first_approver = employee.mapped('field_visit_first_approval')
            second_approver = employee.mapped('field_visit_second_approval')

            # Default: salesperson sees all justifications
            if user.id == visit.user_id.id:
                visible_justifications = visit.justification_ids
            elif user in first_approver:
                # First approver sees:
                # 1. Justifications they sent
                # 2. Justifications sent by salesperson to first approver
                visible_justifications = visit.justification_ids.filtered(
                    lambda j: j.user_id == user or
                              (j.user_id == visit.user_id and j.recipient_type == 'first_approver')
                )
            elif user in second_approver:
                # Second approver sees:
                # 1. Justifications they sent
                # 2. Justifications sent by salesperson to second approver
                visible_justifications = visit.justification_ids.filtered(
                    lambda j: j.user_id == user or
                              (j.user_id == visit.user_id and j.recipient_type == 'second_approver')
                )
            else:
                visible_justifications = visit.justification_ids.browse([])

            visit.justification_ids_visible = visible_justifications

    can_start_timer = fields.Boolean(
        string='Can Start Timer',
        compute='_compute_timer_button_visibility',
        store=False
    )
    can_stop_timer = fields.Boolean(
        string='Can Stop Timer',
        compute='_compute_timer_button_visibility',
        store=False
    )

    # Replace the existing _compute_timer_button_visibility method with this:
    @api.depends_context('uid')
    def _compute_timer_button_visibility(self):
        for visit in self:
            # Get all users involved in this visit (main user + joint visit users)
            all_users = visit.user_id | visit.joint_visit_user_ids

            # Check if current user has permission for this visit
            current_user_has_access = self.env.user in all_users

            if not current_user_has_access:
                visit.can_start_timer = False
                visit.can_stop_timer = False
                continue

            # Find running timer for current user specifically
            user_timer = self.env['account.analytic.line'].search([
                ('source_model', '=', 'field.visit'),
                ('source_record_id', '=', visit.id),
                ('user_id', '=', self.env.user.id),
            ])

            running = user_timer.filtered(lambda t: t.is_timer_running)

            # Set button visibility
            visit.can_start_timer = not running
            visit.can_stop_timer = bool(running)


class FieldVisitJustification(models.Model):
    _name = "field.visit.justification"
    _description = "Field Visit Justification"

    visit_id = fields.Many2one('field.visit', string="Visit", required=True, ondelete="cascade")
    user_id = fields.Many2one('res.users', string="Sender", default=lambda self: self.env.user, required=True)
    datetime = fields.Datetime(string="Date-Time", default=fields.Datetime.now, required=True)
    message = fields.Text(string="Message", required=True)
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    attachment_links = fields.Html(
        string="Attachments",
        compute="_compute_attachment_links",
        sanitize=False
    )
    recipient_type = fields.Selection([
        ('first_approver', 'First Approver'),
        ('second_approver', 'Second Approver'),
        ('salesperson', 'Salesperson')
    ], string="Recipient Type", required=True)
    parent_id = fields.Many2one('field.visit.justification', string="Parent Justification")
    visible_to_ids = fields.Many2many('res.users', string="Visible To", compute="_compute_visible_to_ids", store=True)

    @api.depends('recipient_type', 'visit_id')
    def _compute_visible_to_ids(self):
        for rec in self:
            employees = rec.visit_id.user_id.employee_ids
            first_approver = employees.mapped('field_visit_first_approval')
            second_approver = employees.mapped('field_visit_second_approval')
            salesperson = rec.visit_id.user_id

            # Everyone can see their own justification
            visible_users = rec.user_id | salesperson

            # If recipient_type is set, add only the proper recipient
            if rec.recipient_type == 'first_approver' and first_approver:
                visible_users |= first_approver
            elif rec.recipient_type == 'second_approver' and second_approver:
                visible_users |= second_approver
            elif rec.recipient_type == 'salesperson':
                visible_users |= salesperson

            rec.visible_to_ids = visible_users

    @api.depends('attachment_ids')
    def _compute_attachment_links(self):
        for rec in self:
            links = []
            for att in rec.attachment_ids:
                if att.id:
                    links.append('<a href="/web/content/%d?download=true">%s</a>' % (att.id, att.name))
            rec.attachment_links = "<br/>".join(links)
