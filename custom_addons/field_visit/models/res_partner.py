
from odoo import fields, models,api,_
from odoo.exceptions import AccessError


class ResPartner(models.Model):
    _inherit = "res.partner"

    salesperson_planner_visit_count = fields.Integer(
        string="Number of Salesperson Visits",
        compute="_compute_salesperson_planner_visit_count",
    )

    def _compute_salesperson_planner_visit_count(self):
        partners = self | self.mapped("child_ids")
        partner_data = self.env["field.visit"].read_group(
            [("partner_id", "in", partners.ids)], ["partner_id"], ["partner_id"]
        )
        mapped_data = {m["partner_id"][0]: m["partner_id_count"] for m in partner_data}
        for partner in self:
            visit_count = mapped_data.get(partner.id, 0)
            for child in partner.child_ids:
                visit_count += mapped_data.get(child.id, 0)
            partner.salesperson_planner_visit_count = visit_count

    def action_view_field_visit(self):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "field_visit.all_field_visit_action"
        )
        operator = "child_of" if self.is_company else "="
        action["domain"] = [("partner_id", operator, self.id)]
        return action


    # Apply the filter logic for fetching the customer based on state, city, zip
    @api.model
    def _apply_field_visit_filters(self, args=None):
        args = args or []
        context = self.env.context

        # Only parent customers
        args += [('parent_id', '=', False)]

        # Apply filters from field.visit context
        if context.get('filter_state_id'):
            args += [('state_id', '=', context['filter_state_id'])]
        if context.get('filter_city_id'):
            args += [('city_id', '=', context['filter_city_id'])]
        if context.get('filter_zip_ids'):
            zip_ids = context['filter_zip_ids']
            zip_names = self.env['city.zip'].browse(zip_ids).mapped('name')
            if zip_names:
                args += [('zip', 'in', zip_names)]
        return args

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = self._apply_field_visit_filters(args)
        return super().name_search(name=name, args=args, operator=operator, limit=limit)

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        # Apply custom filters to domain
        domain = self._apply_field_visit_filters(domain)

        # Perform the actual search_read
        records = self.search_read(
            domain=domain,
            fields=list(specification.keys()),
            offset=offset,
            limit=limit,
            order=order,
        )

        # Count handling
        length = self.search_count(domain)
        return {
            'length': length,
            'records': records,
        }




class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    field_visit_first_approval = fields.Many2one('res.users', string='Field Visit First Approval',
                                                  domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
                                                  help='Select the user responsible for first approving "field visit" of this employee')
    field_visit_second_approval = fields.Many2one('res.users', string='Field Visit Second Approval',
                                                  domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
                                                  help='Select the user responsible for second approving "field visit" of this employee')



class ResUsers(models.Model):
    _inherit = 'res.users'

    joint_visit_hierarchy = fields.Selection([
        ('top', 'Top'),
        ('bottom', 'Bottom'),
        ('top_bottom', 'Top-Bottom'),
        ('all', 'All'),
    ], string='Joint Visit Hierarchy')

    allow_checkin_without_plan = fields.Boolean(
        string="Allow Check-in Without Plan",
        help="Allow this user to check-in even if no field plan is created"
    )

    allow_without_location = fields.Boolean(
        string="Allow Without Location",
        help="Allow this user to check-in/out without location data"
    )

    enforce_geofencing_checkin = fields.Boolean(
        string="Enforce Geofencing on Check-in",
        help="Enforce geofencing validation during check-in for this user"
    )

    enforce_geofencing_checkout = fields.Boolean(
        string="Enforce Geofencing on Check-out",
        help="Enforce geofencing validation during check-out for this user"
    )

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if args is None:
            args = []

        context = self.env.context
        current_user_id = context.get('current_user_id')

        if current_user_id:
            visit_user = self.env['res.users'].browse(current_user_id)
            allowed_users = self.env['field.visit']._get_allowed_joint_visit_users(visit_user)
            args = [('id', 'in', allowed_users.ids)] + args

        return super(ResUsers, self).name_search(name, args, operator, limit)


    @api.model
    def web_search_read(self, *args, **kwargs):
        # get current user from context
        current_user_id = self.env.context.get('current_user_id')
        if current_user_id:
            visit_user = self.browse(current_user_id)
            allowed_users = self.env['field.visit']._get_allowed_joint_visit_users(visit_user)
            # Add a domain filter
            kwargs['domain'] = [('id', 'in', allowed_users.ids)] + kwargs.get('domain', [])

        return super(ResUsers, self).web_search_read(*args, **kwargs)


    def write(self, vals):
        for record in self:
            checkin = vals.get("enforce_geofencing_checkin", record.enforce_geofencing_checkin)
            checkout = vals.get("enforce_geofencing_checkout", record.enforce_geofencing_checkout)
            company = record.company_id

            if (checkin or checkout) and company.geofencing_radius <= 0:
                raise AccessError(_("Geofence radius must be configured in company settings."))

        return super().write(vals)
