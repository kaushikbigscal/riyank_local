{
    'name': 'Project Portal WebPush Notify',
    'version': '1.0',
    'category': 'Project',
    'summary': 'Send WebPush Notifications to Portal Users on Task Creation',
    'depends': ['portal'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_frontend': [
            'notification/static/src/js/webpush_portal.js',
        ],
    },
    'installable': True,
    'application': False,
}
