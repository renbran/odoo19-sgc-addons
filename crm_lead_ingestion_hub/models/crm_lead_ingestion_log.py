import json
import logging
from datetime import timedelta

from odoo import fields, models

_logger = logging.getLogger(__name__)

STATUS_SELECTION = [
    ('received', 'Received'),
    ('processing', 'Processing'),
    ('success', 'Success'),
    ('failed', 'Failed'),
    ('duplicate', 'Duplicate'),
    ('rejected', 'Rejected'),
]


class CrmLeadIngestionLog(models.Model):
    _name = 'crm.lead.ingestion.log'
    _description = 'CRM Lead Ingestion Log'
    _order = 'create_date desc'

    source_config_id = fields.Many2one(
        'crm.lead.source.config', required=True, ondelete='cascade', index=True)
    provider = fields.Selection(
        related='source_config_id.provider', store=True, readonly=True)
    dedup_key = fields.Char(required=True, index=True)
    raw_payload = fields.Text()
    parsed_payload = fields.Text()
    status = fields.Selection(
        STATUS_SELECTION, required=True, default='received', index=True)
    error_message = fields.Text()
    lead_id = fields.Many2one('crm.lead', ondelete='set null')
    retry_count = fields.Integer(default=0)
    last_attempt = fields.Datetime()

    _dedup_key_per_source_unique = models.Constraint(
        'unique(source_config_id, dedup_key)',
        'A lead with this dedup key has already been ingested for this '
        'source configuration.')

    def _cron_retry_failed(self):
        from .. import adapters as adapters_pkg

        logs = self.search([('status', '=', 'failed')])
        for log in logs:
            config = log.source_config_id
            if not config or log.retry_count >= config.max_retries:
                continue
            backoff_minutes = config.backoff_interval_minutes * (2 ** log.retry_count)
            if log.last_attempt and fields.Datetime.now() < log.last_attempt + timedelta(minutes=backoff_minutes):
                continue
            try:
                adapter = adapters_pkg.get_adapter(config.provider)
                parsed_payload = json.loads(log.parsed_payload or '{}')
                values = adapter.map_to_lead_values(parsed_payload, config)
                lead = self.env['crm.lead'].sudo().create(values)
                log.write({'status': 'success', 'lead_id': lead.id})
            except Exception as exc:  # noqa: BLE001
                _logger.exception('Retry failed for ingestion log %s', log.id)
                log.write({
                    'retry_count': log.retry_count + 1,
                    'last_attempt': fields.Datetime.now(),
                    'error_message': str(exc),
                })

    def _cron_purge_old_logs(self):
        for config in self.env['crm.lead.source.config'].search([]):
            if not config.retention_days:
                continue
            threshold = fields.Datetime.now() - timedelta(days=config.retention_days)
            old_logs = self.search([
                ('source_config_id', '=', config.id),
                ('create_date', '<', threshold),
            ])
            old_logs.unlink()
