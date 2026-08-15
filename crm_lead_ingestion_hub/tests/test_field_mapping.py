import json

from odoo.tests.common import TransactionCase, tagged

from ..adapters import get_adapter


@tagged('post_install', '-at_install')
class TestFieldMapping(TransactionCase):

    def _config(self, provider, **kw):
        vals = {'name': f'{provider} config', 'provider': provider, 'app_secret': 's'}
        vals.update(kw)
        return self.env['crm.lead.source.config'].create(vals)

    # --- payload parsing ---
    def test_17_meta_payload_parses(self):
        adapter = get_adapter('meta')
        body = json.dumps({
            'entry': [{'changes': [{'value': {
                'leadgen_id': 'lg1',
                'field_data': [
                    {'name': 'full_name', 'values': ['Jane Doe']},
                    {'name': 'email', 'values': ['jane@example.com']},
                ],
            }}]}]
        }).encode()
        parsed = adapter.parse_payload(body, {})
        self.assertEqual(adapter.compute_dedup_key(parsed), 'lg1')

    def test_18_google_ads_user_column_data_parses(self):
        adapter = get_adapter('google_ads')
        body = json.dumps({
            'google_key': 'gk1',
            'user_column_data': [
                {'column_id': 'EMAIL', 'string_value': 'a@b.com'},
                {'column_id': 'FULL_NAME', 'string_value': 'A B'},
            ],
        }).encode()
        parsed = adapter.parse_payload(body, {})
        config = self._config('google_ads')
        values = adapter.map_to_lead_values(parsed, config)
        self.assertEqual(values.get('email_from'), 'a@b.com')

    def test_19_universal_json_body_parses(self):
        adapter = get_adapter('universal')
        body = b'{"foo": "bar"}'
        parsed = adapter.parse_payload(body, {'Content-Type': 'application/json'})
        self.assertEqual(parsed, {'foo': 'bar'})

    def test_20_universal_form_encoded_body_parses(self):
        adapter = get_adapter('universal')
        body = b'foo=bar&baz=qux'
        parsed = adapter.parse_payload(body, {'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(parsed.get('foo'), 'bar')
        self.assertEqual(parsed.get('baz'), 'qux')

    def test_21_malformed_json_raises_and_is_catchable(self):
        adapter = get_adapter('universal')
        with self.assertRaises(Exception):
            adapter.parse_payload(b'{not valid json', {'Content-Type': 'application/json'})

    # --- default and override mapping ---
    def test_28_default_mapping_produces_expected_lead_values(self):
        adapter = get_adapter('meta')
        config = self._config('meta')
        parsed = {
            'entry': [{'changes': [{'value': {
                'leadgen_id': 'lg2',
                'field_data': [
                    {'name': 'full_name', 'values': ['John Smith']},
                    {'name': 'email', 'values': ['john@example.com']},
                    {'name': 'phone_number', 'values': ['+15551234']},
                    {'name': 'company_name', 'values': ['Acme']},
                ],
            }}]}]
        }
        values = adapter.map_to_lead_values(parsed, config)
        self.assertEqual(values['contact_name'], 'John Smith')
        self.assertEqual(values['email_from'], 'john@example.com')
        self.assertEqual(values['phone'], '+15551234')
        self.assertEqual(values['partner_name'], 'Acme')

    def test_29_custom_field_mapping_overrides_target_field(self):
        adapter = get_adapter('universal')
        config = self._config('universal')
        self.env['crm.lead.field.mapping'].create({
            'source_config_id': config.id,
            'source_key': 'custom_email',
            'target_field': 'email_from',
        })
        parsed = {'custom_email': 'mapped@example.com'}
        values = adapter.map_to_lead_values(parsed, config)
        self.assertEqual(values['email_from'], 'mapped@example.com')
