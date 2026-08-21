# -*- coding: utf-8 -*-
from odoo import api, fields, models

# Fixed 5-slot plan (channel, intent) -- see PLAN §05. Index 0 is unused so
# touch_number (1-5) can index straight into it without an off-by-one.
# Touch 5's channel is 'auto': resolved at draft time from which channel
# showed engagement on earlier touches (PLAN §12), not hardcoded here.
TOUCH_PLAN = {
    1: ("whatsapp", "reopen"),
    2: ("email", "proof_point"),
    3: ("whatsapp", "direct_ask"),
    4: ("email", "reframe"),
    5: ("auto", "last_call"),
}


class SgcNurtureTouch(models.Model):
    _name = "sgc.nurture.touch"
    _description = "SGC Nurture Touch"
    _order = "sequence_id, touch_number"

    sequence_id = fields.Many2one(
        "sgc.nurture.sequence", required=True, ondelete="cascade", index=True,
    )
    lead_id = fields.Many2one(
        related="sequence_id.lead_id", store=True, index=True,
    )
    touch_number = fields.Integer(required=True)
    channel = fields.Selection(
        [("whatsapp", "WhatsApp"), ("email", "Email")],
        help="The channel actually used. May differ from the plan's default "
             "for touch 5, which is resolved from engagement history.",
    )
    intent = fields.Char(help="What this touch is for, e.g. 'reopen', 'direct_ask'.")

    scheduled_at = fields.Datetime()
    drafted_at = fields.Datetime()
    sent_at = fields.Datetime()

    body = fields.Text(help="The drafted message text, kept for audit even in dry-run.")
    generation_model = fields.Char(help="llm.provider record name used to draft this touch.")
    generation_cost_usd = fields.Float(digits=(10, 6))

    # Populated once a real send exists (Phase 2+). Left empty in dry-run.
    whatsmeow_message_id = fields.Many2one("whatsmeow.message")
    mail_message_id = fields.Many2one("mail.mail")

    engagement_status = fields.Selection(
        [("none", "None"), ("delivered", "Delivered"), ("read", "Read"),
         ("clicked", "Clicked"), ("replied", "Replied")],
        default="none",
    )
    engagement_at = fields.Datetime()

    delivery_status = fields.Selection(
        [("planned", "Planned"), ("drafted", "Drafted"),
         ("skipped_dry_run", "Skipped (dry run)"), ("sent", "Sent"),
         ("failed", "Failed"), ("validation_blocked", "Blocked by validation")],
        default="planned", required=True,
    )
    failure_reason = fields.Char()

    _touch_number_uniq = models.Constraint(
        "UNIQUE (sequence_id, touch_number)",
        "Each sequence can only have one row per touch number.",
    )

    @api.model
    def _plan_for(self, touch_number):
        return TOUCH_PLAN.get(touch_number)
