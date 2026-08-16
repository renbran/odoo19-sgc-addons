# -*- coding: utf-8 -*-
# Part of CRM Executive Dashboard. See LICENSE file for full copyright and licensing details.

"""
HTTP routes for the CRM Executive Dashboard.

Routes
------
* ``GET /crm-dashboard`` — main dashboard page (HTML, auth='user')
* ``GET /crm-dashboard/executive`` — alias for the main page (URL the
  user requested). Both render the same QWeb template.
* ``POST /crm-dashboard/data`` — JSON-RPC endpoint returning the
  full payload for a given filter. Used by the Owl component for
  live refresh without a full page reload.
* ``POST /crm-dashboard/refresh`` — invalidate the persistent cache
  (manager+ only). Returns ``{"status": "ok"}``.
* ``POST /crm-dashboard/export`` — generate and download a CSV,
  XLSX or PDF export of the current dashboard payload.

Error handling
--------------
All routes are wrapped so that *no* exception can leak to the user.
The dashboard's data endpoint returns a structured error envelope
``{"error": "message", "code": "..."}`` on failure. The HTML page
catches the failure and renders an error banner (via the QWeb
template's ``has_error`` flag) so the user sees a clean message
rather than a stack trace.
"""

import base64
import json
import logging

from odoo import http, _, tools
from odoo.http import request
from odoo.exceptions import AccessDenied, AccessError, UserError

_logger = logging.getLogger(__name__)


# Permission group XMLIDs. Resolved at request time so we don't bake
# the id into the module (which would break across DBs).
_GROUP_USER = 'crm_executive_dashboard.group_crm_dashboard_user'
_GROUP_MANAGER = 'crm_executive_dashboard.group_crm_dashboard_manager'
_GROUP_EXEC = 'crm_executive_dashboard.group_crm_dashboard_executive'


def _user_has_group(group_xmlid):
    """Return True if the current user belongs to the named group."""
    try:
        return request.env.user.has_group(group_xmlid)
    except Exception:
        return False


def _parse_filter(post=None, **kw):
    """Build the filter dict from request arguments.

    Accepts both POST form-encoded and JSON bodies. The result is a
    plain dict ready to hand to ``CrmDashboardKpi.collect_all()``.

    Defaults to ``{'period': 'last_30_days'}`` for anonymous or
    missing parameters — never raises.
    """
    if post is None:
        post = {}
    try:
        body = request.httprequest.get_data(as_text=True) or ''
    except Exception:
        body = ''
    if body and body.lstrip().startswith('{'):
        try:
            post = {**post, **json.loads(body)}
        except (ValueError, TypeError):
            pass

    raw = {**post, **kw}
    # Cast known fields
    filt = {'period': raw.get('period') or 'last_30_days'}
    for key in ('date_from', 'date_to'):
        if raw.get(key):
            filt[key] = raw[key]
    for key in ('user_id', 'team_id', 'source_id', 'stage_id', 'company_id'):
        v = raw.get(key)
        if v not in (None, '', '0', 'false', 'False'):
            try:
                filt[key] = int(v)
            except (TypeError, ValueError):
                pass
    return filt


def _envelope(payload, error=None, code=None):
    """Wrap the payload in a uniform response envelope.

    The frontend always checks ``ok`` before reading payload data.
    """
    if error is None:
        return {'ok': True, 'payload': payload}
    return {'ok': False, 'error': error, 'code': code or 'unknown'}


class CrmDashboardController(http.Controller):
    """HTTP endpoints for the executive CRM dashboard."""

    # ------------------------------------------------------------------
    # HTML pages
    # ------------------------------------------------------------------

    @http.route(
        ['/crm-dashboard', '/crm-dashboard/executive'],
        type='http',
        auth='user',
        website=True,
        readonly=True,
    )
    def dashboard_page(self, **kw):
        """Render the main dashboard page.

        The page is a QWeb template that bootstraps the Owl component.
        The component then fetches its data from the JSON endpoint
        below. This separation lets the page render instantly with a
        loading state, then animate in once data is ready.
        """
        # Access check
        if not _user_has_group(_GROUP_USER):
            return request.render(
                'http_routing.403',
                {'error': _('You need the CRM Dashboard User role to view this page.')},
                status=403,
            )

        values = {
            'page_name': 'crm_dashboard',
            'dashboard_title': _('CRM Executive Dashboard'),
            'dashboard_filter': _parse_filter(**kw),
            'has_error': False,
            'error_message': '',
        }
        try:
            # Render the shell — no data fetch here. The JS will call
            # /crm-dashboard/data on DOMContentLoaded.
            return request.render(
                'crm_executive_dashboard.dashboard_page',
                values,
            )
        except Exception as e:
            _logger.exception("CED: dashboard page render failed: %s", e)
            values['has_error'] = True
            values['error_message'] = str(e)
            # Best-effort: try a stripped-down error template
            try:
                return request.render(
                    'crm_executive_dashboard.dashboard_error',
                    values,
                    status=200,
                )
            except Exception:
                return request.make_response(
                    f'<html><body><h1>Dashboard error</h1><p>{values["error_message"]}</p></body></html>',
                    headers=[('Content-Type', 'text/html; charset=utf-8')],
                )

    # ------------------------------------------------------------------
    # JSON data endpoint
    # ------------------------------------------------------------------

    @http.route(
        '/crm-dashboard/data',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
        readonly=True,
        csrf=False,
    )
    def dashboard_data(self, filter=None, **kw):
        """Return the full dashboard payload for a given filter.

        Used by the Owl component to refresh the page on filter
        change. Returns ``{"ok": True, "payload": {...}}`` on success.
        """
        if not _user_has_group(_GROUP_USER):
            raise AccessDenied()

        try:
            # Service-layer import (lazy — avoids loading on every
            # request that doesn't hit the data endpoint).
            from odoo.addons.crm_executive_dashboard.services import (
                dashboard_cache, chart_data,
            )

            filt = _parse_filter(post=filter or {}, **kw)
            payload = dashboard_cache.get_or_compute(request.env, filt)

            # Post-process charts
            if isinstance(payload, dict) and 'charts' in payload:
                payload['charts'] = chart_data.process(payload['charts'])

            return _envelope(payload)
        except AccessDenied:
            raise
        except Exception as e:
            _logger.exception("CED: dashboard data failed: %s", e)
            return _envelope(None, error=str(e), code='compute_failed')

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    @http.route(
        '/crm-dashboard/refresh',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def dashboard_refresh(self, **kw):
        """Invalidate the persistent cache. Manager+ only."""
        if not _user_has_group(_GROUP_MANAGER):
            raise AccessDenied()
        try:
            from odoo.addons.crm_executive_dashboard.services import dashboard_cache
            dashboard_cache.invalidate(request.env)
            return _envelope({'invalidated': True})
        except Exception as e:
            _logger.exception("CED: refresh failed: %s", e)
            return _envelope(None, error=str(e), code='refresh_failed')

    # ------------------------------------------------------------------
    # Export endpoint (CSV / XLSX / PDF)
    # ------------------------------------------------------------------

    @http.route(
        '/crm-dashboard/export',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def dashboard_export(self, **kw):
        """Generate and stream a dashboard export.

        Accepts either a JSON body (the JS uses this) or form-encoded
        data. Required parameter: ``format`` in ``{'csv', 'xlsx', 'pdf'}``.
        Optional: ``filter`` (string or dict).
        """
        if not _user_has_group(_GROUP_USER):
            raise AccessDenied()

        # Parse the body — accept JSON and form-encoded
        try:
            body = request.httprequest.get_data(as_text=True) or ''
        except Exception:
            body = ''

        params = dict(kw)
        if body and body.lstrip().startswith('{'):
            try:
                params = {**params, **json.loads(body)}
            except (ValueError, TypeError):
                pass

        fmt = (params.get('format') or 'csv').lower()
        if fmt not in ('csv', 'xlsx', 'pdf'):
            fmt = 'csv'

        # ``filter`` may come as a JSON string or as a dict
        raw_filter = params.get('filter')
        if isinstance(raw_filter, str) and raw_filter:
            try:
                filt = json.loads(raw_filter)
            except (ValueError, TypeError):
                filt = {'period': raw_filter}
        elif isinstance(raw_filter, dict):
            filt = raw_filter
        else:
            filt = {}
        if not isinstance(filt, dict):
            filt = {}
        filt.setdefault('period', 'last_30_days')

        try:
            export = request.env['crm.dashboard.export'].sudo()
            result = export.action_generate(filt, fmt)

            if not result or not result.get('file_data'):
                raise UserError(_("Export produced no data."))

            # file_data is base64 (matches the Binary field on the wizard)
            b64 = result['file_data']
            try:
                content = base64.b64decode(b64)
            except Exception:
                content = b64.encode('utf-8') if isinstance(b64, str) else b64

            filename = result.get('filename') or f"crm_dashboard.{fmt}"
            content_type = result.get('file_type') or 'application/octet-stream'

            return request.make_response(
                content,
                headers=[
                    ('Content-Type', content_type),
                    ('Content-Disposition', f'attachment; filename="{filename}"'),
                    ('Content-Length', len(content)),
                    ('X-Content-Type-Options', 'nosniff'),
                ],
            )
        except AccessDenied:
            raise
        except Exception as e:
            _logger.exception("CED: export failed: %s", e)
            return request.make_response(
                json.dumps({'ok': False, 'error': str(e), 'code': 'export_failed'}),
                headers=[('Content-Type', 'application/json')],
                status=500,
            )

    # ------------------------------------------------------------------
    # Saved filters RPC (user+)
    # ------------------------------------------------------------------

    @http.route(
        '/crm-dashboard/filters',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def dashboard_filters(self, **kw):
        """List / create / update saved filters for the current user.

        Body params (JSON-RPC):
            ``op``     — 'list' | 'get_default' | 'create' | 'delete'
            ``name``    — for 'create'
            ``filter``  — dict for 'create'
            ``id``      — for 'delete'
            ``is_default`` — bool
        """
        if not _user_has_group(_GROUP_USER):
            raise AccessDenied()
        try:
            Filter = request.env['crm.dashboard.filter']
            # Read from request body to be safe with param shadowing
            try:
                body = request.httprequest.get_data(as_text=True) or ''
            except Exception:
                body = ''
            body_params = {}
            if body and body.lstrip().startswith('{'):
                try:
                    body_params = json.loads(body)
                except (ValueError, TypeError):
                    body_params = {}
            op = (body_params.get('op') or kw.get('op') or 'list').lower()
            name = body_params.get('name') or kw.get('name') or 'Saved filter'
            f = body_params.get('filter') or kw.get('filter') or {}
            rec_id = body_params.get('id') or kw.get('id') or 0
            is_default = bool(body_params.get('is_default') or kw.get('is_default'))

            if op == 'list':
                recs = Filter.search_for_user([])
                return _envelope([r.action_apply() for r in recs])
            if op == 'get_default':
                return _envelope(Filter.get_default_for_user())
            if op == 'create':
                rec = Filter.create_from_payload(
                    name=name,
                    filter_dict=f,
                    is_default=is_default,
                )
                return _envelope(rec.action_apply())
            if op == 'delete':
                rec = Filter.browse(int(rec_id))
                if not rec.exists():
                    return _envelope(None, error='Not found', code='not_found')
                rec.check_access('unlink')
                rec.unlink()
                return _envelope({'deleted': int(rec_id)})
            return _envelope(None, error=f'Unknown op: {op}', code='bad_op')
        except AccessDenied:
            raise
        except Exception as e:
            _logger.exception("CED: filters RPC failed: %s", e)
            return _envelope(None, error=str(e), code='filters_failed')

    # ------------------------------------------------------------------
    # Public health-check (no auth)
    # ------------------------------------------------------------------

    @http.route(
        '/crm-dashboard/health',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def dashboard_health(self, **kw):
        """Liveness check — returns 200 with a tiny JSON body.

        Useful for uptime monitoring and load balancer health checks.
        """
        try:
            body = json.dumps({
                'status': 'ok',
                'module': 'crm_executive_dashboard',
                'version': '19.0.1.0.0',
            })
            return request.make_response(
                body,
                headers=[('Content-Type', 'application/json')],
            )
        except Exception as e:
            return request.make_response(
                json.dumps({'status': 'error', 'error': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500,
            )
