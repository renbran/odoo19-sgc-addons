# Copyright 2021 Tecnativa - Jairo Llopis
# Copyright 2022 Tecnativa - Pedro M. Baeza
# Copyright 2024 Tecnativa - Carolina Fernandez
# Copyright 2025 SGC Tech AI - Modernized for SGC platform
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "SGC Resource Booking",
    "summary": "AI-enhanced resource booking and appointment management for SGC Tech",
    "version": "19.0.2.0.0",
    "development_status": "Production/Stable",
    "category": "Appointments",
    "website": "https://sgctech.ai",
    "author": "Tecnativa, Odoo Community Association (OCA), SGC Tech",
    "maintainers": ["pedrobaeza", "ows-cloud"],
    "license": "AGPL-3",
    "application": True,
    "installable": True,
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {
        "python": [
            "cssselect",
            "openupgradelib",
        ],
    },
    "depends": [
        "calendar",
        "mail",
        "portal",
        "resource",
        "web_calendar_slot_duration",
    ],
    "data": [
        "data/mail.xml",
        "data/mail_data.xml",
        "data/sgc_booking_data.xml",
        "security/resource_booking_security.xml",
        "security/ir.model.access.csv",
        "templates/portal.xml",
        "wizard/mail_activity_schedule_views.xml",
        "views/calendar_event_views.xml",
        "views/mail_activity_views.xml",
        "views/res_partner_views.xml",
        "views/resource_booking_combination_views.xml",
        "views/resource_booking_type_views.xml",
        "views/resource_booking_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "resource_booking/static/src/js/**/*",
            "resource_booking/static/src/scss/portal.scss",
        ],
        "web.assets_tests": ["resource_booking/static/src/js/tours/**/*"],
    },
    "demo": [
        "demo/res_users_demo.xml",
        "demo/resource_resource_demo.xml",
        "demo/resource_combination_demo.xml",
        "demo/resource_booking_type_demo.xml",
    ],
}
