# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class task_stage_restriction(models.Model):
#     _name = 'task_stage_restriction.task_stage_restriction'
#     _description = 'task_stage_restriction.task_stage_restriction'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

