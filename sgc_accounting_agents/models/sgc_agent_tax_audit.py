# -*- coding: utf-8 -*-
"""UAE VAT and Corporate Tax audit agent.

Implements the ``audit.read`` and ``audit.write`` task codes for the
``agent-04-tax-audit`` role. The agent reads posted journal entries and
tax lines, validates the VAT output/input grid, checks filing readiness,
and records findings as ``sgc.agent.report`` records with an audit trail.

This module runs inside the **client database** (where ``sgc_accounting_agents``
is installed), not the agency database.
"""
import logging
from datetime import date, timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

TASK_AUDIT_READ = "audit.read"
TASK_AUDIT_WRITE = "audit.write"
TASK_REPORT_BUILD = "report.build"

VAT_RATE_AE = 5.0


class SgcAgentTaxAudit(models.Model):
    """A VAT or corporate tax audit run."""

    _name = "sgc.agent.tax.audit"
    _description = "Agent Tax Audit Run"
    _order = "create_date desc, id desc"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, default=lambda self: _("Tax Audit"))
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
    )
    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)
    audit_type = fields.Selection(
        [
            ("vat", "VAT Return Audit"),
            ("corporate_tax", "Corporate Tax Provision"),
            ("filing_readiness", "Filing Readiness Check"),
        ],
        default="vat",
        required=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    started_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)

    # VAT grid findings
    output_vat_total = fields.Float(
        string="Output VAT (AED)", readonly=True,
        help="Total VAT charged on sales (tax lines on out_invoice/out_refund).",
    )
    input_vat_total = fields.Float(
        string="Input VAT (AED)", readonly=True,
        help="Total VAT paid on purchases (tax lines on in_invoice/in_refund).",
    )
    net_vat_payable = fields.Float(
        string="Net VAT Payable (AED)", readonly=True,
        help="Output VAT minus Input VAT. Positive means payable.",
    )
    transactions_audited = fields.Integer(readonly=True)
    exceptions_found = fields.Integer(readonly=True)

    findings = fields.Json(
        readonly=True,
        help="Structured findings: mismatches, missing taxes, rate anomalies.",
    )
    report_id = fields.Many2one(
        "sgc.agent.report", string="Agent Report", readonly=True,
    )
    last_error = fields.Text(readonly=True)

    def action_run_audit(self):
        """Run the tax audit for the selected period."""
        for audit in self:
            audit._run_vat_audit()

    @api.model
    def _cron_run_scheduled_audits(self):
        """Run a VAT audit for the previous quarter for every company that
        has a tax-audit agent assigned (monthly cron)."""
        today = fields.Date.context_today(self)
        # Previous quarter end
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        if today.month <= 3:
            prev_quarter_year = today.year - 1
            prev_quarter_start = date(prev_quarter_year, 10, 1)
            prev_quarter_end = date(prev_quarter_year, 12, 31)
        elif today.month <= 6:
            prev_quarter_start = date(today.year, 1, 1)
            prev_quarter_end = date(today.year, 3, 31)
        elif today.month <= 9:
            prev_quarter_start = date(today.year, 4, 1)
            prev_quarter_end = date(today.year, 6, 30)
        else:
            prev_quarter_start = date(today.year, 7, 1)
            prev_quarter_end = date(today.year, 9, 30)
        companies = self.env["res.company"].search([])
        for company in companies:
            existing = self.search([
                ("company_id", "=", company.id),
                ("period_start", "=", prev_quarter_start),
                ("period_end", "=", prev_quarter_end),
                ("audit_type", "=", "vat"),
            ])
            if existing:
                continue
            audit = self.create({
                "name": _("VAT Audit Q%(q)s %(year)s - %(company)s") % {
                    "q": (prev_quarter_start.month - 1) // 3 + 1,
                    "year": prev_quarter_start.year,
                    "company": company.name,
                },
                "company_id": company.id,
                "period_start": prev_quarter_start,
                "period_end": prev_quarter_end,
                "audit_type": "vat",
                "state": "draft",
            })
            try:
                audit.with_company(company)._run_vat_audit()
            except Exception:
                _logger.exception(
                    "VAT audit failed for company %s", company.name
                )

    def _run_vat_audit(self):
        """Validate the VAT grid for the audit period."""
        self.ensure_one()
        role = getattr(self.env.user, "sgc_agent_role_id", False)
        if role and not role.allows(TASK_AUDIT_READ):
            raise ValueError(
                _("Role %s is not authorised to perform tax audits.") % role.code
            )
        self.write({"state": "running", "started_at": fields.Datetime.now()})
        try:
            findings = self._collect_vat_findings()
            output_vat = findings["totals"]["output_vat"]
            input_vat = findings["totals"]["input_vat"]
            net_payable = output_vat - input_vat
            exceptions = len(findings.get("exceptions", []))
            self.write({
                "state": "completed",
                "completed_at": fields.Datetime.now(),
                "output_vat_total": round(output_vat, 2),
                "input_vat_total": round(input_vat, 2),
                "net_vat_payable": round(net_payable, 2),
                "transactions_audited": findings["totals"]["transactions"],
                "exceptions_found": exceptions,
                "findings": findings,
            })
            # Write the agent report.
            report_vals = {
                "name": self.name,
                "company_id": self.company_id.id,
                "period_start": self.period_start,
                "period_end": self.period_end,
                "payload": findings,
                "note": _(
                    "VAT audit: output %(output)s, input %(input)s, "
                    "net payable %(net)s, %(exc)s exception(s)."
                ) % {
                    "output": round(output_vat, 2),
                    "input": round(input_vat, 2),
                    "net": round(net_payable, 2),
                    "exc": exceptions,
                },
            }
            if role:
                report_vals["role_id"] = role.id
            report = self.env["sgc.agent.report"].sudo().create(report_vals)
            self.write({"report_id": report.id})
            # Log to audit trail.
            if role:
                self.env["sgc.agent.audit"].sudo().log(
                    TASK_AUDIT_WRITE,
                    self._name,
                    res_ids=[self.id],
                    details={
                        "role": role.code,
                        "output_vat": round(output_vat, 2),
                        "input_vat": round(input_vat, 2),
                        "net_payable": round(net_payable, 2),
                        "exceptions": exceptions,
                    },
                )
        except Exception as exc:
            self.write({
                "state": "failed",
                "completed_at": fields.Datetime.now(),
                "last_error": str(exc)[:2000],
            })
            raise

    def _collect_vat_findings(self):
        """Read posted tax lines for the period and validate the VAT grid."""
        self.ensure_one()
        domain = [
            ("date", ">=", self.period_start),
            ("date", "<=", self.period_end),
            ("parent_state", "=", "posted"),
            ("tax_ids", "!=", False),
            ("company_id", "=", self.company_id.id),
        ]
        lines = self.env["account.move.line"].search(domain)
        output_vat = 0.0
        input_vat = 0.0
        transactions = set()
        exceptions = []
        for line in lines:
            transactions.add(line.move_id.id)
            move = line.move_id
            is_sale = move.move_type in ("out_invoice", "out_refund")
            is_purchase = move.move_type in ("in_invoice", "in_refund")
            # Read the actual tax amounts from the tax detail lines. The
            # repartition lines are not consulted: Odoo 19 renamed the link
            # field on account.tax.repartition.line, and the amounts are
            # carried by the tax_lines on the move itself.
            tax_detail_lines = self.env["account.move.line"].search([
                ("move_id", "=", move.id),
                ("tax_line_id", "!=", False),
                ("company_id", "=", self.company_id.id),
            ])
            for tax_line in tax_detail_lines:
                tax = tax_line.tax_line_id
                if not tax or tax.amount_type != "percent":
                    continue
                rate = tax.amount
                if abs(rate - VAT_RATE_AE) > 0.01:
                    exceptions.append({
                        "type": "unexpected_rate",
                        "move": move.name,
                        "tax": tax.name,
                        "rate": rate,
                        "expected": VAT_RATE_AE,
                        "message": _(
                            "Tax %(tax)s on %(move)s has rate %(rate)s%%, "
                            "expected %(expected)s%%."
                        ) % {
                            "tax": tax.name, "move": move.name,
                            "rate": rate, "expected": VAT_RATE_AE,
                        },
                    })
                amount = abs(tax_line.balance or 0.0)
                if tax.type_tax_use == "sale":
                    output_vat += amount
                elif tax.type_tax_use == "purchase":
                    input_vat += amount
            # Check for moves without tax that should have VAT.
            if is_sale and not tax_detail_lines:
                if move.amount_untaxed and abs(move.amount_untaxed) > 0.01:
                    expected_vat = abs(move.amount_untaxed) * VAT_RATE_AE / 100.0
                    if expected_vat > 1.0:
                        exceptions.append({
                            "type": "missing_output_vat",
                            "move": move.name,
                            "amount": round(move.amount_untaxed, 2),
                            "expected_vat": round(expected_vat, 2),
                            "message": _(
                                "Sales entry %(move)s for %(amount)s has no "
                                "output VAT; expected ~%(vat)s."
                            ) % {
                                "move": move.name,
                                "amount": round(move.amount_untaxed, 2),
                                "vat": round(expected_vat, 2),
                            },
                        })
        return {
            "totals": {
                "output_vat": output_vat,
                "input_vat": input_vat,
                "transactions": len(transactions),
            },
            "exceptions": exceptions,
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "company": self.company_id.name,
        }
