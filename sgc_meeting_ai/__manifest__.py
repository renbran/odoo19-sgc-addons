# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "SGC Meeting AI",
    "summary": "AI meeting notes pipeline: transcription (Whisper) + LLM summarization, posted to chatter",
    "version": "19.0.1.1.0",
    "development_status": "Beta",
    "category": "Productivity",
    "website": "https://sgctech.ai",
    "author": "SGC Tech",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "calendar",
        "mail",
        "resource_booking",
        # crm is required for calendar.event.opportunity_id, already relied
        # on by _sgc_register_meeting() — formalized as an explicit
        # dependency when sgc.meeting.notes.opportunity_id (a related field
        # through that path) was added for the sgc_sales_playbook gate hook.
        "crm",
    ],
    "external_dependencies": {
        "python": ["requests", "markupsafe"],
    },
    "data": [
        "security/sgc_meeting_ai_security.xml",
        "security/ir.model.access.csv",
        "data/sgc_meeting_data.xml",
        "data/mail_templates.xml",
        "data/sgc_meeting_invitation_template.xml",
        "views/actions.xml",
        "views/meeting_provider_views.xml",
        "views/meeting_recording_views.xml",
        "views/meeting_notes_views.xml",
        "views/gate_answers_apply_wizard_views.xml",
        "views/calendar_event_views.xml",
        "views/resource_booking_views.xml",
        "views/portal_templates.xml",
        "views/menus.xml",
    ],
}