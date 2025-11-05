from odoo import models, fields, api

class RouteManagement(models.Model):
    _name = 'route.management'
    _description = 'Route Management'

    name = fields.Char(string="Route Name", required=True)

    state_id = fields.Many2many(
        'res.country.state',
        string='States',
        domain=[('country_id.code', '=', 'IN')]
    )

    city_id = fields.Many2many(
        'res.city',
        string='Cities',
        domain="[('state_id', 'in', state_id)]"
    )

    zip_code = fields.Many2many(
        'city.zip',
        string='Areas',
        domain="[('city_id', 'in', city_id)]"
    )

    # partner_id = fields.Many2many(
    #     'res.partner',
    #     string="Customers",
    #     domain=lambda self: self.env['res.partner']._apply_field_visit_filters(
    #         self.env['partner.domain.mixin']._get_partner_domain()
    #     ),
    #     help="Select customers to assign to this route."
    # )

    def _get_customers_domain(self):
        """Always apply _apply_field_visit_filters, optionally add partner domain if module installed"""
        domain = []
        # Add partner.domain.mixin domain only if module is installed
        if self.env['ir.module.module'].sudo().search([
            ('name', '=', 'customer_visibility'),
            ('state', '=', 'installed')
        ], limit=1):
            domain += self.env['partner.domain.mixin']._get_partner_domain()
        # Always apply _apply_field_visit_filters
        return self.env['res.partner']._apply_field_visit_filters(domain)

    partner_id = fields.Many2many(
        'res.partner',
        string="Customers",
        domain=_get_customers_domain,
        help="Select customers to assign to this route."
    )

    assigned_to_ids = fields.Many2many(
        'res.users', string="Assigned To"
    )

    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ], default='active', string="Status")


    @api.onchange('state_id')
    def _onchange_state_id(self):
        # If no state is selected, clear city and zip
        if not self.state_id:
            self.city_id = False
            self.zip_code = False
        else:
            # Remove cities not in selected states
            self.city_id = self.city_id.filtered(lambda c: c.state_id in self.state_id)
            # Remove zip codes not in remaining cities
            self.zip_code = self.zip_code.filtered(lambda z: z.city_id in self.city_id)

    @api.onchange('city_id')
    def _onchange_city_id(self):
        # If no city is selected, clear zip codes
        if not self.city_id:
            self.zip_code = False
        else:
            # Remove zip codes not in selected cities
            self.zip_code = self.zip_code.filtered(lambda z: z.city_id in self.city_id)

    # @api.onchange('state_ids', 'city_ids', 'zip_ids')
    # def _onchange_filters(self):
    #     """ Dynamically filter customers based on selected states, cities, and areas """
    #     domain = [('customer_rank', '>', 0)]
    #
    #     # Filter by states
    #     if self.state_ids:
    #         domain.append(('state_id', 'in', self.state_ids.ids))
    #
    #     # Filter by cities
    #     if self.city_ids:
    #         domain.append(('city', 'in', self.city_ids.mapped('name')))
    #
    #     # Filter by zip/areas
    #     if self.zip_ids:
    #         domain.append(('zip', 'in', self.zip_ids.mapped('name')))
    #
    #     return {'domain': {'partner_id': domain}}


    customer_count_display = fields.Char(
        string="Customers",
        compute="_compute_customer_count_display",
        store=False
    )

    @api.depends('partner_id')
    def _compute_customer_count_display(self):
        for record in self:
            count = len(record.partner_id)
            record.customer_count_display = f"{count} Customers"

