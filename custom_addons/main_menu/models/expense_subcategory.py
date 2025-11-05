from odoo import fields,models

class ExpenseSubcategory(models.Model):

    _name = 'expense.subcategory'

    name=fields.Char("Name")

class ExpenseCategory(models.Model):

    _inherit = 'product.product'

    subcategory_id = fields.Many2one('expense.subcategory', string="Subcategory")