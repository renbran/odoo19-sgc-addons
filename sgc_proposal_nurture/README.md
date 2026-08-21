# SGC - Proposal Nurture Automation

Mirrors, as installable module code, the crm.lead customizations built
directly against the live `odoo19-sgc` database on 2026-07-28 (see the
`marketing-and-lead-generation` project's `scripts/odoo/` directory for the
scripts that created them, and `.claude/skills/nurture-queue/SKILL.md` for
the Claude Code side of this workflow).

## Adoption status (resolved 2026-07-28)

The three custom fields and five automation rules (Rule A, B, C1, C2, C3)
were originally created **directly via XMLRPC** against production, before
this module existed — real rows in `ir.model.fields` / `base.automation` /
`ir.actions.server` with no `ir.model.data` (XML ID) association.

Ownership was checked (`ir.model.data` search by `res_id`) before writing
anything: all 13 records (5 rules, 5 actions, 3 fields) were confirmed
**unowned** — no existing XML ID, no conflict with `studio_customization`.
Adopting `ir.model.data` rows were then created (`module='sgc_proposal_nurture'`,
`noupdate=False`) linking each live record to the XML ID this module
declares for it, and every one was re-read and verified to resolve back to
the original `res_id`. No scratch/duplicate database was available to do a
full install dry-run, so that verification (re-reading every XML ID) is the
level of confidence this has — **the module has still never actually been
installed** on this database. Install would now upgrade the existing
records in place rather than duplicate them, but hasn't been attempted.

## Bug found and fixed during live verification (2026-07-28)

Rule C1/C2 originally used `lead.activity_feedback(['mail.mail_activity_data_todo'])`
to close the "generate sequence" activity when a stop condition fires. That
mixin method only closes activities assigned to whichever user is currently
executing the code — since Rule B assigns the activity to the lead's owner
(not the automation's own execution identity), this silently returned
`True` and closed nothing whenever those two users differed, leaving a
stale "campaign due" activity behind. Confirmed via a live test lead:
direct `mail.activity.search(...) + action_feedback(...)` (bypassing the
assignee filter entirely) closes it correctly regardless of who the
activity is assigned to. Both rules now use that pattern; `post_back.py`
in the `marketing-and-lead-generation` project was fixed the same way.

## Guardrails

Every action here is an internal chatter note (`subtype_xmlid='mail.mt_note'`)
or a scheduled activity. Nothing in this module creates `mail.mail`,
`mail.template`, or triggers Mass Mailing. Outbound copy is written and
sent entirely outside Odoo.
