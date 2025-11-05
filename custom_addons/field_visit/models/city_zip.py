from odoo import models, fields,api

class CityZip(models.Model):
    _name = 'city.zip'
    _description = 'Cities and Zip'

    area_name = fields.Char(string='Area', required=True)
    name = fields.Char(string='Zip Code', required=True)
    city_id = fields.Many2one('res.city', string='City', required=True)

    # zip_code = fields.Char(
    #     string='Area with Zip',
    #     compute='_compute_display_name',
    #     store=True,
    # )

    # @api.depends('area_name', 'name')
    # def _compute_display_name(self):
    #     for rec in self:
    #         rec.display_name = f"{rec.area_name} ({rec.name})"

    @api.depends('name')
    def _compute_display_name(self):
        for city in self:
            area_name = city.area_name if not city.name else f'{city.area_name} ({city.name})'
            city.display_name = area_name

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain = ['|',
                  ('area_name', 'ilike', name),
                  ('name', 'ilike', name)]
        return self.search(domain + args, limit=limit).name_get()