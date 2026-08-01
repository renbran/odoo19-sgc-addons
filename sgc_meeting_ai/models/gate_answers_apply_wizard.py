# Copyright 2026 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

TRANSCRIPT_EXCERPT_CHARS = 2000


class SgcGateAnswersApplyWizard(models.TransientModel):
    """Rep-reviewed confirmation step for applying AI-extracted gate
    answers to an opportunity (S1). Replaces the previous one-click
    action_apply_gate_answers_to_opportunity(), which copied the AI draft
    straight through unreviewed — an LLM inferring "who approves" from a
    transcript satisfies the field without satisfying the discipline the
    Verifiable Buyer Exit Criteria exist to enforce. All 4 fields are
    editable and required on confirm, with the source transcript excerpt
    shown alongside them for reference.
    """

    _name = "sgc.gate.answers.apply.wizard"
    _description = "Review AI-Extracted Gate Answers Before Applying"

    notes_id = fields.Many2one(
        "sgc.meeting.notes", required=True, ondelete="cascade"
    )
    opportunity_id = fields.Many2one(
        related="notes_id.opportunity_id", readonly=True
    )
    transcript_excerpt = fields.Text(
        string="Source Transcript Excerpt",
        readonly=True,
        help="First %d characters of the linked transcript, for reference "
        "while reviewing the AI-extracted answers below." % TRANSCRIPT_EXCERPT_CHARS,
    )
    gate_problem = fields.Text(string="Q1: Specific Problem", required=True)
    gate_cost_of_inaction = fields.Text(
        string="Q2: Cost of Doing Nothing", required=True
    )
    gate_approver = fields.Text(string="Q3: Who Approves", required=True)
    gate_timeline = fields.Text(string="Q4: Timeline", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        notes_id = self.env.context.get("default_notes_id")
        if notes_id:
            notes = self.env["sgc.meeting.notes"].browse(notes_id)
            res.setdefault("gate_problem", notes.gate_draft_problem)
            res.setdefault("gate_cost_of_inaction", notes.gate_draft_cost_of_inaction)
            res.setdefault("gate_approver", notes.gate_draft_approver)
            res.setdefault("gate_timeline", notes.gate_draft_timeline)
            res.setdefault(
                "transcript_excerpt",
                (notes.transcript_id.text or "")[:TRANSCRIPT_EXCERPT_CHARS],
            )
        return res

    def action_confirm(self):
        self.ensure_one()
        opportunity = self.opportunity_id
        if not opportunity:
            raise UserError(_("This meeting isn't linked to a CRM opportunity."))
        if "x_gate_problem" not in self.env["crm.lead"]._fields:
            raise UserError(
                _(
                    "The Sales Playbook module (sgc_sales_playbook) isn't "
                    "installed, so there's no gate to apply these answers to."
                )
            )
        for label, value in (
            (_("Specific Problem"), self.gate_problem),
            (_("Cost of Doing Nothing"), self.gate_cost_of_inaction),
            (_("Who Approves"), self.gate_approver),
            (_("Timeline"), self.gate_timeline),
        ):
            if not (value or "").strip():
                raise UserError(_("%s cannot be blank.") % label)

        opportunity.write(
            {
                "x_gate_problem": self.gate_problem,
                "x_gate_problem_provenance": "ai_confirmed",
                "x_gate_cost_of_inaction": self.gate_cost_of_inaction,
                "x_gate_cost_of_inaction_provenance": "ai_confirmed",
                "x_gate_approver": self.gate_approver,
                "x_gate_approver_provenance": "ai_confirmed",
                "x_gate_timeline": self.gate_timeline,
                "x_gate_timeline_provenance": "ai_confirmed",
            }
        )
        self.notes_id.gate_answers_applied = True
        return {"type": "ir.actions.act_window_close"}
