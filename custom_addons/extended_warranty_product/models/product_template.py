from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_extended_warranty = fields.Boolean(
        string="Is Extended Warranty",
        default=False,
        help="Indicates if this product is an extended warranty service."
    )
