# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    website_id = fields.Many2one('website', related='sale_id.website_id', string='Website',
                                 help='Website where this order has been placed, for eCommerce orders.',
                                 store=True, readonly=True)



    def button_validate(self):
        for picking in self:
            # collect total delivered quantity per product
            product_qty = defaultdict(float)
            for move in picking.move_line_ids:
                product_qty[move.product_id] += move.quantity

            for product, deliver_qty in product_qty.items():
                if product.type == 'product' and not product.allow_out_of_stock_order:
                    warehouse = picking.picking_type_id.warehouse_id
                    free_qty = product.with_context(warehouse=warehouse.id).qty_available
                    if deliver_qty > free_qty:
                        raise UserError(
                            _("Cannot validate delivery: Product '%s' does not have enough stock. "
                              "Available: %s, Trying to deliver: %s")
                            % (product.display_name, free_qty, deliver_qty)
                        )
        return super(StockPicking, self).button_validate()