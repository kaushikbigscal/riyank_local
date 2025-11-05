from odoo import models, fields, api,_
import logging

_logger = logging.getLogger(__name__)

class WhatsAppTemplate(models.Model):
    _name = 'whatsapp.template'
    _description = 'WhatsApp Template'
    _rec_name = 'model_id'

    def _default_model(self):
        """Fetches the 'project.project' model as the default selection."""
        return self.env['ir.model'].search([('model', '=', 'project.project')], limit=1).id

    model_id = fields.Many2one(
        'ir.model',
        string="Model",
        ondelete='cascade',
        default=_default_model,
        required=True
    )

    def _default_project(self):
        return self.env['project.project'].search([('is_fsm', '=', True)], limit=1)

    project_id = fields.Many2one(
        'project.project',
        string="Project",
        default=_default_project,
        domain="[('is_fsm', '=', True)]"
    )

    message = fields.Char(string="Message", help="Set dynamic message using {{task_name}} and {{stage_name}}.")
    attachment_ids = fields.Many2many('ir.attachment')

    stage_id = fields.Many2one(
        'project.task.type',
        string="Stage",
        domain="[('id', 'in', stages_available)]"
    )

    stages_available = fields.Many2many(
        'project.task.type',
        compute="_compute_stages_available",
        string="Available Stages"
    )

    @api.depends('project_id')
    def _compute_stages_available(self):
        """List only stages that belong to the selected project."""
        for record in self:
            if record.project_id:
                record.stages_available = self.env['project.task.type'].search(
                    [('project_ids', 'in', [record.project_id.id])]
                )
            else:
                record.stages_available = False

    show_project = fields.Boolean(
        compute='_compute_show_project',
        store=True
    )

    @api.depends('model_id')
    def _compute_show_project(self):
        """Show project field only when 'Project' model is selected."""
        for record in self:
            record.show_project = record.model_id.model == 'project.project'

    show_stage = fields.Boolean(
        compute='_compute_show_stage',
        store=True
    )

    @api.depends('project_id')
    def _compute_show_stage(self):
        """Show 'Stage' only if a project is selected."""
        for record in self:
            record.show_stage = bool(record.project_id)

    def action_save_template(self):
        """Save template and close form"""
        self.ensure_one()
        self.write({'message': self.message})
        return {'type': 'ir.actions.act_window_close'}


    legend_info = fields.Html(
        string="Template Variables Legend",
        readonly=True,
        sanitize=False,
        default=lambda self: _(
            """
            <div style="width: 326px; height: 58px; max-width: 500px; box-sizing: border-box;">
                <ul style="list-style-type: disc; margin: 0; padding-left: 20px;">
                    <li><span style="font-weight: bold;">{{task_name}}</span>: Name of the service call.</li>
                    <li><span style="font-weight: bold;">{{stage_name}}</span>: Current stage of the service call.</li>
                </ul>
            </div>
            """
        )
    )


class ConfigurationManager(models.Model):
    _inherit = 'configuration.manager'

    @api.model_create_multi
    def create(self, vals_list):
        records = super(ConfigurationManager, self).create(vals_list)
        self._update_template_access()
        return records

    def write(self, vals):
        result = super(ConfigurationManager, self).write(vals)
        self._update_template_access()
        return result

    def unlink(self):
        result = super(ConfigurationManager, self).unlink()
        self._update_template_access()
        return result

    def _update_template_access(self):
        """Update template access based on ConfigurationManager records"""
        try:
            group = self.env.ref('call_stage_changes_send_whatsapp.group_template_access')
            admin_group = self.env.ref('base.group_system')
            admin_users = admin_group.users  # Get admin users

            self.env.cr.execute("SELECT COUNT(*) FROM configuration_manager")
            count = self.env.cr.fetchone()[0]

            print(f"🔍 ConfigurationManager Count: {count}")

            if count > 0:
                group.write({'users': [(6, 0, admin_users.ids)]})  # Assign admin access
                print(f"✅ Assigned {len(admin_users)} Admins to Group")
            else:
                group.write({'users': [(5, 0, 0)]})  # Remove access
                print("❌ Removed all users from group")

            # **Refresh access rights and menus**
            self.env['ir.rule'].clear_caches()
            self.env['ir.ui.menu'].clear_caches()
            self.env['res.groups'].clear_caches()
            self.env['ir.model.access'].call_cache_clearing_methods()

            self.env.cr.commit()

            # **🔹 Store a config parameter**
            self.env['ir.config_parameter'].sudo().set_param('refresh_template_menu', 'True')
            print("🔄 Set ir.config_parameter: refresh_template_menu = True")

            # **🔹 Notify frontend via bus**
            self.env['bus.bus']._sendone('call_stage_changes_send_whatsapp', 'refresh_template_menu', {})
            print("📡 Sent event: refresh_template_menu via bus.bus")

        except Exception as e:
            _logger.error(f"⚠️ Error updating template access: {e}")
    #
    # @api.model
    # def _init_template_menu_visibility(self):
    #     self._update_template_access()

