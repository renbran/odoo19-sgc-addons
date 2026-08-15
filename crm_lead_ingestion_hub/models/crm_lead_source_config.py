import uuid

from odoo import api, fields, models


PROVIDER_SELECTION = [
    ('meta', 'Meta (Facebook/Instagram Lead Ads)'),
    ('google_ads', 'Google Ads'),
    ('linkedin', 'LinkedIn Lead Gen Forms'),
    ('tiktok', 'TikTok Lead Generation'),
    ('snapchat', 'Snapchat Lead Generation'),
    ('universal', 'Universal JSON/Form Webhook'),
]


def _default_webhook_token(self):
    return uuid.uuid4().hex


class CrmLeadSourceConfig(models.Model):
    _name = 'crm.lead.source.config'
    _description = 'CRM Lead Ingestion Source Configuration'

    name = fields.Char(required=True)
    provider = fields.Selection(PROVIDER_SELECTION, required=True)
    webhook_token = fields.Char(
        required=True, copy=False, index=True,
        default=_default_webhook_token,
        help="Unique URL slug identifying this webhook endpoint.")
    app_secret = fields.Char(
        help="Provider app/shared secret used for signature verification.")
    verify_token = fields.Char(
        help="Verification token used for Meta/LinkedIn GET challenge "
             "handshakes during webhook subscription setup.")
    active = fields.Boolean(default=True)
    test_mode = fields.Boolean(
        default=False,
        help="When enabled, ingested payloads are logged but no crm.lead "
             "record is created.")
    team_id = fields.Many2one('crm.team', string='Sales Team')
    user_id = fields.Many2one('res.users', string='Salesperson')
    field_mapping_ids = fields.One2many(
        'crm.lead.field.mapping', 'source_config_id', string='Field Mapping')
    max_retries = fields.Integer(default=5)
    backoff_interval_minutes = fields.Integer(default=15)
    retention_days = fields.Integer(default=90)

    log_ids = fields.One2many(
        'crm.lead.ingestion.log', 'source_config_id', string='Ingestion Logs')
    log_count = fields.Integer(compute='_compute_log_count')

    _webhook_token_unique = models.Constraint(
        'unique(webhook_token)', 'Webhook token must be unique.')

    @api.depends('log_ids')
    def _compute_log_count(self):
        for rec in self:
            rec.log_count = len(rec.log_ids)

    def action_regenerate_token(self):
        for rec in self:
            rec.webhook_token = uuid.uuid4().hex
