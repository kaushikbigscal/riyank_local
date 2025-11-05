from math import radians, sin, cos, sqrt, atan2

from odoo import models, _, fields, api
from odoo.exceptions import AccessError


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    def _compute_distance(self, lat1, lon1, lat2, lon2):
        R = 6371000.0  # Earth radius in meters
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    def _validate_geofence_checkin_visit(self, visit, lat, lon):
        """Validate geofencing for field visit check-in"""
        user = self.env.user
        company = self.env.company

        # if user.allow_without_location:
        #     return True

        # Check company & user settings
        if not (company.enforce_geofencing_checkin and user.enforce_geofencing_checkin):
            return True

        cust_lat = visit.partner_id.partner_latitude
        cust_lon = visit.partner_id.partner_longitude
        if not cust_lat or not cust_lon:
            raise AccessError(_("Customer latitude and longitude are required for geofencing."))

        if not lat or not lon:
            raise AccessError(_("Missing check-in location data."))

        allowed_distance = company.geofencing_radius or 0.0
        if allowed_distance <= 0:
            raise AccessError(_("Allowed geofencing distance must be configured in company settings."))

        distance = self._compute_distance(lat, lon, cust_lat, cust_lon)
        if distance > allowed_distance:
            raise AccessError(_("Check-in location too far! Distance: %.2f meters. Allowed: %.2f meters.") % (
                distance, allowed_distance
            ))
        return True

    def _validate_geofence_checkout_visit(self, visit, lat, lon):
        """Validate geofencing for field visit check-out"""
        user = self.env.user
        company = self.env.company

        # if user.allow_without_location:
        #     return True

        # Check company & user settings
        if not (company.enforce_geofencing_checkout and user.enforce_geofencing_checkout):
            return True

        cust_lat = visit.partner_id.partner_latitude
        cust_lon = visit.partner_id.partner_longitude
        if not cust_lat or not cust_lon:
            raise AccessError(_("Customer latitude and longitude are required for geofencing."))

        if not lat or not lon:
            raise AccessError(_("Missing check-out location data."))

        allowed_distance = company.geofencing_radius or 0.0
        if allowed_distance <= 0:
            raise AccessError(_("Allowed geofencing distance must be configured in company settings."))

        distance = self._compute_distance(lat, lon, cust_lat, cust_lon)
        if distance > allowed_distance:
            raise AccessError(_("Check-out location too far! Distance: %.2f meters. Allowed: %.2f meters.") % (
                distance, allowed_distance
            ))
        return True


    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        compute='_compute_employee_id',
        store=True
    )

    @api.depends('user_id')
    def _compute_employee_id(self):
        for record in self:
            if record.user_id:
                # Get employee from the user
                employee = self.env['hr.employee'].search([
                    ('user_id', '=', record.user_id.id)
                ], limit=1)
                record.employee_id = employee.id if employee else False
            else:
                record.employee_id = False