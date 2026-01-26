# -*- coding: utf-8 -*-
# from odoo import http


# class RestApiHelper(http.Controller):
#     @http.route('/rest_api_helper/rest_api_helper', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/rest_api_helper/rest_api_helper/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('rest_api_helper.listing', {
#             'root': '/rest_api_helper/rest_api_helper',
#             'objects': http.request.env['rest_api_helper.rest_api_helper'].search([]),
#         })

#     @http.route('/rest_api_helper/rest_api_helper/objects/<model("rest_api_helper.rest_api_helper"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('rest_api_helper.object', {
#             'object': obj
#         })
