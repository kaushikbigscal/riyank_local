{
    'name': 'Restrict Debug Mode',
    'version': '17.0',
    'sequence': 1,
    'category': 'Services/Tools',
    'summary': """Restrict Debug Mode.""",
    'description': """Restrict Debug Mode.""",
    'author': 'Odox SoftHub',
    'price': 0,
    'currency': 'USD',
    'website': 'https://www.odoxsofthub.com',
    'support': 'support@odoxsofthub.com',
    'license': 'LGPL-3',
    'depends': ['web'],
    'data': [
        'security/res_users.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odx_restrict_debug/static/src/js/debug.js',
        ],
    },
    'installable': True,
    'application': True,
    'images': ['static/description/thumbnail.gif'],
}
