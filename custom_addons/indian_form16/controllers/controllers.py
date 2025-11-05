# -*- coding: utf-8 -*-
# from odoo import http


# class IndianForm16(http.Controller):
#     @http.route('/indian_form16/indian_form16', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/indian_form16/indian_form16/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('indian_form16.listing', {
#             'root': '/indian_form16/indian_form16',
#             'objects': http.request.env['indian_form16.indian_form16'].search([]),
#         })

#     @http.route('/indian_form16/indian_form16/objects/<model("indian_form16.indian_form16"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('indian_form16.object', {
#             'object': obj
#         })

