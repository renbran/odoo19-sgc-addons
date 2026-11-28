# Copyright 2026 Park Group
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Social Media Buffer",
    "summary": "Publish and schedule social posts through Buffer",
    "version": "19.0.1.0.0",
    "category": "Social Network",
    "development_status": "Beta",
    "license": "AGPL-3",
    "author": "Park Group, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/social",
    "depends": ["social_media_base"],
    "external_dependencies": {"python": ["requests"]},
    "uninstall_hook": "uninstall_hook",
    "data": [
        "security/ir.model.access.csv",
        "data/social_media_data.xml",
        "views/buffer_account_views.xml",
        "views/social_account_views.xml",
    ],
    "installable": True,
}
