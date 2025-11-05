from odoo import models, fields, api
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)
import base64
import binascii



class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_distributor = fields.Boolean(string="Is Distributor")

    enable_distributor = fields.Boolean(
        string='Enable Distributor',
        compute='_compute_enable_distributor',
        store=False
    )

    @api.depends_context('uid')  # recompute per user session if needed
    def _compute_enable_distributor(self):
        enable = self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor')
        for rec in self:
            rec.enable_distributor = bool(enable and enable not in ['False', '0'])

    # show_add_distributor_asset = fields.Boolean(
    #     compute='_compute_show_add_distributor_asset')

    # def _compute_show_add_distributor_asset(self):
    #     """Show the button only when delivery is done & SO is primary"""
    #     for picking in self:
    #         sale = picking.sale_id
    #         picking.show_add_distributor_asset = (
    #                 picking.state == 'done'
    #                 and sale
    #                 and sale.sale_order_type == 'primary_orders'
    #                 and sale.distributor_id
    #         )

    #
    # def action_add_distributor_asset(self):
    #     """Create Distributor Asset records from this picking lines"""
    #     for picking in self:
    #         sale = picking.sale_id
    #         if not (sale and sale.distributor_id):
    #             continue
    #
    #         for move in picking.move_ids_without_package:
    #             self.env['distributor.asset'].create({
    #                 'distributor_id': sale.distributor_id.id,
    #                 'product_id': move.product_id.product_tmpl_id.id,
    #                 'status': 'unallocated',
    #             })
    #     return True

    # def action_add_distributor_asset(self):
    #     """Create Distributor Asset records from picking lines based on quantity and serial numbers"""
    #     for picking in self:
    #         sale = picking.sale_id
    #         if not (sale and sale.distributor_id):
    #             continue
    #         for move in picking.move_ids_without_package:
    #             # if product is tracked, each move_line has a serial/lot
    #             if move.product_id.tracking != 'none':
    #                 for move_line in move.move_line_ids:
    #                     self.env['distributor.asset'].create({
    #                         'distributor_id': sale.distributor_id.id,
    #                         'product_id': move_line.product_id.product_tmpl_id.id,
    #                         'status': 'unallocated',
    #                         'lot_id': move_line.lot_id.id,
    #                     })
    #             else:
    #                 # for untracked products, create assets based on quantity
    #                 qty = int(move.product_uom_qty)
    #                 for i in range(qty):
    #                     self.env['distributor.asset'].create({
    #                         'distributor_id': sale.distributor_id.id,
    #                         'product_id': move.product_id.product_tmpl_id.id,
    #                         'status': 'unallocated',
    #                         'lot_id': False,
    #                     })
    #     return True

    @api.onchange('partner_id', 'sale_id')
    def _onchange_partner_sale(self):
        for picking in self:
            if (picking.sale_id and
                    picking.sale_id.sale_order_type == 'primary_orders' and
                    picking.partner_id and
                    picking.partner_id.company_type == 'distribution'):

                warehouse_loc = picking.partner_id.warehouse_id.lot_stock_id
                if warehouse_loc:
                    picking.location_dest_id = warehouse_loc.id



    # @api.model
    # def _action_done(self):
    #     print("Action Done")
    #     CustomerAsset = self.env['customer.product.mapping']
    #     DistributorAsset = self.env['distributor.asset']
    #
    #     enable_distributor = self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor')
    #     if not enable_distributor:
    #         print("Distributor/Customer Asset creation is disabled by config flag.")
    #         return super()._action_done()
    #
    #     for picking in self:
    #         sale_order = picking.sale_id
    #         if not sale_order:
    #             continue
    #
    #         # Distributor Assets - ONLY primary orders
    #         if sale_order.sale_order_type == 'primary_orders' and sale_order.distributor_id:
    #             distributor_id = sale_order.distributor_id.id
    #
    #             for move in picking.move_ids_without_package:
    #                 product_tmpl_id = move.product_id.product_tmpl_id.id
    #
    #                 if move.product_id.tracking != 'none':
    #                     # Collect all lot_ids for this move at once
    #                     lot_ids = move.move_line_ids.lot_id.ids
    #
    #                     if lot_ids:
    #                         # Fetch existing DistributorAssets in one search instead of inside the loop
    #                         existing_assets = DistributorAsset.search([
    #                             ('lot_id', 'in', lot_ids),
    #                             ('product_id', '=', product_tmpl_id)
    #                         ])
    #                         existing_lot_ids = set(existing_assets.mapped('lot_id').ids)
    #
    #                         # Create only for lot_ids that are not yet in DistributorAsset
    #                         for ml in move.move_line_ids:
    #                             lot_id = ml.lot_id.id
    #                             if not lot_id or lot_id in existing_lot_ids:
    #                                 continue
    #                             DistributorAsset.create({
    #                                 'distributor_id': distributor_id,
    #                                 'product_id': product_tmpl_id,
    #                                 'status': 'unallocated',
    #                                 'lot_id': lot_id,
    #                             })
    #                 else:
    #                     # No tracking: create directly based on qty (no search needed)
    #                     qty = int(move.product_uom_qty)
    #                     DistributorAsset.create([
    #                         {
    #                             'distributor_id': distributor_id,
    #                             'product_id': product_tmpl_id,
    #                             'status': 'unallocated',
    #                             'lot_id': False,
    #                         }
    #                         for i in range(qty)
    #                     ])
    #
    #         # Customer Assets - secondary or direct orders
    #         if sale_order.sale_order_type in ['secondary_orders', 'direct_orders']:
    #             distributor_id = (
    #                 sale_order.distributor_id.id
    #                 if sale_order.sale_order_type == 'secondary_orders'
    #                 else False
    #             )
    #
    #             # --- For secondary orders mark distributor assets allocated ---
    #             if sale_order.sale_order_type == 'secondary_orders':
    #                 for move in picking.move_ids_without_package:
    #                     product_tmpl_id = move.product_id.product_tmpl_id.id
    #                     serials = move.move_line_ids.lot_id.ids
    #                     if not sale_order.exists():
    #                         continue
    #
    #                     if serials:
    #                         # fetch all unallocated assets in one search
    #                         unallocated_assets = DistributorAsset.search([
    #                             ('lot_id', 'in', serials),
    #                             ('product_id', '=', product_tmpl_id),
    #                             ('distributor_id', '=', distributor_id),
    #                             ('status', '=', 'unallocated'),
    #                         ])
    #                         lot2asset = {a.lot_id.id: a for a in unallocated_assets}
    #
    #                         for lot_id in serials:
    #                             asset = lot2asset.get(lot_id)
    #                             if asset:
    #                                 asset.status = 'allocated'
    #                             else:
    #                                 lot_name = self.env['stock.lot'].browse(lot_id).name
    #                                 _logger.info(f"No unallocated asset found for Lot {lot_name}")
    #                     else:
    #                         qty = int(move.product_uom_qty)
    #                         unallocated_assets = DistributorAsset.search([
    #                             ('product_id', '=', product_tmpl_id),
    #                             ('distributor_id', '=', distributor_id),
    #                             ('status', '=', 'unallocated')
    #                         ], limit=qty)
    #                         unallocated_assets.write({'status': 'allocated'})
    #
    #             # --- Skip excluded moves ---
    #             excluded_move_ids = set(picking.picking_parts_ids.mapped("move_id").ids)
    #
    #             # preload Service Call project
    #             Project = self.env['project.project'].sudo()
    #             project = Project.search([('name', '=', 'Service Call')], limit=1)
    #             if not project:
    #                 project = Project.create({'name': 'Service Call', 'is_fsm': True})
    #
    #             now = fields.Datetime.now()
    #
    #             for move in picking.move_ids:
    #                 if move.id in excluded_move_ids:
    #                     _logger.debug(f"Skipping move {move.product_id.display_name}")
    #                     continue
    #
    #                 product = move.product_id
    #                 product_tmpl = product.product_tmpl_id
    #
    #                 # # ✅ Skip products where installed_ok is False
    #                 # if not product_tmpl.installed_ok:
    #                 #     _logger.debug(f"Skipping {product.display_name} (installed_ok=False)")
    #                 #     continue
    #
    #
    #                 serials = move.move_line_ids.lot_id
    #
    #                 if serials:
    #                     serial_list = serials
    #                     qty_list = [1] * len(serials)
    #                 else:
    #                     qty = int(move.product_uom_qty)
    #                     serial_list = [None] * qty
    #                     qty_list = [1] * qty
    #
    #                 # Attachments for product & category once
    #                 installation_attachments = self.env['installation.attachment.line']
    #                 if product_tmpl:
    #                     installation_attachments |= product_tmpl.installation_attachment_line_ids.filtered(
    #                         'upload_file')
    #                 if product.categ_id:
    #                     installation_attachments |= product.categ_id.installation_attachment_line_ids.filtered(
    #                         'upload_file')
    #
    #                 for idx, (lot, qty) in enumerate(zip(serial_list, qty_list), start=1):
    #                     lot_info = lot.name if lot else "No Serial"
    #
    #                     # order line fetch
    #                     order_line = move.sale_line_id
    #                     if not order_line and sale_order:
    #                         order_line = self.env['sale.order.line'].search([
    #                             ('order_id', '=', sale_order.id),
    #                             ('product_id', '=', product.id)
    #                         ], limit=1)
    #
    #                     # status + warranty dates
    #                     unit_status = (order_line.unit_status if order_line else None) or 'chargeable'
    #                     if unit_status == 'warranty' and order_line:
    #                         start_date = sale_order.warranty_start_date or fields.Date.today()
    #                         end_date = order_line.line_warranty_end_date or (fields.Date.today() + timedelta(days=1))
    #                     else:
    #                         start_date = fields.Date.today()
    #                         end_date = fields.Date.today() + timedelta(days=1)
    #
    #
    #                     call_type_value = False
    #                     if unit_status:
    #                         call_type_rec = self.env['call.type'].sudo().search([
    #                             ('name', 'ilike', unit_status.strip())
    #                         ], limit=1)
    #                         if call_type_rec:
    #                             call_type_value = call_type_rec.id
    #
    #                     # create customer asset
    #                     customer_asset = CustomerAsset.create({
    #                         'customer_id': picking.partner_id.id,
    #                         'product_id': product.id,
    #                         'serial_number_ids': lot.id if lot else False,
    #                         'order_id': order_line.id if order_line else False,
    #                         'source_type': 'sale_order' if sale_order.sale_order_type in ['secondary_orders',
    #                                                                                       'direct_orders'] else 'direct_product',
    #                         'start_date': start_date,
    #                         'end_date': end_date,
    #                         'asset_status': 'allocated',
    #                         'status': unit_status,
    #                         'product_category': product.categ_id.id or False,
    #                         'distributor_id': distributor_id,
    #                     })
    #                     _logger.info(f"Customer Asset created: {product.name}, Serial={lot_info}, Status={unit_status}")
    #
    #
    #
    #                     # build HTML for installation
    #                     if product_tmpl.installed_ok:
    #                         installation_html = self._get_html_for_product(order_line, product) if order_line else ''
    #                         desc_html = f"<p>Installation call for product {product.name} (Serial: {lot_info})</p>"
    #                         if installation_html:
    #                             desc_html += installation_html
    #                         task_vals = {
    #                             'name': f"Installation Call - {product.name}",
    #                             'project_id': project.id,
    #                             'is_fsm': True,
    #                             'partner_id': picking.partner_id.id,
    #                             'customer_product_id': customer_asset.id,
    #                             'serial_number': customer_asset.serial_number_ids.id or False,
    #                             'planned_date_begin': False,
    #                             'date_deadline': False,
    #                             'installation_table_html': desc_html,
    #                             'call_type': call_type_value,
    #                             'user_ids': False,
    #                         }
    #                         task = self.env['project.task'].sudo().create(task_vals)
    #
    #                         # attach checklist files
    #                         for attach in installation_attachments:
    #                             try:
    #                                 file_data = base64.b64decode(attach.upload_file, validate=True)
    #                             except (binascii.Error, ValueError):
    #                                 _logger.warning(f"Invalid file in installation attachment {attach.name}, skipped.")
    #                                 continue
    #                             filename = attach.upload_file_filename or attach.name or "attachment.dat"
    #                             task.message_post(
    #                                 body=f"Installation Checklist: {attach.name}",
    #                                 attachments=[(filename, file_data)],
    #                                 message_type='comment',
    #                                 subtype_xmlid='mail.mt_comment'
    #                             )
    #
    #
    #     return super()._action_done()


    # @api.model
    # def _action_done(self):
    #     CustomerAsset = self.env['customer.product.mapping']
    #     DistributorAsset = self.env['distributor.asset']
    #
    #     enable_distributor = self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor')
    #     if not enable_distributor:
    #         return super()._action_done()
    #
    #     for picking in self:
    #         sale_order = picking.sale_id
    #         if not sale_order:
    #             continue
    #
    #         # 1️⃣ Distributor Assets - ONLY for primary orders
    #         if sale_order.sale_order_type == 'primary_orders' and sale_order.distributor_id:
    #             distributor_id = sale_order.distributor_id.id
    #
    #             for move in picking.move_ids_without_package:
    #                 product_tmpl_id = move.product_id.product_tmpl_id.id
    #
    #                 if move.product_id.tracking != 'none':
    #                     lot_ids = move.move_line_ids.lot_id.ids
    #                     if lot_ids:
    #                         existing_assets = DistributorAsset.search([
    #                             ('lot_id', 'in', lot_ids),
    #                             ('product_id', '=', product_tmpl_id)
    #                         ])
    #                         existing_lot_ids = set(existing_assets.mapped('lot_id').ids)
    #
    #                         for ml in move.move_line_ids:
    #                             lot_id = ml.lot_id.id
    #                             if not lot_id or lot_id in existing_lot_ids:
    #                                 continue
    #                             DistributorAsset.create({
    #                                 'distributor_id': distributor_id,
    #                                 'product_id': product_tmpl_id,
    #                                 'status': 'unallocated',
    #                                 'lot_id': lot_id,
    #                             })
    #                 else:
    #                     qty = int(move.product_uom_qty)
    #                     DistributorAsset.create([
    #                         {
    #                             'distributor_id': distributor_id,
    #                             'product_id': product_tmpl_id,
    #                             'status': 'unallocated',
    #                             'lot_id': False,
    #                         }
    #                         for i in range(qty)
    #                     ])
    #
    #         # 2️⃣ Customer Assets - secondary or direct orders
    #         if sale_order.sale_order_type in ['secondary_orders', 'direct_orders']:
    #             distributor_id = (
    #                 sale_order.distributor_id.id
    #                 if sale_order.sale_order_type == 'secondary_orders'
    #                 else False
    #             )
    #
    #             # --- For secondary orders mark distributor assets allocated ---
    #             if sale_order.sale_order_type == 'secondary_orders':
    #                 for move in picking.move_ids_without_package:
    #                     product_tmpl_id = move.product_id.product_tmpl_id.id
    #                     serials = move.move_line_ids.lot_id.ids
    #                     if not sale_order.exists():
    #                         continue
    #
    #                     if serials:
    #                         unallocated_assets = DistributorAsset.search([
    #                             ('lot_id', 'in', serials),
    #                             ('product_id', '=', product_tmpl_id),
    #                             ('distributor_id', '=', distributor_id),
    #                             ('status', '=', 'unallocated'),
    #                         ])
    #                         lot2asset = {a.lot_id.id: a for a in unallocated_assets}
    #
    #                         for lot_id in serials:
    #                             asset = lot2asset.get(lot_id)
    #                             if asset:
    #                                 asset.status = 'allocated'
    #                             else:
    #                                 lot_name = self.env['stock.lot'].browse(lot_id).name
    #                                 _logger.info(f"No unallocated asset found for Lot {lot_name}")
    #                     else:
    #                         qty = int(move.product_uom_qty)
    #                         unallocated_assets = DistributorAsset.search([
    #                             ('product_id', '=', product_tmpl_id),
    #                             ('distributor_id', '=', distributor_id),
    #                             ('status', '=', 'unallocated')
    #                         ], limit=qty)
    #                         unallocated_assets.write({'status': 'allocated'})
    #
    #             # --- Skip excluded moves ---
    #             excluded_move_ids = set(picking.picking_parts_ids.mapped("move_id").ids)
    #
    #             Project = self.env['project.project'].sudo()
    #             project = Project.search([('name', '=', 'Service Call')], limit=1)
    #             if not project:
    #                 project = Project.create({'name': 'Service Call', 'is_fsm': True})
    #
    #             now = fields.Datetime.now()
    #
    #             for move in picking.move_ids:
    #                 if move.id in excluded_move_ids:
    #                     continue
    #
    #                 product = move.product_id
    #                 product_tmpl = product.product_tmpl_id
    #                 serials = move.move_line_ids.lot_id
    #
    #                 if serials:
    #                     serial_list = serials
    #                     qty_list = [1] * len(serials)
    #                 else:
    #                     qty = int(move.product_uom_qty)
    #                     serial_list = [None] * qty
    #                     qty_list = [1] * qty
    #
    #                 installation_attachments = self.env['installation.attachment.line']
    #                 if product_tmpl:
    #                     installation_attachments |= product_tmpl.installation_attachment_line_ids.filtered(
    #                         'upload_file')
    #                 if product.categ_id:
    #                     installation_attachments |= product.categ_id.installation_attachment_line_ids.filtered(
    #                         'upload_file')
    #
    #                 for idx, (lot, qty) in enumerate(zip(serial_list, qty_list), start=1):
    #                     order_line = move.sale_line_id or self.env['sale.order.line'].search([
    #                         ('order_id', '=', sale_order.id),
    #                         ('product_id', '=', product.id)
    #                     ], limit=1)
    #
    #                     unit_status = (order_line.unit_status if order_line else None) or 'chargeable'
    #
    #                     # Normal warranty
    #                     if unit_status == 'warranty' and order_line:
    #                         start_date = sale_order.warranty_start_date or fields.Date.today()
    #                         end_date = order_line.line_warranty_end_date or (fields.Date.today() + timedelta(days=1))
    #                     else:
    #                         start_date = fields.Date.today()
    #                         end_date = fields.Date.today() + timedelta(days=1)
    #
    #                     # 🔹 Extended warranty logic (copied from button_validate)
    #                     extended_start = False
    #                     extended_end = False
    #                     if sale_order and unit_status == 'warranty':
    #                         extended_note_line = sale_order.order_line.filtered(
    #                             lambda line: line.is_extended_warranty
    #                                          and line.display_type == 'line_note'
    #                                          and line.name
    #                                          and product.name
    #                                          and product.name in (line.name or "")
    #                         )
    #
    #                         if extended_note_line:
    #                             import re
    #                             from datetime import datetime
    #                             note_name = extended_note_line[0].name or ""
    #
    #                             start_match = re.search(r'Start Date:\s*(\d{2}-\d{2}-\d{4})', note_name)
    #                             if start_match:
    #                                 try:
    #                                     extended_start = datetime.strptime(start_match.group(1), '%d-%m-%Y').date()
    #                                 except ValueError:
    #                                     _logger.warning(f"Could not parse start date from: {start_match.group(1)}")
    #
    #                             end_match = re.search(r'End Date:\s*(\d{2}-\d{2}-\d{4})', note_name)
    #                             if end_match:
    #                                 try:
    #                                     extended_end = datetime.strptime(end_match.group(1), '%d-%m-%Y').date()
    #                                 except ValueError:
    #                                     _logger.warning(f"Could not parse end date from: {end_match.group(1)}")
    #
    #                     # 🔹 Call type
    #                     call_type_value = False
    #                     if unit_status:
    #                         call_type_rec = self.env['call.type'].sudo().search([
    #                             ('name', 'ilike', unit_status.strip())
    #                         ], limit=1)
    #                         if call_type_rec:
    #                             call_type_value = call_type_rec.id
    #
    #                     # 🔹 Create customer asset (with extended dates)
    #                     customer_asset = CustomerAsset.create({
    #                         'customer_id': picking.partner_id.id,
    #                         'product_id': product.id,
    #                         'serial_number_ids': lot.id if lot else False,
    #                         'order_id': order_line.id if order_line else False,
    #                         'source_type': 'sale_order' if sale_order.sale_order_type in ['secondary_orders',
    #                                                                                       'direct_orders'] else 'direct_product',
    #                         'start_date': start_date,
    #                         'end_date': end_date,
    #                         'extended_start_date': extended_start,
    #                         'extended_end_date': extended_end,
    #                         'asset_status': 'allocated',
    #                         'status': unit_status,
    #                         'product_category': product.categ_id.id or False,
    #                         'distributor_id': distributor_id,
    #                     })
    #
    #                     # 🔹 Create installation call if applicable
    #                     if product_tmpl.installed_ok:
    #                         installation_html = self._get_html_for_product(order_line, product) if order_line else ''
    #                         desc_html = f"<p>Installation call for product {product.name} (Serial: {lot.name if lot else 'No Serial'})</p>"
    #                         if installation_html:
    #                             desc_html += installation_html
    #
    #                         task_vals = {
    #                             'name': f"Installation Call - {product.name}",
    #                             'project_id': project.id,
    #                             'is_fsm': True,
    #                             'partner_id': picking.partner_id.id,
    #                             'customer_product_id': customer_asset.id,
    #                             'serial_number': customer_asset.serial_number_ids.id or False,
    #                             'installation_table_html': desc_html,
    #                             'call_type': call_type_value,
    #                         }
    #                         task = self.env['project.task'].sudo().create(task_vals)
    #
    #                         for attach in installation_attachments:
    #                             try:
    #                                 file_data = base64.b64decode(attach.upload_file, validate=True)
    #                             except (binascii.Error, ValueError):
    #                                 _logger.warning(f"Invalid file in installation attachment {attach.name}, skipped.")
    #                                 continue
    #                             filename = attach.upload_file_filename or attach.name or "attachment.dat"
    #                             task.message_post(
    #                                 body=f"Installation Checklist: {attach.name}",
    #                                 attachments=[(filename, file_data)],
    #                                 message_type='comment',
    #                                 subtype_xmlid='mail.mt_comment'
    #                             )
    #
    #     return super()._action_done()


    # @api.model
    # def _action_done(self):
    #     CustomerAsset = self.env['customer.product.mapping']
    #     DistributorAsset = self.env['distributor.asset']
    #
    #     enable_distributor = self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor')
    #     if not enable_distributor:
    #         return super()._action_done()
    #
    #     for picking in self:
    #         sale_order = picking.sale_id
    #         if not sale_order:
    #             continue
    #
    #         # 1️⃣ Distributor Assets - ONLY for primary orders
    #         if sale_order.sale_order_type == 'primary_orders' and sale_order.distributor_id:
    #             distributor_id = sale_order.distributor_id.id
    #             for move in picking.move_ids_without_package:
    #                 product_tmpl_id = move.product_id.product_tmpl_id.id
    #
    #                 if move.product_id.tracking != 'none':
    #                     lot_ids = move.move_line_ids.lot_id.ids
    #                     if lot_ids:
    #                         existing_assets = DistributorAsset.search([
    #                             ('lot_id', 'in', lot_ids),
    #                             ('product_id', '=', product_tmpl_id)
    #                         ])
    #                         existing_lot_ids = set(existing_assets.mapped('lot_id').ids)
    #
    #                         for ml in move.move_line_ids:
    #                             lot_id = ml.lot_id.id
    #                             if not lot_id or lot_id in existing_lot_ids:
    #                                 continue
    #                             DistributorAsset.create({
    #                                 'distributor_id': distributor_id,
    #                                 'product_id': product_tmpl_id,
    #                                 'status': 'unallocated',
    #                                 'lot_id': lot_id,
    #                             })
    #                 else:
    #                     qty = int(move.product_uom_qty)
    #                     DistributorAsset.create([{
    #                         'distributor_id': distributor_id,
    #                         'product_id': product_tmpl_id,
    #                         'status': 'unallocated',
    #                         'lot_id': False,
    #                     } for _ in range(qty)])
    #
    #         # 2️⃣ Customer Assets - secondary or direct orders
    #         if sale_order.sale_order_type in ['secondary_orders', 'direct_orders']:
    #             distributor_id = sale_order.distributor_id.id if sale_order.sale_order_type == 'secondary_orders' else False
    #
    #             # --- For secondary orders mark distributor assets allocated ---
    #             if sale_order.sale_order_type == 'secondary_orders':
    #                 for move in picking.move_ids_without_package:
    #                     product_tmpl_id = move.product_id.product_tmpl_id.id
    #                     serials = move.move_line_ids.lot_id.ids
    #                     if not sale_order.exists():
    #                         continue
    #
    #                     if serials:
    #                         unallocated_assets = DistributorAsset.search([
    #                             ('lot_id', 'in', serials),
    #                             ('product_id', '=', product_tmpl_id),
    #                             ('distributor_id', '=', distributor_id),
    #                             ('status', '=', 'unallocated'),
    #                         ])
    #                         lot2asset = {a.lot_id.id: a for a in unallocated_assets}
    #
    #                         for lot_id in serials:
    #                             asset = lot2asset.get(lot_id)
    #                             if asset:
    #                                 asset.status = 'allocated'
    #                             else:
    #                                 lot_name = self.env['stock.lot'].browse(lot_id).name
    #                                 _logger.info(f"No unallocated asset found for Lot {lot_name}")
    #                     else:
    #                         qty = int(move.product_uom_qty)
    #                         unallocated_assets = DistributorAsset.search([
    #                             ('product_id', '=', product_tmpl_id),
    #                             ('distributor_id', '=', distributor_id),
    #                             ('status', '=', 'unallocated')
    #                         ], limit=qty)
    #                         unallocated_assets.write({'status': 'allocated'})
    #
    #             # --- Skip excluded moves ---
    #             excluded_move_ids = set(picking.picking_parts_ids.mapped("move_id").ids)
    #
    #             Project = self.env['project.project'].sudo()
    #             project = Project.search([('name', '=', 'Service Call')], limit=1)
    #             if not project:
    #                 project = Project.create({'name': 'Service Call', 'is_fsm': True})
    #
    #             now = fields.Datetime.now()
    #
    #             for move in picking.move_ids:
    #                 if move.id in excluded_move_ids:
    #                     continue
    #
    #                 product = move.product_id
    #                 product_tmpl = product.product_tmpl_id
    #                 serials = move.move_line_ids.lot_id
    #
    #                 if serials:
    #                     serial_list = serials
    #                     qty_list = [1] * len(serials)
    #                 else:
    #                     qty = int(move.product_uom_qty)
    #                     serial_list = [None] * qty
    #                     qty_list = [1] * qty
    #
    #                 installation_attachments = self.env['installation.attachment.line']
    #                 if product_tmpl:
    #                     installation_attachments |= product_tmpl.installation_attachment_line_ids.filtered('upload_file')
    #                 if product.categ_id:
    #                     installation_attachments |= product.categ_id.installation_attachment_line_ids.filtered('upload_file')
    #
    #                 for idx, (lot, qty) in enumerate(zip(serial_list, qty_list), start=1):
    #                     order_line = move.sale_line_id or self.env['sale.order.line'].search([
    #                         ('order_id', '=', sale_order.id),
    #                         ('product_id', '=', product.id)
    #                     ], limit=1)
    #
    #                     unit_status = (order_line.unit_status if order_line else None) or 'chargeable'
    #
    #                     # Normal warranty
    #                     if unit_status == 'warranty' and order_line:
    #                         start_date = sale_order.warranty_start_date or fields.Date.today()
    #                         end_date = order_line.line_warranty_end_date or (fields.Date.today() + timedelta(days=1))
    #                     else:
    #                         start_date = fields.Date.today()
    #                         end_date = fields.Date.today() + timedelta(days=1)
    #
    #                     # Extended warranty logic
    #                     extended_start = False
    #                     extended_end = False
    #                     if sale_order and unit_status == 'warranty':
    #                         extended_note_line = sale_order.order_line.filtered(
    #                             lambda line: line.is_extended_warranty
    #                                          and line.display_type == 'line_note'
    #                                          and line.name
    #                                          and product.name
    #                                          and product.name in (line.name or "")
    #                         )
    #
    #                         if extended_note_line:
    #                             import re
    #                             from datetime import datetime
    #                             note_name = extended_note_line[0].name or ""
    #
    #                             start_match = re.search(r'Start Date:\s*(\d{2}-\d{2}-\d{4})', note_name)
    #                             if start_match:
    #                                 try:
    #                                     extended_start = datetime.strptime(start_match.group(1), '%d-%m-%Y').date()
    #                                 except ValueError:
    #                                     _logger.warning(f"Could not parse start date from: {start_match.group(1)}")
    #
    #                             end_match = re.search(r'End Date:\s*(\d{2}-\d{2}-\d{4})', note_name)
    #                             if end_match:
    #                                 try:
    #                                     extended_end = datetime.strptime(end_match.group(1), '%d-%m-%Y').date()
    #                                 except ValueError:
    #                                     _logger.warning(f"Could not parse end date from: {end_match.group(1)}")
    #
    #                     # Call type
    #                     call_type_value = False
    #                     if unit_status:
    #                         call_type_rec = self.env['call.type'].sudo().search([('name', 'ilike', unit_status.strip())], limit=1)
    #                         if call_type_rec:
    #                             call_type_value = call_type_rec.id
    #
    #                     # ✅ Check existing CustomerAsset to avoid duplicates
    #                     existing_asset = CustomerAsset.search([
    #                         ('customer_id', '=', picking.partner_id.id),
    #                         ('product_id', '=', product.id),
    #                         ('serial_number_ids', '=', lot.id if lot else False),
    #                         ('order_id', '=', order_line.id if order_line else False)
    #                     ], limit=1)
    #
    #                     if not existing_asset:
    #                         # Create customer asset (with extended dates)
    #                         customer_asset = CustomerAsset.create({
    #                             'customer_id': picking.partner_id.id,
    #                             'product_id': product.id,
    #                             'serial_number_ids': lot.id if lot else False,
    #                             'order_id': order_line.id if order_line else False,
    #                             'source_type': 'sale_order' if sale_order.sale_order_type in ['secondary_orders', 'direct_orders'] else 'direct_product',
    #                             'start_date': start_date,
    #                             'end_date': end_date,
    #                             'extended_start_date': extended_start,
    #                             'extended_end_date': extended_end,
    #                             'asset_status': 'allocated',
    #                             'status': unit_status,
    #                             'product_category': product.categ_id.id or False,
    #                             'distributor_id': distributor_id,
    #                         })
    #
    #                         # Create installation call if applicable
    #                         if product_tmpl.installed_ok:
    #                             installation_html = self._get_html_for_product(order_line, product) if order_line else ''
    #                             desc_html = f"<p>Installation call for product {product.name} (Serial: {lot.name if lot else 'No Serial'})</p>"
    #                             if installation_html:
    #                                 desc_html += installation_html
    #
    #                             task_vals = {
    #                                 'name': f"Installation Call - {product.name}",
    #                                 'project_id': project.id,
    #                                 'is_fsm': True,
    #                                 'partner_id': picking.partner_id.id,
    #                                 'customer_product_id': customer_asset.id,
    #                                 'serial_number': customer_asset.serial_number_ids.id or False,
    #                                 'installation_table_html': desc_html,
    #                                 'call_type': call_type_value,
    #                             }
    #                             task = self.env['project.task'].sudo().create(task_vals)
    #
    #                             for attach in installation_attachments:
    #                                 try:
    #                                     file_data = base64.b64decode(attach.upload_file, validate=True)
    #                                 except (binascii.Error, ValueError):
    #                                     _logger.warning(f"Invalid file in installation attachment {attach.name}, skipped.")
    #                                     continue
    #                                 filename = attach.upload_file_filename or attach.name or "attachment.dat"
    #                                 task.message_post(
    #                                     body=f"Installation Checklist: {attach.name}",
    #                                     attachments=[(filename, file_data)],
    #                                     message_type='comment',
    #                                     subtype_xmlid='mail.mt_comment'
    #                                 )
    #
    #     return super()._action_done()

    @api.model
    def _action_done(self):
        CustomerAsset = self.env['customer.product.mapping']
        DistributorAsset = self.env['distributor.asset']

        enable_distributor = self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor')
        if not enable_distributor:
            return super()._action_done()

        for picking in self:
            sale_order = picking.sale_id
            if not sale_order:
                continue

            # Distributor Assets - ONLY for primary orders
            if sale_order.sale_order_type == 'primary_orders' and sale_order.distributor_id:
                distributor_id = sale_order.distributor_id.id
                for move in picking.move_ids_without_package:
                    product_tmpl_id = move.product_id.product_tmpl_id.id

                    if move.product_id.tracking != 'none':
                        lot_ids = move.move_line_ids.lot_id.ids
                        if lot_ids:
                            existing_assets = DistributorAsset.search([
                                ('lot_id', 'in', lot_ids),
                                ('product_id', '=', product_tmpl_id)
                            ])
                            existing_lot_ids = set(existing_assets.mapped('lot_id').ids)

                            for ml in move.move_line_ids:
                                lot_id = ml.lot_id.id
                                if not lot_id or lot_id in existing_lot_ids:
                                    continue
                                DistributorAsset.create({
                                    'distributor_id': distributor_id,
                                    'product_id': product_tmpl_id,
                                    'status': 'unallocated',
                                    'lot_id': lot_id,
                                })
                    else:
                        qty = int(move.product_uom_qty)
                        DistributorAsset.create([{
                            'distributor_id': distributor_id,
                            'product_id': product_tmpl_id,
                            'status': 'unallocated',
                            'lot_id': False,
                        } for _ in range(qty)])

            # Customer Assets - secondary or direct orders
            if sale_order.sale_order_type in ['secondary_orders', 'direct_orders']:
                distributor_id = sale_order.distributor_id.id if sale_order.sale_order_type == 'secondary_orders' else False

                # --- For secondary orders mark distributor assets allocated ---
                if sale_order.sale_order_type == 'secondary_orders':
                    for move in picking.move_ids_without_package:
                        product_tmpl_id = move.product_id.product_tmpl_id.id
                        serials = move.move_line_ids.lot_id.ids
                        if not sale_order.exists():
                            continue

                        if serials:
                            unallocated_assets = DistributorAsset.search([
                                ('lot_id', 'in', serials),
                                ('product_id', '=', product_tmpl_id),
                                ('distributor_id', '=', distributor_id),
                                ('status', '=', 'unallocated'),
                            ])
                            lot2asset = {a.lot_id.id: a for a in unallocated_assets}

                            for lot_id in serials:
                                asset = lot2asset.get(lot_id)
                                if asset:
                                    asset.status = 'allocated'
                                else:
                                    lot_name = self.env['stock.lot'].browse(lot_id).name
                                    _logger.info(f"No unallocated asset found for Lot {lot_name}")
                        else:
                            qty = int(move.product_uom_qty)
                            unallocated_assets = DistributorAsset.search([
                                ('product_id', '=', product_tmpl_id),
                                ('distributor_id', '=', distributor_id),
                                ('status', '=', 'unallocated')
                            ], limit=qty)
                            unallocated_assets.write({'status': 'allocated'})

                # --- Skip excluded moves ---
                excluded_move_ids = set(picking.picking_parts_ids.mapped("move_id").ids)

                Project = self.env['project.project'].sudo()
                project = Project.search([('name', '=', 'Service Call')], limit=1)
                if not project:
                    project = Project.create({'name': 'Service Call', 'is_fsm': True})

                now = fields.Datetime.now()

                for move in picking.move_ids:
                    if move.id in excluded_move_ids:
                        continue

                    product = move.product_id
                    product_tmpl = product.product_tmpl_id
                    serials = move.move_line_ids.lot_id

                    if serials:
                        serial_list = serials
                        qty_list = [1] * len(serials)
                    else:
                        qty = int(move.product_uom_qty)
                        serial_list = [None] * qty
                        qty_list = [1] * qty

                    installation_attachments = self.env['installation.attachment.line']
                    if product_tmpl:
                        installation_attachments |= product_tmpl.installation_attachment_line_ids.filtered(
                            'upload_file')
                    if product.categ_id:
                        installation_attachments |= product.categ_id.installation_attachment_line_ids.filtered(
                            'upload_file')

                    for idx, (lot, qty) in enumerate(zip(serial_list, qty_list), start=1):
                        order_line = move.sale_line_id or self.env['sale.order.line'].search([
                            ('order_id', '=', sale_order.id),
                            ('product_id', '=', product.id)
                        ], limit=1)

                        unit_status = (order_line.unit_status if order_line else None) or 'chargeable'

                        # Normal warranty
                        if unit_status == 'warranty' and order_line:
                            start_date = sale_order.warranty_start_date or fields.Date.today()
                            end_date = order_line.line_warranty_end_date or (fields.Date.today() + timedelta(days=1))
                        else:
                            start_date = fields.Date.today()
                            end_date = fields.Date.today() + timedelta(days=1)

                        # 🟢 Extended Warranty Logic (new)
                        extended_start = False
                        extended_end = False

                        if sale_order:
                            extended_line = sale_order.order_line.filtered(
                                lambda l: l.is_extended_warranty and product.display_name in (l.name or "")
                            )
                            if extended_line:
                                desc = extended_line[0].name or ""
                                _logger.info(f"🔍 Extracting warranty dates from description: {desc}")

                                import re
                                from datetime import datetime as dt
                                match = re.search(
                                    r'from\s+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s+to\s+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
                                    desc, re.IGNORECASE
                                )
                                if match:
                                    try:
                                        start_str, end_str = match.groups()
                                        start_str = start_str.replace('/', '-')
                                        end_str = end_str.replace('/', '-')
                                        extended_start = dt.strptime(start_str, "%d-%m-%Y").date()
                                        extended_end = dt.strptime(end_str, "%d-%m-%Y").date()
                                        _logger.info(
                                            f"✅ Extracted Extended Dates → Start: {extended_start}, End: {extended_end}")
                                    except Exception as e:
                                        _logger.warning(f"Date parse failed for extended warranty: {e}")
                                else:
                                    _logger.debug(f"No date pattern found in: {desc}")

                        # Call type
                        call_type_value = False
                        if unit_status:
                            call_type_rec = self.env['call.type'].sudo().search(
                                [('name', 'ilike', unit_status.strip())], limit=1)
                            if call_type_rec:
                                call_type_value = call_type_rec.id

                        if picking.partner_id:
                            existing_asset = CustomerAsset.search([
                                ('customer_id', '=', picking.partner_id.id),
                                ('product_id', '=', product.id),
                                ('serial_number_ids', '=', lot.id if lot else False),
                                ('order_id', '=', order_line.id if order_line else False)
                            ], limit=1)

                            if existing_asset:
                                vals_to_update = {}
                                if not existing_asset.distributor_id and distributor_id:
                                    vals_to_update['distributor_id'] = distributor_id
                                if not existing_asset.asset_status:
                                    vals_to_update['asset_status'] = 'allocated'

                                vals_to_update.update({
                                    'start_date': start_date,
                                    'end_date': end_date,
                                    'extended_start_date': extended_start,
                                    'extended_end_date': extended_end,
                                    'status': unit_status,
                                })

                                existing_asset.write(vals_to_update)
                                customer_asset = existing_asset
                            else:
                                customer_asset = CustomerAsset.create({
                                    'customer_id': picking.partner_id.id,
                                    'product_id': product.id,
                                    'serial_number_ids': lot.id if lot else False,
                                    'order_id': order_line.id if order_line else False,
                                    'source_type': 'sale_order' if sale_order.sale_order_type in ['secondary_orders',
                                                                                                  'direct_orders'] else 'direct_product',
                                    'start_date': start_date,
                                    'end_date': end_date,
                                    'extended_start_date': extended_start,
                                    'extended_end_date': extended_end,
                                    'asset_status': 'allocated',
                                    'status': unit_status,
                                    'product_category': product.categ_id.id or False,
                                    'distributor_id': distributor_id,
                                })

                        # Installation call creation
                        if product_tmpl.installed_ok:
                            installation_html = self._get_html_for_product(order_line, product) if order_line else ''
                            desc_html = f"<p>Installation call for product {product.name} (Serial: {lot.name if lot else 'No Serial'})</p>"
                            if installation_html:
                                desc_html += installation_html

                            complaint_type = self.env['complaint.type'].search([('name','=','Installation Call')])

                            task_vals = {
                                'name': f"Installation Call - {product.name}",
                                'project_id': project.id,
                                'is_fsm': True,
                                'partner_id': picking.partner_id.id,
                                'customer_product_id': customer_asset.id,
                                'serial_number': customer_asset.serial_number_ids.id or False,
                                'installation_table_html': desc_html,
                                'call_type': call_type_value,
                                'complaint_type_id':complaint_type,

                            }
                            task = self.env['project.task'].sudo().create(task_vals)

                            for attach in installation_attachments:
                                try:
                                    file_data = base64.b64decode(attach.upload_file, validate=True)
                                except (binascii.Error, ValueError):
                                    _logger.warning(f"Invalid file in installation attachment {attach.name}, skipped.")
                                    continue
                                filename = attach.upload_file_filename or attach.name or "attachment.dat"
                                task.message_post(
                                    body=f"Installation Checklist: {attach.name}",
                                    attachments=[(filename, file_data)],
                                    message_type='comment',
                                    subtype_xmlid='mail.mt_comment'
                                )

        return super()._action_done()



    def _get_html_for_product(self, order_line, product):
        """Return installation HTML table for a product:
           - show attachments once
           - show dynamic fields per order line separately
        """
        InstallationLine = self.env['sale.order.installation.line']

        # All lines for this product in the order
        all_lines = InstallationLine.search([
            ('order_id', '=', order_line.order_id.id),
            ('product_id', '=', product.product_tmpl_id.id)
        ])

        if not all_lines:
            return ""

        html = ""

        # --- Attachments (shared across product) ---
        attachment_lines = all_lines.filtered(lambda l: l.file)
        if attachment_lines:
            html += """
            <h4>Attachments</h4>
            <table style="width:100%; border-collapse:collapse; font-size:13px; color:#444; margin-bottom:15px;">
                <thead>
                    <tr style="background-color:#f6f6f6; border-bottom:1px solid #ddd;">
                        <th style="padding:6px; text-align:left;">Attachment Name</th>
                        <th style="padding:6px; text-align:left;">File</th>
                    </tr>
                </thead>
                <tbody>
            """
            for line in attachment_lines:
                file_link = f'/web/content/{line._name}/{line.id}/file/{line.file_name}?download=true'
                file_link_html = f'<a href="{file_link}">{line.file_name or "Download"}</a>'
                html += f"""
                    <tr style="border-bottom:1px solid #eee;">
                        <td style="padding:6px; font-weight:600;">{line.attachment_name}</td>
                        <td style="padding:6px;">{file_link_html}</td>
                    </tr>
                """
            html += "</tbody></table>"

        # --- Dynamic Fields (per order line) ---
        # take only lines of this order_line
        dynamic_lines = all_lines.filtered(
            lambda l: not l.file and l.sale_line_id.id == order_line.id
        )
        if dynamic_lines:
            html += """
            <h4>Custom Fields</h4>
            <table style="width:100%; border-collapse:collapse; font-size:13px; color:#444; margin-bottom:15px;">
                <thead>
                    <tr style="background-color:#f6f6f6; border-bottom:1px solid #ddd;">
                        <th style="padding:6px; text-align:left;">Field</th>
                        <th style="padding:6px; text-align:left;">Value</th>
                    </tr>
                </thead>
                <tbody>
            """
            for line in dynamic_lines:
                html += f"""
                    <tr style="border-bottom:1px solid #eee;">
                        <td style="padding:6px; font-weight:600;">{line.attachment_name}</td>
                        <td style="padding:6px;">{line.product_display_name or ''}</td>
                    </tr>
                """
            html += "</tbody></table>"

        # Save to order for later display if you want
        order_line.order_id.installation_table_html = html

        return html


    # def _action_confirm(self):
    #     res = super()._action_confirm()
    #     for order in self:
    #         if not self.env['ir.config_parameter'].sudo().get_param('product_installation.enable_distributor'):
    #             continue
    #         if order.sale_order_type == 'primary_orders' and order.distributor_id and order.distributor_id.warehouse_id:
    #             for picking in order.picking_ids:
    #                 picking.location_dest_id = order.distributor_id.warehouse_id.lot_stock_id.id
    #         elif order.sale_order_type == 'secondary_orders' and order.distributor_id and order.distributor_id.warehouse_id:
    #             for picking in order.picking_ids:
    #                 picking.location_id = order.distributor_id.warehouse_id.lot_stock_id.id
    #     return res