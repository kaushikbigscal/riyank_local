# models/portal_notification.py
from odoo import models, fields, api
from odoo.http import request
from odoo.tools import format_datetime


class PortalNotification(models.Model):
    _name = "portal.notification"
    _description = "Portal Notifications"
    _order = "create_date desc"

    partner_id = fields.Many2one('res.partner', string="Partner", required=True, ondelete='cascade')
    title = fields.Char(string="Title", required=True)
    message = fields.Text(string="Message")
    url = fields.Char(string="Target URL")
    is_read = fields.Boolean(string="Read", default=False)

    res_model = fields.Char(string="Related Model")
    res_id = fields.Integer(string="Related Record ID")

    @api.model
    def create_for_partner(self, partner, title, message, url="/my/home", res_model=None, res_id=None):
        return self.create({
            "partner_id": partner.id,
            "title": title,
            "message": message,
            "url": url,
            "res_model": res_model,
            "res_id": res_id,
        })
