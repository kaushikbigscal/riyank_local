from odoo import models, fields ,api, _
from random import randint
from odoo.exceptions import ValidationError, AccessError, UserError

class ServiceType(models.Model):
    _name = 'service.type'
    _description = 'Service Type'

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string='Service Type', required=True)
    color = fields.Integer(string='Color', default=_get_default_color)
    bypass_geofencing_for_service_call = fields.Boolean(string="Bypass Geofencing For Service Call")
    
    default_in_call = fields.Boolean(string="Is Default")

    @api.constrains('default_in_call')
    def _check_only_one_default(self):
        if self.env.context.get("install_mode"):  # bypass check during XML load
            return
        for rec in self:
            if rec.default_in_call:
                existing_default = self.search([
                    ('default_in_call', '=', True),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing_default:
                    raise ValidationError(
                        f"Only one Service Type can be set as default.\n"
                        f"'{existing_default.name}' is already set as default."
                    )
    @api.model
    def _get_protected_type_ids(self):
        xml_ids = [
            'industry_fsm.service_type_onsite',
            'industry_fsm.service_type_online',
            'industry_fsm.service_type_inhouse',
            'industry_fsm.service_type_carryon',
        ]
        return [self.env.ref(x).id for x in xml_ids if self.env.ref(x, raise_if_not_found=False)]

    # ---------------------------------
    # Prevent deletion of protected or used types
    # ---------------------------------

    def unlink(self):
        protected_ids = self._get_protected_type_ids()
        for rec in self:
            if rec.id in protected_ids:
                raise UserError(_("Default Service Type '%s' cannot be deleted.") % rec.name)

            # Only check usage in tasks if the field exists
            Task = self.env['project.task']
            if 'service_type_id' in Task._fields:
                used_in_tasks = Task.search_count([('service_type_id', '=', rec.id)])
                if used_in_tasks:
                    raise UserError(
                        _("Service Type '%s' is being used in tasks and cannot be deleted.") % rec.name
                    )

        return super().unlink()

    # ---------------------------------
    # Prevent modifications of protected records
    # ---------------------------------
    def write(self, vals):
        # Allow updates during module install/update
        if self.env.context.get('install_mode'):
            return super(ServiceType, self).write(vals)

        protected_ids = self._get_protected_type_ids()
        protected_fields = ['name']  # Lock name; extend if needed

        for rec in self:
            if rec.id in protected_ids:
                # Prevent renaming protected records
                if any(field in vals for field in protected_fields):
                    raise UserError(_("You cannot modify the default Service Type '%s'.") % rec.name)

                # Ensure On-Site always stays default
                onsite_id = self.env.ref('industry_fsm.service_type_onsite').id
                if rec.id == onsite_id and 'default_in_call' in vals and not vals['default_in_call']:
                    raise UserError(_("On-Site must always remain the default Service Type."))

        return super(ServiceType, self).write(vals)


class ServiceChargeCategory(models.Model):
    _name = 'service.charge.type'
    _description = 'Service Charge Type'
    _rec_name = 'service_charge_type'

    service_charge_type = fields.Char(string='Service Charge Type', required=True)

class CallType(models.Model):
    _name = 'call.type'
    _description = 'Call Type'
    _order = 'name'

    name = fields.Char(string="Call Type", required=True)
    is_system_defined = fields.Boolean(string="System Defined", default=False)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Call Type name must be unique.'),
    ]

    def write(self, vals):
        for record in self:
            if record.is_system_defined:
                raise UserError(_("System-defined call types cannot be editable."))
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.is_system_defined:
                raise UserError(_("System-defined call types cannot be deleted."))
            task_count = self.env['project.task'].search_count(
                [('is_fsm', '=', True), ('call_type', '=', record.id)])
            if task_count > 0:
                raise UserError(_("This call type is used and cannot be deleted."))
        return super().unlink()