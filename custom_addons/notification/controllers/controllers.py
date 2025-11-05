from odoo import http
from odoo.http import request
import json
from odoo.modules.module import get_module_resource

class ServiceWorkerController(http.Controller):

    @http.route('/service_worker.js', type='http', auth='public')
    def webpush_service_worker(self):
        file_path = get_module_resource('notification', 'static', 'service_worker.js')
        with open(file_path, 'rb') as f:
            content = f.read()
        response = request.make_response(
            content,
            headers=[
                ('Content-Type', 'application/javascript'),
            ]
        )
        return response

class WebPushNotification(http.Controller):

    @http.route('/notification/get_vapid_key', type='json', auth='public')
    def get_vapid_key(self):
        key = request.env['ir.config_parameter'].sudo().get_param('mail.web_push_vapid_public_key')
        return {"public_key": key}

    @http.route('/notification/partner_id', type='json', auth='public')
    def get_partner_id(self):
        user = request.env.user
        if user._is_public():
            return {'partner_id': None}
        return {'partner_id': user.partner_id.id}
 

    @http.route('/webpush/save_subscription', type='json', auth='public')
    def save_subscription(self, subscription):
        partner = request.env.user.partner_id

        if partner:
            partner.sudo().write({
                'webpush_subscription': json.dumps(subscription)
            })

            return {'status': 'success'}
        else:
            return {'status': 'failed'}

