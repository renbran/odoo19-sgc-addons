# SGC - AI Nurture Orchestrator

Automates what `sgc_proposal_nurture` currently only flags for a human to
do by hand: a bounded, AI-drafted WhatsApp + email touch sequence for a
lead, gated entirely behind an assigned activity.

## Scope of this build (Phase 0/1: instrumentation + shadow mode)

Everything real runs: enrollment, business-hours scheduling, AI drafting
against the live `llm.provider` (whatever `is_default=True` provider is
configured), deterministic validation, and the centralized stop/pause
matrix. **Nothing is ever sent.** `dry_run` defaults to `True` and this
build has no code path that flips it — a drafted touch is posted as an
internal chatter note on the lead for review, never queued on
`whatsmeow.message` or `mail.mail`. See the rollout phases in the
`nurture-orchestration-plan` artifact for what unlocks real sends later.

## Locked decisions (this build)

These were explicit calls, not defaults, made before writing any code:

1. **Handoff pool** = the whole Sales team (`crm.team.member`), same pool
   `sgc_crm_dashboard.get_leaderboard_mini()` already scores. No SDR-specific
   role exists in this codebase.
2. **Business hours** = Sun-Thu, 09:00-18:00 Asia/Dubai.
3. **Enrollment gate (v1)** = only `sgc_proposal_nurture`'s existing 3-day
   Proposal-stall flag (`crm.lead.x_nurture_state == 'pending'`). No new
   CRM automation rule is introduced by this module.

## What's deliberately NOT wired yet

Per the architecture review that shaped this build:

- **No automatic SDR handoff.** A response stops the sequence and creates
  an urgent activity for the lead's *current* owner. Routing by
  `get_leaderboard_mini()`'s score alone was explicitly rejected as unsafe
  (no availability/workload/specialization signal) -- see
  `sgc.nurture.sequence._select_handoff_sdr`'s docstring for the intended
  Phase-4 formula once workload data exists to weight against.
- **No live send on any channel.** WhatsApp-only, then +email, then
  +handoff are separate later phases, each a deliberate flip, not a config
  toggle sitting in this codebase today.
- Email bounce detection, duplicate-lead detection, and
  "existing active Discuss conversation" are not signal sources this build
  reads -- see the module docstring on `sgc.nurture.sequence` for the full
  list and why each is out of scope for now.

## Models

- `sgc.nurture.sequence` -- one row per lead enrollment. Owns `status`
  (scheduled/active/paused/responded/handed_off/exhausted/stopped/opted_out),
  the touch counter, the schedule, and the centralized
  `_evaluate_stop_conditions` / `_apply_stop` matrix.
- `sgc.nurture.touch` -- one row per planned/drafted touch, for
  observability: what was drafted, when, by which model, and what happened
  to it (`delivery_status`: planned/drafted/skipped_dry_run/sent/failed/validation_blocked).

## Crons

- `SGC AI Nurture: enroll flagged leads` (15 min) -- `_enroll_pending_leads`
- `SGC AI Nurture: process due touches (dry-run)` (15 min) -- `_cron_process_due`
- `SGC AI Nurture: archive stale sequences` (daily) -- `_cron_gc_stale`

## Testing

Follow this project's isolated-test-DB recipe (clone `sgc_staging`, run a
throwaway container with `/opt/odoo-prod/extra-addons` mounted so
`whatsmeow`/`whatsmeow_template` resolve) rather than running against
staging or production directly. All LLM calls in the test suite are
mocked at `requests.post` -- see `tests/test_cadence.py` -- so no test run
ever makes a real API call, even though `_make_request` is exercised for
real.

Not yet installed on any database. Install is a clean `-i
sgc_ai_nurture_orchestrator`, no adoption step needed (unlike
`sgc_proposal_nurture`, nothing here pre-exists live).
