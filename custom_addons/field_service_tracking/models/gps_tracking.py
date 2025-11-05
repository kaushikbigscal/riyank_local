from odoo import models, fields, api


class GpsTracking(models.Model):
    _name = 'gps.tracking'
    _description = 'Employee GPS Tracking Data'
    _order = 'timestamp asc'

    timestamp = fields.Datetime(default=fields.Datetime.now)
    latitude = fields.Float(string='Latitude', digits=(16, 6))
    longitude = fields.Float(string='Longitude', digits=(16, 6))
    employee_id = fields.Many2one('hr.employee', string='Employee')
    attendance_id = fields.Many2one('hr.attendance', string='Attendance')
    synced = fields.Boolean(default=False)
    tracking_type = fields.Selection([
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
        ('call_start', 'Work Start'),
        ('call_end', 'Work End'),
        ('route_point', 'Route Point'),
    ], default='route_point', string='Tracking Type', required=True)

    lead_id = fields.Many2one('crm.lead', string="Lead/Opportunity")

    suspicious = fields.Boolean(string='Suspicious Point', default=False)

    @api.model
    def create_route_point(self, employee_id, latitude, longitude, tracking_type='route_point'):
        """Create a new route tracking point"""
        employee = self.env['hr.employee'].browse(employee_id)

        ###################################################################################
        # Check if employee has a user and GPS tracking is enabled
        if not employee.user_id or not employee.user_id.enable_gps_tracking:
            print(f"GPS tracking is disabled for employee {employee.name}")
            return False
        ###################################################################################

        # Get current active attendance session
        attendance = self.env['hr.attendance'].search([
            ('employee_id', '=', employee_id),
            ('check_out', '=', False)
        ], limit=1)

        vals = {
            'employee_id': employee_id,
            'attendance_id': attendance.id if attendance else False,
            'latitude': latitude,
            'longitude': longitude,
            'tracking_type': tracking_type,
            'timestamp': fields.Datetime.now()
        }
        return self.create(vals)


# Extend existing models to integrate tracking
class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.model
    def create(self, vals):
        """Override create to add route tracking"""
        attendance = super().create(vals)

        # Create route tracking point for check-in
        if ('check_in' in vals and vals.get('in_latitude') and vals.get('in_longitude')
                #######################################################################################################
                and attendance.employee_id.user_id and attendance.employee_id.user_id.enable_gps_tracking):
            #######################################################################################################
            self.env['gps.tracking'].create_route_point(
                employee_id=attendance.employee_id.id,
                latitude=vals['in_latitude'],
                longitude=vals['in_longitude'],
                tracking_type='check_in'
            )

        return attendance

    def write(self, vals):
        """Override write to handle check-out tracking"""
        result = super().write(vals)

        # Create route tracking point for check-out
        if 'check_out' in vals and vals.get('out_latitude') and vals.get('out_longitude'):
            for attendance in self:
                ##########################################################################################
                if (attendance.employee_id.user_id and
                        attendance.employee_id.user_id.enable_gps_tracking):
                    ###########################################################################################
                    self.env['gps.tracking'].create_route_point(
                        employee_id=attendance.employee_id.id,
                        latitude=vals['out_latitude'],
                        longitude=vals['out_longitude'],
                        tracking_type='check_out'
                    )

        return result


#################################################################################################
class ResUsers(models.Model):
    _inherit = 'res.users'

    enable_gps_tracking = fields.Boolean(
        string='Enable GPS Tracking',
        default=False,
        help='Enable GPS tracking for this user. When disabled, the user will not be able to send GPS data or view tracking information.'
    )
#################################################################################################
