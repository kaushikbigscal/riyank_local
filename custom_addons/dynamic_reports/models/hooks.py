# from odoo import SUPERUSER_ID, api
#
# def auto_generate_report_templates(cr, registry):
#     from odoo.api import Environment
#     env = Environment(cr, SUPERUSER_ID, {})
#
#     templates = env['xml.upload'].search([])
#
#     for template in templates:
#         try:
#             template.download_report()
#             print("Generated report for template ID %s", template.id)
#         except Exception as e:
#             print("not found any template")
#
