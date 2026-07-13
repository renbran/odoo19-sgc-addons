# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class GoogleSearchSetupWizard(models.TransientModel):
    _name = 'google.search.setup.wizard'
    _description = 'Google Custom Search Setup Guide'

    step = fields.Selection([
        ('intro', 'Introduction'),
        ('api_key', 'Get API Key'),
        ('search_engine', 'Create Search Engine'),
        ('test', 'Test Configuration'),
        ('complete', 'Setup Complete'),
    ], default='intro', string='Setup Step')

    api_key = fields.Char(string='API Key', help='Your Google Custom Search API key')
    search_engine_id = fields.Char(string='Search Engine ID', help='Your Programmable Search Engine ID')
    test_query = fields.Char(string='Test Query', default='Microsoft Corporation')
    test_result = fields.Text(string='Test Result', readonly=True)
    test_success = fields.Boolean(string='Test Successful', readonly=True)

    def action_next_step(self):
        """Move to next setup step"""
        self.ensure_one()
        
        if self.step == 'intro':
            self.step = 'api_key'
        elif self.step == 'api_key':
            self.step = 'search_engine'
        elif self.step == 'search_engine':
            self.step = 'test'
        elif self.step == 'test':
            # Run test before completing
            self.action_test_connection()
            if self.test_success:
                self.step = 'complete'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'google.search.setup.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_previous_step(self):
        """Go back to previous step"""
        self.ensure_one()
        
        if self.step == 'api_key':
            self.step = 'intro'
        elif self.step == 'search_engine':
            self.step = 'api_key'
        elif self.step == 'test':
            self.step = 'search_engine'
        elif self.step == 'complete':
            self.step = 'test'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'google.search.setup.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_test_connection(self):
        """Test the Google Custom Search configuration"""
        self.ensure_one()
        
        if not self.api_key or not self.search_engine_id:
            self.test_success = False
            self.test_result = "❌ Please enter both API Key and Search Engine ID"
            return
        
        # Temporarily save credentials for testing
        config = self.env['ir.config_parameter'].sudo()
        old_key = config.get_param('llm_lead_scoring.google_search_api_key', '')
        old_engine = config.get_param('llm_lead_scoring.google_search_engine_id', '')
        
        config.set_param('llm_lead_scoring.google_search_api_key', self.api_key)
        config.set_param('llm_lead_scoring.google_search_engine_id', self.search_engine_id)
        
        try:
            # Test search
            web_service = self.env['web.research.service']
            result = web_service.search_google_custom(self.test_query, num_results=3)
            
            if result['success']:
                results = result['results']
                self.test_success = True
                self.test_result = f"""✅ SUCCESS! Found {len(results)} results for "{self.test_query}"

Top Result:
• {results[0]['title'] if results else 'N/A'}
  {results[0]['snippet'][:100] if results else 'N/A'}...

Your Google Custom Search is working perfectly!
Free quota: 100 searches/day
"""
            else:
                self.test_success = False
                self.test_result = f"❌ FAILED: {result['error']}\n\nPlease check your credentials and try again."
                # Restore old values
                config.set_param('llm_lead_scoring.google_search_api_key', old_key)
                config.set_param('llm_lead_scoring.google_search_engine_id', old_engine)
        
        except Exception as e:
            self.test_success = False
            self.test_result = f"❌ ERROR: {str(e)}"
            # Restore old values
            config.set_param('llm_lead_scoring.google_search_api_key', old_key)
            config.set_param('llm_lead_scoring.google_search_engine_id', old_engine)

    def action_save_and_close(self):
        """Save configuration and close wizard"""
        self.ensure_one()
        
        config = self.env['ir.config_parameter'].sudo()
        config.set_param('llm_lead_scoring.google_search_api_key', self.api_key or '')
        config.set_param('llm_lead_scoring.google_search_engine_id', self.search_engine_id or '')
        config.set_param('llm_lead_scoring.enable_web_research', 'True')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Google Custom Search configured successfully! Web research is now enabled.'),
                'type': 'success',
                'sticky': False,
            }
        }
