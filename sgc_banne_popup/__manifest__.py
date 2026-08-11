{
    "name": "SGC Banner/Popup",
    "version": "19.0.2.0.0",
    "summary": "First-login welcome banner and configurable gamification announcements",
    "description": """
SGC Banner/Popup
================

Shows a dismissible, SGC-branded banner once per browser session - on
first login and for any configured gamification announcement (prize
pool figure, campaign text). Configure it from Settings > General
Settings > SGC Gamification Banner.
""",
    "author": "SGC TECH AI",
    "website": "https://sgc-tech.ai",
    "license": "LGPL-3",
    "category": "Gamification",
    "depends": ["gamification", "hr_gamification", "crm", "web"],
    "data": [
        "security/ir.model.access.csv",
        "data/default_config.xml",
        "views/res_config_settings_views.xml",
        "views/sgc_banne_popup.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sgc_banne_popup/static/src/scss/banner.scss",
            "sgc_banne_popup/static/src/js/banner.js",
            "sgc_banne_popup/static/src/xml/banner.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
