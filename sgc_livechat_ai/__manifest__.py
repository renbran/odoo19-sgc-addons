# -*- coding: utf-8 -*-
{
    "name": "SGC Live Chat AI",
    "version": "19.0.1.0.0",
    "summary": "Wire an LLM assistant into the website live-chat floating widget",
    "description": """
SGC Live Chat AI
================
Bridges Odoo's website live chat (im_livechat) to the LLM assistant framework
so the floating chat bubble on the website is answered by a real AI agent that
knows the company (via the assistant's prompt/knowledge) and can optionally use
read-only database tools.

Safety: ships DISABLED. The AI only replies on a live-chat channel once an
operator enables "AI Auto-Reply" on that channel and selects an assistant. No
behaviour changes on install.
""",
    "category": "Website/Live Chat",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": [
        "im_livechat",
        "website_livechat",
        "llm_openai",
        "llm_assistant",
        "llm_thread",
    ],
    "data": [
        "data/llm_provider_freellmapi.xml",
        "data/llm_prompt_sgc.xml",
        "data/llm_assistant_sgc.xml",
        "data/res_users_bot.xml",
        "views/im_livechat_channel_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
