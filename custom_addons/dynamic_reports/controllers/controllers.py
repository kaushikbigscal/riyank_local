# -*- coding: utf-8 -*-
# from odoo import http


# class DynamicReports(http.Controller):
#     @http.route('/dynamic_reports/dynamic_reports', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/dynamic_reports/dynamic_reports/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('dynamic_reports.listing', {
#             'root': '/dynamic_reports/dynamic_reports',
#             'objects': http.request.env['dynamic_reports.dynamic_reports'].search([]),
#         })

#     @http.route('/dynamic_reports/dynamic_reports/objects/<model("dynamic_reports.dynamic_reports"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('dynamic_reports.object', {
#             'object': obj
#         })

