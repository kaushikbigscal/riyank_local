# -*- coding: utf-8 -*-
# from odoo import http


# class InactiveToArchived(http.Controller):
#     @http.route('/inactive_to_archived/inactive_to_archived', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/inactive_to_archived/inactive_to_archived/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('inactive_to_archived.listing', {
#             'root': '/inactive_to_archived/inactive_to_archived',
#             'objects': http.request.env['inactive_to_archived.inactive_to_archived'].search([]),
#         })

#     @http.route('/inactive_to_archived/inactive_to_archived/objects/<model("inactive_to_archived.inactive_to_archived"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('inactive_to_archived.object', {
#             'object': obj
#         })

