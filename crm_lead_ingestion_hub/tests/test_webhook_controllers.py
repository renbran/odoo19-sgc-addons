import hashlib
import hmac
import json

from odoo.tests.common import HttpCase, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWebhookControllersHttp(HttpCase):

    def setUp(self):
        super().setUp()
        self.config = self.env['crm.lead.source.config'].create({
            'name': 'universal http config',
            'provider': 'universal',
            'app_secret': 'topsecret',
        })

    def _url(self, token):
        return f'/crm_lead_ingestion/webhook/universal/{token}'

    def test_30_test_mode_no_lead_created(self):
        self.config.test_mode = True
        body = json.dumps({'name': 'Test Lead'}).encode()
        sig = hmac.new(b'topsecret', body, hashlib.sha256).hexdigest()
        lead_count_before = self.env['crm.lead'].search_count([])
        response = self.url_open(
            self._url(self.config.webhook_token), data=body,
            headers={'Content-Type': 'application/json', 'X-Webhook-Signature': sig})
        self.assertEqual(response.status_code, 200)
        lead_count_after = self.env['crm.lead'].search_count([])
        self.assertEqual(lead_count_before, lead_count_after)
        log = self.env['crm.lead.ingestion.log'].search(
            [('source_config_id', '=', self.config.id)], limit=1, order='id desc')
        self.assertEqual(log.status, 'success')
        self.assertFalse(log.lead_id)

    def test_31_inactive_source_returns_404(self):
        self.config.active = False
        body = b'{}'
        response = self.url_open(self._url(self.config.webhook_token), data=body)
        self.assertEqual(response.status_code, 404)

    def test_success_lead_created_with_valid_signature(self):
        body = json.dumps({'name': 'Real Lead'}).encode()
        sig = hmac.new(b'topsecret', body, hashlib.sha256).hexdigest()
        response = self.url_open(
            self._url(self.config.webhook_token), data=body,
            headers={'Content-Type': 'application/json', 'X-Webhook-Signature': sig})
        self.assertEqual(response.status_code, 200)
        log = self.env['crm.lead.ingestion.log'].search(
            [('source_config_id', '=', self.config.id)], limit=1, order='id desc')
        self.assertEqual(log.status, 'success')
        self.assertTrue(log.lead_id)

    def test_rejected_returns_403_on_bad_signature(self):
        body = b'{"name": "Bad"}'
        response = self.url_open(
            self._url(self.config.webhook_token), data=body,
            headers={'Content-Type': 'application/json', 'X-Webhook-Signature': 'wrong'})
        self.assertEqual(response.status_code, 403)


@tagged('post_install', '-at_install')
class TestSourceConfigAcl(TransactionCase):

    def test_32_sales_user_cannot_write_source_config(self):
        salesman_group = self.env.ref('sales_team.group_sale_salesman')
        user = self.env['res.users'].create({
            'name': 'Sales User',
            'login': 'sales_user_ingestion_test',
            'group_ids': [(6, 0, [salesman_group.id])],
        })
        config = self.env['crm.lead.source.config'].create({
            'name': 'acl config',
            'provider': 'universal',
            'app_secret': 's',
        })
        with self.assertRaises(Exception):
            config.with_user(user).write({'name': 'hacked'})
