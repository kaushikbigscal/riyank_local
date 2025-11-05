# -*- coding: utf-8 -*-
# from odoo import http


# class ExtendedWarrantyProduct(http.Controller):
#     @http.route('/extended_warranty_product/extended_warranty_product', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/extended_warranty_product/extended_warranty_product/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('extended_warranty_product.listing', {
#             'root': '/extended_warranty_product/extended_warranty_product',
#             'objects': http.request.env['extended_warranty_product.extended_warranty_product'].search([]),
#         })

#     @http.route('/extended_warranty_product/extended_warranty_product/objects/<model("extended_warranty_product.extended_warranty_product"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('extended_warranty_product.object', {
#             'object': obj
#         })

