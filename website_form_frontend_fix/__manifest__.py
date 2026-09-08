{
    "name": "Website Form Frontend Fix",
    "version": "19.0.1.0.0",
    "summary": "Fix missing website.file_block template on frontend",
    "description": """
Adds website/static/src/xml/website_form.xml to web.assets_frontend bundle.
This fixes the OwlError: Missing template: website.file_block that prevents
file uploads (e.g. resume uploads) on website forms.
    """,
    "category": "Website",
    "author": "SGC Tech",
    "license": "LGPL-3",
    "depends": ["website"],
    "data": [
        "data/ir_asset.xml",
    ],
}
