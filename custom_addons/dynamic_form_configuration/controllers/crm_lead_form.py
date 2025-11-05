from odoo import http
from odoo.http import request
from lxml import etree
from collections import OrderedDict
import logging, ast

_logger = logging.getLogger(__name__)


class CRMLeadForm(http.Controller):

    @http.route('/web/crm_lead_form/get_lead', type='json', auth='user')
    def get_lead_form(self):
        return self._get_crm_lead_form(lead_type='lead')

    @http.route('/web/crm_lead_form/get_opportunity', type='json', auth='user')
    def get_opportunity_form(self):
        return self._get_crm_lead_form(lead_type='opportunity')

    def _get_crm_lead_form(self, lead_type=None):
        try:
            model_name = "crm.lead"
            view_xml_id = "crm.crm_lead_view_form"

            view_ref = request.env.ref(view_xml_id, raise_if_not_found=False)
            if not view_ref:
                return {'status': False, 'error': f'View {view_xml_id} not found'}

            model = request.env[model_name]
            view_info = model.with_context(lang=request.env.user.lang).get_view(view_ref.id, view_type='form')
            arch = view_info.get('arch', '')
            if not arch:
                return {'status': False, 'error': 'View architecture not found'}

            arch_tree = etree.fromstring(arch)
            sheet_fields = list(arch_tree.iter("field"))
            ordered_fields = OrderedDict()

            for field in sheet_fields:
                field_name = field.get('name')
                if field_name:
                    ordered_fields[field_name] = field

            # Get mobile-enabled fields with caching info
            mobile_fields = request.env['ir.model.fields.mobile'].search([
                ('model_id.model', '=', model_name),
                ('for_mobile', '=', True)
            ])
            mobile_field_map = {
                mf.field_id.name: {
                    'is_caching': mf.is_caching,
                    'caching_refresh_time': mf.caching_refresh_time,
                    'is_instant': mf.is_instant,
                }
                for mf in mobile_fields if mf.field_id
            }

            if not mobile_field_map:
                return {'status': False, 'error': 'No mobile fields found for this model'}

            fields_data = model.fields_get()
            result = {
                'models': {
                    model_name: []
                },
                'dynamic_fields': {
                    model_name: []
                }
            }

            for field_name, field_element in ordered_fields.items():
                if field_name in mobile_field_map and field_name in fields_data:
                    field_info = fields_data[field_name]
                    mobile_config = mobile_field_map[field_name]

                    result['models'][model_name].append({
                        'name': field_name,
                        'string': field_info.get('string', field_name),
                        'type': field_info.get('type', 'char'),
                        'readonly': field_info.get('readonly', False),
                        'required': field_info.get('required', False),
                        'is_caching': mobile_config.get('is_caching', False),
                        'caching_refresh_time': mobile_config.get('caching_refresh_time', ''),
                        'is_instant': mobile_config.get('is_instant', False),
                        'widget': field_info.get('widget', ''),
                    })

            # Add dynamic fields
            dynamic_fields = request.env['dynamic.fields'].search([('model', '=', model_name), ('status', '=', 'form')])
            result['dynamic_fields'] = []
            for field in dynamic_fields:

                selection_data = []
                if field.selection_field:
                    try:
                        selection_data = ast.literal_eval(field.selection_field)
                    except Exception:
                        selection_data = []

                result['dynamic_fields'].append({
                    "name": field.name,
                    "field_description": field.field_description,
                    "field_type": field.field_type,
                    "selection_field": selection_data,
                    "ref_model_id": {
                        "fields": {
                            "model": field.ref_model_id.model if field.ref_model_id else False
                        }
                    },
                    "widget_id": {
                        "fields": {
                            "name": field.widget_id.name if field.widget_id else False
                        }
                    },
                    "required": field.required,
                    "readonly": field.readonly,
                    "is_instant": field.is_instant,
                })

            return result

        except Exception as e:
            _logger.exception("Error fetching CRM lead form")
            return {'status': False, 'error': str(e)}
