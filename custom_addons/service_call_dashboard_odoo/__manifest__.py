{
    'name': 'Service Call Dashboard',
    'version': '17.0.1.0.0',
    'category': 'Services/Project',
    'sequece': 1,
    'summary': """Service Call Dashboard.""",
    'description': """In this dashboard user can get the Detailed Information 
     about Calls, Customers, Employee, Hours recorded, Total Margin and Total 
     Sale Orders.""",
    # 'depends': ['sale_management', 'project', 'sale_timesheet'],
    'depends': [
        'industry_fsm',
        'calendar',
    ],
    'data': ['views/service_dashboard_views.xml'],
    'assets': {
        'web.assets_backend': [
            'web/static/src/views/form/**/*',
            ('include', 'web._assets_helpers'),
            # 'web/static/src/libs/fontawesome/css/font-awesome.css',
            # 'web/static/lib/bootstrap/scss/_variables.scss',
            ('include', 'web._assets_bootstrap'),
            'service_call_dashboard_odoo/static/src/css/service_dashboard.css',
            'service_call_dashboard_odoo/static/src/xml/service_call_dashboard_templates.xml',
            'service_call_dashboard_odoo/static/src/js/service_call_dashboard.js',
            'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.9.4/Chart.js',
        ]},
    # 'images': ['static/description/banner.png'],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
