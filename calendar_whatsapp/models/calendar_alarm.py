from odoo import api, fields, models


class CalendarAlarm(models.Model):
    _inherit = "calendar.alarm"

    alarm_type = fields.Selection(
        selection_add=[("whatsapp", "WhatsApp Message")],
        ondelete={"whatsapp": "set default"},
    )
    whatsapp_template_id = fields.Many2one(
        "whatsmeow.template", string="WhatsApp Template",
        domain=[("model", "=", "calendar.event")],
        compute="_compute_whatsapp_template_id", readonly=False, store=True,
        help="Template used to render WhatsApp reminder content.")

    @api.depends("alarm_type", "whatsapp_template_id")
    def _compute_whatsapp_template_id(self):
        for alarm in self:
            if alarm.alarm_type == "whatsapp" and not alarm.whatsapp_template_id:
                alarm.whatsapp_template_id = self.env["ir.model.data"]._xmlid_to_res_id(
                    "calendar_whatsapp.whatsmeow_template_calendar_reminder")
            elif alarm.alarm_type != "whatsapp" or not alarm.whatsapp_template_id:
                alarm.whatsapp_template_id = False
