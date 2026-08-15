import hmac
import json

from .base import LeadProviderAdapter, register


@register
class GoogleAdsLeadAdapter(LeadProviderAdapter):
    provider_code = 'google_ads'
    source_label = 'Google Ads'
    medium_label = 'Search'

    def verify_signature(self, headers, query_params, raw_body, config):
        if not config.app_secret:
            return False
        provided = headers.get('X-Webhook-Secret') or query_params.get('secret', '')
        return hmac.compare_digest(config.app_secret, provided or '')

    def parse_payload(self, raw_body, headers):
        return json.loads(raw_body.decode('utf-8'))

    def compute_dedup_key(self, parsed_payload):
        google_key = parsed_payload.get('google_key') or parsed_payload.get('lead_id')
        if google_key:
            return str(google_key)
        return self._sha256_of(json.dumps(parsed_payload, sort_keys=True).encode())

    def _column_map(self, parsed_payload):
        result = {}
        for item in parsed_payload.get('user_column_data', []):
            key = item.get('column_id') or item.get('column_name')
            if key:
                result[key] = item.get('string_value')
        return result

    def map_to_lead_values(self, parsed_payload, config):
        columns = self._column_map(parsed_payload)
        campaign_id = parsed_payload.get('campaign_id')
        form_id = parsed_payload.get('form_id')
        campaign_label = f'Campaign {campaign_id}' if campaign_id else (
            f'Form {form_id}' if form_id else None)
        values = self._base_lead_values(
            config,
            contact_name=columns.get('FULL_NAME') or columns.get('First Name'),
            email=columns.get('EMAIL'),
            phone=columns.get('PHONE_NUMBER'),
            company=columns.get('COMPANY_NAME'),
            campaign_label=campaign_label,
        )
        return self._apply_field_mapping(values, parsed_payload, config)
