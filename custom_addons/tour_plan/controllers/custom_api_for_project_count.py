from odoo import http
from odoo.http import request


class ProjectTaskAPI(http.Controller):

    @http.route('/web/todo/count', type='json', auth='user')
    def task_count(self, user_ids=None, tag_ids=None):
        domain = [
            ('project_id', '=', False),
            ('parent_id', '=', False)
        ]

        if user_ids:
            try:
                user_ids = [int(uid) for uid in user_ids]
                user_conditions = [('user_ids', '=', user_id) for user_id in user_ids]
                domain += ['&'] * (len(user_conditions) - 1) + user_conditions
            except ValueError:
                return {
                    'status': 'false',
                    'error': 'Invalid user_ids format. Must be a list of integers.'
                }

        if tag_ids:
            try:
                tag_ids = [int(tid) for tid in tag_ids]
                tag_conditions = [('tag_ids', '=', tag_id) for tag_id in tag_ids]
                domain += ['&'] * (len(tag_conditions) - 1) + tag_conditions
            except ValueError:
                return {
                    'status': 'false',
                    'error': 'Invalid tag_ids format. Must be a list of integers.'
                }


        try:
            task_data = request.env['project.task'].sudo().read_group(
                domain=domain,
                fields=['personal_stage_type_id'],
                groupby=['personal_stage_type_id']
            )

            grouped_data = {}
            for group in task_data:
                stage_id = group['personal_stage_type_id'][0]
                stage_name = group['personal_stage_type_id'][1]
                count = group['personal_stage_type_id_count']

                if stage_name not in grouped_data:
                    grouped_data[stage_name] = {
                        'stage_id': stage_id,
                        'stage_name': stage_name,
                        'count': count
                    }

            response = {
                'status': 'success',
                'data': list(grouped_data.values())
            }
            return response


        except Exception as query_error:

            message = {str(query_error)}

            return {

                'status': 'false',
                'error': message

            }

# from odoo import http
# from odoo.http import request, Response
#
# class ProjectTaskAPI(http.Controller):
#
#     @http.route('/api/project/count', type='json', auth='user', methods=['GET'])
#     def task_count(self, user_id=None, tag_ids=None, company_id=None, last_update_status=None):
#         try:
#             domain = [("is_internal_project", "=", False)]
#
#             if user_id:
#                 try:
#                     user_id = int(user_id)
#                     domain.append(('user_id', '=', user_id))
#                 except ValueError:
#                     return {'status': 'false', 'error': 'Invalid user_id format. Must be an integer.'}
#
#             if tag_ids:
#                 try:
#                     tag_ids = [int(tag_id) for tag_id in tag_ids.split(',')]
#                     domain.append(('tag_ids', 'in', tag_ids))
#                 except ValueError:
#                     return {'status': 'false', 'error': 'Invalid tag_ids format. Must be a comma-separated list of integers.'}
#
#             if company_id:
#                 try:
#                     company_id = int(company_id)
#                     domain.append(('company_id', '=', company_id))
#                 except ValueError:
#                     return {'status': 'false', 'error': 'Invalid company_id format. Must be an integer.'}
#
#             if last_update_status:
#                 if not isinstance(last_update_status, str):
#                     return {'status': 'false', 'error': 'Invalid last_update_status format. Must be a string.'}
#                 domain.append(('last_update_status', '=', last_update_status))
#
#
#             task_data = request.env['project.project'].sudo().read_group(
#                 domain=domain,
#                 fields=['stage_id'],
#                 groupby=['stage_id']
#             )
#
#             response_data = [
#                 {
#                     'stage_id': group['stage_id'][0],
#                     'stage_name': group['stage_id'][1],
#                     'count': group['stage_id_count']
#                 } for group in task_data
#             ]
#
#             return {
#                 'status': 'success',
#                 'data': response_data
#             }
#
#         except Exception as e:
#
#             return {
#                 'status': 'false',
#                 'error': 'str(e)'
#
#             }