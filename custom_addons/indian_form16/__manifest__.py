{
    'name': 'Indian Form 16 Generator',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Generate Form 16 for Indian employees',
    'description': """
        This module allows you to generate Form 16 for Indian employees.
        Select an employee and assessment year to generate the form.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['hr', 'om_hr_payroll','base','mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/form16_views.xml',
        'report/form16_report.xml'
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}