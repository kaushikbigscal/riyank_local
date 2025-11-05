""" Device token clear when logout"""
from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.session import Session  # Import the original Session class

class SessionInherit(Session):  # Inheriting the original Session controller

    @http.route('/web/session/destroy', type='json', auth="user")
    def destroy(self):
        user = request.env['res.users'].sudo().browse(request.session.uid)  # Fetch logged-in user
        if user.exists() and 'device_token' in user:
            user.sudo().write({'device_token': False})  # Clear the device_token

        return super().destroy()  # Call the original method

    @http.route('/web/session/logout', type='http', auth="none")
    def logout(self, redirect='/web'):
        user_id = request.session.uid  # Get user ID from session
        if user_id:
            user = request.env['res.users'].sudo().browse(user_id)
            if user.exists() and 'device_token' in user:
                user.sudo().write({'device_token': False})  # Clear the device_token


        return super().logout(redirect)  # Call the original method