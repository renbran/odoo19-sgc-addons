import hashlib
import hmac
import json

from .base import LeadProviderAdapter, register


@register
class TikTokLeadAdapter(LeadProviderAdapter):
    provider_code = 'tiktok'
    source_label = 'TikTok Lead Generation'
    medium_label = 'Social'

    def verify_signature(self, headers, query_params, raw_body, config):
        signature_header = headers.get('X-TikTok-Signature', '')
        if not signature_header or not config.app_secret:
            return False
        expected = hmac.new(
            config.app_secret.encode(), raw_body or b'', hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    def parse_payload(self, raw_body, headers):
        return json.loads(raw_body.decode('utf-8'))

    def compute_dedup_key(self, parsed_payload):
        lead_id = parsed_payload.get('lead_id') or parsed_payload.get('id')
        if lead_id:
            return str(lead_id)
        return self._sha256_of(json.dumps(parsed_payload, sort_keys=True).encode())

    def _field_map(self, parsed_payload):
        result = {}
        for field in parsed_payload.get('fields', []):
            name = field.get('name')
            if name:
                result[name] = field.get('value')
        return result

    def map_to_lead_values(self, parsed_payload, config):
        fields_map = self._field_map(parsed_payload)
        form_id = parsed_payload.get('form_id')
        campaign_label = f'Form {form_id}' if form_id else None
        values = self._base_lead_values(
            config,
            contact_name=fields_map.get('name'),
            email=fields_map.get('email'),
            phone=fields_map.get('phone_number'),
            company=fields_map.get('company_name'),
            campaign_label=campaign_label,
        )
        return self._apply_field_mapping(values, parsed_payload, config)
