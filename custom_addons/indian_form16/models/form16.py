from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)


class Form16(models.Model):
    _name = 'indian.form16'
    _description = 'Form 16'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    assessment_year = fields.Many2one('financial.year', string='Financial Year', required=True)
    # employee_wage = fields.Monetary(string='Employee Wage', compute='_compute_employee_wage', store=True)
    generated_form = fields.Html(string='Generated Form')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    form_pdf = fields.Binary(string='Form 16 PDF', attachment=True)
    form_pdf_filename = fields.Char(string='PDF Filename')
    currency_id = fields.Many2one('res.currency', string='Currency', related='company_id.currency_id', readonly=True)

    def action_generate_form(self):
        self.ensure_one()
        try:
            pdf_content, filename = self.generate_form16_pdf()
            self.write({
                'form_pdf': base64.b64encode(pdf_content),
                'form_pdf_filename': filename
            })
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/?model=indian.form16&id={}&field=form_pdf&filename_field=form_pdf_filename&download=true'.format(
                    self.id),
                'target': 'self',
            }
        except Exception as e:
            _logger.error(f"Error generating Form 16 PDF: {str(e)}")
            raise UserError(f"An error occurred while generating the Form 16 PDF: {str(e)}")

    def get_current_date(self):
        return fields.Date.context_today(self)

    def _get_financial_year_start(self):
        current_date = datetime.now()
        if current_date.month >= 4:
            year = current_date.year
        else:
            year = current_date.year - 1
        return datetime(year, 4, 1).date()
        # return datetime(2025, 4, 1).date()

    def _get_financial_year_end(self):
        current_date = datetime.now()
        if current_date.month >= 4:
            year = current_date.year + 1
        else:
            year = current_date.year
        return datetime(year, 3, 31).date()
       # return datetime(2026, 3, 31).date()

    def generate_form16_pdf(self):
        self.ensure_one()
        employee = self.employee_id
        company = self.company_id or self.env.company

        start_date = self._get_financial_year_start()
        end_date = self._get_financial_year_end()

        payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '>=', start_date),
            ('date_to', '<=', end_date)
        ])

        total_earnings = 0
        section10 = 0
        standard_ded = 0
        applicable_80ccd2 = 0
        tds_deducated= 0
        for payslip in payslips:
            for line in payslip.line_ids:
                if line.category_id.code == "GROSS":
                    total_earnings += int(line.total)
                if line.category_id.code == "PF_EMP":
                    applicable_80ccd2 += int(line.total)
                if line.category_id.code == "TDS":
                    tds_deducated += int(line.total)

        if total_earnings < 144000:
            professional_tax = 0
        else:
            professional_tax = 0

        #DEDECTION PART
        declaration = self.env['it.declaration.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('status', '>=', 'locked'),
        ])

        tax_regime = declaration.tax_regime
        total_other_ded_vi_a = (declaration.permanent_physical_disability_40_80 +
                                declaration.medical_insurance_specified_disease_only_senior_citizen +
                                declaration.medical_insurance_for_handicapped_severe +
                                declaration.superannuation_exemption +
                                declaration.rajiv_gandhi_equity_scheme +
                                declaration.permanent_physical_disability_above_80 +
                                declaration.interest_on_electric_vehicle)

        applicable_other_ded_vi_a = (min(75000, declaration.permanent_physical_disability_40_80) +
                                     min(100000, declaration.medical_insurance_specified_disease_only_senior_citizen) +
                                     min(125000, declaration.medical_insurance_for_handicapped_severe) +
                                     min(25000, declaration.rajiv_gandhi_equity_scheme) +
                                     min(125000, declaration.permanent_physical_disability_above_80) +
                                     min(150000, declaration.interest_on_electric_vehicle))
        if declaration:
            if tax_regime == "old_regime":
                regime_type = "No"
                standard_ded = 50000
                previous_emp_income = declaration.income_after_exemptions
                other_income = declaration.total_declared_other
                let_out_income_loss = declaration.total_exemption
                vi_a_deductions = declaration.applicable_declared_vi_a_deductions
                sec_80c_total = declaration.total_declared_80c
                sec_80c_applicable = declaration.applicable_declared_80c
                ccc80_total = declaration.contribution_to_pension_fund
                ccc80_applicable = min(150000, declaration.contribution_to_pension_fund)
                ccd80_1_total = 0
                ccc80_1_applicable = 0
                total_80ccd1b = declaration.contribution_to_nps
                applicable_80ccd1b = min(50000, declaration.contribution_to_nps)
                applicable_80ccd2 = applicable_80ccd2
                total_80d = declaration.total_declared_medical
                applicable_80d = declaration.applicable_declared_medical
                total_80e = declaration.interests_on_loan_self_higher
                total_80cch = 0
                total_80cch_2 = 0
                total_80g = declaration.donation_50_exemption + declaration.donation_political_parties + declaration.donation_100_exemption + declaration.donation_children_education
                total_80tta = declaration.interests_on_deposites
                applicable_80tta = min(10000, declaration.interests_on_deposites)
                total_other_ded_vi_a = total_other_ded_vi_a
                applicable_other_ded_vi_a = applicable_other_ded_vi_a
                tds_deducated = tds_deducated

            elif tax_regime == "new_regime":
                print("Inside in Tax NEw Regime")
                regime_type = "Yes"
                standard_ded = 75000
                previous_emp_income = declaration.income_after_exemptions
                other_income = declaration.total_declared_other
                let_out_income_loss = max(0, declaration.total_income_loss)
                vi_a_deductions = 0
                sec_80c_total = 0
                sec_80c_applicable = 0
                ccc80_total = 0
                ccc80_applicable = 0
                ccd80_1_total = 0
                ccc80_1_applicable = 0
                total_80ccd1b = 0
                applicable_80ccd1b = 0
                applicable_80ccd2 = applicable_80ccd2
                total_80d = 0
                applicable_80d = 0
                total_80e = 0
                total_80cch = 0
                total_80cch_2 = 0
                total_80g = 0
                total_80tta = 0
                applicable_80tta = 0
                total_other_ded_vi_a = 0
                applicable_other_ded_vi_a = 0
                taxable_amount = (total_earnings + other_income + let_out_income_loss + previous_emp_income) - applicable_80ccd2 - standard_ded
                tds_deducated = tds_deducated
                #tax_on_income, rebate, total_surchargen, total_cessn = self.calculate_new_regime_tax(taxable_amount)

        else:
            raise ValueError("Please Declare the IT Declaration and It should be Locked")


        # if declaration.tax_regime == "new_regime":
        #     taxable_amount = (total_earnings + other_income + let_out_income_loss + previous_emp_income) - applicable_80ccd2 - standard_ded

        tax_on_income, rebate, total_surchargen, total_cessn= self.calculate_tax(taxable_amount, tax_regime)
        print(f"tax",tax_on_income)
        print(f"Rebate",rebate)
        print(total_cessn)

        # Prepare data for the template
        data = {
            'employee': employee,
            'company': company,
            'assessment_year': self.assessment_year,
            'regime_type': regime_type,
            'total_earnings': total_earnings,
            'professional_tax': professional_tax,
            'previous_emp_income': previous_emp_income,
            'standard_ded': standard_ded,
            'section10': section10,
            'other_income': other_income,
            'let_out_income_loss': let_out_income_loss,
            'sec_80c_total': sec_80c_total,
            'sec_80c_applicable': sec_80c_applicable,
            'ccc80_total': ccc80_total,
            'ccc80_applicable': ccc80_applicable,
            'ccd80_1_total': ccd80_1_total,
            'ccc80_1_applicable': ccc80_1_applicable,
            'total_80ccd1b': total_80ccd1b,
            'applicable_80ccd1b': applicable_80ccd1b,
            'applicable_80ccd2': applicable_80ccd2,
            'vi_a_deductions': vi_a_deductions,
            'total_80d': total_80d,
            'applicable_80d': applicable_80d,
            'total_80g': total_80g,
            'total_80e': total_80e,
            'total_80cch': total_80cch,
            'total_80cch_2': total_80cch_2,
            'total_80tta': total_80tta,
            'total_other_ded_vi_a': total_other_ded_vi_a,
            'applicable_other_ded_vi_a': applicable_other_ded_vi_a,
            'applicable_80tta': applicable_80tta,
            'tax_on_income': tax_on_income,
            'total_cessn': total_cessn,
            'current_date': self.get_current_date(),
            'rebate': rebate,
            'total_surchargen': total_surchargen,
            'tds_deducated': tds_deducated


        }

        # Generate PDF
        report_name = 'indian_form16.form16_report_template'
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(report_name, [self.id], data=data)

        filename = f"Form16_{employee.name}_{self.assessment_year.name}.pdf"
        return pdf_content, filename

    def calculate_tax(self, taxable_salary, tax_regime):
        if tax_regime == "old_regime":

            return self.calculate_old_regime_tax(taxable_salary)
        elif tax_regime == "new_regime":
            return self.calculate_new_regime_tax(taxable_salary)
        else:
            raise ValueError("Invalid tax regime")

    def calculate_old_regime_tax(self, taxable_amount):
        # Ensure taxable_amount is a float
        taxable_amount = float(taxable_amount)

        # Old regime tax slabs
        if taxable_amount > 0 and taxable_amount <= 250000:
            taxo = 0.0
        elif taxable_amount > 250000 and taxable_amount <= 500000:
            taxo = ((taxable_amount - 250000) * 0.05)
        elif taxable_amount > 500000 and taxable_amount <= 1000000:
            taxo = ((taxable_amount - 500000) * 0.20) + 12500
        elif taxable_amount > 1000000:
            taxo = ((taxable_amount - 1000000) * 0.30) + 112500
        else:
            taxo = 0.0

        if taxable_amount <= 500000:
            taxo = 0.0

        surchargeo = 0.0
        if taxable_amount > 5000000 and taxable_amount <= 10000000:
            surchargeo = taxo * 0.10
            # /* check Marginal Relif*/
            if taxable_amount > 5000000 and taxable_amount <= 5195896:
                surchargeo = (taxable_amount - 5000000) * 0.70
                surchargeo = surchargeo + 0.0

        elif taxable_amount > 10000000 and taxable_amount <= 20000000:
            surchargeo = taxo * 0.15
            # /* check Marginal Relif*/
            if taxable_amount > 10000000 and taxable_amount <= 10214695:
                surchargeo = (taxable_amount - 10000000) * 0.70
                surchargeo = surchargeo + 281250.0

        elif taxable_amount > 20000000 and taxable_amount <= 50000000:
            surchargeo = taxo * 0.25
            # /* check Marginal Relif*/
            if taxable_amount > 20000000 and taxable_amount <= 20930000:
                surchargeo = (taxable_amount - 20000000) * 0.70
                surchargeo = surchargeo + 871875.0

        elif taxable_amount > 50000000:
            surchargeo = taxo * 0.37
            # /* check Marginal Relif*/
            if taxable_amount > 50000000 and taxable_amount <= 53017827:
                surchargeo = (taxable_amount - 50000000) * 0.70
                surchargeo = surchargeo + 3703125.0

        cesso = 0.0
        if taxo > 0:
            cesso = (taxo + surchargeo) * ((self.company_id.cess) / 100)

        tottaxo = taxo + surchargeo

        return float(tottaxo)

    def calculate_new_regime_tax(self, taxable_amount):
        taxable_amount = float(taxable_amount)
        rebate = 0.0
        if 0 < taxable_amount <= 400000:
            taxo = 0.0
        elif 400000 < taxable_amount <= 800000:
            taxo = ((taxable_amount - 400000) * .05)
        elif 800000 < taxable_amount <= 1200000:
            taxo = ((taxable_amount - 800000) * .10) + 20000
        elif 1200000 < taxable_amount <= 1600000:
            taxo = ((taxable_amount - 1200000) * .15) + 60000
        elif 1600000 < taxable_amount <= 2000000:
            taxo = ((taxable_amount - 1600000) * .20) + 120000
        elif 2000000 < taxable_amount <= 2400000:
            taxo = ((taxable_amount - 2000000) * .25) + 200000
        elif taxable_amount > 2400000:
            taxo = ((taxable_amount - 2400000) * .30) + 300000
        else:
            taxo = 0.0

        if taxo <= 60000:  # Rebate amount if more than 60,000
            rebate = taxo
            taxo = 0.0


            # Apply Marginal Relief for FY 2025-26 (Threshold ₹12,00,000)
        threshold = 1200000
        if taxable_amount > threshold:
            excess_income = taxable_amount - threshold
            if taxo > excess_income:
                taxo = excess_income  # Reduce tax if it exceeds excess income

        surchargen = 0.0
        marginal_relief = "No"

        if 5000000 < taxable_amount <= 10000000:
            surchargen = taxo * 0.10  # Normal surcharge at 10%
            excess_income = taxable_amount - 5000000
            excess_tax = (taxo + surchargen) - 1080000  # Base tax at ₹50L is ₹10,80,000

            # Apply Marginal Relief if excess tax is more than excess income
            if excess_tax > excess_income:
                surchargen -= (excess_tax - excess_income)
                marginal_relief = "Yes"

        elif 10000000 < taxable_amount <= 20000000:
            surchargen = taxo * .15
            # /* check Marginal Relief*/
            excess_income = taxable_amount - 10000000
            excess_tax = (taxo + surchargen) - 2838000

            if excess_tax > excess_income:
                surchargen -= (excess_tax - excess_income)
                marginal_relief = "Yes"

        elif 20000000 < taxable_amount <= 50000000:
            surchargen = taxo * .25
            # /* check Marginal Relief*/
            excess_income = taxable_amount - 20000000
            excess_tax = (taxo + surchargen) - 6417000

            if excess_tax > excess_income:
                surchargen -= (excess_tax - excess_income)
                marginal_relief = "Yes"

        elif taxable_amount > 50000000:
            surchargen = taxo * .25
            # /* check Marginal Relief*/
            excess_income = taxable_amount - 20000000
            excess_tax = (taxo + surchargen) - 18225000

            if excess_tax > excess_income:
                surchargen -= (excess_tax - excess_income)
                marginal_relief = "Yes"

        cessn = 0.0
        tottaxo = 0.0
        total_taxo = 0.0
        total_cessn = 0.0
        total_surchargen = 0.0
        gratuity_from_previous_system = 0.0
        if taxo > 0:
            cessn = (taxo + surchargen) * .04
            total_cessn = cessn
            total_surchargen = surchargen
            total_taxo = taxo
            tottaxo = total_taxo + total_cessn + total_surchargen + gratuity_from_previous_system

        return int(total_taxo), int(rebate), int(total_surchargen), int(total_cessn)

