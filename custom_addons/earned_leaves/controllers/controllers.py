# -*- coding: utf-8 -*-
# from odoo import http


# class EarnedLeaves(http.Controller):
#     @http.route('/earned_leaves/earned_leaves', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/earned_leaves/earned_leaves/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('earned_leaves.listing', {
#             'root': '/earned_leaves/earned_leaves',
#             'objects': http.request.env['earned_leaves.earned_leaves'].search([]),
#         })

#     @http.route('/earned_leaves/earned_leaves/objects/<model("earned_leaves.earned_leaves"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('earned_leaves.object', {
#             'object': obj
#         })

