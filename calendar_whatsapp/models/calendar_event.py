from odoo import api, models, _

from odoo.addons.whatsmeow.models.whatsmeow_message import DIGITS, PHONE_FIELDS


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    @api.model
    def _whatsapp_digits(self, partner):
        """Digits-only phone number for a partner, or '' when it has none."""
        for field_name in PHONE_FIELDS:
            if field_name in partner._fields:
                digits = DIGITS.sub("", partner[field_name] or "")
                if digits:
                    return digits
        return ""

    def _do_whatsapp_reminder(self, alarms):
        """Queue a WhatsApp reminder to attendees that haven't declined the event."""
        Message = self.env["whatsmeow.message"]
        fallback_session = self.env["whatsmeow.session"].search([], limit=1)
        for event in self:
            declined_partners = event.attendee_ids.filtered_domain(
                [("state", "=", "declined")]).partner_id
            event_partners = event._mail_get_partners()[event.id]
            for alarm in alarms:
                partners = event_partners.filtered(
                    lambda partner: partner not in declined_partners)
                # notify_responsible governs the internal organiser; external
                # attendees are notified regardless. Mirrors calendar_sms.
                if event.user_id and not alarm.notify_responsible:
                    partners -= event.user_id.partner_id

                template = alarm.whatsapp_template_id
                if template:
                    body = template._render_body([event.id]).get(event.id, "")
                else:
                    body = _(
                        "Reminder: your meeting %(name)s starts in 30 minutes.",
                        name=event.name)
                session = (template.session_id if template else False) or fallback_session
                if not session:
                    continue

                vals_list = []
                for partner in partners:
                    digits = self._whatsapp_digits(partner)
                    if not digits:
                        continue
                    vals_list.append({
                        "session_id": session.id,
                        "direction": "out",
                        "phone": digits,
                        "partner_id": partner.id,
                        "message_type": "text",
                        "body": body,
                        "source_res_model": "calendar.event",
                        "source_res_id": event.id,
                    })
                if vals_list:
                    Message.create(vals_list)._log_on_source()

    def _get_trigger_alarm_types(self):
        return super()._get_trigger_alarm_types() + ["whatsapp"]
