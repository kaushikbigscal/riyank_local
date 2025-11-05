from math import radians, sin, cos, sqrt, atan2
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    enable_geofence = fields.Boolean(
        string='Enforce Geo-fencing on Day-in',
        help='Enable location-based attendance checking for this user'
    )
    enable_geofence_day_out = fields.Boolean(string='Enforce Geo-fencing on Day-out')

    day_in_reminder_enabled = fields.Boolean(
        string="Enable Day In Reminder",
        help="Use working schedule for day-based reminders")
    
    day_out_reminder_enabled = fields.Boolean(string="Enable Day Out Reminder")

    auto_day_out = fields.Boolean(string="Auto Day Out")

    attendance_capture_mode = fields.Selection([
        ('web', 'Web Only'),
        ('mobile', 'Mobile Only'),
        ('mobile-web','Mobile & Web'),
        ('biometric', 'Biometric Only'),
    ], string="Attendance Capture Mode", default='mobile-web')


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.model
    def create(self, values):
        attendance = super(HrAttendance, self).create(values)
        attendance._check_company_range()
        return attendance

    def write(self, values):
        res = super(HrAttendance, self).write(values)
        self._check_company_range()
        return res

    def _compute_distance(self, lat1, lon1, lat2, lon2):
        # Radius of the earth in kilometers
        R = 6371.0

        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Calculate the change in coordinates
        dlon = lon2 - lon1
        dlat = lat2 - lat1

        # Apply Haversine formula
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = R * c

        return distance

    def _check_company_range(self):
        company = self.env.company
        user = self.env.user

        company_latitude = company.company_latitude or 0.0
        company_longitude = company.company_longitude or 0.0
        allowed_distance_meters = company.allowed_distance or 100  # meters

        _logger.info(
            f'Company Location: ({company_latitude}, {company_longitude}), Allowed Distance: {allowed_distance_meters}m')

        for attendance in self:
            is_check_in = attendance.check_in and not attendance.check_out
            is_check_out = attendance.check_out

            # For check-in
            if is_check_in:
                if not (company.enable_geofence and user.enable_geofence):
                    continue

                if not (attendance.in_latitude and attendance.in_longitude):
                    raise UserError(
                        _("Missing location for check-in. Please enable location services."))

                distance_meters = self._compute_distance(
                    company_latitude, company_longitude,
                    attendance.in_latitude, attendance.in_longitude
                ) * 1000

                if distance_meters > allowed_distance_meters:
                    raise UserError(_(
                        "You are outside the allowed range for check-in."
                    ))

            # For check-out
            if is_check_out:
                if not (company.enable_geofence_day_out and user.enable_geofence_day_out):
                    continue

                if not (attendance.out_latitude and attendance.out_longitude):
                    raise UserError(
                        _("Missing location for check-out. Please enable location services."))

                distance_meters = self._compute_distance(
                    company_latitude, company_longitude,
                    attendance.out_latitude, attendance.out_longitude
                ) * 1000

                if distance_meters > allowed_distance_meters:
                    raise UserError(_(
                        "You are outside the allowed range for check-out."
                    ))
