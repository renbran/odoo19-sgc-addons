# SGC - AI Nurture Orchestrator

Automates what `sgc_proposal_nurture` currently only flags for a human to
do by hand: an AI-drafted WhatsApp + email touch sequence for a lead,
gated entirely behind an assigned activity -- and behind an explicit
person clicking a button at every step.

## Nothing runs on a timer

There is no cron in this module that sweeps leads or sequences. Every
step is a person clicking a button, full stop:

1. **Start Nurture Sequence** (button on the lead form, visible only when
   `sgc_proposal_nurture`'s 3-day-stalled flag is set) -- creates the
   `sgc.nurture.sequence`. Drafts nothing.
2. **Draft Next Touch** (button on the sequence) -- generates ONE AI
   draft, runs it through deterministic validation, stores it. Sends
   nothing. The counter does not advance.
3. **Send This Touch** (button on the sequence, confirmation dialog) --
   sends exactly the draft a person just read: creates a real
   `whatsmeow.message` (WhatsApp) or `mail.mail` (email) row. Only now
   does the counter advance and `next_touch_at` update.

`next_touch_at` is informational only -- "not before this time" for the
next draft. Nothing polls it, nothing acts on it automatically.

An earlier version of this module had `_enroll_pending_leads`/
`_cron_process_due` wired to 15-minute crons that swept every eligible
lead automatically. That was deliberately removed after review -- keep it
removed. If you're tempted to re-add a cron here, don't; add a manual
"process my queue" button instead.

## Real sending

`_send_whatsapp` creates a `whatsmeow.message` row (state `outgoing`) and
lets whatsmeow's own always-on `cron_process_outgoing` handle pacing,
retries, and opt-out enforcement -- this module never talks to the
gateway directly. `_send_email` creates a `mail.mail` row (state
`outgoing`, checked against `mail.blacklist` first) and lets Odoo's own
"Mail: Email Queue Manager" cron send it. Both of those crons are
pre-existing, always-on infrastructure this module reuses rather than
duplicates -- they are not part of this module and are not disabled by
anything here.

A per-sequence `dry_run` boolean (default off) lets a manager test the
draft/send button flow on a real lead without a real message reaching
them -- "Send This Touch" still requires the same click, it just stops
short of creating the real message/mail row.

## Audit trail on the lead itself

Every touch-point (`action_start_nurture`, a draft, a blocked/failed draft,
a real send, a failed send, a stop/pause/resume) is logged twice: a full
`message_post` on the `sgc.nurture.sequence` record (for anyone drilling in
via the "Nurture" smart button), and an internal log note
(`_message_log`, `sgc.nurture.sequence._log_to_lead`) posted directly onto
the **lead's own chatter**. The second one is what makes this visible to a
salesperson/SDR who never opens the sequence record at all -- they just see
it in the log on the lead they're already looking at. Log notes don't
notify followers; they're an audit trail, not a ping.

## Locked decisions (this build)

1. **Handoff pool** = the whole Sales team (`crm.team.member`), same pool
   `sgc_crm_dashboard.get_leaderboard_mini()` already scores. No SDR-specific
   role exists in this codebase. Not automatic in this build regardless --
   see below.
2. **Business hours** = Sun-Thu, 09:00-18:00 Asia/Dubai. Used only to
   compute the informational `next_touch_at`.
3. **"Start Nurture Sequence" is available on any active lead, any stage**
   -- not gated behind `sgc_proposal_nurture`'s 3-day Proposal-stall flag.
   That flag, when present, is recorded as the sequence's *reason*
   (`sequence_type = 'proposal_stall'` vs `'manual'`) but no longer decides
   whether the button is clickable. A rep looking at a lead in New must be
   able to start nurture on it right now, not wait for an automatic flag
   that only ever fires for Proposal-stage leads. No new CRM automation
   rule is introduced by this module either way.

## What's deliberately NOT wired yet

- **No automatic SDR handoff.** A response stops the sequence and creates
  an urgent activity for the lead's *current* owner. Routing by
  `get_leaderboard_mini()`'s score alone was explicitly rejected as unsafe
  (no availability/workload/specialization signal) -- see
  `sgc.nurture.sequence._select_handoff_sdr`'s docstring for the intended
  Phase-4 formula once workload data exists to weight against.
- Email bounce detection, duplicate-lead detection, and
  "existing active Discuss conversation" are not signal sources this build
  reads -- see the module docstring on `sgc.nurture.sequence` for the full
  list and why each is out of scope for now.

## Models

- `sgc.nurture.sequence` -- one row per lead enrollment. Owns `status`
  (scheduled/active/paused/responded/handed_off/exhausted/stopped/opted_out),
  the touch counter, the schedule, and the centralized
  `_evaluate_stop_conditions` / `_apply_stop` matrix. The stop matrix is
  re-checked before both drafting and sending, since a lead can close in
  the gap between the two.
- `sgc.nurture.touch` -- one row per drafted/sent touch, for observability:
  what was drafted, when, by which model, and what happened to it
  (`delivery_status`: planned/drafted/skipped_dry_run/sent/failed/validation_blocked).

## Crons

- `SGC AI Nurture: archive stale sequences` (daily) -- `_cron_gc_stale`.
  The only cron in this module. Housekeeping only: archives sequences
  already in a terminal state from default list views. Never drafts,
  never sends, never touches a lead.

## Testing

Follow this project's isolated-test-DB recipe (clone `sgc_staging`, run a
throwaway container with `/opt/odoo-prod/extra-addons` mounted so
`whatsmeow`/`whatsmeow_template` resolve) rather than running against
staging or production directly. LLM calls are mocked at `requests.post`
(see `tests/test_cadence.py`); `tests/test_real_send.py` exercises the
real `whatsmeow.message`/`mail.mail` creation paths without mocking, since
creating the row (not actually dispatching it) is what proves this
module's own logic is correct -- dispatch is whatsmeow's/Odoo's own
already-tested queue infrastructure, not this module's job to re-verify.
