import requests
import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WebResearchService(models.Model):
    _name = 'web.research.service'
    _description = 'Web Research Service'

    def search_company_info(self, company_name, website=None):
        config = self.env['ir.config_parameter'].sudo()
        api_key = config.get_param('llm_lead_scoring.google_search_api_key', '')
        search_engine_id = config.get_param('llm_lead_scoring.google_search_engine_id', '')

        if not api_key or not search_engine_id:
            return {'success': False, 'error': 'Google Search API not configured', 'results': []}

        query = company_name
        if website:
            query = '%s %s' % (company_name, website)

        return self.search_google_custom(query, num_results=5)

    def search_google_custom(self, query, num_results=5):
        config = self.env['ir.config_parameter'].sudo()
        api_key = config.get_param('llm_lead_scoring.google_search_api_key', '')
        search_engine_id = config.get_param('llm_lead_scoring.google_search_engine_id', '')

        if not api_key or not search_engine_id:
            return {'success': False, 'error': 'Google Search API not configured', 'results': []}

        try:
            url = 'https://www.googleapis.com/customsearch/v1'
            params = {
                'key': api_key,
                'cx': search_engine_id,
                'q': query,
                'num': min(num_results, 10),
            }
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get('items', []):
                results.append({
                    'title': item.get('title', ''),
                    'link': item.get('link', ''),
                    'snippet': item.get('snippet', ''),
                })

            return {'success': True, 'results': results}

        except requests.exceptions.HTTPError as e:
            _logger.error('Google Search API HTTP error: %s', str(e))
            if hasattr(e, 'response') and e.response:
                try:
                    err_data = e.response.json()
                    return {'success': False, 'error': err_data.get('error', {}).get('message', str(e)), 'results': []}
                except (ValueError, KeyError):
                    pass
            return {'success': False, 'error': str(e), 'results': []}
        except requests.exceptions.RequestException as e:
            _logger.error('Google Search API request error: %s', str(e))
            return {'success': False, 'error': str(e), 'results': []}

    def search_google_maps(self, business_name, address=None):
        config = self.env['ir.config_parameter'].sudo()
        api_key = config.get_param('llm_lead_scoring.google_maps_api_key', '')

        if not api_key:
            return {'success': False, 'error': 'Google Maps API not configured'}

        try:
            query = business_name
            if address:
                query = '%s %s' % (business_name, address)

            url = 'https://maps.googleapis.com/maps/api/place/findplacefromtext/json'
            params = {
                'key': api_key,
                'input': query,
                'inputtype': 'textquery',
                'fields': 'name,formatted_address,rating,user_ratings_total,types,website,formatted_phone_number',
            }
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if not data.get('candidates'):
                return {'success': False, 'error': 'No business found', 'results': []}

            candidates = []
            for candidate in data['candidates'][:3]:
                candidates.append({
                    'name': candidate.get('name', ''),
                    'address': candidate.get('formatted_address', ''),
                    'rating': candidate.get('rating'),
                    'ratings_total': candidate.get('user_ratings_total'),
                    'types': candidate.get('types', []),
                    'website': candidate.get('website', ''),
                    'phone': candidate.get('formatted_phone_number', ''),
                })

            return {'success': True, 'results': candidates}

        except requests.exceptions.RequestException as e:
            _logger.error('Google Maps API error: %s', str(e))
            return {'success': False, 'error': str(e)}

    def analyze_tech_stack(self, website_url):
        if not website_url:
            return {'success': False, 'error': 'No website URL provided'}

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }
            response = requests.get(website_url, headers=headers, timeout=15, verify=False)
            html = response.text.lower()

            tech_signals = {
                'CMS': self._detect_cms(html),
                'Analytics': self._detect_analytics(html),
                'JavaScript_Frameworks': self._detect_js_frameworks(html),
                'Ecommerce': self._detect_ecommerce(html),
                'Marketing_Tools': self._detect_marketing_tools(html),
                'Web_Server': response.headers.get('Server', 'Unknown'),
            }

            return {'success': True, 'tech_stack': tech_signals}

        except requests.exceptions.RequestException as e:
            _logger.error('Tech stack analysis error for %s: %s', website_url, str(e))
            return {'success': False, 'error': str(e)}

    def _detect_cms(self, html):
        signals = []
        if 'wp-content' in html or 'wordpress' in html:
            signals.append('WordPress')
        if 'drupal' in html:
            signals.append('Drupal')
        if 'joomla' in html:
            signals.append('Joomla')
        if 'shopify' in html:
            signals.append('Shopify')
        if 'squarespace' in html:
            signals.append('Squarespace')
        if 'wix' in html:
            signals.append('Wix')
        if 'hubspot' in html:
            signals.append('HubSpot')
        return signals or ['Unknown/Static']

    def _detect_analytics(self, html):
        signals = []
        if 'google-analytics' in html or 'ga.js' in html or 'gtag' in html:
            signals.append('Google Analytics')
        if 'facebook.com/tr' in html or 'fbq(' in html:
            signals.append('Facebook Pixel')
        if 'hotjar' in html:
            signals.append('Hotjar')
        if 'hubspot' in html and 'analytics' in html:
            signals.append('HubSpot Analytics')
        return signals or ['None detected']

    def _detect_js_frameworks(self, html):
        signals = []
        if 'react' in html or 'reactjs' in html:
            signals.append('React')
        if 'vue' in html:
            signals.append('Vue.js')
        if 'angular' in html:
            signals.append('Angular')
        if 'jquery' in html:
            signals.append('jQuery')
        if 'next.js' in html or 'nextjs' in html:
            signals.append('Next.js')
        return signals or ['Unknown']

    def _detect_ecommerce(self, html):
        signals = []
        if 'woocommerce' in html:
            signals.append('WooCommerce')
        if 'shopify' in html:
            signals.append('Shopify')
        if 'magento' in html:
            signals.append('Magento')
        if 'ecwid' in html:
            signals.append('Ecwid')
        if 'add_to_cart' in html or 'addtocart' in html:
            signals.append('Generic Cart')
        return signals or ['None detected']

    def _detect_marketing_tools(self, html):
        signals = []
        if 'mailchimp' in html:
            signals.append('Mailchimp')
        if 'convertkit' in html:
            signals.append('ConvertKit')
        if 'activecampaign' in html:
            signals.append('ActiveCampaign')
        if 'intercom' in html:
            signals.append('Intercom')
        if 'livechat' in html or 'live chat' in html:
            signals.append('Live Chat')
        if 'zendesk' in html:
            signals.append('Zendesk')
        return signals or ['None detected']
