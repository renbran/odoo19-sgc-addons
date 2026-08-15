import json
import logging
import traceback

import psycopg2

from odoo import http
from odoo.http import request

from .. import adapters as adapters_pkg

_logger = logging.getLogger(__name__)

PROVIDERS = ('meta', 'google_ads', 'linkedin', 'tiktok', 'snapchat', 'universal')


class LeadIngestionWebhookController(http.Controller):

    def _handle(self, provider, token):
        env = request.env(su=True)
        config = env['crm.lead.source.config'].sudo().search(
            [('webhook_token', '=', token), ('provider', '=', provider), ('active', '=', True)],
            limit=1)
        if not config:
            return request.make_response('Not found', status=404)

        adapter = adapters_pkg.get_adapter(provider)
        query_params = request.httprequest.args.to_dict()

        if request.httprequest.method == 'GET':
            challenge = adapter.handle_verification_challenge(query_params, config)
            if challenge is not None:
                return request.make_response(challenge, status=200)
            return request.make_response('Not found', status=404)

        raw_body = request.httprequest.get_data()
        # Werkzeug's Headers object does case-insensitive lookups; a plain
        # dict built from .items() does not, and headers like
        # X-LI-Signature / X-TikTok-Signature get re-cased on the wire.
        headers = request.httprequest.headers

        if not adapter.verify_signature(headers, query_params, raw_body, config):
            _logger.warning('Rejected webhook for provider=%s token=%s: signature verification failed', provider, token)
            env['crm.lead.ingestion.log'].create({
                'source_config_id': config.id,
                'dedup_key': adapter._sha256_of(raw_body),
                'raw_payload': raw_body.decode('utf-8', errors='replace'),
                'status': 'rejected',
                'error_message': 'Signature verification failed.',
            })
            return request.make_response('Forbidden', status=403)

        try:
            parsed_payload = adapter.parse_payload(raw_body, headers)
            dedup_key = adapter.compute_dedup_key(parsed_payload)
        except Exception as exc:  # noqa: BLE001
            _logger.exception('Failed to parse payload for provider=%s token=%s', provider, token)
            env['crm.lead.ingestion.log'].create({
                'source_config_id': config.id,
                'dedup_key': adapter._sha256_of(raw_body),
                'raw_payload': raw_body.decode('utf-8', errors='replace'),
                'status': 'failed',
                'error_message': f'Payload parse error: {exc}',
            })
            return request.make_response('OK', status=200)

        log = None
        try:
            with env.cr.savepoint():
                log = env['crm.lead.ingestion.log'].create({
                    'source_config_id': config.id,
                    'dedup_key': dedup_key,
                    'raw_payload': raw_body.decode('utf-8', errors='replace'),
                    'parsed_payload': json.dumps(parsed_payload),
                    'status': 'received',
                })
        except psycopg2.errors.UniqueViolation:
            existing = env['crm.lead.ingestion.log'].search(
                [('source_config_id', '=', config.id), ('dedup_key', '=', dedup_key)], limit=1)
            if existing:
                existing.write({'status': 'duplicate'})
            return request.make_response('OK', status=200)

        if config.test_mode:
            log.write({'status': 'success'})
            return request.make_response('OK', status=200)

        try:
            with env.cr.savepoint():
                values = adapter.map_to_lead_values(parsed_payload, config)
                lead = env['crm.lead'].create(values)
                log.write({'status': 'success', 'lead_id': lead.id})
        except Exception as exc:  # noqa: BLE001
            _logger.exception('Lead creation failed for provider=%s token=%s', provider, token)
            log.write({
                'status': 'failed',
                'error_message': traceback.format_exc(),
                'retry_count': 0,
            })

        return request.make_response('OK', status=200)


def _make_route(provider):
    path = f'/crm_lead_ingestion/webhook/{provider}/<string:token>'

    @http.route(path, type='http', auth='public', csrf=False, methods=['GET', 'POST'])
    def _handler(self, token, **kwargs):
        return self._handle(provider, token)

    return _handler


for _provider in PROVIDERS:
    setattr(LeadIngestionWebhookController, f'webhook_{_provider}', _make_route(_provider))
