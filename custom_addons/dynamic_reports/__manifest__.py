# -*- coding: utf-8 -*-
{
    'name': "dynamic_reports",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/security_templates.xml',

        'views/views.xml',
        #'views/templates.xml',
    ],
    # 'post_init_hook': 'auto_generate_report_templates',

    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

