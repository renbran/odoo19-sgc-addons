import hashlib
import hmac
import json

from odoo.tests.common import TransactionCase, tagged

from ..adapters import get_adapter


@tagged('post_install', '-at_install')
class TestSignatureVerification(TransactionCase):

    def _config(self, provider, **kw):
        vals = {
            'name': f'{provider} config',
            'provider': provider,
            'app_secret': 'topsecret',
            'verify_token': 'verifyme',
        }
        vals.update(kw)
        return self.env['crm.lead.source.config'].create(vals)

    def _hmac(self, secret, body):
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    # --- Meta ---
    def test_01_meta_valid_signature_accepted(self):
        config = self._config('meta')
        body = b'{"entry": []}'
        sig = self._hmac('topsecret', body)
        headers = {'X-Hub-Signature-256': f'sha256={sig}'}
        adapter = get_adapter('meta')
        self.assertTrue(adapter.verify_signature(headers, {}, body, config))

    def test_02_meta_invalid_signature_rejected(self):
        config = self._config('meta')
        body = b'{"entry": []}'
        headers = {'X-Hub-Signature-256': 'sha256=deadbeef'}
        adapter = get_adapter('meta')
        self.assertFalse(adapter.verify_signature(headers, {}, body, config))

    def test_03_meta_missing_signature_rejected(self):
        config = self._config('meta')
        adapter = get_adapter('meta')
        self.assertFalse(adapter.verify_signature({}, {}, b'{}', config))

    def test_04_meta_verification_challenge_correct_token(self):
        config = self._config('meta')
        adapter = get_adapter('meta')
        query = {'hub.mode': 'subscribe', 'hub.verify_token': 'verifyme', 'hub.challenge': 'chal123'}
        self.assertEqual(adapter.handle_verification_challenge(query, config), 'chal123')

    def test_05_meta_verification_challenge_wrong_token(self):
        config = self._config('meta')
        adapter = get_adapter('meta')
        query = {'hub.mode': 'subscribe', 'hub.verify_token': 'wrong', 'hub.challenge': 'chal123'}
        self.assertIsNone(adapter.handle_verification_challenge(query, config))

    # --- Google Ads ---
    def test_06_google_ads_valid_secret_accepted(self):
        config = self._config('google_ads')
        adapter = get_adapter('google_ads')
        headers = {'X-Webhook-Secret': 'topsecret'}
        self.assertTrue(adapter.verify_signature(headers, {}, b'{}', config))

    def test_07_google_ads_invalid_secret_rejected(self):
        config = self._config('google_ads')
        adapter = get_adapter('google_ads')
        headers = {'X-Webhook-Secret': 'wrong'}
        self.assertFalse(adapter.verify_signature(headers, {}, b'{}', config))

    # --- LinkedIn ---
    def test_08_linkedin_valid_signature_accepted(self):
        config = self._config('linkedin')
        body = b'{"leadId": "1"}'
        sig = self._hmac('topsecret', body)
        headers = {'X-LI-Signature': sig}
        adapter = get_adapter('linkedin')
        self.assertTrue(adapter.verify_signature(headers, {}, body, config))

    def test_09_linkedin_invalid_signature_rejected(self):
        config = self._config('linkedin')
        headers = {'X-LI-Signature': 'bad'}
        adapter = get_adapter('linkedin')
        self.assertFalse(adapter.verify_signature(headers, {}, b'{}', config))

    # --- TikTok ---
    def test_10_tiktok_valid_signature_accepted(self):
        config = self._config('tiktok')
        body = b'{"lead_id": "1"}'
        sig = self._hmac('topsecret', body)
        headers = {'X-TikTok-Signature': sig}
        adapter = get_adapter('tiktok')
        self.assertTrue(adapter.verify_signature(headers, {}, body, config))

    def test_11_tiktok_invalid_signature_rejected(self):
        config = self._config('tiktok')
        headers = {'X-TikTok-Signature': 'bad'}
        adapter = get_adapter('tiktok')
        self.assertFalse(adapter.verify_signature(headers, {}, b'{}', config))

    # --- Snapchat ---
    def test_12_snapchat_valid_signature_accepted(self):
        config = self._config('snapchat')
        body = b'{"lead_id": "1"}'
        sig = self._hmac('topsecret', body)
        headers = {'X-Snap-Signature': sig}
        adapter = get_adapter('snapchat')
        self.assertTrue(adapter.verify_signature(headers, {}, body, config))

    def test_13_snapchat_invalid_signature_rejected(self):
        config = self._config('snapchat')
        headers = {'X-Snap-Signature': 'bad'}
        adapter = get_adapter('snapchat')
        self.assertFalse(adapter.verify_signature(headers, {}, b'{}', config))

    # --- Universal ---
    def test_14_universal_valid_secret_header_accepted(self):
        config = self._config('universal')
        adapter = get_adapter('universal')
        headers = {'X-Webhook-Secret': 'topsecret'}
        self.assertTrue(adapter.verify_signature(headers, {}, b'{}', config))

    def test_15_universal_valid_secret_query_param_accepted(self):
        config = self._config('universal')
        adapter = get_adapter('universal')
        self.assertTrue(adapter.verify_signature({}, {'secret': 'topsecret'}, b'{}', config))

    def test_16_universal_invalid_secret_rejected(self):
        config = self._config('universal')
        adapter = get_adapter('universal')
        self.assertFalse(adapter.verify_signature({}, {'secret': 'wrong'}, b'{}', config))
