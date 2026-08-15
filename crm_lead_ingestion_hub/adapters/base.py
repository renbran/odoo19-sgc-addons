import abc
import hashlib

_ADAPTER_REGISTRY = {}


def register(cls):
    """Class decorator: instantiate and register an adapter by provider_code."""
    _ADAPTER_REGISTRY[cls.provider_code] = cls()
    return cls


def get_adapter(provider_code):
    return _ADAPTER_REGISTRY[provider_code]


class LeadProviderAdapter(abc.ABC):
    """Common interface every provider adapter must implement.

    verify_signature MUST be called, and MUST pass, before any DB write —
    it is the entire security boundary for these public, session-less
    webhook routes.
    """

    provider_code = None

    @abc.abstractmethod
    def verify_signature(self, headers, query_params, raw_body, config):
        """Return True if the inbound request is authentic for `config`."""

    @abc.abstractmethod
    def parse_payload(self, raw_body, headers):
        """Return a dict parsed from the raw request body."""

    @abc.abstractmethod
    def compute_dedup_key(self, parsed_payload):
        """Return a stable string key identifying this lead delivery."""

    @abc.abstractmethod
    def map_to_lead_values(self, parsed_payload, config):
        """Return a dict of crm.lead field values."""

    def handle_verification_challenge(self, query_params, config):
        """Override for providers needing a GET handshake (Meta, LinkedIn).

        Return the plain-text challenge response, or None if this request
        is not a verification challenge.
        """
        return None

    def _sha256_of(self, raw_body):
        return hashlib.sha256(raw_body or b'').hexdigest()

    #: Human-readable UTM source label per provider, e.g. "Meta Lead Ads".
    source_label = None
    #: UTM medium label, e.g. "Social" or "Search".
    medium_label = 'Social'

    def _base_lead_values(self, config, contact_name=None, email=None,
                           phone=None, company=None, description=None,
                           campaign_label=None):
        values = {}
        if contact_name:
            values['contact_name'] = contact_name
        if email:
            values['email_from'] = email
        if phone:
            values['phone'] = phone
        if company:
            values['partner_name'] = company
        if description:
            values['description'] = description
        if config.team_id:
            values['team_id'] = config.team_id.id
        if config.user_id:
            values['user_id'] = config.user_id.id
        values.setdefault('name', contact_name or company or 'New lead')

        env = config.env
        if self.source_label:
            values['source_id'] = self._get_or_create(
                env, 'utm.source', self.source_label).id
        if self.medium_label:
            values['medium_id'] = self._get_or_create(
                env, 'utm.medium', self.medium_label).id
        if campaign_label:
            values['campaign_id'] = self._get_or_create(
                env, 'utm.campaign', campaign_label).id
        return values

    @staticmethod
    def _get_or_create(env, model_name, name):
        record = env[model_name].sudo().search([('name', '=', name)], limit=1)
        if not record:
            record = env[model_name].sudo().create({'name': name})
        return record

    def _apply_field_mapping(self, values, parsed_payload, config):
        for mapping in config.field_mapping_ids:
            source_value = self._get_nested(parsed_payload, mapping.source_key)
            if source_value is not None:
                values[mapping.target_field] = source_value
        return values

    @staticmethod
    def _get_nested(payload, dotted_key):
        current = payload
        for part in dotted_key.split('.'):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
