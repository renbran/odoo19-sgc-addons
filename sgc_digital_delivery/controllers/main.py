# -*- coding: utf-8 -*-
"""Controllers for SGC Digital Product Delivery.

Routes:
  GET /shop/digital/download   — Secure file download (public, token-guarded)
  GET /my/downloads            — Portal page: all digital purchases (auth=user)

Security (download endpoint):
  - access_token is compared with constant-time consteq() — no timing attacks.
  - Order must be in state 'sale' or 'done' (payment confirmed).
  - product_id must be a digital line on that exact order.
  - Response headers prevent caching and content-type sniffing.
  - No file bytes are ever exposed without passing all checks.
"""
import base64
import logging
import re

from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.wrappers import Response

from odoo import http
from odoo.http import request
from odoo.tools.misc import consteq

_logger = logging.getLogger(__name__)

# Allowed characters in download filenames sent to the browser
_SAFE_FILENAME_RE = re.compile(r'[^\w.\-]')


def _sanitize_filename(name: str) -> str:
    """Return a browser-safe filename (no path traversal, no special chars)."""
    name = (name or 'download.zip').strip()
    # Remove any directory components
    name = name.replace('\\', '/').split('/')[-1]
    # Replace unsafe characters with underscores
    name = _SAFE_FILENAME_RE.sub('_', name)
    return name or 'download.zip'


class SGCDigitalDownloadController(http.Controller):

    @http.route(
        '/shop/digital/download',
        type='http',
        auth='public',
        website=True,
        csrf=False,          # GET request — CSRF not applicable
        sitemap=False,       # Never index this endpoint
    )
    def digital_download(self, order_id=None, access_token=None, product_id=None, **kwargs):
        """Serve a digital product file to an authenticated buyer.

        The access_token is the sale order's portal access token (from portal.mixin).
        This endpoint is the ONLY way buyers can access digital files — direct
        ir.attachment URLs are blocked for portal/public users via ir.rule.
        """
        # ── 1. Input validation ───────────────────────────────────────────────
        if not all([order_id, access_token, product_id]):
            _logger.warning('SGC Digital download: missing parameters.')
            raise Forbidden()

        try:
            order_id = int(order_id)
            product_id = int(product_id)
        except (ValueError, TypeError):
            _logger.warning('SGC Digital download: non-integer id parameters.')
            raise Forbidden()

        # Reject non-positive IDs (prevent browsing id=0 or negative)
        if order_id <= 0 or product_id <= 0:
            _logger.warning('SGC Digital download: non-positive id parameters.')
            raise Forbidden()

        # Cap token length to prevent memory / ReDoS attacks on consteq
        if len(str(access_token)) > 256:
            _logger.warning('SGC Digital download: access_token exceeds max length.')
            raise Forbidden()

        # ── 2. Load order with sudo (token validates identity) ────────────────
        order = request.env['sale.order'].sudo().browse(order_id)
        if not order.exists():
            raise NotFound()

        # ── 3. Constant-time token comparison ─────────────────────────────────
        order_token = order.access_token or ''
        if not order_token or not consteq(order_token, str(access_token)):
            _logger.warning(
                'SGC Digital download: invalid access_token for order %s.', order_id
            )
            raise Forbidden()

        # ── 4. Order must be confirmed / done ─────────────────────────────────
        if order.state not in ('sale', 'done'):
            _logger.warning(
                'SGC Digital download: order %s is in state "%s", not confirmed.',
                order.name, order.state,
            )
            raise Forbidden()

        # ── 5. Find the digital product in this specific order ────────────────
        product_tmpl = None
        for line in order.order_line:
            if (
                line.product_id.id == product_id
                and line.product_id.is_digital
                and line.product_id.product_tmpl_id.digital_file
            ):
                product_tmpl = line.product_id.product_tmpl_id
                break

        if not product_tmpl:
            _logger.warning(
                'SGC Digital download: product %s not found as digital line on order %s.',
                product_id, order.name,
            )
            raise NotFound()

        # ── 6. Thread-safe download count increment ───────────────────────────
        request.env.cr.execute(
            "UPDATE product_template "
            "SET digital_download_count = digital_download_count + 1 "
            "WHERE id = %s",
            [product_tmpl.id],
        )

        # ── 7. Decode and stream the file ─────────────────────────────────────
        try:
            file_bytes = base64.b64decode(product_tmpl.digital_file)
        except Exception:
            _logger.exception(
                'SGC Digital download: failed to decode binary for product %s.',
                product_tmpl.id,
            )
            raise NotFound()

        filename = _sanitize_filename(product_tmpl.digital_filename)
        _logger.info(
            'SGC Digital: file "%s" downloaded by order %s (%s)',
            filename, order.name, order.partner_id.email,
        )

        return Response(
            file_bytes,
            status=200,
            headers=[
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(file_bytes))),
                ('X-Content-Type-Options', 'nosniff'),
                ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
                ('Pragma', 'no-cache'),
            ],
        )


class SGCDigitalPortalController(http.Controller):

    @http.route(
        '/my/downloads',
        type='http',
        auth='user',
        website=True,
    )
    def portal_downloads(self, **kwargs):
        """Portal page: list all digital products the logged-in user has purchased.

        Shows every confirmed sale order that contains at least one digital
        product, grouped by order.  Each row has a "Download" button that hits
        the secure /shop/digital/download endpoint.
        """
        partner = request.env.user.partner_id

        # Include orders belonging to any contact under the partner (child_of)
        orders = request.env['sale.order'].sudo().search([
            ('partner_id', 'child_of', partner.commercial_partner_id.id),
            ('state', 'in', ('sale', 'done')),
        ], order='date_order desc')

        digital_orders = []
        for order in orders:
            digital_lines = order._get_digital_lines()
            if not digital_lines:
                continue
            items = []
            for line in digital_lines:
                tmpl = line.product_id.product_tmpl_id
                items.append({
                    'product_name': line.product_id.name,
                    'filename': tmpl.digital_filename or 'download.zip',
                    'download_url': (
                        '/shop/digital/download'
                        f'?order_id={order.id}'
                        f'&access_token={order.access_token}'
                        f'&product_id={line.product_id.id}'
                    ),
                })
            digital_orders.append({
                'order': order,
                'items': items,
            })

        return request.render(
            'sgc_digital_delivery.portal_my_downloads',
            {
                'digital_orders': digital_orders,
                'page_name': 'downloads',
            },
        )
