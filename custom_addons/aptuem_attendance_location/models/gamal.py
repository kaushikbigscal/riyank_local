# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)

from odoo import fields, models, api

class ResCompany(models.Model):
    _inherit = 'res.company'


    enable_geofence = fields.Boolean(string="Enforce Geo-fencing on Day-in", default=False, help="Enable Location-based attendance checking for the company")
    enable_geofence_day_out = fields.Boolean(string="Enforce Geo-fencing on Day-out", default=False)

    company_latitude = fields.Float(string='Company Latitude', digits=(16, 6),
                                   help='Set Company Latitude here')
    company_longitude = fields.Float(string='Company Longitude', digits=(16, 6),
                                    help='Set Company Longitude here')
    allowed_distance = fields.Float(
        string='Allowed Distance (M)', digits=(16, 2),
        help='Set the allowed distance for check-in or check-out in meters. Example: 2.5 for 2.5 meters.'
    )

    day_in_reminder_enabled = fields.Boolean(
        string="Enable Day In Reminder",
        help="Use working schedule for day-based reminders")
    
    day_out_reminder_enabled = fields.Boolean(string="Enable Day Out Reminder")

    auto_day_out = fields.Boolean(string="Auto Day Out")

