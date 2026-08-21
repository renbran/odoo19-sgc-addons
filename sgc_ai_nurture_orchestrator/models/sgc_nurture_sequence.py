# -*- coding: utf-8 -*-
"""sgc.nurture.sequence -- the orchestration container for one lead's
5-touch nurture run.

Design note (see PLAN.md / the nurture-orchestration-plan artifact for the
full architecture): this file implements the whole engine -- business-hours
scheduling, AI drafting, deterministic validation, a centralized stop/pause
matrix, and real sending on both WhatsApp and email -- but nothing in it
runs on a timer. There is no cron anywhere in this module. Every step is a
person clicking a button:

    crm.lead.action_start_nurture()        creates the sequence
    action_draft_next_touch()              generates ONE draft, stores it,
                                            sends nothing
    action_send_drafted_touch()            sends exactly that draft for
                                            real (whatsmeow.message /
                                            mail.mail), only after a person
                                            has seen it

`next_touch_at` is informational only -- "not before this time" for the
next draft -- never a trigger. Nothing polls it. A previous build of this
module had `_enroll_pending_leads`/`_cron_process_due` wired to 15-minute
crons; that was deliberately removed. Keep it that way -- see the
`sgc_ai_nurture_orchestrator` README for why.

Centralized stop/pause matrix (`_evaluate_stop_conditions`) -- the table
this method implements:

    event                          outcome
    -----                          -------
    WhatsApp reply                 stop -> responded
    Email reply                    stop -> responded
    Meeting booked                 stop -> responded  (booking IS the win)
    Lead marked Won                stop -> stopped
    Lead marked Lost / archived    stop -> stopped
    Partner opted out (WhatsApp)   stop -> opted_out
    Manual stop (manager)          stop -> stopped
    Manual pause (manager)         pause -> paused

Known gaps, not wired in this build (no reliable signal source yet -- listed
here instead of silently omitted):
    * a WhatsApp number whatsmeow's own `cron_check_numbers` has confirmed
      isn't registered falls back to email at channel-resolution time
      (`_resolve_channel` / `_is_whatsapp_number_invalid`) rather than
      stopping the sequence -- that's deliberate, not a gap. What's still
      missing is email bounce detection: no `mail.mail` failure-state
      wiring exists here, so a bouncing address just silently exhausts.
    * duplicate-lead detection -- no dedup model exists in this codebase.
    * "existing active conversation" -- would need to check whatsmeow_discuss
      channel state, not implemented here.
    * manual reassignment of the lead's salesperson mid-sequence -- not
      currently treated as a stop signal; arguably should pause, not stop,
      since a human taking the lead isn't the same as the lead going cold.

Handoff on response is intentionally *not* automatic in this build. The
architecture review that shaped this module explicitly rejected routing a
responsive lead by leaderboard score alone -- that score has no
availability, workload, or specialization signal, so a naive weighted draw
would just keep pointing the top performer at hot leads until they drown.
`_select_handoff_sdr` documents the intended Phase-4 formula but is not
called from `_evaluate_stop_conditions`; a response instead creates an
urgent activity for the lead's *current* owner. Wire the real handoff once
workload/capacity fields exist to weight against.
"""
import logging
import re
from datetime import timedelta

import pytz
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import config as odoo_config
from odoo.tools.mail import email_normalize

_logger = logging.getLogger(__name__)

BUSINESS_TZ = "Asia/Dubai"
# Sunday=6, Monday=0 ... Saturday=5 in Python's weekday(); UAE work week is
# Sun-Thu, confirmed for this build rather than assumed.
BUSINESS_WEEKDAYS = {6, 0, 1, 2, 3}  # Sun, Mon, Tue, Wed, Thu
BUSINESS_START_HOUR = 9
BUSINESS_END_HOUR = 18

MAX_TOUCHES = 5
ENGAGEMENT_FAST_DELAY = timedelta(days=1)
ENGAGEMENT_SLOW_DELAY = timedelta(days=2)
# How recent last_engagement_at must be, relative to the touch that's about
# to go out, to count as "engaged since" for the 1-day gap (PLAN §05).
ENGAGEMENT_LOOKBACK = timedelta(days=3)

# Deterministic guardrails a draft must clear before a person is even shown
# it for review (PLAN §08/§09). Semantic checks (tone, hallucination) are Phase 5
# LLM-validator territory and out of scope here -- these are the checks that
# don't need a second model call to get right.
_FORBIDDEN_PATTERNS = [
    (re.compile(r"\bas an ai\b", re.I), "self-identifies as an AI in a way that reads as a disclosure dodge"),
    (re.compile(r"\bi am (?:an? )?(?:language model|chatbot|bot)\b", re.I), "self-identifies as a bot"),
    (re.compile(r"\bguarantee(?:d)?\b", re.I), "makes a guarantee claim"),
    (re.compile(r"\b100%\s*(?:certain|guaranteed|sure)\b", re.I), "makes an absolute certainty claim"),
    (re.compile(r"\bi (?:called|spoke to|met with|discussed with) you\b", re.I), "claims a contact event that may not have happened"),
]
# A bare currency figure the draft invented -- the lead's own price fields
# are never interpolated into the prompt, so any AED/USD/$ amount in the
# output was hallucinated, not sourced.
_CURRENCY_RE = re.compile(r"(?:AED|USD|\$)\s?[\d,]+(?:\.\d+)?", re.I)


class SgcNurtureSequence(models.Model):
    _name = "sgc.nurture.sequence"
    _description = "SGC Nurture Sequence"
    _inherit = ["mail.thread"]
    _order = "id desc"

    lead_id = fields.Many2one(
        "crm.lead", required=True, index=True, ondelete="cascade",
        tracking=True,
    )
    trigger_activity_id = fields.Many2one(
        "mail.activity",
        help="The gating activity that enrolled this lead. May be empty by "
             "the time the sequence finishes -- the activity itself gets "
             "closed out on stop.",
    )
    sequence_type = fields.Char(
        default="proposal_stall",
        help="Which CRM rule fed this enrollment. Only one value exists in "
             "v1 (sgc_proposal_nurture's 3-day Proposal-stall flag); this "
             "is a string, not a selection, so a future gate doesn't need "
             "a schema change to register a new type.",
    )

    status = fields.Selection(
        [
            ("scheduled", "Scheduled"),
            ("active", "Active"),
            ("paused", "Paused"),
            ("responded", "Responded"),
            ("handed_off", "Handed Off"),
            ("exhausted", "Exhausted"),
            ("stopped", "Stopped"),
            ("opted_out", "Opted Out"),
        ],
        default="scheduled", required=True, tracking=True, index=True,
    )
    dry_run = fields.Boolean(
        default=False, tracking=True,
        help="Per-sequence safety override, off by default. When True, "
             "action_send_drafted_touch still requires the same explicit "
             "click but stops short of creating a real whatsmeow.message or "
             "mail.mail -- useful for a manager testing the flow on a real "
             "lead without a real message reaching them.",
    )

    current_touch = fields.Integer(default=0)
    max_touches = fields.Integer(default=MAX_TOUCHES)
    next_touch_at = fields.Datetime(index=True)
    last_touch_at = fields.Datetime()
    last_engagement_at = fields.Datetime()
    engagement_state = fields.Selection(
        [("none", "None"), ("weak", "Weak"), ("strong", "Strong")],
        default="none",
        help="Weak = a read/open (attention). Strong = a reply or a click "
             "on a booking/proposal link (intent). Only strong engagement "
             "stops the sequence outright; weak engagement just shortens "
             "the next delay to 1 day (PLAN §04).",
    )

    assigned_sdr_id = fields.Many2one("res.users", tracking=True)
    handoff_at = fields.Datetime()

    stopped_reason = fields.Char()
    stop_event = fields.Selection(
        [
            ("wa_reply", "WhatsApp Reply"),
            ("email_reply", "Email Reply"),
            ("meeting_booked", "Meeting Booked"),
            ("won", "Opportunity Won"),
            ("lost", "Opportunity Lost / Archived"),
            ("opted_out", "Opted Out"),
            ("manual_stop", "Manual Stop"),
            ("exhausted", "Touches Exhausted"),
        ],
    )

    pause_until = fields.Datetime()
    pause_reason = fields.Char()
    paused_by = fields.Many2one("res.users")

    touch_ids = fields.One2many("sgc.nurture.touch", "sequence_id")
    touch_count = fields.Integer(compute="_compute_touch_count")
    has_pending_draft = fields.Boolean(
        compute="_compute_has_pending_draft",
        help="A touch is drafted and waiting for 'Send This Touch' to be "
             "clicked. Drives button visibility -- purely a UI convenience, "
             "action_send_drafted_touch re-checks this for real.",
    )

    company_id = fields.Many2one(
        related="lead_id.company_id", store=True, readonly=True,
    )
    active = fields.Boolean(default=True)

    # NOTE: there is deliberately no DB constraint here enforcing "one live
    # sequence per lead". That needs a partial unique index (UNIQUE ...
    # WHERE status IN ('scheduled','active','paused')), which Odoo's
    # models.Constraint can't express -- it only emits a plain ALTER TABLE
    # ... ADD CONSTRAINT, no WHERE clause. crm.lead.action_start_nurture
    # checks nurture_eligible before creating instead (best-effort, no row
    # lock -- acceptable given enrollment is now one person clicking one
    # button, not a cron sweeping many leads at once).
    _current_touch_within_bounds = models.Constraint(
        "CHECK (current_touch >= 0 AND current_touch <= max_touches)",
        "current_touch must stay within 0..max_touches.",
    )

    @api.depends("touch_ids")
    def _compute_touch_count(self):
        for seq in self:
            seq.touch_count = len(seq.touch_ids)

    @api.depends("touch_ids.delivery_status", "touch_ids.touch_number", "current_touch")
    def _compute_has_pending_draft(self):
        for seq in self:
            seq.has_pending_draft = bool(seq.touch_ids.filtered(
                lambda t: t.touch_number == seq.current_touch + 1
                and t.delivery_status == "drafted"))

    # -- business hours ------------------------------------------------------
    @api.model
    def _get_next_business_datetime(self, dt=None):
        """The next moment `dt` (naive UTC, Odoo's storage convention) lands
        inside Sun-Thu 09:00-18:00 Asia/Dubai. If `dt` already qualifies, it
        is returned unchanged (not bumped to a boundary) -- callers add their
        own delay on top of this before calling in again.
        """
        tz = pytz.timezone(BUSINESS_TZ)
        moment_utc = pytz.utc.localize(dt or fields.Datetime.now())
        local = moment_utc.astimezone(tz)

        for _hop in range(14):  # a week+ of daily hops is always enough
            if local.weekday() in BUSINESS_WEEKDAYS:
                start = local.replace(hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0)
                end = local.replace(hour=BUSINESS_END_HOUR, minute=0, second=0, microsecond=0)
                if local < start:
                    local = start
                    break
                if local <= end:
                    break
                # Past today's window: fall through to next-day scan below.
            local = (local + timedelta(days=1)).replace(
                hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0,
            )
            if local.weekday() in BUSINESS_WEEKDAYS:
                break

        return local.astimezone(pytz.utc).replace(tzinfo=None)

    def _sgc_commit(self):
        """No-op under --test-enable: a real commit() there would break the
        test runner's rollback-at-the-end transaction. `Registry.in_test_mode()`
        doesn't exist in this Odoo version -- `config['test_enable']` is the
        real process-wide marker (same landmine sgc_ai_job._sgc_commit
        already documents; reused here rather than rediscovered).
        """
        if odoo_config["test_enable"]:
            return
        self.env.cr.commit()

    def _sgc_rollback(self):
        if odoo_config["test_enable"]:
            return
        self.env.cr.rollback()

    # -- drafting (manual trigger only) ----------------------------------------
    def _resolve_channel(self, touch_number):
        self.ensure_one()
        plan = self.env["sgc.nurture.touch"]._plan_for(touch_number)
        if not plan:
            return None, None
        channel, intent = plan
        wa_invalid = self._is_whatsapp_number_invalid()
        if channel == "whatsapp" and wa_invalid:
            channel = "email"
        if channel != "auto":
            return channel, intent

        # Touch 5: prefer whichever channel actually saw engagement.
        wa_engaged = self.touch_ids.filtered(
            lambda t: t.channel == "whatsapp" and t.engagement_status != "none")
        email_engaged = self.touch_ids.filtered(
            lambda t: t.channel == "email" and t.engagement_status != "none")
        if wa_engaged and not email_engaged and not wa_invalid:
            return "whatsapp", intent
        if email_engaged and not wa_engaged:
            return "email", intent
        # Both or neither: WhatsApp is the lower-friction close (PLAN §12),
        # unless it's already known-bad for this contact.
        return ("email" if wa_invalid else "whatsapp"), intent

    def action_draft_next_touch(self):
        """The only place a draft gets generated -- a person clicking
        "Draft Next Touch". Never sends anything; a draft sits at
        delivery_status='drafted' until action_send_drafted_touch is
        separately clicked. Re-drafting an already-drafted (not yet sent)
        touch is allowed -- it just regenerates that same touch_number's row
        rather than advancing past it.
        """
        self.ensure_one()
        should_stop, reason, event = self._evaluate_stop_conditions()
        if should_stop:
            self._apply_stop(reason, event)
            raise UserError(self.env._(
                "This sequence just stopped instead of drafting: %s", reason))

        touch_number = self.current_touch + 1
        if touch_number > self.max_touches:
            self._apply_stop(self.env._("All touches sent with no response."), "exhausted")
            raise UserError(self.env._("All %s touches are already used.", self.max_touches))

        channel, intent = self._resolve_channel(touch_number)
        if not channel:
            raise UserError(self.env._("No touch plan for touch %s.", touch_number))

        # Re-drafting reuses the same row (touch_number is unique per
        # sequence) rather than creating a second one.
        touch = self.touch_ids.filtered(lambda t: t.touch_number == touch_number)
        vals = {"channel": channel, "intent": intent, "scheduled_at": fields.Datetime.now()}
        if touch:
            touch.write(vals)
        else:
            touch = self.env["sgc.nurture.touch"].create({
                "sequence_id": self.id, "touch_number": touch_number, **vals,
            })

        try:
            body = self._generate_body(touch_number, channel, intent)
        except Exception as err:
            _logger.exception("Nurture sequence %s: draft generation failed", self.id)
            touch.write({
                "delivery_status": "failed",
                "failure_reason": str(err)[:500],
                "drafted_at": fields.Datetime.now(),
            })
            raise UserError(self.env._("Draft generation failed: %s", str(err)[:300])) from err

        ok, block_reason = self._validate_draft(body, channel)
        touch.write({
            "body": body,
            "drafted_at": fields.Datetime.now(),
            "generation_model": self._llm_provider_name(),
        })

        if not ok:
            touch.write({
                "delivery_status": "validation_blocked",
                "failure_reason": block_reason,
            })
            self.message_post(body=(
                f"Touch {touch_number} draft BLOCKED by validation: "
                f"{block_reason}\n\nDraft was:\n{body}"
            ))
            raise UserError(self.env._(
                "Draft was blocked by validation: %s", block_reason))

        touch.delivery_status = "drafted"
        self.message_post(body=(
            f"Touch {touch_number}/{self.max_touches} drafted ({channel}). "
            f"Awaiting review -- use \"Send This Touch\" to actually send "
            f"it:\n\n{body}"
        ))
        return touch

    def action_send_drafted_touch(self):
        """The only place a real WhatsApp message or email gets created --
        a person clicking "Send This Touch" after reading the draft
        action_draft_next_touch produced. Re-checks the stop matrix first:
        a lead can close, get lost, or reply in the time between drafting
        and sending.
        """
        self.ensure_one()
        touch_number = self.current_touch + 1
        touch = self.touch_ids.filtered(
            lambda t: t.touch_number == touch_number and t.delivery_status == "drafted")
        if not touch:
            raise UserError(self.env._(
                "No drafted touch waiting to send. Use \"Draft Next Touch\" first."))

        should_stop, reason, event = self._evaluate_stop_conditions()
        if should_stop:
            self._apply_stop(reason, event)
            raise UserError(self.env._(
                "This sequence just stopped instead of sending: %s", reason))

        if self.dry_run:
            touch.delivery_status = "skipped_dry_run"
            self.message_post(body=self.env._(
                "Touch %s marked sent (dry-run override on this sequence -- "
                "nothing actually left the building).", touch_number))
        else:
            try:
                if touch.channel == "whatsapp":
                    self._send_whatsapp(touch)
                else:
                    self._send_email(touch)
            except UserError:
                raise
            except Exception as err:
                _logger.exception("Nurture sequence %s: send failed", self.id)
                touch.write({"delivery_status": "failed", "failure_reason": str(err)[:500]})
                raise UserError(self.env._("Send failed: %s", str(err)[:300])) from err

            touch.write({"delivery_status": "sent", "sent_at": fields.Datetime.now()})
            self.message_post(body=self.env._(
                "Touch %s/%s sent via %s by %s.",
                touch_number, self.max_touches, touch.channel, self.env.user.name))

        self._advance_after_touch(touch_number, engaged=self._is_recently_engaged())
        return touch

    # -- real sending -----------------------------------------------------------
    def _send_whatsapp(self, touch):
        """Creates a real, queued whatsmeow.message -- state defaults to
        'outgoing', so whatsmeow's own cron_process_outgoing (unrelated to
        this module, always-on) picks it up with its existing pacing,
        retry, and opt-out enforcement. This method never calls a gateway
        directly; it only ever creates the row whatsmeow already knows how
        to send safely (PLAN §11.3 -- see whatsmeow_composer.py for the
        exact same pattern this mirrors).
        """
        self.ensure_one()
        lead = self.lead_id
        digits = re.sub(r"\D", "", lead.phone or lead.mobile or
                         lead.partner_id.phone or lead.partner_id.mobile or "")
        if not digits:
            raise UserError(self.env._("This lead has no phone number to WhatsApp."))

        Message = self.env["whatsmeow.message"]
        partner = Message._find_partner(digits)
        session = self.env["whatsmeow.session"].search(
            [("status", "=", "connected")], order="id", limit=1)
        if not session:
            raise UserError(self.env._("No connected WhatsApp session to send from."))

        message = Message.create({
            "session_id": session.id,
            "direction": "out",
            "phone": digits,
            "partner_id": partner.id if partner else False,
            "message_type": "text",
            "body": touch.body,
        })
        touch.whatsmeow_message_id = message.id

    def _send_email(self, touch):
        """Creates a real, queued mail.mail -- state 'outgoing' is the
        default, so the existing "Mail: Email Queue Manager" cron (unrelated
        to this module, always-on) sends it on its own schedule. Checked
        against mail.blacklist first since that list exists precisely to
        stop exactly this kind of automated outbound mail.
        """
        self.ensure_one()
        lead = self.lead_id
        to_email = lead.email_from
        if not to_email:
            raise UserError(self.env._("This lead has no email address."))
        normalized = email_normalize(to_email)
        if normalized and self.env["mail.blacklist"].sudo().search_count(
                [("email", "=", normalized)]):
            raise UserError(self.env._("%s is on the mail blacklist.", to_email))

        from_email = (lead.user_id.email if lead.user_id else False) or self.env.company.email
        mail = self.env["mail.mail"].sudo().create({
            "subject": self.env._("Following up -- %s", lead.partner_name or lead.name),
            "body_html": Markup("<p>%s</p>") % touch.body.replace("\n", "<br/>"),
            "email_to": to_email,
            "email_from": from_email,
            "model": "crm.lead",
            "res_id": lead.id,
            "auto_delete": False,
        })
        touch.mail_message_id = mail.id

    def _is_recently_engaged(self):
        """Whether `last_engagement_at` is recent enough to count as
        "engaged since" for the 1-day gap (PLAN §05) -- engagement_state
        alone doesn't decay, so a reply from 3 weeks ago must not still be
        shortening every future delay.
        """
        self.ensure_one()
        if not self.last_engagement_at:
            return False
        return self.last_engagement_at >= fields.Datetime.now() - ENGAGEMENT_LOOKBACK

    def _advance_after_touch(self, touch_number, engaged):
        """Advances the counter and computes an informational
        next_touch_at -- "not before this time" for whoever clicks "Draft
        Next Touch" next. Nothing polls this field; there is no cron.
        """
        self.ensure_one()
        delay = ENGAGEMENT_FAST_DELAY if engaged else ENGAGEMENT_SLOW_DELAY
        self.write({
            "current_touch": touch_number,
            "last_touch_at": fields.Datetime.now(),
            "next_touch_at": self._get_next_business_datetime(
                fields.Datetime.now() + delay),
        })

    def _llm_provider_name(self):
        provider = self.env["llm.provider"].get_default_provider()
        return provider.name if provider else False

    def _generate_body(self, touch_number, channel, intent):
        self.ensure_one()
        provider = self.env["llm.provider"].get_default_provider()
        if not provider:
            raise UserError(self.env._("No default llm.provider is configured."))
        prompt = self._build_prompt(touch_number, channel, intent)
        return provider._make_request(prompt).strip()

    def _build_prompt(self, touch_number, channel, intent):
        self.ensure_one()
        lead = self.lead_id
        prior = "\n".join(
            f"  Touch {t.touch_number} ({t.channel}): {t.body or '(blocked/failed, no body)'}"
            for t in self.touch_ids.sorted("touch_number")
            if t.touch_number < touch_number
        ) or "  (none -- this is the first touch)"

        # sgc_sales_playbook's 4 gate questions, when answered, are the
        # closest thing to real BANT this codebase has -- reuse them
        # verbatim rather than inventing a parallel field set.
        gate = []
        for fname, label in (
            ("x_gate_problem", "Problem"),
            ("x_gate_cost_of_inaction", "Cost of inaction"),
            ("x_gate_approver", "Approver"),
            ("x_gate_timeline", "Timeline"),
        ):
            value = getattr(lead, fname, False)
            if value:
                gate.append(f"  {label}: {value}")
        gate_block = "\n".join(gate) or "  (gate questions not yet answered)"

        objection_block = "  (none logged)"
        objections = getattr(lead, "x_objection_ids", self.env["sgc.lead.objection"])
        if objections:
            objection_block = "\n".join(
                f"  {o.objection_type or 'objection'}: {o.reframe_used or '(no reframe logged)'}"
                for o in objections
            )

        return f"""You are drafting ONE {channel} message for an SGC Tech AI sales
follow-up sequence. This is touch {touch_number} of {self.max_touches} for this lead.
Touch intent: {intent}.

Lead: {lead.contact_name or lead.partner_name or 'the contact'}
Company: {lead.partner_name or 'unknown'}
CRM stage: {lead.stage_id.name or 'unknown'}

Qualification gate answers on file:
{gate_block}

Objections logged for this lead (use for the "reframe" touch if relevant):
{objection_block}

Prior touches already sent in this sequence:
{prior}

Write the {channel} message body only -- no subject line, no explanation,
no markdown formatting, no placeholder brackets.

Hard rules, do not violate any of them:
- Do not invent a price, discount, or dollar/AED figure of any kind.
- Do not invent a case study, client name, or specific result.
- Do not invent a product capability not implied by the notes above.
- Do not promise a specific implementation or delivery date.
- Do not claim a call, meeting, or conversation happened if it isn't in the
  prior touches above.
- Do not describe yourself as an AI, a bot, or a language model.
- Do not use the word "guarantee" or claim 100% certainty about anything.
- Keep it short: 2-4 sentences for WhatsApp, under 120 words for email.
- End with a low-pressure next step, not a hard close.
"""

    # -- validation -----------------------------------------------------------
    def _validate_draft(self, body, channel):
        """Deterministic checks only (PLAN §09) -- semantic/tone checking
        via a second LLM call is Phase 5, not implemented here.
        """
        if not body or not body.strip():
            return False, "Empty draft."
        if len(body) > 4000:
            return False, "Draft implausibly long -- likely a generation error."
        for pattern, description in _FORBIDDEN_PATTERNS:
            if pattern.search(body):
                return False, f"Forbidden content: {description}."
        if _CURRENCY_RE.search(body):
            return False, "Draft contains an unsourced currency figure."
        recent_cutoff = fields.Datetime.now() - timedelta(days=2)
        duplicate = self.touch_ids.filtered(
            lambda t: t.body and t.body.strip() == body.strip()
            and t.drafted_at and t.drafted_at >= recent_cutoff
        )
        if duplicate:
            return False, "Identical to a recently drafted touch."
        return True, None

    # -- engagement -----------------------------------------------------------
    def _register_engagement(self, strength, at=None):
        """strength: 'weak' (open/read) or 'strong' (reply/click-to-book).
        Strong engagement is handled by `_evaluate_stop_conditions` on the
        next cron pass (a reply is also a stop event, not just a signal);
        this method only updates the tracking fields both paths share.
        """
        self.ensure_one()
        at = at or fields.Datetime.now()
        if self.engagement_state != "strong":
            self.engagement_state = strength
        self.last_engagement_at = at

    # -- stop / pause matrix ---------------------------------------------------
    def _evaluate_stop_conditions(self):
        """Returns (should_stop, reason, event_code). See the module
        docstring for the full table and the gaps this build doesn't cover.
        Checked both before drafting a touch (cron path) and from inbound
        hooks (reply/meeting/won/lost), so it must be cheap and read-only.
        """
        self.ensure_one()
        lead = self.lead_id

        if not lead.active:
            if lead.lost_reason_id:
                return True, f"Lead marked Lost ({lead.lost_reason_id.name}).", "lost"
            return True, "Lead archived.", "lost"

        if lead.stage_id.is_won:
            return True, "Opportunity marked Won.", "won"

        if self._is_partner_opted_out():
            return True, "Contact has opted out of WhatsApp.", "opted_out"

        return False, None, None

    def _is_partner_opted_out(self):
        self.ensure_one()
        partner = self.lead_id.partner_id
        if not partner or "whatsmeow_optout" not in partner._fields:
            return False
        return bool(partner.whatsmeow_optout)

    def _is_whatsapp_number_invalid(self):
        """True once whatsmeow's own `cron_check_numbers` has confirmed the
        contact's number isn't on WhatsApp. This doesn't stop the sequence
        outright (email may still work) -- callers use it to keep touch
        planning off WhatsApp for this lead, not to fill the "invalid phone"
        gap in the module docstring, which is about not knowing a number is
        bad *before* whatsmeow has had a chance to check it.
        """
        self.ensure_one()
        partner = self.lead_id.partner_id
        if not partner or "whatsmeow_registered" not in partner._fields:
            return False
        return partner.whatsmeow_registered == "no"

    def _apply_stop(self, reason, event_code):
        self.ensure_one()
        status = {
            "won": "stopped", "lost": "stopped", "opted_out": "opted_out",
            "wa_reply": "responded", "email_reply": "responded",
            "meeting_booked": "responded", "manual_stop": "stopped",
            "exhausted": "exhausted",
        }.get(event_code, "stopped")

        self.write({
            "status": status,
            "stopped_reason": reason,
            "stop_event": event_code,
            "next_touch_at": False,
        })
        self.message_post(body=f"Nurture sequence stopped: {reason}")

        if self.trigger_activity_id.exists():
            self.trigger_activity_id.action_feedback(feedback=reason)

        if status == "responded":
            self._create_response_handoff_activity()

    def _create_response_handoff_activity(self):
        """Phase 0: no automatic reassignment -- see the module docstring
        for why. Just makes sure the current owner can't miss it.
        """
        self.ensure_one()
        lead = self.lead_id
        self.env["mail.activity"].create({
            "res_model_id": self.env["ir.model"]._get_id("crm.lead"),
            "res_id": lead.id,
            "activity_type_id": self.env.ref("mail.mail_activity_data_todo").id,
            "summary": "Lead responded to nurture -- follow up now",
            "note": f"Nurture sequence #{self.id} stopped: {self.stopped_reason}",
            "user_id": lead.user_id.id or self.env.uid,
            "date_deadline": fields.Date.today(),
        })

    def _select_handoff_sdr(self):
        """Not called anywhere in this build -- see the module docstring
        and README for why. Documents the intended Phase-4 formula so the
        next person to wire real handoff isn't starting from a blank page:

            assignment_weight = performance_score
                                 * availability_factor
                                 * workload_factor
                                 * specialization_factor

        `performance_score` already exists (`sgc_crm_dashboard`'s
        `get_leaderboard_mini` scoring: meetings_booked * 50 +
        proposal_pipeline_value / 1000). `availability_factor` needs a
        working-hours + approved-leave check against `crm.team.member`.
        `workload_factor` needs a count of each rep's currently-open
        responsive/hot leads (this model's own `assigned_sdr_id` becomes
        that source once handoff is live) so a top performer already
        drowning in hot leads doesn't keep absorbing more. No
        `specialization_factor` signal exists in this codebase yet (no
        lead-type/vertical tagging on crm.team.member).

        Once those three factors have real data behind them, a weighted
        random draw across eligible SDRs (not a strict top-1 pick) is the
        mechanism -- not implemented here.
        """
        raise NotImplementedError(
            "Handoff routing is not active in this build -- see docstring."
        )

    # -- manager overrides (PLAN §16) -----------------------------------------
    def action_pause(self, reason=None, until=None):
        for seq in self:
            seq.write({
                "status": "paused",
                "pause_reason": reason or self.env._("Paused by %s", self.env.user.name),
                "pause_until": until,
                "paused_by": self.env.uid,
            })
            seq.message_post(body=f"Paused: {seq.pause_reason}")

    def action_resume(self):
        for seq in self:
            if seq.status != "paused":
                continue
            seq.write({
                "status": "active",
                "pause_until": False,
                "next_touch_at": seq._get_next_business_datetime(),
            })
            seq.message_post(body="Resumed by " + self.env.user.name)

    def action_stop(self, reason=None):
        for seq in self:
            seq._apply_stop(
                reason or self.env._("Stopped by %s", self.env.user.name),
                "manual_stop",
            )

    @api.model
    def _cron_gc_stale(self):
        """Housekeeping only -- terminal sequences older than 90 days lose
        their `active` flag so they stop cluttering default list views.
        Never unlinked: touch history is the audit trail (PLAN §10/§18).
        """
        cutoff = fields.Datetime.now() - timedelta(days=90)
        stale = self.search([
            ("active", "=", True),
            ("status", "in", ("exhausted", "stopped", "opted_out", "handed_off")),
            ("write_date", "<", cutoff),
        ])
        stale.write({"active": False})
