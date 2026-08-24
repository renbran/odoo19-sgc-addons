# -*- coding: utf-8 -*-
import base64
import csv
import io
import logging
import random
from datetime import timedelta

from markupsafe import escape

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Live crm.stage ids confirmed via read-only SQL against odoo19-sgc (no
# crm.stage data file ships in this repo — stages are DB-only). Used only as
# the fallback default when the matching ir.config_parameter is unset.
# 5=No Answer, 7=Not Interested, 11/12=per-rep "No Answer - Talha/John Pipeline"
DEFAULT_DEAD_END_STAGE_IDS = "5,7,11,12"

# Dead-lead cleanup grace mechanics: identified by this exact activity
# summary so the archive decision can be keyed off "has this lead actually
# been warned" rather than dwell-time arithmetic (see _cron_dead_lead_cleanup).
DEAD_LEAD_GRACE_ACTIVITY_SUMMARY = "Stale Lead: set Lost Reason"
DEAD_LEAD_GRACE_PERIOD_DAYS = 7

# The 4 Verifiable Buyer Exit Criteria (playbook Phase 4). Order matters —
# it's the order shown in the UI and in the "missing" error message.
GATE_FIELDS = [
    ("x_gate_problem", "Q1: Specific problem"),
    ("x_gate_cost_of_inaction", "Q2: Cost of doing nothing"),
    ("x_gate_approver", "Q3: Who approves"),
    ("x_gate_timeline", "Q4: Timeline"),
]

# Per-field provenance replaces the old single x_gate_extracted_from_ai
# boolean (S1) — each of the 4 gate answers is either typed directly by the
# rep, or confirmed by the rep from an sgc_meeting_ai AI transcript summary
# (never applied silently: sgc_meeting_ai's apply wizard requires the rep to
# review/edit each value before confirming).
PROVENANCE_SELECTION = [
    ("manual", "Manual"),
    ("ai_confirmed", "AI (Rep-Confirmed)"),
]
GATE_PROVENANCE_FIELDS = [f"{field_name}_provenance" for field_name, _label in GATE_FIELDS]

# Daily lead distribution: same live-verified ids as the rest of this file
# (see SALES_PLAYBOOK_BUILD_DOCUMENTATION.md §2) — 1="New" stage, team id 1
# is the "Sales" crm.team.
DEFAULT_LEAD_DISTRIBUTION_TEAM_ID = "1"
DEFAULT_LEAD_DISTRIBUTION_STAGE_ID = "1"
DEFAULT_LEAD_DISTRIBUTION_TARGET_PER_SDR = "60"

# Follow Up stage escalation: 6="Follow Up" (same live-verified id table).
DEFAULT_FOLLOW_UP_STAGE_ID = "6"
DEFAULT_FOLLOW_UP_DAY2_THRESHOLD = "2"
DEFAULT_FOLLOW_UP_DAY4_THRESHOLD = "4"
DEFAULT_FOLLOW_UP_DAY5_THRESHOLD = "5"
DEFAULT_FOLLOW_UP_ESCALATION_BATCH_LIMIT = "200"

# Idempotency markers, same shape as DEAD_LEAD_GRACE_ACTIVITY_SUMMARY — a
# lead's escalation level is keyed off "does this exact activity already
# exist", not off dwell-time arithmetic alone, so a lead already notified
# at day 2 never gets re-notified every day until it crosses day 4.
FOLLOW_UP_DAY2_ESCALATION_SUMMARY = "Follow Up Stalled: Day 2 Notification"
FOLLOW_UP_DAY4_ESCALATION_SUMMARY = "Follow Up Stalled: Day 4 Final Warning"


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # ── Verifiable Buyer Exit Criteria (the gate) ──────────────────────────
    x_gate_problem = fields.Text(string="Gate Q1: Specific Problem")
    x_gate_cost_of_inaction = fields.Text(string="Gate Q2: Cost of Doing Nothing")
    x_gate_approver = fields.Text(string="Gate Q3: Who Approves")
    x_gate_timeline = fields.Text(string="Gate Q4: Timeline")
    x_gate_answered_count = fields.Integer(
        string="Gate Questions Answered",
        compute="_compute_gate_status",
        store=True,
    )
    x_gate_status = fields.Selection(
        [
            ("not_started", "Not Started"),
            ("partial", "Partial"),
            ("qualified", "Qualified"),
        ],
        string="Gate Status",
        compute="_compute_gate_status",
        store=True,
    )
    x_gate_override_reason = fields.Text(
        string="Gate Override Reason",
        groups="sales_team.group_sale_manager",
        help="Set only when a Sales Manager overrides the Proposal-stage "
        "qualification gate. Logged to chatter when written. ORM-level "
        "groups= means the ORM silently strips this value from any write() "
        "by a non-manager before it ever reaches Python — write() below "
        "re-checks has_group() as defense in depth, not as the primary "
        "control.",
    )
    x_gate_problem_provenance = fields.Selection(
        PROVENANCE_SELECTION, string="Q1 Provenance", default="manual"
    )
    x_gate_cost_of_inaction_provenance = fields.Selection(
        PROVENANCE_SELECTION, string="Q2 Provenance", default="manual"
    )
    x_gate_approver_provenance = fields.Selection(
        PROVENANCE_SELECTION, string="Q3 Provenance", default="manual"
    )
    x_gate_timeline_provenance = fields.Selection(
        PROVENANCE_SELECTION, string="Q4 Provenance", default="manual"
    )
    x_is_sales_manager = fields.Boolean(
        string="Is Sales Manager",
        compute="_compute_is_sales_manager",
    )
    x_objection_ids = fields.One2many(
        "sgc.lead.objection", "lead_id", string="Objections"
    )

    # ── Pre-call research capture (non-blocking) ───────────────────────────
    x_research_pain_tier = fields.Selection(
        [
            ("tier1_direct", "Tier 1: Direct Pain"),
            ("tier2_latent", "Tier 2: Latent Pain"),
            ("tier3_none", "Tier 3: No Pain Visible"),
        ],
        string="Pre-Call Pain Tier",
    )
    x_research_pain_note = fields.Text(
        string="Pain Signal Found",
        help="The specific signal found during pre-call research (a review "
        "quote, a hiring post, listing count/areas, etc).",
    )
    x_research_done = fields.Boolean(
        string="Pre-Call Research Done",
        compute="_compute_x_research_done",
        store=True,
        help="Computed from Pre-Call Pain Tier — any tier set means the "
        "3-minute research routine was done. Not independently settable, "
        "so it can never drift from the tier that actually backs it.",
    )
    x_is_pre_call_stage = fields.Boolean(
        string="Is Pre-Call Stage",
        compute="_compute_x_is_pre_call_stage",
        store=True,
        help="True while stage_id.sequence <= 1 (New / Valid Contact). "
        "Exists only so the research-nudge banner's invisible domain can "
        "reference a plain boolean instead of dotting into stage_id.sequence "
        "— that dotted form evaluates fine server-side but crashes the web "
        "client's form renderer (many2one fields aren't exposed as objects "
        "with sub-properties to the client-side domain evaluator), which "
        "made every crm.lead form throw an OwlError on open.",
    )
    x_auto_archived_run = fields.Char(
        string="Auto-Archived Run",
        index=True,
        help="ISO date of the dead-lead cleanup run that archived this "
        "lead, if any. Filter by this value to review or reverse a "
        "specific run (unarchive + clear this field undoes exactly one "
        "run, not the whole history of auto-archiving).",
    )

    @api.depends(
        "x_gate_problem",
        "x_gate_cost_of_inaction",
        "x_gate_approver",
        "x_gate_timeline",
    )
    def _compute_gate_status(self):
        for lead in self:
            answered = sum(
                1 for field_name, _label in GATE_FIELDS if (lead[field_name] or "").strip()
            )
            lead.x_gate_answered_count = answered
            if answered == 0:
                lead.x_gate_status = "not_started"
            elif answered < len(GATE_FIELDS):
                lead.x_gate_status = "partial"
            else:
                lead.x_gate_status = "qualified"

    @api.model
    def _get_gate_provenance_domain(self, bucket):
        """Domain fragment classifying a lead's gate-answer provenance as a
        whole, from the 4 per-field provenance selections. 'ai' = at least
        one field is ai_confirmed (OR across the 4 fields); 'human' = all 4
        are manual (AND across the 4 fields) — the exact complement of
        'ai', so the two buckets always partition the full population
        cleanly (ai_n + human_n == total_n)."""
        if bucket == "ai":
            domain = []
            for field_name in GATE_PROVENANCE_FIELDS[1:]:
                domain += ["|"]
            for field_name in GATE_PROVENANCE_FIELDS:
                domain += [(field_name, "=", "ai_confirmed")]
            return domain
        return [(field_name, "=", "manual") for field_name in GATE_PROVENANCE_FIELDS]

    def _compute_is_sales_manager(self):
        is_manager = self.env.user.has_group("sales_team.group_sale_manager")
        for lead in self:
            lead.x_is_sales_manager = is_manager

    @api.depends("x_research_pain_tier")
    def _compute_x_research_done(self):
        for lead in self:
            lead.x_research_done = bool(lead.x_research_pain_tier)

    @api.depends("stage_id.sequence")
    def _compute_x_is_pre_call_stage(self):
        for lead in self:
            lead.x_is_pre_call_stage = bool(lead.stage_id and lead.stage_id.sequence <= 1)

    @api.model
    def _get_gate_stage_id(self):
        """Live crm.stage records ship with no XML ID in this repo (confirmed:
        no crm.stage data file exists anywhere in the codebase — stages were
        created out-of-band on the live DB). Read the Proposal stage id from
        a config parameter (defaulting to the live-verified id 9) instead of
        hardcoding it, so a stage reshuffle doesn't require a code change."""
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.gate_stage_id", "9")
        )
        try:
            return int(param)
        except (TypeError, ValueError):
            return 9

    @api.model
    def _get_gate_stage(self):
        """crm.stage record for the configured gate, or an empty recordset
        if sgc_sales_playbook.gate_stage_id doesn't resolve to a real stage
        (deleted/renumbered stage, typo'd config param, etc). Callers MUST
        fail OPEN when this is empty — a broken config parameter must never
        block the entire sales team's kanban. Also used by
        sgc_crm_dashboard to surface this degraded state on the
        Qualification panel instead of failing silently."""
        gate_stage_id = self._get_gate_stage_id()
        stage = self.env["crm.stage"].browse(gate_stage_id).exists()
        if not stage:
            _logger.warning(
                "SGC sales playbook: configured gate_stage_id=%s does not "
                "resolve to a crm.stage record. The Proposal-stage gate is "
                "DISABLED (failing open) until "
                "sgc_sales_playbook.gate_stage_id is corrected in Settings "
                "> Technical > System Parameters.",
                gate_stage_id,
            )
        return stage

    def write(self, vals):
        # groups="sales_team.group_sale_manager" on x_gate_override_reason
        # already strips this key when a non-manager writes through the ORM
        # in their own context — but that protection doesn't cover every
        # path into write() (sudo(), server actions, XML-RPC, CSV import).
        # Re-check explicitly and drop it before the gate check ever sees
        # it, so a non-manager can never self-grant the bypass.
        is_manager = self.env.user.has_group("sales_team.group_sale_manager")
        override_reason = vals.get("x_gate_override_reason")
        if override_reason and not is_manager:
            vals = dict(vals)
            vals.pop("x_gate_override_reason")
            override_reason = None

        if "stage_id" in vals:
            self._check_proposal_gate(vals)

        res = super().write(vals)

        if override_reason:
            now_str = fields.Datetime.to_string(fields.Datetime.now())
            for lead in self:
                lead.message_post(
                    body=_(
                        "Proposal qualification gate overridden by %(user)s "
                        "on %(when)s. Stage: %(stage)s. Reason: %(reason)s"
                    )
                    % {
                        "user": self.env.user.display_name,
                        "when": now_str,
                        "stage": lead.stage_id.display_name,
                        "reason": override_reason,
                    }
                )
        return res

    @api.model
    def _get_gate_excluded_stage_ids(self):
        """Stage ids that must never be gated regardless of sequence —
        distinct from _get_dead_end_stage_ids() (used by the cleanup cron)
        even though they default to the same set today. The two config
        parameters answer different questions (which stages count as
        'gone cold' for archival vs. which stages a rep can always move
        into without qualification) and a future pipeline restructure could
        easily need to change one without the other — coupling them to a
        single param would silently break whichever concern wasn't being
        edited. Defaults to the live dead-end pipelines (5,7,11,12): their
        sequence (10-11) sits ABOVE Won (9) purely because they were
        appended to the stage list later, so a naive sequence threshold
        would wrongly require the gate before a rep can give up on an
        unresponsive lead."""
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.gate_excluded_stage_ids", DEFAULT_DEAD_END_STAGE_IDS)
        )
        try:
            return [int(x) for x in param.split(",") if x.strip()]
        except ValueError:
            return [int(x) for x in DEFAULT_DEAD_END_STAGE_IDS.split(",")]

    @api.model
    def _get_gate_mode(self):
        """off: gate disabled entirely. warn (default): missing criteria
        post a chatter note + create an activity for the salesperson, but
        the write is allowed. block: raise UserError, refusing the write."""
        mode = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.gate_mode", "warn")
        )
        return mode if mode in ("off", "warn", "block") else "warn"

    def _check_proposal_gate(self, vals):
        gate_mode = self._get_gate_mode()
        if gate_mode == "off":
            return

        gate_stage = self._get_gate_stage()
        if not gate_stage:
            # Fail OPEN — _get_gate_stage() already logged a WARNING.
            return

        new_stage_id = vals.get("stage_id")
        if not new_stage_id:
            return
        gate_excluded_ids = self._get_gate_excluded_stage_ids()
        if new_stage_id in gate_excluded_ids:
            # Exiting to a dead end is never gated, regardless of sequence
            # — see _get_gate_excluded_stage_ids() for why this is its own
            # config parameter rather than reusing dead_end_stage_ids.
            return
        new_stage = self.env["crm.stage"].browse(new_stage_id).exists()
        if not new_stage or new_stage.sequence < gate_stage.sequence:
            # Below the gate threshold (e.g. New -> Follow Up) — not gated.
            return
        if vals.get("x_gate_override_reason"):
            # Override reason supplied in the same write — let it through.
            return

        for lead in self:
            if lead.stage_id.id not in gate_excluded_ids and lead.stage_id.sequence >= gate_stage.sequence:
                # Already at/past Proposal (e.g. an unrelated field edit, a
                # bounce back into the same stage, or a rep dragging further
                # within the gated range) — don't re-block routine saves on
                # deals that predate this gate. Explicitly excludes dead-end
                # stages: their sequence is also >= gate_stage.sequence (see
                # above), but sitting in a dead-end stage was never actually
                # gated, so reviving such a lead straight into Proposal must
                # still be checked.
                continue
            merged = {
                field_name: vals.get(field_name, lead[field_name])
                for field_name, _label in GATE_FIELDS
            }
            missing = [
                label for field_name, label in GATE_FIELDS if not (merged[field_name] or "").strip()
            ]
            if not missing:
                continue

            if gate_mode == "block":
                raise UserError(
                    _(
                        "Cannot move '%(name)s' to Proposal — the Verifiable "
                        "Buyer Exit Criteria are incomplete.\n\nMissing: "
                        "%(missing)s\n\nAnswer all 4 gate questions in the "
                        "Qualification tab, or ask a Sales Manager to "
                        "override with a reason."
                    )
                    % {"name": lead.name, "missing": ", ".join(missing)}
                )

            # gate_mode == "warn": allow the write, but make the gap visible
            # — mirrors the dry-run/live wording used by the cleanup cron so
            # the two controls read consistently.
            lead.message_post(
                body=_(
                    "Qualification gate incomplete for '%(name)s' moving to "
                    "%(stage)s, but allowed (sgc_sales_playbook.gate_mode="
                    "warn). Missing: %(missing)s"
                )
                % {
                    "name": lead.name,
                    "stage": new_stage.display_name,
                    "missing": ", ".join(missing),
                }
            )
            todo = self.env.ref("mail.mail_activity_data_todo")
            lead._ensure_activity(
                todo,
                "Gate Incomplete: allowed by gate_mode=warn",
                "Moved to %s without all 4 gate questions answered. Missing: "
                "%s. Complete these before the deal reaches Won."
                % (new_stage.display_name, ", ".join(missing)),
            )

    def action_open_gate_override_wizard(self):
        self.ensure_one()
        if not self.env.user.has_group("sales_team.group_sale_manager"):
            raise UserError(_("Only a Sales Manager can override the qualification gate."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Override Qualification Gate"),
            "res_model": "sgc.gate.override.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_lead_id": self.id},
        }

    # ── Pipeline discipline: weekly gate review ─────────────────────────────

    def _ensure_activity(self, activity_type, summary, note):
        """Idempotent: skip if an open activity with this exact summary
        already exists on the lead (avoids re-flagging every cron run).
        Assignee falls back from the lead's own salesperson to the team
        leader to the cron's own user — never crashes on user_id=False."""
        self.ensure_one()
        existing = self.env["mail.activity"].search(
            [
                ("res_model", "=", "crm.lead"),
                ("res_id", "=", self.id),
                ("summary", "=", summary),
            ],
            limit=1,
        )
        if existing:
            return
        assignee = self.user_id or self.team_id.user_id or self.env.user
        self.env["mail.activity"].create(
            {
                "res_model_id": self.env["ir.model"]._get_id("crm.lead"),
                "res_id": self.id,
                "activity_type_id": activity_type.id,
                "summary": summary,
                "note": note,
                "user_id": assignee.id,
                "date_deadline": fields.Date.today(),
            }
        )

    @api.model
    def _get_weekly_gate_review_batch_limit(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.weekly_gate_review_batch_limit", "50")
        )
        try:
            return max(int(param), 0)
        except (TypeError, ValueError):
            return 50

    @api.model
    def _cron_weekly_gate_review(self):
        """Scans deals at/after Meeting Booked for incomplete gates, and any
        open deal stalled 3+ weeks in its current stage. Creates a reminder
        activity on the rep for each (idempotent — see _ensure_activity).
        Manager-facing visibility is the sgc_crm_dashboard "Qualification &
        Gate Compliance" panel and the executive AI "discovery_health"
        preset, not an emailed digest — deliberately no email is sent here.

        Each half is capped at sgc_sales_playbook.weekly_gate_review_batch_limit
        (default 50) — the "stalled" domain alone matched 6,013 leads against
        a live production snapshot; uncapped, the first run would create
        thousands of activities in one pass.
        """
        todo = self.env.ref("mail.mail_activity_data_todo")
        batch_limit = self._get_weekly_gate_review_batch_limit()

        ungated = self.search(
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("stage_id.sequence", ">=", 7),
                ("x_gate_status", "!=", "qualified"),
            ],
            limit=batch_limit,
            order="date_last_stage_update asc",
        )
        for lead in ungated:
            missing = [
                label for field_name, label in GATE_FIELDS if not (lead[field_name] or "").strip()
            ]
            lead._ensure_activity(
                todo,
                "Pipeline Gate Review: incomplete",
                "Complete the gate questions or move this deal back to "
                "discovery. Missing: %s" % ", ".join(missing),
            )

        stall_cutoff = fields.Datetime.now() - timedelta(weeks=3)
        stalled = self.search(
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("date_last_stage_update", "!=", False),
                ("date_last_stage_update", "<=", stall_cutoff),
            ],
            limit=batch_limit,
            order="date_last_stage_update asc",
        )
        for lead in stalled:
            lead._ensure_activity(
                todo,
                "Pipeline Gate Review: stalled",
                "Stalled 3+ weeks in '%s'. Requalify or kill this deal."
                % lead.stage_id.display_name,
            )

        _logger.info(
            "SGC weekly gate review: %d ungated, %d stalled", len(ungated), len(stalled)
        )

    # ── Pipeline discipline: dead-lead cleanup ──────────────────────────────

    @api.model
    def _get_dead_end_stage_ids(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.dead_end_stage_ids", DEFAULT_DEAD_END_STAGE_IDS)
        )
        try:
            return [int(x) for x in param.split(",") if x.strip()]
        except ValueError:
            return [int(x) for x in DEFAULT_DEAD_END_STAGE_IDS.split(",")]

    @api.model
    def _get_dead_lead_cleanup_batch_limit(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.dead_lead_cleanup_batch_limit", "500")
        )
        try:
            return max(int(param), 0)
        except (TypeError, ValueError):
            return 500

    @api.model
    def _get_dead_lead_cleanup_report_user(self):
        """Whose res.users record the dry-run CSV attachment is written to.
        Config param first, falling back to the first Sales Manager, then
        the cron's own user — never raises for lack of configuration."""
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.dead_lead_cleanup_report_user_id")
        )
        if param:
            try:
                user = self.env["res.users"].browse(int(param)).exists()
                if user:
                    return user
            except (TypeError, ValueError):
                pass
        manager_group = self.env.ref("sales_team.group_sale_manager", raise_if_not_found=False)
        manager = manager_group.user_ids[:1] if manager_group else self.env["res.users"]
        return manager or self.env.user

    def _dead_lead_cleanup_grace_activities_by_lead(self, leads):
        """Map lead id -> its existing dead-lead grace activity (if any).
        The archive decision is keyed off this artifact's existence and age,
        not off how long the lead has been sitting in a dead-end stage —
        dwell time alone can't tell "already warned 10 days ago" apart from
        "never warned, just happens to be old," and on a cold start (first
        run, or any run after a gap) every pre-existing backlog lead looks
        like the latter under a pure dwell-time rule."""
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "crm.lead"),
                ("res_id", "in", leads.ids),
                ("summary", "=", DEAD_LEAD_GRACE_ACTIVITY_SUMMARY),
            ]
        )
        by_lead = {}
        for activity in activities:
            existing = by_lead.get(activity.res_id)
            if existing is None or activity.create_date < existing.create_date:
                by_lead[activity.res_id] = activity
        return by_lead

    def _dead_lead_cleanup_write_dry_run_csv(self, leads):
        """Write the exact dry-run candidate set as a reviewable CSV
        attachment instead of just IDs in a log line nobody reads."""
        grace_expiry_cutoff = fields.Datetime.now() - timedelta(days=DEAD_LEAD_GRACE_PERIOD_DAYS)
        grace_by_lead = self._dead_lead_cleanup_grace_activities_by_lead(leads)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "id", "name", "partner", "salesperson", "stage",
            "date_last_stage_update", "expected_action",
        ])
        for lead in leads:
            activity = grace_by_lead.get(lead.id)
            if not activity:
                expected_action = "grace_activity"
            elif activity.create_date <= grace_expiry_cutoff:
                expected_action = "archive"
            else:
                expected_action = "grace_active_not_expired"
            writer.writerow([
                lead.id,
                lead.name,
                lead.partner_id.display_name or "",
                lead.user_id.display_name or "",
                lead.stage_id.display_name,
                fields.Datetime.to_string(lead.date_last_stage_update) or "",
                expected_action,
            ])

        report_user = self._get_dead_lead_cleanup_report_user()
        filename = "sgc_dead_lead_cleanup_dryrun_%s.csv" % fields.Date.today().isoformat()
        attachment = self.env["ir.attachment"].sudo().create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(buf.getvalue().encode("utf-8")),
            "res_model": "res.users",
            "res_id": report_user.id,
            "mimetype": "text/csv",
        })
        _logger.info(
            "SGC dead-lead cleanup DRY RUN CSV written: ir.attachment id=%d, "
            "name=%s, attached to res.users id=%d (%s). Review it before "
            "setting sgc_sales_playbook.dead_lead_cleanup_mode='live'.",
            attachment.id, filename, report_user.id, report_user.display_name,
        )
        return attachment

    @api.model
    def _cron_dead_lead_cleanup(self):
        """Leads parked 30+ days in a dead-end stage (No Answer / Not
        Interested / per-rep dead-end pipelines) with no lost_reason_id ever
        get archived — reps have been using these stages as a substitute for
        the standard Lost flow, so nothing ever leaves active pipeline.

        Staleness is measured on `date_last_stage_update` (stock field, set
        on every stage change), not `write_date`. B1 fixed
        _cron_weekly_gate_review's "stalled" check this way but the archival
        cron here was left on write_date — verified against a real
        production snapshot (sgc_staging, 2026-07-26 restore) that this
        under-caught by 4-8x: most parked leads get write_date bumped by
        unrelated touches (chatter, activities, background jobs) well after
        they actually went cold, which hid them from a write_date filter.
        date_last_stage_update only changes when the lead actually enters
        this stage, which is what "parked 30+ days" is supposed to mean.

        The grace-vs-archive split is keyed off the grace activity itself,
        not off a second dwell-time threshold. A lead only archives if it
        already has an open DEAD_LEAD_GRACE_ACTIVITY_SUMMARY activity that is
        DEAD_LEAD_GRACE_PERIOD_DAYS old or older; every other stale lead gets
        the grace activity (created now) and nothing else this run. This
        replaced an earlier "37+ days dwell = archive immediately" rule that
        assumed the cron had been running continuously since day one — that
        assumption breaks on cold start, on any execution gap, and after the
        cron is disabled/re-enabled: verified against a real production
        snapshot that a naive first-ever run would have hard-archived 127
        leads with zero prior warning. Keying off the artifact instead of
        the arithmetic means no lead is ever archived without a record
        proving it was warned first, in every one of those cases.

        Defaults to DRY RUN (log-only + CSV attachment, no writes) via the
        'sgc_sales_playbook.dead_lead_cleanup_mode' config parameter. Do not
        flip it to 'live' on the production DB without first reviewing the
        dry-run CSV — see the module README.

        Live mode: uses action_set_lost() (probability=0 + standard lost
        bookkeeping, not a raw active=False write), processes in batches of
        200 capped at a per-run limit (config param
        dead_lead_cleanup_batch_limit, default 500), stamps every archived
        lead with x_auto_archived_run so one filter can undo one run, and
        unlinks any open activities on archived leads so they leave reps'
        to-do lists. Idempotent: archived leads drop out of the active=True
        search domain, so an immediate second run selects 0 additional
        records.
        """
        dry_run = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.dead_lead_cleanup_mode", "dry_run")
            != "live"
        )
        stage_ids = self._get_dead_end_stage_ids()
        stale_cutoff = fields.Datetime.now() - timedelta(days=30)
        batch_limit = self._get_dead_lead_cleanup_batch_limit()

        stale = self.search(
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("stage_id", "in", stage_ids),
                ("lost_reason_id", "=", False),
                ("date_last_stage_update", "!=", False),
                ("date_last_stage_update", "<=", stale_cutoff),
            ],
            limit=batch_limit,
            order="date_last_stage_update asc",
        )

        if dry_run:
            self._dead_lead_cleanup_write_dry_run_csv(stale)
            _logger.info(
                "SGC dead-lead cleanup DRY RUN: %d lead(s) would be "
                "flagged/archived (capped at batch limit %d; set "
                "sgc_sales_playbook.dead_lead_cleanup_mode='live' to enable "
                "after reviewing the CSV). IDs: %s",
                len(stale),
                batch_limit,
                stale.ids,
            )
            return

        todo = self.env.ref("mail.mail_activity_data_todo")
        grace_expiry_cutoff = fields.Datetime.now() - timedelta(days=DEAD_LEAD_GRACE_PERIOD_DAYS)
        grace_by_lead = self._dead_lead_cleanup_grace_activities_by_lead(stale)

        to_grace_prompt = self.env["crm.lead"]
        to_archive = self.env["crm.lead"]
        for lead in stale:
            activity = grace_by_lead.get(lead.id)
            if not activity:
                to_grace_prompt |= lead
            elif activity.create_date <= grace_expiry_cutoff:
                to_archive |= lead
            # else: grace already given and still within its window — leave
            # it alone this run, it isn't due for a decision yet.

        for lead in to_grace_prompt:
            lead._ensure_activity(
                todo,
                DEAD_LEAD_GRACE_ACTIVITY_SUMMARY,
                "Stale 30+ days in '%s' with no Lost Reason set. Set one, "
                "or it will be auto-archived in %d days." % (
                    lead.stage_id.display_name, DEAD_LEAD_GRACE_PERIOD_DAYS,
                ),
            )

        run_marker = fields.Date.today().isoformat()
        archived_count = 0
        if to_archive:
            default_lost_reason = self.env.ref(
                "sgc_sales_playbook.lost_reason_stale", raise_if_not_found=False
            )
            # Batches of 200 so one cron tick never locks/rewrites the
            # whole candidate set (up to batch_limit) in a single write.
            for offset in range(0, len(to_archive), 200):
                batch = to_archive[offset:offset + 200]
                for lead in batch:
                    lead.message_post(
                        body=_(
                            "Auto-archived by SGC dead-lead cleanup: grace "
                            "period expired with no Lost Reason set in "
                            "'%(stage)s'. Run marker: %(marker)s"
                        )
                        % {"stage": lead.stage_id.display_name, "marker": run_marker}
                    )
                self.env["mail.activity"].search(
                    [
                        ("res_model", "=", "crm.lead"),
                        ("res_id", "in", batch.ids),
                    ]
                ).unlink()
                set_lost_kwargs = {"x_auto_archived_run": run_marker}
                if default_lost_reason:
                    set_lost_kwargs["lost_reason_id"] = default_lost_reason.id
                batch.action_set_lost(**set_lost_kwargs)
                archived_count += len(batch)

        _logger.info(
            "SGC dead-lead cleanup: %d flagged (grace), %d archived (run marker %s)",
            len(to_grace_prompt),
            archived_count,
            run_marker,
        )

    # ── Daily lead distribution to SDRs ─────────────────────────────────────

    @api.model
    def _get_lead_distribution_mode(self):
        """dry_run (default): compute the plan and write a reviewable CSV,
        no writes. live: actually reassigns leads. Mirrors
        _cron_dead_lead_cleanup's safety default — a bulk reassignment
        across every SDR is easy to get wrong on a first run (wrong team,
        wrong stage id), so it ships defaulting to dry-run same as that
        cron."""
        mode = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.lead_distribution_mode", "dry_run")
        )
        return mode if mode in ("dry_run", "live") else "dry_run"

    @api.model
    def _get_lead_distribution_target_per_sdr(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "sgc_sales_playbook.lead_distribution_target_per_sdr",
                DEFAULT_LEAD_DISTRIBUTION_TARGET_PER_SDR,
            )
        )
        try:
            return max(int(param), 0)
        except (TypeError, ValueError):
            return int(DEFAULT_LEAD_DISTRIBUTION_TARGET_PER_SDR)

    @api.model
    def _get_lead_distribution_stage(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "sgc_sales_playbook.lead_distribution_stage_id",
                DEFAULT_LEAD_DISTRIBUTION_STAGE_ID,
            )
        )
        try:
            stage_id = int(param)
        except (TypeError, ValueError):
            stage_id = int(DEFAULT_LEAD_DISTRIBUTION_STAGE_ID)
        return self.env["crm.stage"].browse(stage_id).exists()

    @api.model
    def _get_lead_distribution_source_user(self):
        """Whose New-stage lead pool gets drained to fill the SDRs. Config
        param first (an explicit user id), falling back to the standard
        Administrator account (base.user_admin, ships with every Odoo db)
        rather than a hardcoded id — res.users ids are not guaranteed
        stable across environments."""
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.lead_distribution_source_user_id")
        )
        if param:
            try:
                user = self.env["res.users"].browse(int(param)).exists()
                if user:
                    return user
            except (TypeError, ValueError):
                pass
        return self.env.ref("base.user_admin", raise_if_not_found=False) or self.env["res.users"]

    @api.model
    def _get_lead_distribution_team(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "sgc_sales_playbook.lead_distribution_team_id",
                DEFAULT_LEAD_DISTRIBUTION_TEAM_ID,
            )
        )
        try:
            team_id = int(param)
        except (TypeError, ValueError):
            team_id = int(DEFAULT_LEAD_DISTRIBUTION_TEAM_ID)
        return self.env["crm.team"].browse(team_id).exists()

    @api.model
    def _get_lead_distribution_sdr_users(self):
        """The distribution pool: active members of the configured
        crm.team, MINUS that team's own leader (crm.team.user_id) MINUS
        the Administrator account — confirmed against a live snapshot
        (2026-08-21) that the "Sales" team's leader IS Bran Madelo, so
        excluding the team lead structurally also excludes him without a
        hardcoded user id that would silently stop applying the moment
        the team lead changes. An optional extra exclusion list
        (lead_distribution_excluded_user_ids, empty by default) covers
        any other one-off exclusion without a code change."""
        team = self._get_lead_distribution_team()
        if not team:
            return self.env["res.users"]

        excluded_ids = set()
        if team.user_id:
            excluded_ids.add(team.user_id.id)
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        if admin:
            excluded_ids.add(admin.id)
        extra_param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.lead_distribution_excluded_user_ids", "")
        )
        for token in extra_param.split(","):
            token = token.strip()
            if token.isdigit():
                excluded_ids.add(int(token))

        members = team.crm_team_member_ids.filtered(
            lambda m: m.active and m.user_id.active and m.user_id.id not in excluded_ids
        )
        return members.mapped("user_id")

    @api.model
    def _get_lead_distribution_report_user(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.lead_distribution_report_user_id")
        )
        if param:
            try:
                user = self.env["res.users"].browse(int(param)).exists()
                if user:
                    return user
            except (TypeError, ValueError):
                pass
        manager_group = self.env.ref("sales_team.group_sale_manager", raise_if_not_found=False)
        manager = manager_group.user_ids[:1] if manager_group else self.env["res.users"]
        return manager or self.env.user

    def _lead_distribution_write_report_csv(self, assignments, mode):
        """Reviewable CSV of exactly which leads move to which SDR this
        run — same 'attachment, not just a log line' approach as the
        dead-lead cleanup dry-run (see _dead_lead_cleanup_write_dry_run_csv).
        Written in both dry_run and live mode, so a live run leaves the
        same audit trail behind it."""
        if not assignments:
            return None
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "name", "partner", "from_user", "to_sdr", "mode"])
        for sdr, leads in assignments.items():
            for lead in leads:
                writer.writerow([
                    lead.id,
                    lead.name,
                    lead.partner_id.display_name or "",
                    lead.user_id.display_name or "",
                    sdr.display_name,
                    mode,
                ])

        report_user = self._get_lead_distribution_report_user()
        filename = "sgc_lead_distribution_%s_%s.csv" % (mode, fields.Date.today().isoformat())
        attachment = self.env["ir.attachment"].sudo().create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(buf.getvalue().encode("utf-8")),
            "res_model": "res.users",
            "res_id": report_user.id,
            "mimetype": "text/csv",
        })
        _logger.info(
            "SGC lead distribution CSV written: ir.attachment id=%d, name=%s, "
            "attached to res.users id=%d (%s).",
            attachment.id, filename, report_user.id, report_user.display_name,
        )
        return attachment

    @api.model
    def _cron_daily_lead_distribution(self):
        """Tops up each SDR's "New"-stage queue to a fixed daily target
        (default 60) by reassigning leads from the Administrator's
        New-stage pool — SGC's top-of-funnel dump (~5,500 New leads live,
        see SALES_PLAYBOOK_BUILD_DOCUMENTATION.md §1) sits under
        Administrator until an SDR is assigned. Runs daily via ir.cron but
        no-ops on Saturday/Sunday — ir.cron has no native weekday
        scheduling, so the skip is done here in Python rather than via two
        extra pause/resume crons.

        "Fill", not "add N flat": an SDR already at/above the target
        (e.g. worked through fewer leads yesterday) gets 0 new leads this
        run; only the shortfall is pulled from the source pool. Confirmed
        against a live snapshot (2026-08-21) this produces a real per-SDR
        spread (39-124 already in New) rather than a uniform +60 for
        everyone regardless of backlog.

        The SDR pool is the configured crm.team's active members minus
        that team's own leader minus Administrator (see
        _get_lead_distribution_sdr_users) — not a hardcoded user list, so
        team roster changes don't require a code change.

        Defaults to DRY RUN (CSV attachment + log only) via
        'sgc_sales_playbook.lead_distribution_mode' — flip to 'live' only
        after reviewing the dry-run CSV attached to the report user.
        """
        today = fields.Date.today()
        if today.weekday() >= 5:  # 5=Saturday, 6=Sunday
            _logger.info(
                "SGC lead distribution: skipped, %s is a weekend.", today.isoformat()
            )
            return

        stage = self._get_lead_distribution_stage()
        if not stage:
            _logger.warning(
                "SGC lead distribution: configured lead_distribution_stage_id "
                "does not resolve to a crm.stage record. Skipping this run."
            )
            return

        source_user = self._get_lead_distribution_source_user()
        if not source_user:
            _logger.warning(
                "SGC lead distribution: no source user resolved "
                "(lead_distribution_source_user_id unset and base.user_admin "
                "missing). Skipping this run."
            )
            return

        sdrs = self._get_lead_distribution_sdr_users()
        if not sdrs:
            _logger.warning(
                "SGC lead distribution: no active SDR users resolved for "
                "the configured team (excluding the team leader and "
                "Administrator). Skipping this run."
            )
            return

        target = self._get_lead_distribution_target_per_sdr()
        mode = self._get_lead_distribution_mode()

        needed = {}
        for sdr in sdrs:
            current = self.search_count([
                ("user_id", "=", sdr.id),
                ("stage_id", "=", stage.id),
                ("active", "=", True),
            ])
            needed[sdr.id] = max(target - current, 0)

        total_needed = sum(needed.values())
        if total_needed == 0:
            _logger.info(
                "SGC lead distribution: every SDR already at/above target "
                "(%d). Nothing to do.", target,
            )
            return

        candidates = self.search(
            [
                ("user_id", "=", source_user.id),
                ("stage_id", "=", stage.id),
                ("active", "=", True),
            ],
            order="create_date asc",
            limit=total_needed,
        )

        # Deterministic allocation order (by login) so a partially-starved
        # source pool always shorts the same SDRs last, not whichever
        # order sdrs happens to iterate in this run.
        assignments = {}
        cursor = 0
        for sdr in sdrs.sorted("login"):
            take = min(needed[sdr.id], len(candidates) - cursor)
            if take <= 0:
                continue
            assignments[sdr] = candidates[cursor:cursor + take]
            cursor += take

        self._lead_distribution_write_report_csv(assignments, mode)

        assigned_total = sum(len(leads) for leads in assignments.values())
        if mode == "dry_run":
            _logger.info(
                "SGC lead distribution DRY RUN: would reassign %d of %d "
                "needed lead(s) from %s across %d SDR(s) (source pool had "
                "%d New-stage lead(s) available). Set "
                "sgc_sales_playbook.lead_distribution_mode='live' to enable "
                "after reviewing the CSV.",
                assigned_total, total_needed, source_user.display_name,
                len(assignments), len(candidates),
            )
            return

        for sdr, leads in assignments.items():
            for offset in range(0, len(leads), 200):
                leads[offset:offset + 200].write({"user_id": sdr.id})

        _logger.info(
            "SGC lead distribution: reassigned %d lead(s) from %s across "
            "%d SDR(s) (target %d each; source pool had %d New-stage "
            "lead(s) available).",
            assigned_total, source_user.display_name, len(assignments),
            target, len(candidates),
        )

    # ── Follow Up stage escalation (day 2 / day 4 / day 5) ──────────────────

    @api.model
    def _get_follow_up_escalation_mode(self):
        """dry_run (default): compute the plan and write a reviewable CSV —
        no email, no activity, no reassignment. Same safety convention as
        every other bulk cron in this file."""
        mode = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.follow_up_escalation_mode", "dry_run")
        )
        return mode if mode in ("dry_run", "live") else "dry_run"

    @api.model
    def _get_follow_up_stage(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.follow_up_stage_id", DEFAULT_FOLLOW_UP_STAGE_ID)
        )
        try:
            stage_id = int(param)
        except (TypeError, ValueError):
            stage_id = int(DEFAULT_FOLLOW_UP_STAGE_ID)
        return self.env["crm.stage"].browse(stage_id).exists()

    @api.model
    def _get_follow_up_threshold(self, key, default):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_sales_playbook.follow_up_%s_threshold" % key, str(default))
        )
        try:
            return max(int(param), 1)
        except (TypeError, ValueError):
            return default

    @api.model
    def _get_follow_up_escalation_batch_limit(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "sgc_sales_playbook.follow_up_escalation_batch_limit",
                DEFAULT_FOLLOW_UP_ESCALATION_BATCH_LIMIT,
            )
        )
        try:
            return max(int(param), 0)
        except (TypeError, ValueError):
            return int(DEFAULT_FOLLOW_UP_ESCALATION_BATCH_LIMIT)

    @api.model
    def _business_days_elapsed(self, start_dt, end_date):
        """Business days (Mon-Fri) elapsed from `start_dt` (a datetime) up
        to `end_date` (a date), not counting the start day itself. A lead
        that entered Follow Up Friday afternoon is 0 elapsed through
        Friday, 1 through Monday, 2 through Tuesday — weekends don't
        advance the count, matching the user's explicit choice that this
        timer runs on business days only."""
        if not start_dt:
            return 0
        start_date = start_dt.date() if hasattr(start_dt, "date") else start_dt
        if end_date <= start_date:
            return 0
        elapsed = 0
        cursor_date = start_date
        while cursor_date < end_date:
            cursor_date += timedelta(days=1)
            if cursor_date.weekday() < 5:
                elapsed += 1
        return elapsed

    def _send_follow_up_email(self, lead, subject, body):
        salesperson = lead.user_id
        email_to = salesperson.email or (salesperson.partner_id.email or False)
        if not email_to:
            _logger.warning(
                "SGC follow-up escalation: salesperson %s (id %d) has no "
                "email set — cannot send '%s' for lead %d.",
                salesperson.display_name, salesperson.id, subject, lead.id,
            )
            return
        mail = self.env["mail.mail"].sudo().create({
            "subject": subject,
            "body_html": "<p>%s</p>" % escape(body),
            "email_to": email_to,
            "auto_delete": True,
        })
        try:
            mail.send()
        except Exception:
            _logger.exception(
                "SGC follow-up escalation: failed to send email for lead "
                "%d to %s", lead.id, email_to,
            )

    def _send_follow_up_escalation(self, lead, activity_type, summary, subject, body):
        """Both channels the task asked for: an Odoo activity (idempotent
        via `summary` — see _ensure_activity) for the in-app/bell
        notification, an actual outbound email, and a chatter note so the
        trail survives even if the activity is later marked done."""
        lead._ensure_activity(activity_type, summary, body)
        lead.message_post(body=body, subject=subject)
        self._send_follow_up_email(lead, subject, body)

    def _follow_up_escalation_write_report_csv(self, day2_notified, day4_warned, day5_redistributed, mode):
        if not day2_notified and not day4_warned and not day5_redistributed:
            return None
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "name", "salesperson", "action", "new_sdr", "mode"])
        for lead in day2_notified:
            writer.writerow([lead.id, lead.name, lead.user_id.display_name, "day2_notify", "", mode])
        for lead in day4_warned:
            writer.writerow([lead.id, lead.name, lead.user_id.display_name, "day4_final_warning", "", mode])
        for lead, new_sdr in day5_redistributed:
            writer.writerow([lead.id, lead.name, lead.user_id.display_name, "day5_redistribute", new_sdr.display_name, mode])

        report_user = self._get_lead_distribution_report_user()
        filename = "sgc_follow_up_escalation_%s_%s.csv" % (mode, fields.Date.today().isoformat())
        attachment = self.env["ir.attachment"].sudo().create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(buf.getvalue().encode("utf-8")),
            "res_model": "res.users",
            "res_id": report_user.id,
            "mimetype": "text/csv",
        })
        _logger.info(
            "SGC follow-up escalation CSV written: ir.attachment id=%d, "
            "name=%s, attached to res.users id=%d (%s).",
            attachment.id, filename, report_user.id, report_user.display_name,
        )
        return attachment

    @api.model
    def _cron_follow_up_stage_escalation(self):
        """3-step Follow Up stage discipline, thresholds counted in
        BUSINESS days (Mon-Fri) of pure stage dwell (date_last_stage_update)
        — the same dwell measure already used by every other timer in this
        file (_cron_weekly_gate_review, _cron_dead_lead_cleanup):

        - Business day 2+: notification (email + Odoo activity) to the
          assigned salesperson. Idempotent per lead via
          FOLLOW_UP_DAY2_ESCALATION_SUMMARY.
        - Business day 4+: final warning (email + Odoo activity).
          Idempotent via FOLLOW_UP_DAY4_ESCALATION_SUMMARY.
        - Business day 5+: redistributed to a RANDOM different SDR — the
          same pool as the daily lead-distribution cron (see
          _get_lead_distribution_sdr_users: Sales team minus team leader
          minus Administrator), explicitly excluding the lead's own
          current owner so it always actually changes hands — and moved
          back to the "New" stage (reusing the same stage config as the
          distribution cron). This exits the Follow Up search domain, so
          it can never re-trigger.

        Highest threshold wins per lead per run (day5 check first, then
        day4, then day2): if the cron was disabled for a stretch and a
        lead jumps straight past an earlier threshold, it's redistributed
        rather than sent a now-pointless day-2 notification.

        Runs daily via ir.cron but no-ops on Saturday/Sunday — thresholds
        are business-day counted, so nothing changes over the weekend to
        check.

        Defaults to DRY RUN via
        'sgc_sales_playbook.follow_up_escalation_mode' — writes a
        reviewable CSV, sends no email, creates no activity, reassigns
        nothing. Flip to 'live' only after reviewing the CSV.
        """
        today = fields.Date.today()
        if today.weekday() >= 5:  # 5=Saturday, 6=Sunday
            _logger.info(
                "SGC follow-up escalation: skipped, %s is a weekend.", today.isoformat()
            )
            return

        stage = self._get_follow_up_stage()
        if not stage:
            _logger.warning(
                "SGC follow-up escalation: configured follow_up_stage_id "
                "does not resolve to a crm.stage record. Skipping this run."
            )
            return

        mode = self._get_follow_up_escalation_mode()
        day2 = self._get_follow_up_threshold("day2", int(DEFAULT_FOLLOW_UP_DAY2_THRESHOLD))
        day4 = self._get_follow_up_threshold("day4", int(DEFAULT_FOLLOW_UP_DAY4_THRESHOLD))
        day5 = self._get_follow_up_threshold("day5", int(DEFAULT_FOLLOW_UP_DAY5_THRESHOLD))
        batch_limit = self._get_follow_up_escalation_batch_limit()

        leads = self.search(
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("stage_id", "=", stage.id),
                ("date_last_stage_update", "!=", False),
            ],
            limit=batch_limit,
            order="date_last_stage_update asc",
        )

        new_stage = self._get_lead_distribution_stage()

        day2_notified = self.env["crm.lead"]
        day4_warned = self.env["crm.lead"]
        day5_redistributed = []  # [(lead, new_sdr), ...]

        for lead in leads:
            elapsed = self._business_days_elapsed(lead.date_last_stage_update, today)
            if elapsed >= day5:
                if not new_stage:
                    continue
                pool = self._get_lead_distribution_sdr_users() - lead.user_id
                if not pool:
                    continue
                new_sdr = pool[random.randrange(len(pool))]
                day5_redistributed.append((lead, new_sdr))
            elif elapsed >= day4:
                already_warned = self.env["mail.activity"].search_count([
                    ("res_model", "=", "crm.lead"),
                    ("res_id", "=", lead.id),
                    ("summary", "=", FOLLOW_UP_DAY4_ESCALATION_SUMMARY),
                ])
                if not already_warned:
                    day4_warned |= lead
            elif elapsed >= day2:
                already_notified = self.env["mail.activity"].search_count([
                    ("res_model", "=", "crm.lead"),
                    ("res_id", "=", lead.id),
                    ("summary", "=", FOLLOW_UP_DAY2_ESCALATION_SUMMARY),
                ])
                if not already_notified:
                    day2_notified |= lead

        self._follow_up_escalation_write_report_csv(day2_notified, day4_warned, day5_redistributed, mode)

        if mode == "dry_run":
            _logger.info(
                "SGC follow-up escalation DRY RUN: would notify %d (day "
                "%d+), warn %d (day %d+), redistribute %d (day %d+). Set "
                "sgc_sales_playbook.follow_up_escalation_mode='live' to "
                "enable after reviewing the CSV.",
                len(day2_notified), day2, len(day4_warned), day4,
                len(day5_redistributed), day5,
            )
            return

        todo = self.env.ref("mail.mail_activity_data_todo")
        for lead in day2_notified:
            self._send_follow_up_escalation(
                lead, todo, FOLLOW_UP_DAY2_ESCALATION_SUMMARY,
                _("Follow Up Stalled (Day %d+): please action") % day2,
                _(
                    "'%(name)s' has been in Follow Up for %(days)d+ "
                    "business days without moving. Please action it today."
                ) % {"name": lead.name, "days": day2},
            )
        for lead in day4_warned:
            self._send_follow_up_escalation(
                lead, todo, FOLLOW_UP_DAY4_ESCALATION_SUMMARY,
                _("FINAL WARNING: Follow Up Stalled (Day %d+)") % day4,
                _(
                    "'%(name)s' has been in Follow Up for %(days)d+ "
                    "business days without moving. It will be "
                    "redistributed to another SDR on day %(day5)d if not "
                    "actioned."
                ) % {"name": lead.name, "days": day4, "day5": day5},
            )

        for lead, new_sdr in day5_redistributed:
            old_owner = lead.user_id
            lead.message_post(body=_(
                "Auto-redistributed by SGC follow-up escalation: stalled "
                "%(days)d+ business days in Follow Up with no action. "
                "Reassigned from %(old)s to %(new)s and moved back to "
                "%(stage)s."
            ) % {
                "days": day5,
                "old": old_owner.display_name,
                "new": new_sdr.display_name,
                "stage": new_stage.display_name,
            })
            lead.write({"user_id": new_sdr.id, "stage_id": new_stage.id})

        _logger.info(
            "SGC follow-up escalation: notified %d, warned %d, "
            "redistributed %d.",
            len(day2_notified), len(day4_warned), len(day5_redistributed),
        )
