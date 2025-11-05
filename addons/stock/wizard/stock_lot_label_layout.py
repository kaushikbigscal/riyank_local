# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from odoo import fields, models


class ProductLabelLayout(models.TransientModel):
    _name = 'lot.label.layout'
    _description = 'Choose the sheet layout to print lot labels'

    move_line_ids = fields.Many2many('stock.move.line')
    label_quantity = fields.Selection([
        ('lots', 'One per lot/SN'),
        ('units', 'One per unit')], string="Quantity to print", required=True, default='lots', help="If the UoM of a lot is not 'units', the lot will be considered as a unit and only one label will be printed for this lot.")
    print_format = fields.Selection([
        ('2x7', '2 x 7'),
        ('dymo', 'Dymo Label'),('4x7','4 x 7 Label'),('4x12','4 x 12 Label')], string="Format", default='2x7', required=True)

    quantity=fields.Integer("Quantity", default=1)
    pricelist_id = fields.Many2one('product.pricelist', string="Pricelist")
    move_quantity = fields.Selection([
        ('move', 'Operation Quantities'),
        ('custom', 'Custom')], string="Quantity to print", required=True, default='move')
    extra_html = fields.Char('Extra Content', default='')


    def process(self):
        self.ensure_one()
        xml_id = 'stock.action_report_lot_label'
        if self.print_format == 'dymo':
            xml_id = 'stock.action_report_lot_label_dymo'
        elif self.print_format == '4x7':
            xml_id = 'stock.action_report_lot_label_4x7'
        elif self.print_format == '4x12':
            xml_id = 'stock.action_report_lot_label_4x12'


        docids = []

        if self.label_quantity == 'lots':
            for lot in self.move_line_ids.lot_id:
                docids.extend([lot.id] * (self.quantity or 1))
        else:
            uom_categ_unit = self.env.ref('uom.product_uom_categ_unit')
            quantity_by_lot = defaultdict(int)
            for move_line in self.move_line_ids:
                if not move_line.lot_id:
                    continue
                if move_line.product_uom_id.category_id == uom_categ_unit:
                    quantity_by_lot[move_line.lot_id.id] += int(move_line.quantity)
                else:
                    quantity_by_lot[move_line.lot_id.id] += 1
            for lot_id, qty in quantity_by_lot.items():
                docids.extend([lot_id] * qty * (self.quantity or 1))

        report_action = self.env.ref(xml_id).report_action(docids, config=False)
        report_action.update({'close_on_report_download': True})
        return report_action

