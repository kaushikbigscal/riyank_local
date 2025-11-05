from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import re
import logging
from datetime import date
_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        """Validate picking, handle serials, and create Customer–Product Mapping including extended warranty dates parsed from description."""

        # 1️⃣ Validate serial numbers for parts
        for part in self.picking_parts_ids:
            if part.tracking == 'serial':
                if len(part.lot_ids) != part.quantity:
                    raise UserError(
                        _('You need to provide a serial number for each part quantity for %s') % part.part_name
                    )

        # 2️⃣ Create/update stock moves for parts
        self.picking_parts_ids._create_stock_moves()

        # 3️⃣ Call super to complete normal validation
        res = super(StockPicking, self).button_validate()

        # 4️⃣ Create Customer–Product Mapping
        CustomerProductMapping = self.env['customer.product.mapping']

        for picking in self:
            customer = picking.partner_id
            sale_order = picking.sale_id

            for move in picking.move_ids:
                product = move.product_id
                serials = move.move_line_ids.mapped("lot_id") or [False]

                for lot in serials:
                    order_line = move.sale_line_id or False
                    unit_status = 'chargeable'

                    # Determine status & warranty dates
                    if order_line:
                        unit_status = order_line.unit_status or 'chargeable'

                    if unit_status == 'warranty' and sale_order and order_line:
                        start_date = sale_order.warranty_start_date or fields.Date.today()
                        end_date = order_line.line_warranty_end_date or (fields.Date.today() + timedelta(days=1))
                    else:
                        start_date = fields.Date.today()
                        end_date = fields.Date.today() + timedelta(days=1)

                    # 🟢 Extract Extended Warranty Dates from Description
                    extended_start = False
                    extended_end = False

                    if sale_order:
                        # Find the related extended warranty product line that contains the base product name
                        extended_line = sale_order.order_line.filtered(
                            lambda l: l.is_extended_warranty and product.display_name in (l.name or "")
                        )
                        if extended_line:
                            desc = extended_line[0].name or ""
                            _logger.info(f"🔍 Extracting warranty dates from description: {desc}")

                            # Regex to extract "from <date> to <date>"
                            match = re.search(
                                r'from\s+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s+to\s+(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
                                desc, re.IGNORECASE
                            )

                            if match:
                                try:
                                    start_str, end_str = match.groups()
                                    start_str = start_str.replace('/', '-')
                                    end_str = end_str.replace('/', '-')
                                    from datetime import datetime as dt
                                    extended_start = dt.strptime(start_str, "%d-%m-%Y").date()
                                    extended_end = dt.strptime(end_str, "%d-%m-%Y").date()
                                    _logger.info(
                                        f"✅ Extracted Extended Dates → Start: {extended_start}, End: {extended_end}")
                                except Exception as e:
                                    _logger.warning(f"⚠️ Date parse failed for extended warranty: {e}")
                            else:
                                _logger.debug(f"No date pattern found in: {desc}")

                    # Avoid duplicates
                    domain = [
                        ('customer_id', '=', customer.id),
                        ('product_id', '=', product.id),
                        ('order_id', '=', order_line.id if order_line else False),
                    ]
                    if lot:
                        domain.append(('serial_number_ids', '=', lot.id))

                    existing = CustomerProductMapping.search(domain, limit=1)

                    # 5️⃣ Create or Update Mapping
                    mapping_vals = {
                        'customer_id': customer.id,
                        'product_id': product.id,
                        'serial_number_ids': lot.id if lot else False,
                        'order_id': order_line.id if order_line else False,
                        'source_type': 'sale_order' if sale_order else 'direct_product',
                        'start_date': start_date,
                        'end_date': end_date,
                        'extended_start_date': extended_start,
                        'extended_end_date': extended_end,
                        'status': unit_status,
                        'product_category': product.categ_id.id if product.categ_id else False,
                    }

                    if existing:
                        _logger.info(f"🔄 Updating existing mapping for {product.display_name}")
                        existing.write(mapping_vals)
                    else:
                        _logger.info(f"🆕 Creating new mapping: {mapping_vals}")
                        CustomerProductMapping.create(mapping_vals)

        return res

class CustomerProductMapping(models.Model):
    _inherit = "customer.product.mapping"

    extended_start_date = fields.Date(
        string="Extended Warranty Start Date",
        help="Start date of the extended warranty period extracted from description.",
        tracking=True
    )
    extended_end_date = fields.Date(
        string="Extended Warranty End Date",
        help="End date of the extended warranty period extracted from description.",
        tracking=True
    )

    @api.model
    def _cron_extended_warranty_status(self):
        """
        Cron to manage normal + extended warranty and mark asset chargeable when both expire.
        Handles:
        - start_date, end_date  (Normal Warranty)
        - extended_start_date, extended_end_date  (Extended Warranty)
        """
        today = date.today()
        _logger.info("Extended Warranty Cron started on %s", today)

        records = self.search([])

        for rec in records:
            try:
                # --- CASE 1: Normal Warranty still active ---
                if rec.end_date and today <= rec.end_date:
                    continue  # No action needed

                # --- CASE 2: No Extended Warranty defined ---
                if not rec.extended_start_date or not rec.extended_end_date:
                    if rec.end_date and today > rec.end_date and rec.status != 'chargeable':
                        rec.status = 'chargeable'
                        rec.message_post(
                            body=_("Asset warranty period is over. The asset is now chargeable.")
                        )
                        _logger.info("Warranty expired (no extension): Asset %s set to chargeable.",
                                     rec.name)
                    continue

                # --- CASE 3: Extended Warranty Active ---
                if rec.end_date and today > rec.end_date and today <= rec.extended_end_date:
                    if rec.status != 'warranty':
                        rec.status = 'warranty'
                    last_log = rec.message_ids.filtered(
                        lambda m: 'extended warranty is starting' in m.body.lower()
                    )
                    if not last_log:
                        rec.message_post(
                            body=_("Asset warranty is over and extended warranty is starting.")
                        )
                    # Optionally extend visible warranty end date
                    rec.end_date = rec.extended_end_date
                    _logger.info("Asset %s under extended warranty until %s.",
                                 rec.name,
                                 rec.extended_end_date)
                    continue

                # --- CASE 4: Extended Warranty Expired ---
                if rec.extended_end_date and today > rec.extended_end_date:
                    if rec.status != 'chargeable':
                        rec.status = 'chargeable'
                        rec.message_post(
                            body=_("Extended warranty period is over. The asset is now chargeable.")
                        )
                        _logger.info("Extended warranty expired: Asset %s set to chargeable.",
                                     rec.name)

            except Exception as e:
                _logger.error("Error processing asset %s: %s", rec.id, e)

        _logger.info("Extended Warranty Cron completed successfully.")