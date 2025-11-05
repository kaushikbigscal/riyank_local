# -*- coding: utf-8 -*-
{
    'name': "extended_warranty_product",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': [
        'product',
        'sale',
        'account',
        'stock',          # for stock.picking inheritance
        'industry_fsm',   # for customer.product.mapping inheritance
    ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/extended_warranty_product.xml',
        'data/cron_extended_warranty_status.xml',
        'views/views.xml',
        'views/templates.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}

