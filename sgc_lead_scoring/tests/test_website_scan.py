# -*- coding: utf-8 -*-
"""Tests for the company-website scanner (``models/website_scan.py``).

Pure-function module — no Odoo environment needed for most of these, but we
run under TransactionCase like the rest of the suite for consistency.
Network-touching behavior (_fetch_one) is mocked; is_safe_public_url is
exercised against literal IP addresses so it never depends on real DNS/
network access in CI/sandboxes.
"""
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.sgc_lead_scoring.models import website_scan as ws


class TestIsSafePublicUrl(TransactionCase):
    """SSRF guard (Decision: resolve-then-check, not just a hostname string
    check, so a hostname that merely *points at* an internal IP is caught)."""

    def test_rejects_bad_scheme(self):
        self.assertFalse(ws.is_safe_public_url('ftp://8.8.8.8/'))
        self.assertFalse(ws.is_safe_public_url('file:///etc/passwd'))

    def test_rejects_embedded_credentials(self):
        self.assertFalse(ws.is_safe_public_url('http://user:pass@8.8.8.8/'))

    def test_rejects_loopback_literal(self):
        self.assertFalse(ws.is_safe_public_url('http://127.0.0.1/'))
        self.assertFalse(ws.is_safe_public_url('http://[::1]/'))

    def test_rejects_private_ranges(self):
        for host in ('10.0.0.5', '192.168.1.1', '172.16.0.1'):
            self.assertFalse(ws.is_safe_public_url('http://%s/' % host), host)

    def test_rejects_link_local_metadata_endpoint(self):
        # 169.254.169.254 is the cloud-provider instance-metadata IP — a
        # classic SSRF target and must always be blocked.
        self.assertFalse(ws.is_safe_public_url('http://169.254.169.254/'))

    def test_accepts_public_ip_literal(self):
        self.assertTrue(ws.is_safe_public_url('http://8.8.8.8/'))
        self.assertTrue(ws.is_safe_public_url('https://8.8.8.8/contact'))

    def test_rejects_blank_or_malformed(self):
        self.assertFalse(ws.is_safe_public_url(''))
        self.assertFalse(ws.is_safe_public_url('not a url'))

    def test_rejects_hostname_that_resolves_internal(self):
        """DNS-rebinding style case: the hostname string itself gives no hint
        of anything internal, but it resolves to a private IP — must still
        be rejected because we check the resolved address, not the string."""
        with patch.object(ws.socket, 'getaddrinfo', return_value=[
            (2, 1, 6, '', ('10.1.2.3', 0)),
        ]):
            self.assertFalse(ws.is_safe_public_url('http://totally-legit-vendor.example/'))

    def test_accepts_hostname_that_resolves_public(self):
        with patch.object(ws.socket, 'getaddrinfo', return_value=[
            (2, 1, 6, '', ('93.184.216.34', 0)),
        ]):
            self.assertTrue(ws.is_safe_public_url('http://example.test/'))

    def test_rejects_unresolvable_hostname(self):
        import socket as real_socket
        with patch.object(ws.socket, 'getaddrinfo', side_effect=real_socket.gaierror):
            self.assertFalse(ws.is_safe_public_url('http://does-not-exist.invalid/'))


class TestExtractText(TransactionCase):

    def test_strips_script_and_style(self):
        html = '<html><head><style>.x{}</style></head><body>' \
               '<script>evil()</script><p>Contact us: 555-1234</p></body></html>'
        text = ws._extract_text(html)
        self.assertIn('Contact us: 555-1234', text)
        self.assertNotIn('evil()', text)

    def test_never_raises_on_garbage(self):
        self.assertEqual(ws._extract_text(None), '')
        self.assertEqual(ws._extract_text(12345), '')


class TestScanCompanyWebsite(TransactionCase):

    def test_blank_website_returns_empty(self):
        self.assertEqual(ws.scan_company_website(''), [])
        self.assertEqual(ws.scan_company_website(None), [])

    def test_unsafe_website_returns_empty(self):
        self.assertEqual(ws.scan_company_website('http://127.0.0.1/'), [])
        self.assertEqual(ws.scan_company_website('http://169.254.169.254/'), [])

    def test_adds_https_when_missing_scheme(self):
        with patch.object(ws, 'is_safe_public_url', return_value=True), \
             patch.object(ws, '_fetch_one', return_value=('https://acme.com', '<p>hi</p>')):
            evidence = ws.scan_company_website('acme.com')
        self.assertTrue(evidence)
        self.assertEqual(evidence[0]['url'], 'https://acme.com')

    def test_builds_evidence_shape(self):
        # Only the home page (first candidate URL) "succeeds"; the
        # contact/about paths 404 — real sites rarely have all of them.
        def fetch(url):
            if url == 'https://acme.com':
                return ('https://acme.com', '<p>Call 555-123-4567</p>')
            return None
        with patch.object(ws, 'is_safe_public_url', return_value=True), \
             patch.object(ws, '_fetch_one', side_effect=fetch):
            evidence = ws.scan_company_website('https://acme.com')
        self.assertEqual(len(evidence), 1)
        item = evidence[0]
        self.assertEqual(item['provider'], 'website_scan')
        self.assertIn('555-123-4567', item['snippet'])
        self.assertIn('retrieved_at', item)

    def test_stops_at_max_pages(self):
        with patch.object(ws, 'is_safe_public_url', return_value=True), \
             patch.object(ws, '_fetch_one', return_value=('https://acme.com/x', '<p>content</p>')):
            evidence = ws.scan_company_website('https://acme.com')
        self.assertLessEqual(len(evidence), ws._MAX_PAGES)

    def test_fetch_failure_yields_no_evidence(self):
        with patch.object(ws, 'is_safe_public_url', return_value=True), \
             patch.object(ws, '_fetch_one', return_value=None):
            evidence = ws.scan_company_website('https://acme.com')
        self.assertEqual(evidence, [])
