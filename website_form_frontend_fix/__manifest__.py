{
    "name": "Website Form Frontend Fix",
    "version": "19.0.1.0.0",
    "summary": "Fix missing website.file_block template on frontend",
    "description": """
Adds website/static/src/xml/website_form.xml to web.assets_frontend bundle.
This fixes the OwlError: Missing template: website.file_block that prevents
file uploads (e.g. resume uploads) on website forms.

Root cause: Odoo 19.0-20260513 includes form.js in web.assets_frontend via
the snippets/**/*.js glob, but the website_form.xml template (which defines
website.file_block) is only in website.assets_wysiwyg (backend editor bundle).
    """,
    "category": "Website",
    "author": "SGC Tech",
    "license": "LGPL-3",
    "depends": ["website"],
    "data": [],
    "assets": {
        "web.assets_frontend": [
            "website/static/src/xml/website_form.xml",
        ],
    },
}
