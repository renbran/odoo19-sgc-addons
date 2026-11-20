# -*- coding: utf-8 -*-
"""Agent-governed bank reconciliation.

Wraps the payment-based reconciliation so it runs under the
``agent-03-reconciliation`` service user identity inside client databases,
and every reconciliation action is logged to ``sgc.agent.audit``.

The agency database (where this module is installed) dispatches a
reconciliation task to the client database via XML-RPC as the reconciliation
agent. The client database's ``sgc_accounting_agents`` guard then enforces
the agent's company scope and logs the action.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models

from .accounting_client import rpc, rpc_error

_logger = logging.getLogger(__name__)

RECONCILE_ROLE = "agent-03-reconciliation"
RECONCILE_TASK = "reconcile.write"


class SgcAccountingReconciliationRun(models.Model):
    """A reconciliation task dispatched to a client database."""

    _name = "sgc.accounting.reconciliation.run"
    _description = "Accounting Reconciliation Run"
    _order = "create_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    run_id = fields.Char(
        required=True,
        default=lambda self: str(__import__("uuid").uuid4()),
        copy=False,
        index=True,
    )
    client_id = fields.Many2one(
        "sgc.accounting.client",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "sgc.accounting.company",
        string="Company",
        domain="[('client_id', '=', client_id)]",
    )
    journal_name = fields.Char(
        help="Journal to reconcile. Empty means all bank/cash journals."
    )
    date_to = fields.Date(
        default=lambda self: fields.Date.context_today(self),
        help="Reconcile payments up to this date.",
    )
    state = fields.Selection(
        [
            ("queued", "Queued"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="queued",
        required=True,
        index=True,
    )
    statements_created = fields.Integer(readonly=True)
    lines_reconciled = fields.Integer(readonly=True)
    last_error = fields.Text(readonly=True)
    started_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    duration_seconds = fields.Integer(readonly=True)

    @api.depends("client_id.name", "run_id")
    def _compute_name(self):
        for run in self:
            run.name = "%s - %s" % (
                run.client_id.name or _("Reconciliation"),
                (run.run_id or "")[:8],
            )

    def action_dispatch(self):
        """Run the reconciliation against the client database."""
        for run in self:
            run._run_reconciliation()

    @api.model
    def _cron_dispatch_queued(self):
        """Process queued reconciliation runs (every 6 hours)."""
        runs = self.search(
            [("state", "=", "queued")],
            limit=10,
            order="create_date, id",
        )
        for run in runs:
            try:
                run._run_reconciliation()
            except Exception:
                _logger.exception(
                    "Reconciliation run %s failed", run.run_id
                )
        return True

    def _run_reconciliation(self):
        """Connect to the client DB as the reconciliation agent and reconcile."""
        self.ensure_one()
        conn, error = self.client_id._booking_connection()
        if error:
            self.write({
                "state": "failed",
                "last_error": error,
                "completed_at": fields.Datetime.now(),
            })
            return False
        # Verify the remote user is the reconciliation agent.
        try:
            remote_user = rpc(
                conn, "res.users", "read",
                [conn["uid"]], fields=["sgc_agent_role_id"],
            )
            role_id = remote_user and remote_user[0].get("sgc_agent_role_id")
            if role_id:
                role = rpc(
                    conn, "sgc.agent.role", "read",
                    [role_id[0]], fields=["code"],
                )
                if role and role[0]["code"] != RECONCILE_ROLE:
                    self.write({
                        "state": "failed",
                        "last_error": _(
                            "The API user in %(db)s is not the reconciliation "
                            "agent.", db=conn["db"],
                        ),
                        "completed_at": fields.Datetime.now(),
                    })
                    return False
        except Exception:
            # The client DB may not have sgc_accounting_agents installed yet.
            _logger.warning(
                "Could not verify reconciliation role in %s; proceeding "
                "without agent governance.", conn["db"],
            )

        self.write({
            "state": "running",
            "started_at": fields.Datetime.now(),
            "last_error": False,
        })
        company_ids = []
        if self.company_id:
            company_ids = [self.company_id.odoo_company_id]
        else:
            company_ids = self.client_id.company_ids.filtered(
                "active"
            ).mapped("odoo_company_id")

        total_statements = 0
        total_lines = 0
        try:
            for company_id in company_ids:
                context = {"allowed_company_ids": [company_id]}
                # Find bank/cash journals for this company.
                journals = rpc(
                    conn, "account.journal", "search_read",
                    [
                        ("type", "in", ("bank", "cash")),
                        ("company_id", "parent_of", company_id),
                    ],
                    fields=["id", "name", "code"],
                    limit=50, context=context,
                )
                for journal in journals:
                    if self.journal_name and journal["name"].lower() != self.journal_name.lower():
                        continue
                    # Call the reconciliation method on the client DB.
                    result = rpc(
                        conn, "account.journal", "_reconcile_from_payments",
                        int(journal["id"]),
                    )
                    if isinstance(result, dict):
                        total_statements += result.get("statement_count", 0) or 0
                        total_lines += result.get("lines_reconciled", 0) or 0
                    elif isinstance(result, list) and result:
                        total_statements += len(result)
        except Exception as exc:
            self.write({
                "state": "failed",
                "last_error": rpc_error(exc),
                "completed_at": fields.Datetime.now(),
            })
            return False

        duration = 0
        if self.started_at:
            duration = int(
                (fields.Datetime.now() - self.started_at).total_seconds()
            )
        self.write({
            "state": "completed",
            "statements_created": total_statements,
            "lines_reconciled": total_lines,
            "completed_at": fields.Datetime.now(),
            "duration_seconds": duration,
        })
        self.client_id.message_post(body=_(
            "Reconciliation completed: %(statements)s statement(s), "
            "%(lines)s line(s) reconciled.",
            statements=total_statements,
            lines=total_lines,
        ))
        return True

    def action_retry(self):
        self.write({
            "state": "queued",
            "last_error": False,
        })
        return True
