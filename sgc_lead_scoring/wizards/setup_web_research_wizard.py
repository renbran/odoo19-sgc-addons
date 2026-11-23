# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SetupWebResearchWizard(models.TransientModel):
    _name = 'setup.web.research.wizard'
    _description = 'Web Research Provider Setup Wizard'

    provider_type = fields.Selection([
        ('tavily', 'Tavily'),
        ('exa', 'Exa'),
        ('serper', 'Serper.dev'),
        ('serpapi', 'SerpAPI'),
        ('searxng', 'SearXNG (self-hosted)'),
        ('google', 'Google Custom Search (legacy)'),
    ], required=True, default='tavily')
    api_key = fields.Char()
    base_url = fields.Char(help='Required for searxng')
    search_engine_id = fields.Char(help='Required for google')
    test_query = fields.Char(default='Microsoft Corporation')
    test_result = fields.Text(readonly=True)
    test_success = fields.Boolean(readonly=True)

    def action_test_connection(self):
        self.ensure_one()
        provider = self.env['web.research.provider'].new({
            'name': 'wizard-test',
            'provider_type': self.provider_type,
            'api_key': self.api_key,
            'base_url': self.base_url,
            'search_engine_id': self.search_engine_id,
            'active': True,
        })
        # `new()` builds an in-memory, unsaved record; _call_provider only reads
        # fields off it and never writes, so this is safe to use for a dry-run test.
        service = self.env['web.research.service']
        results, success = service._call_provider(provider, self.test_query, 3)[:2]
        if success:
            self.test_success = True
            top = results[0]['title'] if results else 'N/A'
            self.test_result = _('SUCCESS! Found %d results for "%s"\nTop result: %s') % (
                len(results), self.test_query, top,
            )
        else:
            self.test_success = False
            self.test_result = _('FAILED: connection test did not return results. Check credentials.')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'setup.web.research.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_save_provider(self):
        self.ensure_one()
        Provider = self.env['web.research.provider']
        existing = Provider.search([('provider_type', '=', self.provider_type)], limit=1)
        vals = {
            'name': dict(self._fields['provider_type'].selection).get(self.provider_type),
            'provider_type': self.provider_type,
            'api_key': self.api_key,
            'base_url': self.base_url,
            'search_engine_id': self.search_engine_id,
            'active': True,
        }
        if existing:
            existing.write(vals)
        else:
            Provider.create(vals)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%s provider saved and enabled.') % self.provider_type,
                'type': 'success',
                'sticky': False,
            }
        }
