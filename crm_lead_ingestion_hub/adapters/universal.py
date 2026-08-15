import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from .base import LeadProviderAdapter, register


@register
class UniversalWebhookAdapter(LeadProviderAdapter):
    provider_code = 'universal'
    source_label = 'Universal Webhook'
    medium_label = None

    def verify_signature(self, headers, query_params, raw_body, config):
        if not config.app_secret:
            return False
        signature_header = headers.get('X-Webhook-Signature')
        if signature_header:
            expected = hmac.new(
                config.app_secret.encode(), raw_body or b'', hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature_header)
        provided = headers.get('X-Webhook-Secret') or query_params.get('secret', '')
        return hmac.compare_digest(config.app_secret, provided or '')

    def parse_payload(self, raw_body, headers):
        content_type = (headers.get('Content-Type') or '').lower()
        text = (raw_body or b'').decode('utf-8')
        if 'application/json' in content_type:
            return json.loads(text) if text else {}
        return dict(parse_qsl(text))

    def compute_dedup_key(self, parsed_payload):
        return self._sha256_of(json.dumps(parsed_payload, sort_keys=True).encode())

    def map_to_lead_values(self, parsed_payload, config):
        campaign_label = parsed_payload.get('source') if isinstance(parsed_payload, dict) else None
        values = self._base_lead_values(config, campaign_label=campaign_label)
        return self._apply_field_mapping(values, parsed_payload, config)
