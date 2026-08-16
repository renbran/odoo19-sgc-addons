# -*- coding: utf-8 -*-
"""Manager review workflow.

Notification content rules (spec section: review alert content):

INCLUDED - gate name, employee name, due date, days remaining, the
requirement list with target / current value / met-or-not, the overall
score, and a link to the review record.

EXCLUDED - customer names, deal names, invoice numbers, payment references,
journal entries, salary or contract data, and any accounting identifier.
Monetary requirement values are shown as aggregate totals only, which is the
same figure the CES user already sees in their own banner.

No email is sent unless ``sgc_ces_kpi_banner.review_email_enabled`` is
explicitly turned on; by default the reviewer receives an ``mail.activity``
plus an Odoo inbox notification.
"""
import logging

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SgcCesGateReview(models.Model):
    _name = "sgc.ces.gate.review"
    _description = "SGC CES Gate Review"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "alert_scheduled_date desc, id desc"

    name = fields.Char(required=True, readonly=True)
    instance_id = fields.Many2one(
        "sgc.ces.gate.instance", required=True, ondelete="cascade", index=True, readonly=True
    )
    employee_id = fields.Many2one(
        "hr.employee", related="instance_id.employee_id", store=True, index=True
    )
    user_id = fields.Many2one("res.users", related="instance_id.user_id", store=True, index=True)
    reviewer_user_id = fields.Many2one("res.users", index=True, tracking=True, string="Reviewer")
    company_id = fields.Many2one(
        "res.company", related="instance_id.company_id", store=True, index=True
    )

    alert_type = fields.Selection(
        [
            ("due_soon", "Due soon"),
            ("overdue", "Overdue"),
            ("manual", "Manual"),
        ],
        required=True,
        readonly=True,
        index=True,
    )
    alert_scheduled_date = fields.Date(required=True, readonly=True, index=True)
    due_date = fields.Date(related="instance_id.due_date", store=True)

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("submitted", "Submitted"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    decision = fields.Selection(
        [
            ("pass", "Met - pass the gate"),
            ("fail", "Not met - fail the gate"),
            ("extend", "Grant an extension"),
            ("defer", "Defer the decision"),
        ],
        tracking=True,
    )
    decision_notes = fields.Text()
    decided_on = fields.Datetime(readonly=True)
    decided_by_id = fields.Many2one("res.users", readonly=True)
    reminder_count = fields.Integer(default=0, readonly=True)
    last_reminder_on = fields.Date(readonly=True)

    snapshot_score = fields.Float(readonly=True)
    snapshot_summary = fields.Html(readonly=True, sanitize=False)

    _instance_alert_uniq = models.Constraint(
        "UNIQUE(instance_id, alert_type, alert_scheduled_date)",
        "A review alert of this type already exists for this gate and date.",
    )

    # ------------------------------------------------------------- creation
    @api.model
    def create_for_instance(self, instance, reason="manual"):
        instance.ensure_one()
        scheduled = {
            "due_soon": instance.review_date,
            "overdue": instance.due_date,
        }.get(reason, fields.Date.context_today(self))
        reviewer = instance.manager_user_id
        review = self.create(
            {
                "name": _("Gate review: %s") % instance.name,
                "instance_id": instance.id,
                "alert_type": reason,
                "alert_scheduled_date": scheduled,
                "reviewer_user_id": reviewer.id if reviewer else False,
                "snapshot_score": instance.score,
                "snapshot_summary": instance._review_body_text(),
            }
        )
        review._notify_reviewer()
        return review

    def _notify_reviewer(self):
        Activity = self.env["mail.activity"]
        activity_type = self.env.ref(
            "sgc_ces_kpi_banner.mail_activity_type_ces_gate_review", raise_if_not_found=False
        ) or self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        model_id = self.env["ir.model"]._get_id(self._name)
        for review in self:
            if not review.reviewer_user_id:
                _logger.info(
                    "sgc_ces_kpi_banner: review %s has no resolvable reviewer; "
                    "no activity scheduled", review.id
                )
                continue
            Activity.sudo().create(
                {
                    "res_model_id": model_id,
                    "res_id": review.id,
                    "activity_type_id": activity_type.id if activity_type else False,
                    "summary": review.name,
                    "note": review.snapshot_summary or "",
                    "user_id": review.reviewer_user_id.id,
                    "date_deadline": review.instance_id.due_date,
                }
            )
            body = review.snapshot_summary or ""
            if review._email_enabled():
                # Opt-in only: sends a real notification email.
                review.message_notify(
                    partner_ids=review.reviewer_user_id.partner_id.ids,
                    subject=review.name,
                    body=body,
                )
            # Default: do NOT post any chatter message either. The mail.activity
            # created just above is the only channel that reaches the reviewer;
            # no mail.mail row should ever be queued by the default config.
        return True

    def _email_enabled(self):
        return self.env["sgc.ces.identity"]._param_bool(
            "sgc_ces_kpi_banner.review_email_enabled", False
        )

    # ------------------------------------------------------------- workflow
    def _check_reviewer(self):
        if self.env.su or self.env.uid == SUPERUSER_ID:
            return
        for review in self:
            if self.env.user.has_group("sgc_ces_kpi_banner.group_ces_kpi_admin"):
                continue
            if review.reviewer_user_id and review.reviewer_user_id.id != self.env.uid:
                raise UserError(
                    _("Only the assigned reviewer or a CES KPI administrator can act on "
                      "this review.")
                )

    def action_start(self):
        self._check_reviewer()
        self.write({"state": "in_progress"})
        self.mapped("instance_id").write({"state": "in_review"})
        return True

    def action_submit(self):
        self._check_reviewer()
        for review in self:
            if not review.decision:
                raise UserError(_("Choose a decision before submitting the review."))
            if review.decision in ("fail", "extend") and not review.decision_notes:
                raise UserError(_("A written justification is required for this decision."))
        self.write({"state": "submitted"})
        return True

    def action_apply(self):
        """Apply the decision. Considerations are created, never in-place edits."""
        self._check_reviewer()
        for review in self:
            if review.state not in ("submitted", "in_progress"):
                raise UserError(_("Only a submitted review can be applied."))
            instance = review.instance_id
            if review.decision == "pass":
                instance.action_mark_passed()
            elif review.decision == "fail":
                instance.action_mark_failed()
            elif review.decision == "extend":
                instance.state = "extended"
            elif review.decision == "defer":
                instance.state = "pending_review"
            review.write(
                {
                    "state": "done",
                    "decided_on": fields.Datetime.now(),
                    "decided_by_id": self.env.uid,
                }
            )
            review.activity_ids.filtered(lambda a: a.user_id == review.reviewer_user_id).unlink()
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    # ------------------------------------------------------------ reminders
    @api.model
    def _cron_send_review_reminders(self, batch_size=200):
        """Idempotent: at most one reminder per review per day."""
        today = fields.Date.context_today(self)
        pending = self.search(
            [
                ("state", "in", ("pending", "in_progress")),
                "|",
                ("last_reminder_on", "=", False),
                ("last_reminder_on", "<", today),
            ],
            limit=batch_size,
        )
        sent = 0
        for review in pending:
            try:
                if not review.reviewer_user_id:
                    continue
                review.message_post(
                    body=_("Reminder: gate review still open (due %s).")
                    % (fields.Date.to_string(review.due_date) or _("not set")),
                    subtype_xmlid="mail.mt_note",
                )
                review.write(
                    {"last_reminder_on": today, "reminder_count": review.reminder_count + 1}
                )
                sent += 1
            except Exception:  # noqa: BLE001
                _logger.exception("sgc_ces_kpi_banner: reminder failed for review %s", review.id)
                self.env.cr.rollback()
        return sent
