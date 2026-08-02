# -*- coding: utf-8 -*-
{
    "name": "SGC Live Chat AI",
    "version": "19.0.2.0.0",
    "summary": "AI auto-reply for the website live-chat widget (self-contained, freellmapi)",
    "description": """
SGC Live Chat AI
================
Makes the website live-chat floating widget answered by an AI assistant that
knows the company. Self-contained: it calls an OpenAI-compatible endpoint
(freellmapi) directly and posts the reply as the channel operator. It does NOT
depend on the site's other llm_* modules (whose provider dispatch is currently
broken), so it works independently.

Config lives in Settings > Technical > System Parameters:
  - sgc_livechat_ai.endpoint       (default http://freellmapi-prod:3001/v1)
  - sgc_livechat_ai.model          (default auto)
  - sgc_livechat_ai.api_key        (paste your freellmapi key)
  - sgc_livechat_ai.system_prompt  (company knowledge + behaviour rules)
  - sgc_livechat_ai.max_history    (default 12)

Safety: ships DISABLED. AI replies only on live-chat channels where an operator
turns on "AI Auto-Reply" AND a valid api_key is set.
""",
    "category": "Website/Live Chat",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "external_dependencies": {"python": ["openai"]},
    "depends": [
        "im_livechat",
        "website_livechat",
    ],
    "data": [
        "data/config_params.xml",
        "data/res_users_bot.xml",
        "views/im_livechat_channel_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
