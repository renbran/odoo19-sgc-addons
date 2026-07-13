import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class LeadEnrichmentCascade(models.AbstractModel):
    _name = 'lead.enrichment.cascade'
    _description = 'Cascade Enrichment Service (Apollo → Abstract → Hunter)'

    PROVIDERS = ['llm.enrichment', 'apollo.enrichment', 'abstract.enrichment', 'hunter.enrichment']
    PROVIDER_LABELS = {
        'llm.enrichment': 'AI Web Research (LLM)',
        'apollo.enrichment': 'Apollo.io',
        'abstract.enrichment': 'Abstract API',
        'hunter.enrichment': 'Hunter.io',
    }

    def enrich_lead(self, lead):
        provider_name = ''
        result = {'success': False, 'error': 'All providers failed', 'provider': 'none'}

        for prov in self.PROVIDERS:
            try:
                svc = self.env[prov]
            except KeyError:
                _logger.warning('Provider %s not registered, skipping', prov)
                continue

            try:
                result = svc.enrich_lead(lead)
                if result.get('success'):
                    result['provider'] = self.PROVIDER_LABELS.get(prov, prov)
                    return result
                else:
                    _logger.info(
                        'Provider %s failed for lead %s: %s',
                        prov, lead.id, result.get('error', 'unknown'),
                    )
            except Exception as e:
                _logger.warning(
                    'Provider %s raised error for lead %s: %s',
                    prov, lead.id, str(e),
                )
                result = {'success': False, 'error': str(e), 'provider': self.PROVIDER_LABELS.get(prov, prov)}

        return result
