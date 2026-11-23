import logging
import re
import requests
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

NOMINATIM_URL = 'https://nominatim.openstreetmap.org'


class LocationEnrichment(models.AbstractModel):
    _name = 'location.enrichment'
    _description = 'Free Geocoding & Location Intelligence (OpenStreetMap Nominatim)'

    UAE_EMIRATES = {
        'abu dhabi': 'Abu Dhabi',
        'dubai': 'Dubai',
        'sharjah': 'Sharjah',
        'ajman': 'Ajman',
        'umm al quwain': 'Umm Al Quwain',
        'ras al khaimah': 'Ras Al Khaimah',
        'fujairah': 'Fujairah',
        'al ain': 'Al Ain',
    }

    UAE_EMIRATES_AR = {
        'أبو ظبي': 'Abu Dhabi',
        'دبي': 'Dubai',
        'الشارقة': 'Sharjah',
        'عجمان': 'Ajman',
        'أم القيوين': 'Umm Al Quwain',
        'رأس الخيمة': 'Ras Al Khaimah',
        'الفجيرة': 'Fujairah',
        'العين': 'Al Ain',
    }

    UAE_PRIORITY = {
        'Dubai': 100,
        'Abu Dhabi': 90,
        'Sharjah': 75,
        'Ajman': 65,
        'Al Ain': 65,
        'Ras Al Khaimah': 60,
        'Fujairah': 55,
        'Umm Al Quwain': 50,
    }

    TERRITORY_ZONES = {
        'dubai': 'Dubai',
        'abu dhabi': 'Abu Dhabi',
        'northern': 'Northern Emirates',
        'international': 'International',
    }

    def geocode(self, address, city=None, country=None):
        parts = [p for p in [address, city, country] if p]
        q = ', '.join(parts)
        if not q.strip():
            return {'success': False, 'error': 'No location data to geocode'}

        try:
            resp = requests.get(
                f'{NOMINATIM_URL}/search',
                params={'q': q, 'format': 'json', 'limit': 1, 'addressdetails': 1},
                headers={
                    'User-Agent': 'SGCTech-LeadScoring/1.0 (admin@sgctech.ai)',
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return {'success': False, 'error': 'No geocoding results'}

            result = data[0]
            addr = result.get('address', {})
            lat = float(result.get('lat', 0))
            lng = float(result.get('lon', 0))

            city_raw = (
                addr.get('city') or addr.get('town')
                or addr.get('village') or addr.get('county') or ''
            ).strip().lower()

            emirate = self._detect_uae_emirate(city_raw, addr)
            country_code = addr.get('country_code', '') or ''
            territory = self._determine_territory(emirate, country, country_code)
            priority = self.UAE_PRIORITY.get(emirate, 30)

            return {
                'success': True,
                'lat': lat,
                'lng': lng,
                'display_name': result.get('display_name', ''),
                'city': addr.get('city') or addr.get('town') or addr.get('village') or '',
                'state': addr.get('state', ''),
                'country': addr.get('country', ''),
                'country_code': addr.get('country_code', ''),
                'postcode': addr.get('postcode', ''),
                'emirate': emirate,
                'territory': territory,
                'priority_score': priority,
                'raw': result,
            }
        except requests.exceptions.RequestException as e:
            _logger.error('Nominatim geocoding error: %s', str(e))
            return {'success': False, 'error': str(e)}

    def _detect_uae_emirate(self, city_raw, address):
        if not city_raw:
            return ''

        if city_raw in self.UAE_EMIRATES:
            return self.UAE_EMIRATES[city_raw]

        if city_raw in self.UAE_EMIRATES_AR:
            return self.UAE_EMIRATES_AR[city_raw]

        combined = city_raw + ' ' + (address.get('state', '') or '').strip().lower()
        combined += ' ' + (address.get('country', '') or '').strip().lower()
        for ar_name, en_name in self.UAE_EMIRATES_AR.items():
            if ar_name in combined:
                return en_name

        state = (address.get('state', '') or '').strip().lower()
        if state in self.UAE_EMIRATES:
            return self.UAE_EMIRATES[state]
        if state in self.UAE_EMIRATES_AR:
            return self.UAE_EMIRATES_AR[state]

        for key, label in self.UAE_EMIRATES.items():
            if key in city_raw or city_raw in key:
                return label

        return ''

    def _determine_territory(self, emirate, country, country_code=''):
        if emirate in ('Dubai',):
            return 'Dubai'
        if emirate in ('Abu Dhabi', 'Al Ain'):
            return 'Abu Dhabi'
        if emirate:
            return 'Northern Emirates'
        if country_code == 'ae':
            return 'Northern Emirates'
        if country:
            c = country.lower()
            if c in ('uae', 'united arab emirates', 'الإمارات العربية المتحدة', 'الامارات'):
                return 'Northern Emirates'
        return 'International'

    def score_location(self, lead):
        score = 50
        details = {}

        city = lead.city or ''
        country = lead.country_id.name or ''
        state = lead.state_id.name or ''
        street = lead.street or ''
        partner_city = lead.partner_id.city or ''
        partner_country = lead.partner_id.country_id.name or ''

        geo_city = city or partner_city
        geo_country = country or partner_country
        geo_street = street or lead.street2 or ''

        if not geo_city and not geo_country:
            return {'score': 50, 'details': {'note': 'No location data available'}}

        result = self.geocode(geo_street, geo_city, geo_country)
        if not result.get('success'):
            return {'score': 50, 'details': {'note': 'Geocoding unavailable'}}

        priority = result.get('priority_score', 30)
        emirate = result.get('emirate', '')
        territory = result.get('territory', 'International')

        score = priority

        details = {
            'emirate': emirate or 'N/A',
            'territory': territory,
            'city': result.get('city', ''),
            'country': result.get('country', ''),
            'priority_score': priority,
        }

        return {'score': score, 'details': details}

    def enrich_lead_location(self, lead):
        location = self.score_location(lead)
        if not location.get('details'):
            return {'success': False, 'error': 'Could not score location'}

        d = location['details']
        to_write = {}
        if d.get('emirate') and d['emirate'] != 'N/A':
            to_write['x_emirate'] = d['emirate']
        if d.get('territory'):
            to_write['x_territory'] = d['territory']
        if d.get('city'):
            to_write['x_geo_city'] = d['city']
        if d.get('priority_score', 0) > 0:
            to_write['x_location_score'] = d['priority_score']

        if to_write:
            lead.write(to_write)

        return {
            'success': True,
            'location_score': location['score'],
            'fields_updated': list(to_write.keys()),
        }
