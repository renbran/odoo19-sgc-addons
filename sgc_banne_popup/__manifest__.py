{
    "name": "SGC Banner/Popup",
    "version": "19.0.1.2.0",
    "summary": "Persistent gamification banner with price pool and configurable announcement",
    "description": """
SGC Banner/Popup
===============

Adds a persistent pop-up banner for gamification activities with price pool display.
Allows configuration of price pool amount and customizable banner text.
The banner appears once per session and can be dismissed by the user.
""",
    "author": "SGC TECH AI",
    "website": "https://sgc-tech.ai",
    "category": "Gamification",
    "depends": ["gamification", "hr_gamification", "crm"],
    "data": [
        "views/sgc_banne_popup.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}