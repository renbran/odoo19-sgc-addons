{
    "name": "Calendar - WhatsApp",
    "version": "19.0.1.0.0",
    "summary": "Send WhatsApp messages as event reminders",
    "description": "Adds a WhatsApp reminder alarm type to calendar events, "
                   "sending through the whatsmeow gateway queue.",
    "category": "Productivity/Calendar",
    "author": "SGC Tech",
    "license": "LGPL-3",
    "depends": ["calendar", "whatsmeow", "whatsmeow_template"],
    "data": [
        "data/whatsmeow_template_data.xml",
        "views/calendar_alarm_views.xml",
    ],
    "installable": True,
    "application": False,
}
