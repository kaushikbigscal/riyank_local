# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models

from datetime import timedelta
from odoo.exceptions import ValidationError


class ProductLabelLayout(models.TransientModel):
    _name = 'picking.label.type'
    _description = 'Choose whether to print product or lot/sn labels'

    picking_ids = fields.Many2many('stock.picking')
    label_type = fields.Selection([
        ('products', 'Product Labels'),
        ('lots', 'Lot/SN Labels')], string="Labels to print", required=True, default='products')
    # enable_customer_product_mapping = fields.Boolean("Create Customer Product Mapping")


    def process(self):
        # if not self.enable_customer_product_mapping:
        #     raise ValidationError(_(
        #         "You are not allowed to print label if you want then first enable create customer product mapping"
        #     ))

        if not self.picking_ids:
            return

        CustomerProductMapping = self.env['customer.product.mapping']

        for picking in self.picking_ids:
            customer = picking.partner_id
            sale_order = picking.sale_id  # direct access, no getattr

            for move in picking.move_ids:
                product = move.product_id

                # Serial numbers from operations tab (move lines)
                serials = move.move_line_ids.mapped("lot_id")
                if not serials:
                    continue

                for lot in serials:
                    op_exists = picking.move_line_ids.filtered(
                        lambda ml: ml.product_id.id == product.id and ml.lot_id.id == lot.id
                    )
                    if not op_exists:
                        continue  # skip if not in operations tab

                    # Find related sale order line if exists
                    order_line = False
                    if sale_order:
                        order_line = self.env['sale.order.line'].search([
                            ('order_id', '=', sale_order.id),
                            ('product_id', '=', product.id)
                        ], limit=1)

                    # Check for existing mapping (avoid duplicates across pickings)
                    existing = CustomerProductMapping.search([
                        ('customer_id', '=', customer.id),
                        ('product_id', '=', product.id),
                        ('serial_number_ids', '=', lot.id),
                        ('order_id', '=', order_line.id if order_line else False),
                    ], limit=1)

                    if not existing:
                        CustomerProductMapping.create({
                            'customer_id': customer.id,
                            'product_id': product.id,
                            'serial_number_ids': lot.id,
                            'order_id': order_line.id if order_line else False,
                            'source_type': 'sale_order' if sale_order else 'direct_product',
                            'start_date': fields.Date.today(),
                            'end_date': fields.Date.today() + timedelta(days=1),
                            'status': 'chargeable',
                            'product_category': product.categ_id.id if product.categ_id else False,
                        })

        # Continue with your original label printing logic
        if self.label_type == 'products':
            return self.picking_ids.action_open_label_layout()

        view = self.env.ref('stock.lot_label_layout_form_picking')
        return {
            'name': _('Choose Labels Layout'),
            'type': 'ir.actions.act_window',
            'res_model': 'lot.label.layout',
            'views': [(view.id, 'form')],
            'target': 'new',
            'context': {'default_move_line_ids': self.picking_ids.move_line_ids.ids},
        }
