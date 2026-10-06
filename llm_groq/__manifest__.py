{
    "name": "Groq AI Provider",
    "version": "19.0.1.0.0",
    "category": "AI/Agent",
    "summary": "Groq AI provider integration for Odoo, providing chat and embedding capabilities",
    "author": "Tachimao",
    "website": "https://www.tachimao.com",
    "license": "LGPL-3",
    "depends": [
        "llm",
        "llm_tool",
        "llm_training",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/llm_publisher.xml",
    ],
    "assets": {
        "web.assets_backend": [
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
