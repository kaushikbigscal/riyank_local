{
    'name': 'Advanced Attendance Control',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Control multiple check-ins/outs for employees',
    'description': """
        This module adds a global setting to allow or disallow multiple check-ins/outs for employees.
    """,
    'depends': ['hr_attendance'],
    'data': [
        'views/res_config_settings_views.xml'
    ],
    'installable': True,
    'auto_install': False,
}