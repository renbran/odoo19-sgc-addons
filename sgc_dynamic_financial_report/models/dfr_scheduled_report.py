# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

# ── Shared selections ────────────────────────────────────────────────────
REPORT_TYPE_SELECTION = [
    ("balance_sheet", "Balance Sheet"),
    ("profit_loss", "Profit & Loss"),
    ("cash_flow", "Cash Flow Statement"),
    ("trial_balance", "Trial Balance"),
    ("general_ledger", "General Ledger"),
    ("partner_ledger", "Partner Ledger"),
    ("aged_receivable", "Aged Receivable"),
    ("aged_payable", "Aged Payable"),
    ("tax_report", "Tax Report"),
]

TARGET_MOVE_SELECTION = [
    ("posted", "All Posted Entries"),
    ("all", "All Entries"),
    ("draft", "Draft Entries Only"),
]

# Map our friendly `interval_type` selection onto the (interval_number,
# interval_type) pair that ``ir.cron`` expects. ``ir.cron.interval_type`` is a
# stored selection on the core model and accepts these exact values.
INTERVAL_TYPE_TO_CRON = {
    "daily": (1, "days"),
    "weekly": (1, "weeks"),
    "monthly": (1, "months"),
    "quarterly": (3, "months"),
    "yearly": (1, "years"),
}


class SgcDfrScheduledReport(models.Model):
    """Definition of a SGC Dynamic Financial Report that runs on a cron.

    Each record owns one ``ir.cron`` that periodically invokes
    :meth:`_run`. The method instantiates a transient wizard with the saved
    parameters, runs the engine, writes an audit-log row, and (optionally)
    emails the rendered HTML to the configured recipients.

    Schedules can be deactivated (``active=False``) without removing the
    cron record - this is useful for pausing rather than deleting.
    """

    _name = "sgc.dfr.scheduled.report"
    _description = "SGC DFR Scheduled Report"
    _order = "name, id"
    _rec_name = "name"
    _inherit = ["mail.thread"]

    # ── Identification ────────────────────────────────────────────────
    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
        help="Human-readable label for this scheduled report.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        tracking=True,
        help="Inactive schedules keep their cron record but do not "
             "produce reports until re-activated.",
    )

    # ── Report parameters ─────────────────────────────────────────────
    report_type = fields.Selection(
        selection=REPORT_TYPE_SELECTION,
        string="Report Type",
        required=True,
        default="balance_sheet",
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    date_from = fields.Date(
        string="Start Date",
        required=True,
    )
    date_to = fields.Date(
        string="End Date",
        required=True,
    )
    enable_comparison = fields.Boolean(
        string="Enable Comparison",
        default=False,
    )
    target_move = fields.Selection(
        selection=TARGET_MOVE_SELECTION,
        string="Target Moves",
        default="posted",
        required=True,
    )

    account_ids = fields.Many2many(
        comodel_name="account.account",
        relation="sgc_dfr_scheduled_account_rel",
        string="Accounts",
    )
    partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="sgc_dfr_scheduled_partner_rel",
        string="Partners",
    )
    analytic_account_ids = fields.Many2many(
        comodel_name="account.analytic.account",
        relation="sgc_dfr_scheduled_analytic_rel",
        string="Analytic Accounts",
    )
    journal_ids = fields.Many2many(
        comodel_name="account.journal",
        relation="sgc_dfr_scheduled_journal_rel",
        string="Journals",
        domain="[('company_id', '=', company_id)]",
    )

    # ── Display flags ─────────────────────────────────────────────────
    show_hierarchy = fields.Boolean(
        string="Show Account Hierarchy",
        default=True,
    )
    show_zero_balance = fields.Boolean(
        string="Show Zero Balance Accounts",
        default=False,
    )
    hide_parent_hierarchy = fields.Boolean(
        string="Hide Parent Hierarchy",
        default=False,
    )

    # ── Schedule ──────────────────────────────────────────────────────
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Run As User",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        help="User under whose permissions the report will be generated. "
             "Pick a user with read access to all the companies / "
             "accounts that the report spans.",
    )
    cron_id = fields.Many2one(
        comodel_name="ir.cron",
        string="Scheduled Action",
        readonly=True,
        ondelete="set null",
        copy=False,
        help="Backing ``ir.cron`` record. Created automatically when the "
             "schedule is saved; deleted when the schedule is unlinked.",
    )
    interval_type = fields.Selection(
        selection=[
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("yearly", "Yearly"),
        ],
        string="Run Every",
        default="monthly",
        required=True,
        tracking=True,
    )
    next_run = fields.Date(
        string="Next Run",
        help="Date on which the schedule will next produce a report. "
             "Defaults to today on creation.",
    )
    last_run = fields.Datetime(
        string="Last Run",
        readonly=True,
        help="Last time the schedule was actually executed by the cron "
             "worker.",
    )

    # ── Email delivery ────────────────────────────────────────────────
    mail_template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Email Template",
        help="Template used to email the rendered report. The template "
             "must be a regular mail.template (model ``sgc.dfr.scheduled.report`` "
             "or compatible). When unset, no email is sent.",
    )
    recipient_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="sgc_dfr_scheduled_recipient_rel",
        string="Recipients",
        help="Partners that will receive a copy of each generated report "
             "via the configured mail template.",
    )

    # ── Constraints ──────────────────────────────────────────────────
    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(
                    _("The start date must be earlier than or equal to the end date.")
                )

    # ── CRUD hooks: keep the cron in sync with the schedule ───────────
    @api.model_create_multi
    def create(self, vals_list):
        schedules = super().create(vals_list)
        for schedule in schedules:
            schedule._create_cron()
        return schedules

    def write(self, vals):
        result = super().write(vals)
        # Anything that affects scheduling or report content forces a
        # cron refresh. ``_create_cron`` is idempotent.
        if any(
            f in vals
            for f in (
                "name", "active", "interval_type", "next_run",
                "user_id", "report_type", "company_id",
                "date_from", "date_to",
            )
        ):
            self._create_cron()
        return result

    def unlink(self):
        # Remove the backing cron records first so we never leave orphans
        # referencing a deleted schedule.
        crons = self.mapped("cron_id")
        result = super().unlink()
        if crons:
            crons.unlink()
        return result

    # ── Cron management ───────────────────────────────────────────────
    def _create_cron(self):
        """Create or update the ``ir.cron`` record for each schedule.

        Idempotent: safe to call multiple times; existing crons are
        updated in place rather than duplicated.
        """
        Cron = self.env["ir.cron"]
        for schedule in self:
            interval_number, interval_type = INTERVAL_TYPE_TO_CRON.get(
                schedule.interval_type, (1, "days")
            )
            next_call = fields.Datetime.to_datetime(schedule.next_run) \
                if schedule.next_run else fields.Datetime.now()
            # ``ir.cron`` expects a literal Python expression in `code`
            # that runs inside an env whose ``model`` is set. Calling
            # ``_run_on_cron`` with the schedule id keeps the entrypoint
            # name short and avoids leaking user code into cron's global
            # namespace.
            cron_vals = {
                "name": "SGC DFR: %s" % schedule.name,
                "model_id": self.env["ir.model"]._get_id(
                    schedule._name
                ),
                "state": "code",
                "code": (
                    "model.browse(%d)._run_on_cron()" % schedule.id
                ),
                "user_id": schedule.user_id.id,
                "interval_number": interval_number,
                "interval_type": interval_type,
                "nextcall": next_call,
                "active": bool(schedule.active),
                "priority": 5,
            }
            if schedule.cron_id:
                schedule.cron_id.write(cron_vals)
            else:
                cron = Cron.create(cron_vals)
                schedule.with_context(skip_cron_sync=True).write(
                    {"cron_id": cron.id}
                )
        return True

    # ── Entry point invoked by ir.cron ────────────────────────────────
    def _run_on_cron(self):
        """Run the schedule from the cron worker.

        Catches and logs exceptions so a single failing schedule does
        not block the cron worker; the row's ``last_run`` is only updated
        on success.
        """
        self.ensure_one()
        try:
            self._run()
            self.write({"last_run": fields.Datetime.now()})
        except Exception as exc:  # noqa: BLE001 - top-level guard for cron
            _logger.exception(
                "SGC DFR scheduled report '%s' failed: %s",
                self.name, exc,
            )
            # Re-raise so ``ir.cron`` records the failure and (depending
            # on its policy) retries.
            raise

    # ── Core: actually generate + email ───────────────────────────────
    def _run(self):
        """Generate the report for ``self`` and dispatch emails.

        Returns the newly-created :class:`sgc.dfr.report.log` record.
        """
        self.ensure_one()
        Wizard = self.env["sgc.financial.report.wizard"]
        Log = self.env["sgc.dfr.report.log"]

        wizard = Wizard.create(self._wizard_vals())
        try:
            engine = self.env["sgc.financial.report.engine"].with_context(
                wizard_id=wizard.id,
            )
            result = engine._generate_report(wizard)
            wizard.write({
                "result_html": result.get("html", ""),
                "state": "computed",
            })
            log = Log.create_from_wizard(
                wizard, result,
                source="scheduled",
                scheduled_report=self,
            )
        finally:
            # Transient wizard: discard immediately so it does not pile
            # up in transient tables.
            wizard.unlink()

        if self.mail_template_id and self.recipient_ids:
            self._send_report_email(log)
        return log

    # ── UI button: run once without scheduling ────────────────────────
    def action_preview(self):
        """Run the schedule a single time from the form view.

        Returns an action that shows the resulting audit log row so the
        user can immediately inspect the output.
        """
        self.ensure_one()
        log = self._run()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sgc.dfr.report.log",
            "res_id": log.id,
            "view_mode": "form",
            "target": "current",
        }

    # ── Email dispatch ────────────────────────────────────────────────
    def _send_report_email(self, log):
        """Send the rendered report to ``self.recipient_ids``.

        Uses the configured ``mail.template`` if any, otherwise falls
        back to a plain ``mail.mail`` record with the audit summary.
        """
        self.ensure_one()
        recipients = self.recipient_ids
        if not recipients:
            return False

        partner_to_email = {
            p.id: p.email_normalized or p.email for p in recipients
        }
        emails = [e for e in partner_to_email.values() if e]
        if not emails:
            _logger.warning(
                "SGC DFR schedule '%s' has recipients without email; "
                "skipping notification.", self.name,
            )
            return False

        subject = _("SGC Dynamic Financial Report: %s") % self.name
        body_html = (
            "<p>%s</p>"
            "<p><strong>Period:</strong> %s &mdash; %s</p>"
            "<p><strong>Generated:</strong> %s</p>"
            "<hr/>%s"
        ) % (
            _("Please find below the scheduled financial report."),
            fields.Date.to_string(self.date_from),
            fields.Date.to_string(self.date_to),
            fields.Datetime.to_string(log.generated_at),
            log.result_summary or "",
        )

        # ``mail.template`` (when configured) takes precedence; the
        # template is responsible for its own body and subject.
        if self.mail_template_id:
            # mail.template.send_mail returns the newly-created mail.mail id
            self.mail_template_id.send_mail(
                self.id,
                force_send=True,
                email_values={
                    "recipient_ids": [
                        (4, p.id) for p in recipients if p.id
                    ],
                    "subject": subject,
                    "body_html": body_html,
                },
            )
        else:
            mail = self.env["mail.mail"].create({
                "subject": subject,
                "body_html": body_html,
                "recipient_ids": [(4, p.id) for p in recipients if p.id],
                "auto_delete": True,
            })
            mail.send()
        return True

    # ── Wizard value builder ──────────────────────────────────────────
    def _wizard_vals(self):
        """Return a vals dict suitable for ``sgc.financial.report.wizard.create``."""
        self.ensure_one()
        return {
            "report_type": self.report_type,
            "company_id": self.company_id.id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "enable_comparison": self.enable_comparison,
            "target_move": self.target_move,
            "show_hierarchy": self.show_hierarchy,
            "show_zero_balance": self.show_zero_balance,
            "hide_parent_hierarchy": self.hide_parent_hierarchy,
            "account_ids": [(6, 0, self.account_ids.ids)],
            "partner_ids": [(6, 0, self.partner_ids.ids)],
            "analytic_account_ids": [(6, 0, self.analytic_account_ids.ids)],
            "journal_ids": [(6, 0, self.journal_ids.ids)],
        }