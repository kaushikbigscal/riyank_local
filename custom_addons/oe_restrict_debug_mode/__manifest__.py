{
    'name': 'Restrict Debug Mode Access',
    'version': '17.0.1.0.0',
    'category': 'Security',
    'summary': 'Restrict Debug Mode access for unauthorized users in Odoo backend',
    'description': """
        Restrict Debug Mode Access for Odoo 17
        =====================================
        
        This module provides a security enhancement to control access to Odoo's
        Developer Mode (Debug Mode) in the backend interface.
        
        Key Features:
        - Allows only users belonging to a specific security group to use Debug Mode.
        - Show visual overlay and "Access Denied" message.
        
        This helps in maintaining data integrity and preventing unintended
        modifications by non-technical users.
    """,
    'author': 'Sheikh Muhammad Saad, OdooElevate',
    'website': 'https://odooelevate.odoo.com/',
    'depends': ['base', 'web'],
    'data': [
        'security/restrict_debug_security.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'oe_restrict_debug_mode/static/src/core/debug/restrict_debug.js',
            'oe_restrict_debug_mode/static/src/core/debug/restrict_debug_view.xml',
            'oe_restrict_debug_mode/static/src/core/debug/restrict_debug.scss',
        ],
    },
    'license': 'AGPL-3',
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
