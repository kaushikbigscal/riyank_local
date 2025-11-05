from odoo import http
from odoo.http import request
from lxml import etree


class MobileFieldsController(http.Controller):

    @http.route('/web/mobile_fields', type='json', auth='user')
    def get_mobile_fields(self):
        """
        API endpoint to get fields marked as 'for_mobile' for a given model and view reference ID.
        Combines the fields from the model and the view, and filters based on 'for_mobile'.
        Includes visibility conditions extracted from the view XML using domain, groups, and invisible.
        """
        try:
            request_data = request.httprequest.get_json()
            model_name = request_data.get('model')
            view_xml_id = request_data.get('view_xml_id')

            if not model_name or not view_xml_id:
                return {'status': 'false', 'error': 'Model and view_xml_id are required'}

            if model_name not in request.env:
                return {'status': 'false', 'error': f'Model "{model_name}" does not exist.'}

            # Get model fields
            model_obj = request.env[model_name]
            fields_data = model_obj.fields_get()

            # Get view reference
            view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
            if not view_ref:
                return {'status': 'false', 'error': f'View {view_xml_id} not found'}

            # Get view architecture
            view_info = model_obj.with_context(lang=request.env.user.lang).get_view(view_ref.id, view_type='form')
            arch = view_info.get('arch', '')
            if not arch:
                return {'status': 'false', 'error': 'View architecture not found'}

            arch_tree = etree.fromstring(arch)

            # Combine fields from model and view (get intersection)
            model_fields = set(fields_data.keys())
            view_fields = set(field.get('name') for field in arch_tree.xpath("//field") if field.get('name'))
            common_fields = model_fields.intersection(view_fields)  # Get only common fields

            # Fetch 'for_mobile' fields
            mobile_field_model = request.env['ir.model.fields.mobile']
            mobile_fields = {}
            for_mobile_records = mobile_field_model.search(
                [('field_id.model', '=', model_name), ('for_mobile', '=', True)])

            # Collect fields marked as 'for_mobile' and present in both model and view
            for_mobile_fields = {rec.field_id.name for rec in for_mobile_records}

            # Process fields for response
            for field_name in common_fields:
                if field_name in for_mobile_fields:
                    field_info = fields_data.get(field_name, {})
                    # Find visibility conditions from the view using domain, groups, and invisible
                    view_field = arch_tree.xpath(f"//field[@name='{field_name}']")
                    visibility_conditions = None
                    invisible_condition = None

                    if view_field:
                        domain = view_field[0].get('domain', None)
                        groups = view_field[0].get('groups', None)
                        invisible_condition = view_field[0].get('invisible', None)

                        visibility_conditions = {
                            'domain': domain,
                            'groups': groups,
                            'invisible': invisible_condition
                        }

                    # Add field info with visibility conditions
                    mobile_fields[field_name] = {
                        'type': field_info.get('type'),
                        'string': field_info.get('string'),
                        'readonly': field_info.get('readonly'),
                        'required': field_info.get('required', False),
                        'selection': field_info.get('selection', []),
                        'depends': field_info.get('depends', False),
                        'visibility_conditions': visibility_conditions
                    }
                    # Add relation field information
                    if field_info.get('type') in ['many2one', 'one2many', 'many2many']:
                        mobile_fields[field_name].update({
                            'relation': field_info.get('relation', ''),
                            'relation_field': field_info.get('relation_field', ''),
                            'relation_comodel': field_info.get('comodel_name', ''),
                            'context': field_info.get('context', {}),
                        })

            return {
                'status': 'success',
                'fields': mobile_fields
            }

        except Exception as e:
            return {'status': 'false', 'error': str(e)}
