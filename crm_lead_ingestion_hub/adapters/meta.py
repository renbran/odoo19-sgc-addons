import hashlib
import hmac
import json

from .base import LeadProviderAdapter, register


@register
class MetaLeadAdapter(LeadProviderAdapter):
    provider_code = 'meta'

    def verify_signature(self, headers, query_params, raw_body, config):
        signature_header = headers.get('X-Hub-Signature-256', '')
        if not signature_header.startswith('sha256=') or not config.app_secret:
            return False
        expected = hmac.new(
            config.app_secret.encode(), raw_body or b'', hashlib.sha256
        ).hexdigest()
        provided = signature_header.split('=', 1)[1]
        return hmac.compare_digest(expected, provided)

    def handle_verification_challenge(self, query_params, config):
        if query_params.get('hub.mode') != 'subscribe':
            return None
        if query_params.get('hub.verify_token') == config.verify_token:
            return query_params.get('hub.challenge', '')
        return None

    def parse_payload(self, raw_body, headers):
        return json.loads(raw_body.decode('utf-8'))

    def compute_dedup_key(self, parsed_payload):
        try:
            entry = parsed_payload['entry'][0]
            change = entry['changes'][0]
            return str(change['value']['leadgen_id'])
        except (KeyError, IndexError, TypeError):
            return self._sha256_of(json.dumps(parsed_payload, sort_keys=True).encode())

    def map_to_lead_values(self, parsed_payload, config):
        field_data = {}
        try:
            entry = parsed_payload['entry'][0]
            change = entry['changes'][0]
            for field in change['value'].get('field_data', []):
                field_data[field['name']] = ','.join(field.get('values', []))
        except (KeyError, IndexError, TypeError):
            pass
        values = self._base_lead_values(
            config,
            contact_name=field_data.get('full_name'),
            email=field_data.get('email'),
            phone=field_data.get('phone_number'),
            company=field_data.get('company_name'),
        )
        return self._apply_field_mapping(values, parsed_payload, config)
