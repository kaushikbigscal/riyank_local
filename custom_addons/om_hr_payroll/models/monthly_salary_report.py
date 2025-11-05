from lxml import etree
from odoo import models, fields, api, tools
import logging

_logger = logging.getLogger(__name__)


class MonthlySalaryReport(models.Model):
    _name = 'monthly.salary.report'
    _description = 'Monthly Salary Report'
    _auto = False
    _rec_name = 'employee_id'

    # Static fields
    employee_id = fields.Many2one('hr.employee', string='Employee')
    employee_code = fields.Char(string='Employee Code')
    employee_name = fields.Char(string='Employee Name')
    month = fields.Char(string='Month')
    company_id = fields.Many2one('res.company', string='Company Name')
    department_id = fields.Many2one('hr.department', string='Department Name')
    date_from = fields.Date(string='Start Date')

    # -------------------------------------------------------------------------
    # GET USED SALARY RULES
    # -------------------------------------------------------------------------
    def _get_used_salary_rules(self):
        """Fetch salary rules from structures and sort by sequence"""
        try:
            structures = self.env['hr.payroll.structure'].search([])
            if not structures:
                return self.env['hr.salary.rule'].browse([])

            rule_ids = []
            for structure in structures:
                possible_fields = ['rule_ids', 'salary_rule_ids', 'hr_salary_rule_ids', 'payslip_rule_ids']
                for field_name in possible_fields:
                    if hasattr(structure, field_name):
                        field_value = getattr(structure, field_name)
                        if field_value:
                            rule_ids.extend(field_value.ids)
                            break

            rule_ids = list(set(rule_ids))
            if not rule_ids:
                return self.env['hr.salary.rule'].search([]).sorted(lambda r: (r.sequence, r.name))

            used_rules = self.env['hr.salary.rule'].browse(rule_ids)
            return used_rules.sorted(lambda r: (r.sequence, r.name))

        except Exception as e:
            _logger.error(f"Error getting salary rules: {str(e)}")
            return self.env['hr.salary.rule'].search([]).sorted(lambda r: (r.sequence, r.name))

    # -------------------------------------------------------------------------
    # DYNAMIC FIELD REGISTRATION
    # -------------------------------------------------------------------------
    def _register_dynamic_fields(self):
        """Register dynamic fields based on salary rules"""
        used_rules = self._get_used_salary_rules()
        for rule in used_rules:
            field_name = f"x_{''.join(c if c.isalnum() else '_' for c in rule.code.lower())}"
            if field_name not in self._fields:
                field = fields.Float(
                    string=rule.code,
                    readonly=True,
                    default=0.0,
                    digits=(16, 2)
                )
                self._add_field(field_name, field)
        return True

    # -------------------------------------------------------------------------
    # AUTO REGISTER HOOK
    # -------------------------------------------------------------------------
    def _register_hook(self):
        super()._register_hook()
        self._register_dynamic_fields()
        self._create_dynamic_view()
        self.clear_caches()

    # -------------------------------------------------------------------------
    # CREATE SQL VIEW
    # -------------------------------------------------------------------------
    def _create_dynamic_view(self):
        """Create SQL view with dynamic salary rule columns"""
        try:
            tools.drop_view_if_exists(self.env.cr, self._table)
            used_rules = self._get_used_salary_rules()

            # Base fixed columns
            fixed_columns = [
                "row_number() OVER () AS id",
                "e.id AS employee_id",
                'e."x_empCode" AS employee_code',
                "e.name AS employee_name",
                "TO_CHAR(p.date_from, 'Mon-YY') AS month",
                "p.date_from AS date_from",
                "e.company_id AS company_id",
                "e.department_id AS department_id",
            ]

            # Dynamic salary rule columns
            rule_selects = []
            for rule in used_rules:
                field_name = f"x_{''.join(c if c.isalnum() else '_' for c in rule.code.lower())}"
                rule_selects.append(f"""
                    COALESCE((
                        SELECT SUM(pl.amount)
                        FROM hr_payslip_line pl
                        JOIN hr_payslip p2 ON pl.slip_id = p2.id
                        WHERE p2.employee_id = e.id
                        AND pl.salary_rule_id = {rule.id}
                        AND p2.state = 'done'
                        AND p2.date_from = p.date_from
                        GROUP BY p2.employee_id, p2.date_from
                    ), 0) AS {field_name}""")

            all_columns = fixed_columns + rule_selects

            select_query = f"""
                CREATE OR REPLACE VIEW {self._table} AS (
                    SELECT
                        {", ".join(all_columns)}
                    FROM hr_employee e
                    JOIN hr_payslip p ON p.employee_id = e.id
                    WHERE e.active = true
                    AND p.state = 'done'
                    GROUP BY e.id, e."x_empCode", e.name, p.date_from, e.company_id, e.department_id
                )
            """

            self.env.cr.execute(select_query)
            _logger.info(f"SQL View {self._table} successfully recreated")
        except Exception as e:
            _logger.error(f"Failed to create view: {str(e)}")
            raise


    # -------------------------------------------------------------------------
    # ORDER DYNAMIC FIELDS BY SEQUENCE
    # -------------------------------------------------------------------------
    def _get_ordered_dynamic_fields(self):
        """Return dynamic fields in exact salary structure sequence"""
        used_rules = self._get_used_salary_rules()
        ordered_fields = []
        for rule in used_rules:
            field_name = f"x_{''.join(c if c.isalnum() else '_' for c in rule.code.lower())}"
            if field_name in self._fields:
                ordered_fields.append((field_name, self._fields[field_name]))
        return ordered_fields

    # -------------------------------------------------------------------------
    # GENERATE DYNAMIC VIEW ARCH
    # -------------------------------------------------------------------------
    def get_dynamic_view_arch(self):
        """Generate tree view XML dynamically with fields ordered by sequence"""
        arch = """
        <tree string="Monthly Salary Report" create="false" edit="false">
            <field name="employee_code"/>
            <field name="employee_name"/>
            <field name="month"/>
            <field name="department_id"/>
            <field name="company_id"/>
        """
        for field_name, field in self._get_ordered_dynamic_fields():
            arch += f'\n<field name="{field_name}" string="{field.string}"/>'
        arch += "\n</tree>"
        return arch

    @api.model
    def get_view(self, view_id=None, view_type='tree', **options):
        res = super().get_view(view_id, view_type, **options)
        if view_type == 'tree':
            try:
                # Always regenerate arch dynamically
                arch = self.get_dynamic_view_arch()
                doc = etree.fromstring(arch)
                res['arch'] = etree.tostring(doc, encoding='unicode')
            except Exception as e:
                _logger.error(f"Failed to generate dynamic view: {str(e)}")
                raise
        return res

    @api.model
    def refresh_view(self):
        # First re-register all dynamic fields BEFORE forcing view reload
        self._register_dynamic_fields()
        self._create_dynamic_view()
        self.clear_caches()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


# -------------------------------------------------------------------------
# OVERRIDE SALARY RULE WRITE TO REFRESH VIEW
# -------------------------------------------------------------------------
class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    def write(self, vals):
        res = super().write(vals)
        if {'code', 'name', 'sequence'} & set(vals):
            self.env['monthly.salary.report'].refresh_view()
        return res


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    def write(self, vals):
        res = super().write(vals)
        if 'rule_ids' in vals:
            self.env['monthly.salary.report'].refresh_view()
        return res


