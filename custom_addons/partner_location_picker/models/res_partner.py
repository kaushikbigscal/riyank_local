from odoo import api, fields, models, _
import requests
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    def action_get_browser_location(self):
        """
        Return client action to trigger browser geolocation
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'get_browser_location',

        }

    def set_browser_location(self, browser_lat, browser_lng):
        """
        Set partner location from browser geolocation
        """
        try:
            lat = float(browser_lat)
            lng = float(browser_lng)

            self.write({
                'partner_latitude': lat,
                'partner_longitude': lng,
                'date_localization': fields.Date.context_today(self)
            })
            self.compute_address_from_coords()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Browser location saved successfully!'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except (ValueError, TypeError):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Failed to save browser location'),
                    'type': 'danger',
                    'sticky': False,
                }
            }

    def compute_address_from_coords(self):
        """Compute readable address from partner_latitude and partner_longitude and set partner fields"""

        provider_id = self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.geo_provider')
        provider_tech_name = None

        if provider_id:
            provider = self.env['base.geo_provider'].sudo().browse(int(provider_id))
            provider_tech_name = provider.tech_name

        apikey = self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.google_map_api_key')

        for partner in self:
            latitude = partner.partner_latitude
            longitude = partner.partner_longitude

            if not latitude or not longitude:
                continue

            result_address = None
            country_rec = state_rec = city_rec = None
            address = {}

            try:
                # =============== FETCH ADDRESS ===============
                if provider_tech_name == 'googlemap' and apikey:
                    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={latitude},{longitude}&key={apikey}"
                    response = requests.get(url)
                    data = response.json()
                    if 'results' in data and len(data['results']) > 0:
                        result_address = data['results'][0].get('formatted_address')
                        components = data['results'][0].get('address_components', [])
                        for comp in components:
                            types = comp.get('types', [])
                            if 'country' in types:
                                address['country'] = comp.get('long_name')
                                address['country_code'] = comp.get('short_name')
                            elif 'administrative_area_level_1' in types:
                                address['state'] = comp.get('long_name')
                                address['state_code'] = comp.get('short_name')
                            elif 'locality' in types or 'administrative_area_level_2' in types:
                                address['city'] = comp.get('long_name')
                            elif 'postal_code' in types:
                                address['postcode'] = comp.get('long_name')
                            elif 'route' in types:
                                address['road'] = comp.get('long_name')
                            elif 'street_number' in types:
                                address['house_number'] = comp.get('long_name')
                            elif 'sublocality' in types or 'neighborhood' in types:
                                address['suburb'] = comp.get('long_name')
                            elif 'quarter' in types:
                                address['quarter'] = comp.get('long_name')
                            elif 'residential' in types:
                                address['residential'] = comp.get('long_name')
                            elif 'hamlet' in types:
                                address['hamlet'] = comp.get('long_name')

                elif provider_tech_name == 'openstreetmap':
                    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}"
                    response = requests.get(url, headers={'User-Agent': 'Odoo Partner'})
                    response.raise_for_status()
                    data = response.json()
                    result_address = data.get('display_name')
                    address = data.get('address', {})

                # =============== COUNTRY ===============
                country_name = address.get('country')
                country_code = address.get('country_code', '').upper()

                country_rec = None
                if country_code:
                    country_rec = self.env['res.country'].search([('code', '=', country_code)], limit=1)
                if not country_rec and country_name:
                    country_rec = self.env['res.country'].search([('name', 'ilike', country_name)], limit=1)
                if country_rec:
                    partner.country_id = country_rec.id
                    partner.country_code = country_code

                # =============== STATE ===============
                state_name = address.get('state')
                if state_name and country_rec:
                    state_rec = self.env['res.country.state'].search([
                        ('name', 'ilike', state_name),
                        ('country_id', '=', country_rec.id)
                    ], limit=1)
                    if not state_rec:
                        state_rec = self.env['res.country.state'].create({
                            'name': state_name,
                            'code': address.get('state_code', state_name[:3].upper()),
                            'country_id': country_rec.id,
                        })
                    partner.state_id = state_rec.id

                # =============== CITY, ZIP ===============
                city = address.get('city') or address.get('town') or address.get('village')
                postcode = address.get('postcode')
                partner.city = city
                partner.zip = postcode

                if city:
                    city_rec = self.env['res.city'].search([('name', 'ilike', city)], limit=1)
                    if not city_rec:
                        city_rec = self.env['res.city'].create({
                            'name': city,
                            'state_id': state_rec.id if state_rec else False,
                            'country_id': country_rec.id if country_rec else False,
                        })
                    partner.city_id = city_rec.id

                # =============== STREET, STREET2 (HUMAN READABLE) ===============
                if result_address and city:
                    parts = [p.strip() for p in result_address.split(",")]
                    try:
                        city_index = next(i for i, p in enumerate(parts) if city.lower() in p.lower())
                    except StopIteration:
                        city_index = len(parts)

                    if city_index >= 1:
                        street2 = parts[city_index - 1]
                        street = ", ".join(parts[:city_index - 1])
                    else:
                        street2 = ""
                        street = ", ".join(parts[:city_index])

                    partner.street = street
                    partner.street2 = street2

            except requests.RequestException:
                continue

# from odoo import api, fields, models, _
# import requests
# import logging
#
# _logger = logging.getLogger(__name__)
#
#
# class ResPartner(models.Model):
#     _inherit = "res.partner"
#
#
#     def set_browser_location(self, browser_lat, browser_lng):
#         """
#         Set partner location from browser geolocation
#         """
#         _logger.info("=" * 80)
#         _logger.info("📱 SET_BROWSER_LOCATION CALLED")
#         _logger.info(f"📍 Latitude: {browser_lat}, Longitude: {browser_lng}")
#         _logger.info(f"👤 Partner: {self.name} (ID: {self.id})")
#         _logger.info("=" * 80)
#
#         try:
#             lat = float(browser_lat)
#             lng = float(browser_lng)
#
#             self.write({
#                 'partner_latitude': lat,
#                 'partner_longitude': lng,
#                 'date_localization': fields.Date.context_today(self)
#             })
#             self.compute_address_from_coords()
#
#             print("✅ Address computed and remark updated")
#             _logger.info(f"✅ Location saved: {lat}, {lng}")
#
#             return {
#                 'type': 'ir.actions.client',
#                 'tag': 'display_notification',
#                 'params': {
#                     'title': _('Success'),
#                     'message': _('Browser location saved successfully!'),
#                     'type': 'success',
#                     'sticky': False,
#                 }
#             }
#         except (ValueError, TypeError) as e:
#             _logger.error(f"❌ Error: {e}")
#             return {
#                 'type': 'ir.actions.client',
#                 'tag': 'display_notification',
#                 'params': {
#                     'title': _('Error'),
#                     'message': _('Failed to save browser location'),
#                     'type': 'danger',
#                     'sticky': False,
#                 }
#             }
#
#     def compute_address_from_coords(self):
#         """Compute readable address from partner_latitude and partner_longitude and store in remark"""
#         print("=" * 80)
#         print("📌 compute_address_from_coords called")
#
#         provider_id = self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.geo_provider')
#         provider_tech_name = None
#
#         if provider_id:
#             provider = self.env['base.geo_provider'].sudo().browse(int(provider_id))
#             provider_tech_name = provider.tech_name
#             print(f"🌐 Geo provider: {provider_tech_name}")
#         else:
#             print("⚠️ No geo provider configured")
#
#         apikey = self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.google_map_api_key')
#         if provider_tech_name == 'googlemap' and not apikey:
#             print("⚠️ Google Maps API key not found")
#
#         for partner in self:
#             latitude = partner.partner_latitude
#             longitude = partner.partner_longitude
#             print(f"👤 Partner: {partner.name} (ID: {partner.id})")
#             print(f"   Latitude: {latitude}, Longitude: {longitude}")
#
#             if not latitude or not longitude:
#                 partner.remark = "Coordinates not set"
#                 print("⚠️ Coordinates not set, skipping address fetch")
#                 continue
#
#             result_address = None
#
#             try:
#                 if provider_tech_name == 'googlemap' and apikey:
#                     url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={latitude},{longitude}&key={apikey}"
#                     print(f"🔗 Calling Google Maps API: {url}")
#                     response = requests.get(url)
#                     data = response.json()
#                     if 'results' in data and len(data['results']) > 0:
#                         result_address = data['results'][0].get('formatted_address')
#
#                 elif provider_tech_name == 'openstreetmap':
#                     url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}"
#                     print(f"🔗 Calling OpenStreetMap API: {url}")
#                     response = requests.get(url, headers={'User-Agent': 'Odoo Partner'})
#                     response.raise_for_status()
#                     data = response.json()
#                     result_address = data.get('display_name')
#
#             except requests.RequestException as e:
#                 print(f"❌ Error fetching address for partner {partner.id}: {e}")
#                 result_address = f"Error fetching address: {str(e)}"
#
#             partner.remark = result_address or 'Address not found'
#             print(f"✅ Partner {partner.id} remark updated: {partner.remark}")
#
#         print("=" * 80)





