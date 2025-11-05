{
    'name': 'Customer Location Picker',
    'version': '1.0',
    'category': 'Contacts',
    'summary': 'Add a button to auto-fill address from current GPS location',
    'description': 'This module adds a "Pick Current Location" button to customer form, which fetches current location and fills address fields automatically.',
    'depends': ['base', 'web'],
    'data': [
        'views/res_partner_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'partner_location_picker/static/src/js/location_picker.js',
            # 'partner_location_picker/static/src/xml/partner_geolocation.xml',
        ],
    },
    'installable': True,
    'application': False,
}
