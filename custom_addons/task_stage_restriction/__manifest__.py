{
    'name': 'Task Stage Restriction',
    'version': '1.0',
    'category': 'Project',
    'summary': 'Restrict employees from changing task stages',
    'depends': ['project'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}