{
    "name": "SGC TECH AI App Home",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": "Enterprise-style full-page application launcher for SGC TECH AI",
    "description": """
SGC TECH AI Enterprise App Home
================================

Replaces the default landing experience with a full-page, searchable,
branded application launcher. Every tile opens the application's existing
Odoo action; the tile list is always filtered by the current user's real
menu access (no security bypass, no new groups). Does not modify any
existing app, menu, action, or permission.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["web", "base"],
    "data": [
        "security/ir.model.access.csv",
        "data/sgc_app_home_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sgc_app_home/static/src/scss/app_home.scss",
            "sgc_app_home/static/src/js/app_home.js",
            "sgc_app_home/static/src/xml/app_home.xml",
            "sgc_app_home/static/src/scss/home_systray.scss",
            "sgc_app_home/static/src/js/home_systray.js",
            "sgc_app_home/static/src/xml/home_systray.xml",
        ],
    },
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": False,
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
}
