# -*- coding: utf-8 -*-
"""Company-website scanner — pure, Odoo-free helper module (mirrors the
``lead_intelligence.py`` split: no ``self.env`` here, just plain functions
over plain data so they're unit-testable and safe to call from a thread).

Fetches a handful of pages from a lead's OWN company website (home + the
usual contact/about paths) and returns evidence dicts in the exact same
shape ``lead_intelligence.normalize_evidence()`` produces, so they can be
concatenated onto the search-engine evidence list and flow through the same
prompt-injection-defended ``<<BEGIN_EVIDENCE>>`` pipeline untouched.

Every failure mode (unresolvable host, private/internal IP, connection
error, non-HTML response, broken markup) degrades to "no evidence from this
page" — this scanner must never raise and never block enrichment.
"""
import ipaddress
import logging
import socket
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

_logger = logging.getLogger(__name__)

_CONTACT_PATHS = ('', '/contact', '/contact-us', '/about', '/about-us')
_MAX_PAGES = 3
_MAX_CHARS_PER_PAGE = 4000
_FETCH_TIMEOUT = 8
_MAX_REDIRECTS = 4
_USER_AGENT = 'Mozilla/5.0 (compatible; SGCLeadResearchBot/1.0)'


def is_safe_public_url(url):
    """True iff ``url`` is http(s), has no embedded credentials, and every
    IP its host resolves to is public (not private/loopback/link-local/
    reserved/multicast). DNS-resolves the host so a hostname that merely
    *points at* an internal address (DNS rebinding / hostname trick) is
    caught too, unlike a plain string-prefix check on the hostname."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ('http', 'https'):
        return False
    host = (parsed.hostname or '').lower()
    if not host or parsed.username or parsed.password:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            return False
    return True


def _extract_text(html):
    """Visible-text extraction, tolerant of malformed markup. Never raises."""
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return ' '.join(text.split())
    except Exception:
        _logger.warning('website_scan: HTML text extraction failed', exc_info=True)
        return ''


def _fetch_one(url):
    """Fetch one URL, manually validating + following redirects (capped) so
    a redirect to an internal host can't be used to bypass the safety
    check. Returns ``(final_url, html_text)`` or ``None`` on any failure."""
    current = url
    for _hop in range(_MAX_REDIRECTS):
        if not is_safe_public_url(current):
            return None
        try:
            resp = requests.get(
                current, timeout=_FETCH_TIMEOUT, allow_redirects=False,
                headers={'User-Agent': _USER_AGENT},
            )
        except requests.exceptions.RequestException:
            return None
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get('Location')
            if not location:
                return None
            current = urljoin(current, location)
            continue
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get('Content-Type', '')
        if 'html' not in content_type and 'text/plain' not in content_type:
            return None
        return current, resp.text[:500000]
    return None


def scan_company_website(website_url):
    """Fetch home + likely contact/about pages from the lead's own company
    website and return normalized evidence dicts (same shape as
    ``lead_intelligence.normalize_evidence()``), tagged
    ``provider: 'website_scan'`` so the prompt can treat it as the most
    authoritative source for contact details. Returns ``[]`` for any blank,
    unsafe, or unreachable site — never raises."""
    base = (website_url or '').strip()
    if not base:
        return []
    if not base.startswith(('http://', 'https://')):
        base = 'https://' + base
    if not is_safe_public_url(base):
        return []

    evidence = []
    seen_urls = set()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    for path in _CONTACT_PATHS:
        if len(evidence) >= _MAX_PAGES:
            break
        candidate = base.rstrip('/') + path
        if candidate in seen_urls:
            continue
        seen_urls.add(candidate)
        result = _fetch_one(candidate)
        if not result:
            continue
        final_url, html = result
        text = _extract_text(html)
        if not text:
            continue
        label = path.strip('/').replace('-', ' ').title()
        evidence.append({
            'title': 'Company Website%s' % (' - %s' % label if label else ''),
            'url': final_url,
            'snippet': text[:_MAX_CHARS_PER_PAGE],
            'provider': 'website_scan',
            'retrieved_at': retrieved_at,
        })
    return evidence
