import hashlib
import hmac
import json

from .base import LeadProviderAdapter, register


@register
class LinkedInLeadAdapter(LeadProviderAdapter):
    provider_code = 'linkedin'
    source_label = 'LinkedIn Lead Gen Forms'
    medium_label = 'Social'

    def verify_signature(self, headers, query_params, raw_body, config):
        if not config.app_secret:
            return False
        signature_header = headers.get('X-LI-Signature')
        if signature_header:
            expected = hmac.new(
                config.app_secret.encode(), raw_body or b'', hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature_header)
        provided = headers.get('X-Webhook-Secret') or query_params.get('secret', '')
        return hmac.compare_digest(config.app_secret, provided or '')

    def handle_verification_challenge(self, query_params, config):
        if query_params.get('challengeCode') and query_params.get('verify_token') == config.verify_token:
            return query_params.get('challengeCode')
        return None

    def parse_payload(self, raw_body, headers):
        return json.loads(raw_body.decode('utf-8'))

    def compute_dedup_key(self, parsed_payload):
        lead_id = parsed_payload.get('leadId') or parsed_payload.get('id')
        if lead_id:
            return str(lead_id)
        return self._sha256_of(json.dumps(parsed_payload, sort_keys=True).encode())

    def _form_answers(self, parsed_payload):
        result = {}
        for answer in parsed_payload.get('formResponse', {}).get('answers', []):
            question = answer.get('question')
            if question:
                result[question] = answer.get('answer')
        return result

    def map_to_lead_values(self, parsed_payload, config):
        answers = self._form_answers(parsed_payload)
        form_id = parsed_payload.get('formId')
        campaign_id = parsed_payload.get('campaignId')
        campaign_label = f'Campaign {campaign_id}' if campaign_id else (
            f'Form {form_id}' if form_id else None)
        values = self._base_lead_values(
            config,
            contact_name=answers.get('First Name', '') + ' ' + answers.get('Last Name', ''),
            email=answers.get('Email Address') or answers.get('Work Email'),
            phone=answers.get('Phone Number'),
            company=answers.get('Company Name'),
            campaign_label=campaign_label,
        )
        return self._apply_field_mapping(values, parsed_payload, config)
