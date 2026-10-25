# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .accounting_client import CLIENT_STATUSES


class ResPartner(models.Model):
    _inherit = "res.partner"

    accounting_client_ids = fields.One2many(
        "sgc.accounting.client",
        "partner_id",
        string="Accounting Workspaces",
    )
    accounting_client_id = fields.Many2one(
        "sgc.accounting.client",
        string="Accounting Workspace",
        compute="_compute_accounting_client",
        store=True,
    )
    accounting_status = fields.Selection(
        CLIENT_STATUSES,
        related="accounting_client_id.status",
        store=True,
        string="Accounting Status",
    )
    accounting_client_code = fields.Char(
        related="accounting_client_id.client_code",
        store=True,
        string="Accounting Client Code",
    )
    accounting_db_name = fields.Char(
        related="accounting_client_id.db_name",
        store=True,
        string="Accounting Database",
    )
    accounting_base_url = fields.Char(
        related="accounting_client_id.workspace_url",
        store=True,
        string="Accounting Workspace URL",
    )
    accounting_storage_root = fields.Char(
        related="accounting_client_id.storage_root",
        store=True,
        string="Accounting Storage Root",
    )
    accounting_context = fields.Json(
        string="Accounting Context",
        compute="_compute_accounting_context",
    )

    @api.depends("accounting_client_ids", "accounting_client_ids.active")
    def _compute_accounting_client(self):
        for partner in self:
            partner.accounting_client_id = partner.accounting_client_ids.filtered(
                lambda client: client.active
            )[:1]

    @api.depends(
        "accounting_client_id",
        "accounting_client_id.client_code",
        "accounting_client_id.name",
        "accounting_client_id.legal_name",
        "accounting_client_id.workspace_url",
        "accounting_client_id.db_name",
        "accounting_client_id.mcp_url",
        "accounting_client_id.storage_root",
        "accounting_client_id.assigned_agent",
        "accounting_client_id.auto_post_max_aed",
        "accounting_client_id.min_confidence",
        "accounting_client_id.require_trn",
        "accounting_client_id.company_ids",
        "accounting_client_id.company_ids.odoo_company_id",
        "accounting_client_id.company_ids.name",
        "accounting_client_id.company_ids.trn",
        "accounting_client_id.company_ids.is_default",
        "accounting_client_id.company_ids.active",
    )
    def _compute_accounting_context(self):
        for partner in self:
            client = partner.accounting_client_id
            if not client:
                partner.accounting_context = {}
                continue
            partner.accounting_context = {
                "client_code": client.client_code,
                "client_name": client.name,
                "legal_name": client.legal_name or client.name,
                "workspace_url": client.workspace_url or "",
                "db_name": client.db_name or "",
                "mcp_url": client.mcp_url or "",
                "storage_root": client.storage_root or "",
                "assigned_agent": client.assigned_agent or "",
                "thresholds": {
                    "auto_post_max_aed": client.auto_post_max_aed,
                    "min_confidence": client.min_confidence,
                    "require_trn": client.require_trn,
                },
                "companies": [
                    {
                        "odoo_company_id": company.odoo_company_id,
                        "name": company.name,
                        "trn": company.trn or "",
                        "is_default": company.is_default,
                        "active": company.active,
                    }
                    for company in client.company_ids
                ],
            }

    def action_open_accounting_client(self):
        self.ensure_one()
        if not self.accounting_client_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": self.accounting_client_id.name,
            "res_model": "sgc.accounting.client",
            "res_id": self.accounting_client_id.id,
            "view_mode": "form",
            "target": "current",
        }
