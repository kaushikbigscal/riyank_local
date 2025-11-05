
from odoo import fields, models


class FieldVisitCloseReason(models.Model):
    _name = "field.visit.close.reason"
    _description = "Field Visit Close Reason"

    name = fields.Char(string="Description", required=True, translate=True)
    close_type = fields.Selection(
        selection=[("cancel", "Cancel"), ("incident", "Incident")],
        string="Type",
        required=True,
        default="cancel",
    )
    require_image = fields.Boolean(default=False)
    reschedule = fields.Boolean(default=False)
