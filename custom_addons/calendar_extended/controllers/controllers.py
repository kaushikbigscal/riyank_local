# -*- coding: utf-8 -*-
# from odoo import http


# class CalendarExtended(http.Controller):
#     @http.route('/calendar_extended/calendar_extended', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/calendar_extended/calendar_extended/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('calendar_extended.listing', {
#             'root': '/calendar_extended/calendar_extended',
#             'objects': http.request.env['calendar_extended.calendar_extended'].search([]),
#         })

#     @http.route('/calendar_extended/calendar_extended/objects/<model("calendar_extended.calendar_extended"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('calendar_extended.object', {
#             'object': obj
#         })

