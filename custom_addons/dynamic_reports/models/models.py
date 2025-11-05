import base64

from odoo import models, fields
import xml.etree.ElementTree as ET

from odoo.exceptions import UserError


class XmlUpload(models.Model):
    _name = 'xml.upload'
    _description = 'Uploaded XML File'

    name = fields.Char("Filename")
    xml_file = fields.Binary("XML File")
    xml_content = fields.Text("XML Content" ,readonly=False)
    model_id = fields.Many2one('ir.model', string='Target Model')
    # report_config_id = fields.Many2one('xml.upload', string='Report Template', required=True)
    report_action = fields.Selection([
        ('action_xml_upload_custom_report_format_for_all', 'Employee PaySlip Report'),
        ('action_xml_upload_custom_report_format_for_all_service_call', 'Service Call Detailed report'),
        ('action_xml_upload_custom_report_format_for_all_account_move_invoice', 'Invoice Report'),
    ], string="Report Type", required=True)

    def parse_xml(self, xml_data):
        try:

            self.xml_content = xml_data.decode('utf-8')
            print(self.xml_content)
        except ET.ParseError as e:
            raise ValueError(f"XML Parse Error: {str(e)}")



    def upload_and_parse_xml(self):
        if self.xml_file:
            xml_data = base64.b64decode(self.xml_file)
            print(xml_data)
            self.parse_xml(xml_data)
        else:
            raise ValueError("No XML file uploaded")

    def download_report(self):
        self.ensure_one()

        if not self.model_id:
            raise UserError("Please select a model.")



        model = self.model_id.model
        record_model = self.env[self.model_id.model]
        if model == 'hr.payslip':
            if self.xml_content:
                xml_content = self.xml_content.strip()
                if xml_content.startswith('<?xml'):
                    xml_content = xml_content.split('?>', 1)[1].strip()

                if self.report_action == 'action_xml_upload_custom_report_format_for_all':

                    view = self.env.ref('dynamic_reports.report_template_xml_upload')
                    view.arch_db = xml_content
                    view.write({'arch_db': xml_content})
                    report_action = 'dynamic_reports.action_xml_upload_custom_report_format_for_all'


            target_record = record_model.search([], limit=1)
        elif model == 'project.task':
            if self.xml_content:
                xml_content = self.xml_content.strip()
                if xml_content.startswith('<?xml'):
                    xml_content = xml_content.split('?>', 1)[1].strip()

                view = self.env.ref('dynamic_reports.report_template_service_call_xml_upload')
                view.arch_db = xml_content
                view.write({'arch_db': xml_content})
            report_action = 'dynamic_reports.action_xml_upload_custom_report_format_for_all_service_call'
            target_record = record_model.search([], limit=1)

        elif model == 'account.move':
            if self.xml_content:
                xml_content = self.xml_content.strip()
                if xml_content.startswith('<?xml'):
                    xml_content = xml_content.split('?>', 1)[1].strip()

                view = self.env.ref('dynamic_reports.report_template_xml_upload_account_move_invoice')
                view.arch_db = xml_content
                view.write({'arch_db': xml_content})
            report_action = 'dynamic_reports.action_xml_upload_custom_report_format_for_all_account_move_invoice'
            target_record = record_model.search([], limit=1)

        else:
            raise UserError("No report action defined for the selected model.")

        return self.env.ref(report_action).report_action(target_record)

