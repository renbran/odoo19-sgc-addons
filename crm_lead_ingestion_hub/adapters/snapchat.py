import hashlib
import hmac
import json

from .base import LeadProviderAdapter, register


@register
class SnapchatLeadAdapter(LeadProviderAdapter):
    provider_code = 'snapchat'
    source_label = 'Snapchat Lead Generation'
    medium_label = 'Social'

    def verify_signature(self, headers, query_params, raw_body, config):
        signature_header = headers.get('X-Snap-Signature', '')
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

    def _answers(self, parsed_payload):
        result = {}
        for answer in parsed_payload.get('form_data', []):
            key = answer.get('key')
            if key:
                result[key] = answer.get('value')
        return result

    def map_to_lead_values(self, parsed_payload, config):
        answers = self._answers(parsed_payload)
        campaign_id = parsed_payload.get('campaign_id')
        campaign_label = f'Campaign {campaign_id}' if campaign_id else None
        values = self._base_lead_values(
            config,
            contact_name=answers.get('name'),
            email=answers.get('email'),
            phone=answers.get('phone'),
            company=answers.get('company'),
            campaign_label=campaign_label,
        )
        return self._apply_field_mapping(values, parsed_payload, config)
