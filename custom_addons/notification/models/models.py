import json
import logging
from odoo import models, api, fields
from pywebpush import webpush, WebPushException

from odoo.http import request

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    webpush_subscription = fields.Text("WebPush Subscription")


class MailPartnerDevice(models.Model):
    _inherit = 'mail.partner.device'


    @staticmethod
    def send_webpush_to_partner(partner, title, body, url="/web"):
        if not partner.webpush_subscription:
            _logger.warning("🚫 Partner has no webpush subscription")
            return False

        try:
            subscription_info = json.loads(partner.webpush_subscription)
            env = partner.env  # Use the partner’s env to get config
            ir_params = env['ir.config_parameter'].sudo()

            vapid_private_key = ir_params.get_param('mail.web_push_vapid_private_key')
            vapid_claims = {"sub": "mailto:admin@example.com"}

            payload = json.dumps({
                "title": title,
                "body": body,
                "url": url,
            })

            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
            )
            _logger.info("✅ WebPush sent to %s", partner.name)
            return True

        except WebPushException as ex:
            _logger.warning("❌ WebPushException: %s", repr(ex))
        except Exception as e:
            _logger.warning("❌ General Exception: %s", str(e))
        return False

