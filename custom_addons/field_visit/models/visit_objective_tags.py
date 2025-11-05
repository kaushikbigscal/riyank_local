# -*- coding: utf-8 -*-

from random import randint

from pkg_resources import require

from odoo import api, fields, models, SUPERUSER_ID
from odoo.osv import expression


class VisitObjectiveTag(models.Model):
    _name = "visit.objective"
    _description = "Visit Objective"
    _order = "name"

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char('Name', required=True, translate=True)
    color = fields.Integer(string='Color', default=_get_default_color,
        help="Transparent tags are not visible in the kanban view of your projects and tasks.")
    sub_objective_ids = fields.One2many(
        'visit.subobjective',
        'visit_objective_id',
        string="Sub Objectives"
    )

    @api.model
    def name_create(self, name):
        existing_objective = self.search([('name', '=ilike', name.strip())], limit=1)
        if existing_objective:
            return existing_objective.id, existing_objective.display_name
        return super().name_create(name)

    visit_type = fields.Selection([
        ('all', 'All Visit Types'),
        ('customer_wise', 'Customer-wise'),
        ('city_wise', 'City-wise'),
        ('official_work', 'Official Work')
    ], string="Visit Type", default='all')

class VisitSubObjective(models.Model):
    _name = "visit.subobjective"
    _description = "Sub Objective"
    _order = "name"

    name = fields.Char(string="Sub Objective", required=True, translate=True)
    visit_objective_id = fields.Many2one('visit.objective', string="Visit Objective", ondelete='cascade', required=True)

