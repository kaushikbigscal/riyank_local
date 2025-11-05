from odoo import models, fields, api,_
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.exceptions import ValidationError, AccessError


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_city_wise = fields.Boolean("City-wise", config_parameter="field_visit.enable_city_wise",tracking=True)
    enable_customer_wise = fields.Boolean("Customer-wise", config_parameter="field_visit.enable_customer_wise",tracking=True)
    enable_route_wise = fields.Boolean("Routes-wise", config_parameter="field_visit.enable_route_wise",tracking=True)
    enable_official_work = fields.Boolean("Official Work", config_parameter="field_visit.enable_official_work")

    enable_planned_approval = fields.Boolean("Enable Plan Approval", config_parameter="field_visit.enable_planned_approval",tracking=True)
    check_in_with_plan = fields.Boolean("Restrict Check-in if Plan Not Approved",tracking=True)
    check_in_without_plan = fields.Boolean("Allow Check-in Without Plan",tracking=True)

    plan_lock_period = fields.Boolean("Plan Lock Period",tracking=True)
    month = fields.Selection([
        ('current_month', 'Current Month'),
        ('previous_month', 'Previous Month'),
    ], string="Month", default="current_month",tracking=True)

    joint_visit_hierarchy = fields.Selection([
        ('top','Top'),
        ('bottom','Bottom'),
        ('top_bottom','Top-Bottom'),
        ('all','All'),
    ], string="Joint Visit Hierarchy",help = "Top: My manager, his manager, up-to-top, "
                                                            "Bottom: My reports, each reports’ reports, up-to-bottom user can see, "
                                                            "All: All the employees of MY company",default="all",tracking=True,required=True)

    plan_open_date = fields.Date("Plan Open Date")
    plan_close_date = fields.Date("Plan Close Date")

    # dhruti start
    allow_unplanned_work = fields.Boolean("Allow Unplanned Work", tracking=True)
    # unplanned_activity_types = fields.Many2many(
    #     'field.visit.activity.type',
    #     string="Unplanned Activity Types",
    #     help="Types of unplanned activities allowed for field visits"
    # )
    checkin_out_difference = fields.Integer(
        string="Check-in/out Difference (minutes)",
        help="Allowed time gap between check-in and check-out"
    )
    geofencing_radius = fields.Integer(
        string="Geofencing Radius (meters)",
        help="Maximum allowed distance for check-in/check-out"
    )
    enforce_geofencing_checkin = fields.Boolean("Enforce Geofencing on Check-in", tracking=True)
    enforce_geofencing_checkout = fields.Boolean("Enforce Geofencing on Check-out", tracking=True)
    attendance_before_checkin = fields.Boolean("Attendance Must Before Check-in", tracking=True)
    # dhruti end

    @api.onchange('month')
    def _onchange_month(self):
        """Set open & close dates automatically based on selected month."""
        if not self.month:
            self.plan_open_date = False
            self.plan_close_date = False
            return

        today = date.today()

        if self.month == 'current_month':
            start_date = today.replace(day=1)
            end_date = (start_date + relativedelta(months=1)) - relativedelta(days=1)
        else:  # previous_month
            start_date = (today.replace(day=1) - relativedelta(months=1))
            end_date = (today.replace(day=1) - relativedelta(days=1))

        self.plan_open_date = start_date
        self.plan_close_date = end_date


    @api.constrains('check_in_with_plan', 'enable_planned_approval')
    def _check_check_in_with_plan_requires_approval(self):
        for company in self:
            if company.check_in_with_plan and not company.enable_planned_approval:
                raise ValidationError(_(
                    "'Restrict Check-in if Plan Not Approved' requires 'Enable Plan Approval' to be enabled."
                ))

    @api.onchange('check_in_with_plan')
    def _onchange_check_in_with_plan(self):
        """Auto-enable planned approval if restrict check-in is enabled"""
        if self.check_in_with_plan and not self.enable_planned_approval:
            self.enable_planned_approval = True

    @api.model
    def _register_hook(self):
        """Set initial menu visibility when module is installed/updated"""
        res = super()._register_hook()
        self._update_menu_visibility()
        return res

    def _update_menu_visibility(self):
        """Update menu visibility based on company settings"""

        # existing route-wise menu toggle
        menu_route = self.env.ref('field_visit.menu_field_visit_routes', raise_if_not_found=False)
        if menu_route:
            any_company_enabled = self.search_count([('enable_route_wise', '=', True)]) > 0
            menu_route.sudo().active = any_company_enabled

        # **new** approval menu toggle
        menu_waiting = self.env.ref('field_visit.menu_waiting_for_approval', raise_if_not_found=False)
        if menu_waiting:
            any_company_approval = self.search_count([('enable_planned_approval', '=', True)]) > 0
            menu_waiting.sudo().active = any_company_approval

        # if you also want to hide/show the “Management” parent menu:
        menu_management = self.env.ref('field_visit.menu_field_visit_management', raise_if_not_found=False)
        if menu_management:
            menu_management.sudo().active = any_company_approval

    def write(self, vals):
        # ✅ Geofencing validation
        checkin = vals.get("enforce_geofencing_checkin", self.enforce_geofencing_checkin)
        checkout = vals.get("enforce_geofencing_checkout", self.enforce_geofencing_checkout)
        distance = vals.get("geofencing_radius", self.geofencing_radius)

        if (checkin or checkout) and distance <= 0:
            raise AccessError(_("Geofence radius must be set if geofencing is enabled."))

        res = super().write(vals)
        if 'enable_route_wise' in vals or 'enable_planned_approval' in vals:
            self._update_menu_visibility()
        return res

    @api.onchange("enforce_geofencing_checkin", "enforce_geofencing_checkout")
    def _onchange_geo_flags(self):
        if not self.enforce_geofencing_checkin and not self.enforce_geofencing_checkout:
            self.geofencing_radius = 0.0