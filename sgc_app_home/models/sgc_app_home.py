from odoo import api, models

# Application -> existing top-level ir.ui.menu XML ID -> icon asset + search keywords.
# Keyed by XML ID (never a raw database id) so the mapping survives across
# environments where record ids differ. Any menu without an entry here falls
# back to _DEFAULT_ICON and no extra keywords - it still appears in the grid.
_APP_META = {
    "kyc_management.menu_kyc_enhanced_root": ("kyc_enhanced.png", ["kyc", "compliance", "verification"]),
    "sgc_executive_dashboard.menu_sgc_executive_root": ("executive.png", ["executive", "command center"]),
    "mail.menu_root_discuss": ("discuss.png", ["chat", "messages"]),
    "hr_payroll_community.menu_hr_payroll_community_root": ("payroll.png", ["salary", "hr"]),
    "sgc_payment.menu_payment_executive_center": ("payment_center.png", ["payments", "finance"]),
    "calendar.mail_menu_calendar": ("calendar.png", ["schedule", "meetings"]),
    "project_todo.menu_todo_todos": ("todo.png", ["tasks", "reminders"]),
    "sgc_payment.menu_payment_management_root": ("payment_management.png", ["payments", "finance", "bank"]),
    "sgc_elearning.menu_learning_root": ("learning.png", ["training", "courses"]),
    "resource_booking.resource_booking_main_menu": ("resource_bookings.png", ["booking", "scheduling"]),
    "ora_ai_base.vapi_menu_root": ("voice_assistant.png", ["ai", "voice", "assistant"]),
    "contacts.menu_contacts": ("contacts.png", ["partners", "people"]),
    "crm.crm_menu_root": ("crm.png", ["leads", "pipeline", "opportunities"]),
    "sale.sale_menu_root": ("sales.png", ["quotations", "orders"]),
    "spreadsheet_dashboard.spreadsheet_dashboard_menu_root": ("dashboards.png", ["reports", "kpi"]),
    "sttl_sale_subscription.sttl_subscription_menu_act": ("subscriptions.png", ["recurring", "contracts"]),
    "point_of_sale.menu_point_root": ("point_of_sale.png", ["pos", "retail", "till"]),
    "account.menu_finance": ("invoicing.png", ["invoice", "accounting", "billing"]),
    "sgc_meeting_ai.sgc_meeting_ai_main_menu": ("sgc_meeting_ai.png", ["ai", "meeting", "meet"]),
    "eh_uae_payroll_wps.menu_eh_uae_wps_root": ("uae_wps.png", ["wps", "payroll", "uae"]),
    "project.menu_main_pm": ("project.png", ["tasks", "milestones"]),
    "hr_timesheet.timesheet_menu_root": ("timesheets.png", ["time tracking", "hours"]),
    "website.menu_website_configuration": ("website.png", ["site", "cms"]),
    "ai_brain.menu_ai_brain_root": ("ai_brain.png", ["ai", "brain", "insights"]),
    "sgc_persona.menu_sgc_persona_root": ("sgc_ai.png", ["ai", "assistant", "chat"]),
    "website_slides.website_slides_menu_root": ("elearning.png", ["courses", "training", "slides"]),
    "llm.menu_llm_root": ("llm.png", ["ai", "llm", "language model"]),
    "sgc_lead_scoring.menu_llm_lead_scoring_root": ("llm_lead_scoring.png", ["ai", "llm", "scoring", "leads"]),
    "mass_mailing.mass_mailing_menu_root": ("email_marketing.png", ["email", "campaigns"]),
    "mass_mailing_sms.mass_mailing_sms_menu_root": ("sms_marketing.png", ["sms", "campaigns", "text"]),
    "survey.menu_surveys": ("surveys.png", ["forms", "feedback"]),
    "purchase.menu_purchase_root": ("purchase.png", ["procurement", "rfq", "vendors"]),
    "stock.menu_stock_root": ("inventory.png", ["stock", "warehouse", "deliveries"]),
    "hr.menu_hr_root": ("employees.png", ["hr", "staff", "people"]),
    "hr_attendance.menu_hr_attendance_root": ("attendances.png", ["check in", "presence"]),
    "hr_recruitment.menu_hr_recruitment_root": ("recruitment.png", ["hiring", "candidates", "jobs"]),
    "hr_holidays.menu_hr_holidays_root": ("time_off.png", ["leave", "vacation", "holidays"]),
    "im_livechat.menu_livechat_root": ("live_chat.png", ["chat", "support"]),
    "utm.menu_link_tracker_root": ("link_tracker.png", ["utm", "links", "tracking"]),
    "base.menu_management": ("apps.png", ["modules", "store"]),
    "base.menu_administration": ("settings.png", ["configuration", "preferences"]),
}

_DEFAULT_ICON = "default_app.png"
_ICON_BASE_URL = "/sgc_app_home/static/src/img/apps/"


class SgcAppHome(models.AbstractModel):
    _name = "sgc.app.home"
    _description = "SGC App Home - icon and search metadata for top-level menus"

    @api.model
    def get_app_meta(self, menu_ids):
        """Resolve icon + search keywords for a list of ir.ui.menu ids.

        Keyed by XML ID rather than the raw ids passed in, so the mapping in
        _APP_META keeps working even if record ids differ between databases.
        """
        xmlid_by_res_id = {}
        if menu_ids:
            data_records = self.env["ir.model.data"].sudo().search_read(
                [("model", "=", "ir.ui.menu"), ("res_id", "in", menu_ids)],
                ["res_id", "module", "name"],
            )
            for rec in data_records:
                xmlid_by_res_id[rec["res_id"]] = f"{rec['module']}.{rec['name']}"

        result = {}
        for menu_id in menu_ids:
            xmlid = xmlid_by_res_id.get(menu_id)
            icon_file, keywords = _APP_META.get(xmlid, (None, []))
            result[menu_id] = {
                "icon": _ICON_BASE_URL + (icon_file or _DEFAULT_ICON),
                "keywords": keywords,
            }
        return result
