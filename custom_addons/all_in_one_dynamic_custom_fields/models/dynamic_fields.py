# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: MOHAMMED DILSHAD TK (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
################################################################################
from xlrd.xlsx import ET

from odoo import api, fields, models, _


class DynamicFields(models.Model):
    """Creates dynamic fields model to create and manage new fields"""
    _name = 'dynamic.fields'
    _rec_name = 'field_description'
    _description = 'Custom Dynamic Fields'
    _inherit = 'ir.model.fields'

    @api.model
    def get_possible_field_types(self):
        """Return all available field types other than 'o2m' and
           'reference' fields."""
        field_list = sorted((key, key) for key in fields.MetaField.by_type)
        field_list.remove(('one2many', 'one2many'))
        field_list.remove(('reference', 'reference'))
        field_list.remove(('json', 'json'))
        field_list.remove(('many2one_reference', 'many2one_reference'))
        field_list.remove(('properties', 'properties'))
        field_list.remove(('properties_definition', 'properties_definition'))
        return field_list

    @api.onchange('model_id')
    def _onchange_model_id(self):
        """Pass selected model into model field to filter position fields,
            set values to form_view_ids to filter form view ids and pass
            values to tree_view_ids to filter tree view ids"""
        for rec in self:
            rec.model = rec.model_id.model
            rec.write({'form_view_ids': [(6, 0, rec.model_id.view_ids.filtered(
                lambda view: view.type == 'form' and view.mode == 'primary')
                                          .ids)]})
            rec.write({'tree_view_ids': [(6, 0, self.model_id.view_ids.filtered(
                lambda view: view.type == 'tree' and view.mode == 'primary')
                                          .ids)]})

    model = fields.Char(string='Model', help="To store selected model name")
    position_field_id = fields.Many2one(comodel_name='ir.model.fields',
                                        string='Field Name',
                                        required=True, ondelete='cascade',
                                        help="Position field for new field"
                                        , domain=lambda
            self: "[('model', '=', model)]")
    position = fields.Selection(selection=[('before', 'Before'),
                                           ('after', 'After')],

                                string='Position',
                                required=True, help="Position of new field")
    model_id = fields.Many2one(comodel_name='ir.model', string='Model',
                               required=True,
                               index=True,
                               help="The model this field belongs to")
    ref_model_id = fields.Many2one(comodel_name='ir.model', string='Relational '
                                                                   'Model',
                                   index=True, help="Relational model"
                                                    " for relational fields")
    selection_field = fields.Char(string="Selection Options",
                                  help="The model this field belongs to")
    field_type = fields.Selection(selection='get_possible_field_types',
                                  string='Field Type', required=True,
                                  help="Data type of new field")
    tree_field_ids = fields.Many2many('ir.model.fields',
                                      'tree_field_ids',
                                      compute='_compute_tree_field_ids')
    ttype = fields.Selection(string="Field Type", related='field_type',
                             help="Field type of field")
    widget_id = fields.Many2one(comodel_name='dynamic.field.widgets',
                                string='Widget', help="Widgets for field",
                                domain=lambda self: "[('data_type', '=', "
                                                    "field_type)]")
    groups = fields.Many2many('res.groups',
                              'dynamic_fields_group_rel',
                              'dynamic_field_id',
                              'dynamic_group_id',
                              help="Groups of field")
    extra_features = fields.Boolean(string="Show Extra Properties",
                                    help="Enable to add extra features")
    status = fields.Selection(selection=[('draft', 'Draft'), ('form',
                                                              'Field Created')],

                              string='Status',
                              index=True, readonly=True, tracking=True,
                              copy=False, default='draft',
                              help='State for record')
    form_view_ids = fields.Many2many(comodel_name='ir.ui.view',
                                     string="Form View IDs",
                                     help="Stores form view ids")
    tree_view_ids = fields.Many2many(comodel_name='ir.ui.view',
                                     relation="rel_tree_view",
                                     string="Tree View IDs",
                                     help="Stores tree view ids")
    form_view_id = fields.Many2one(comodel_name='ir.ui.view',
                                   string="Form View ID",
                                   required=True,
                                   help="Form view id of the model",
                                   domain=lambda self: "[('id', 'in', "
                                                       "form_view_ids)]")
    form_view_inherit_id = fields.Char(string="Form View Inherit Id",
                                       related='form_view_id.xml_id',
                                       help="Form view inherit id(adds"
                                            " by selecting form view id)")
    add_field_in_tree = fields.Boolean(string="Add Field to the Tree View",
                                       help="Enable to add field in tree view")
    tree_view_id = fields.Many2one(comodel_name='ir.ui.view',
                                   string="Tree View ID",
                                   help="Tree view id of the model",
                                   domain=lambda self: "[('id', 'in', "
                                                       "tree_view_ids)]")
    tree_view_inherit_id = fields.Char(string="External Id",
                                       related='tree_view_id.xml_id',
                                       help="Tree view inherit id(adds"
                                            " by selecting tree view id)")
    tree_field_id = fields.Many2one('ir.model.fields',
                                    string='Tree Field',
                                    help='Position for new field',
                                    domain="[('id', 'in', tree_field_ids)]")
    tree_field_position = fields.Selection(selection=[('before', 'Before'),
                                                      ('after', 'After')],

                                           string='Tree Position',
                                           help="Position of new field in "
                                                "tree view")
    is_visible_in_tree_view = fields.Boolean(string='Visible In List View',
                                             help="Enable to make the field "
                                                  "visible in selected list "
                                                  "view of the model")
    created_tree_view_id = fields.Many2one('ir.ui.view',
                                           string='Created Tree view',
                                           help='This is the currently '
                                                'created tree view')
    created_form_view_id = fields.Many2one('ir.ui.view',
                                           string='Created form view',
                                           help='Created form view id for the '
                                                'dynamic field')
    invisible_type = fields.Selection([
        ('none', 'None'),
        ('task', 'For Task'),
        ('service_call', 'For Service Call')
    ], string="Invisible", help="Choose type for invisibility condition")

    # NEW: user-entered invisible/domain expression for dynamic view injection
    invisible_domain = fields.Char(
        string="Invisible Expression",
        help=(
            "Enter the view-level invisible expression (domain) to be applied "
            "for the created field, e.g. [('complementary','=','None')]. "
            "This will be placed directly as the field's invisible attribute "
            "in the generated view. Enable Extra Features to see this field."
        )
    )

    show_invisible_type = fields.Boolean(string="Show Invisible Type", compute='_compute_show_invisible_type')

    is_instant = fields.Boolean(string="Is Instant")

    @api.depends('model_id')
    def _compute_show_invisible_type(self):
        for rec in self:
            rec.show_invisible_type = rec.model_id.model == 'project.task'

    @api.depends('tree_view_id')
    def _compute_tree_field_ids(self):
        """Compute function to find the tree view fields of selected tree view
        in field tree_view_id"""
        for rec in self:
            if rec.tree_view_id:
                field_list = []
                if rec.tree_view_id.xml_id:
                    fields = ET.fromstring(self.env.ref(
                        rec.tree_view_id.xml_id).arch).findall(".//field")
                    for field in fields:
                        field_list.append(field.get('name'))
                inherit_id = rec.tree_view_id.inherit_id if rec.tree_view_id.inherit_id else False
                while inherit_id:
                    if inherit_id.xml_id:
                        fields = ET.fromstring(self.env.ref(
                            inherit_id.xml_id).arch).findall(".//field")
                        for field in fields:
                            field_list.append(field.get('name'))
                    inherit_id = inherit_id.inherit_id if inherit_id.inherit_id else False
                self.tree_field_ids = self.env['ir.model.fields'].search(
                    [('model_id', '=', self.model_id.id),
                     ('name', 'in', field_list)])
            else:
                rec.tree_field_ids = False

    @api.onchange('add_field_in_tree')
    def _onchange_add_field_in_tree(self):
        """Function to clear values of tree_view_id and tree_field_id"""
        if not self.add_field_in_tree:
            self.tree_view_id = False
            self.tree_field_id = False


    def action_create_dynamic_field(self):
        """Function to create dynamic field to a particular model, data type, properties, etc."""
        self.write({'status': 'form'})

        IrModelFields = self.env['ir.model.fields'].sudo()
        IrUIView = self.env['ir.ui.view'].sudo()

        # Create currency_id field if type is monetary and currency_id doesn't exist
        if self.field_type == 'monetary' and not IrModelFields.search([
            ('model_id', '=', self.model_id.id),
            ('name', '=', 'currency_id')
        ]):
            IrModelFields.create({
                'name': 'x_currency_id',
                'field_description': 'Currency',
                'model_id': self.model_id.id,
                'ttype': 'many2one',
                'relation': 'res.currency',
                'is_dynamic_field': True
            })

        # Create the dynamic field itself
        IrModelFields.create({
            'name': self.name,
            'field_description': self.field_description,
            'model_id': self.model_id.id,
            'ttype': self.field_type,
            'relation': self.ref_model_id.model if self.ref_model_id else None,
            'required': self.required,
            'index': self.index,
            'store': self.store,
            'help': self.help,
            'readonly': self.readonly,
            'selection': self.selection_field,
            'copied': self.copied,
            'is_dynamic_field': True
        })

        # Build modifiers (invisible condition)
        invisible_attr = ''
        # Old behavior for project.task option
        if self.model_id.model == 'project.task':
            if self.invisible_type == 'none':
                invisible_attr = ''
            elif self.invisible_type == 'task':
                invisible_attr = ' invisible="not is_fsm"'
            elif self.invisible_type == 'service_call':
                invisible_attr = ' invisible="is_fsm"'
        # New behavior: if user entered a custom invisible_domain, use it
        if self.invisible_domain:
            # Escape double quotes to avoid breaking XML attribute quoting
            safe_domain = self.invisible_domain
            # Ensure attribute is prepended with a space if present
            invisible_attr = f' invisible="{safe_domain}"'
        # Prepare optional widget part
        widget_attr = f' widget="{self.widget_id.name}"' if self.widget_id else ''

        # Build arch_base using the dynamic field name and dynamic invisible expression
        arch_base = _(
            '<?xml version="1.0"?>'
            '<data>'
            '<field name="%(position_field)s" position="%(position)s">'
            '<field name="%(field_name)s"%(widget)s%(invisible)s/>'
            '</field>'
            '</data>'
        ) % {
                        'position_field': self.position_field_id.name,
                        'position': self.position,
                        'field_name': self.name,
                        'widget': widget_attr,
                        'invisible': invisible_attr
                    }

        inherit_form_view_name = f"{self.form_view_id.name}.inherit.dynamic.custom.{self.field_description}.field"
        inherit_id = self.env.ref(self.form_view_id.xml_id)

        # Create the inherited view (dynamically) — this is still Python; no XML files touched
        self.created_form_view_id = IrUIView.create({
            'name': inherit_form_view_name,
            'type': 'form',
            'model': self.model_id.model,
            'mode': 'extension',
            'inherit_id': inherit_id.id,
            'arch_base': arch_base,
            'active': True,
        })

        # Add field to tree view
        self.action_create_to_tree_view()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_create_to_tree_view(self):
        """Function to add field to tree view"""
        if self.add_field_in_tree:
            optional = "show" if self.is_visible_in_tree_view else "hide"
            tree_view_arch_base = (_(f'''
                                    <data>
                                    <xpath expr="//field[@name='{self.tree_field_id.name}']" position="{self.tree_field_position}">
                                    <field name="{self.name}" optional="{optional}"/>
                            </xpath>
                            </data>'''))
            inherit_tree_view_name = str(
                self.tree_view_id.name) + ".inherit.dynamic.custom" + \
                                     str(self.field_description) + ".field"
            self.created_tree_view_id = self.env['ir.ui.view'].sudo().create({
                'name': inherit_tree_view_name,
                'type': 'tree',
                'model': self.model_id.model,
                'mode': 'extension',
                'inherit_id': self.tree_view_id.id,
                'arch_base': tree_view_arch_base,
                'active': True})
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

    def unlink(self):
        """Super unlink function that also deletes the field from ir.model.fields"""
        # Deactivate the created views
        if self.form_view_id:
            self.created_form_view_id.active = False
        if self.tree_view_id:
            self.created_tree_view_id.active = False

        # Check the field type and delete from ir.model.fields only if it's not Many2many
        field = self.env['ir.model.fields'].sudo().search([
            ('name', '=', self.name),
            ('model_id', '=', self.model_id.id),
            ('is_dynamic_field', '=', True)
        ])

        # Only delete the field if its type is not Many2many
        if field and field.ttype != 'many2many':
            field.unlink()

        # Continue with normal deletion of this record
        res = super(DynamicFields, self).unlink()
        return res
