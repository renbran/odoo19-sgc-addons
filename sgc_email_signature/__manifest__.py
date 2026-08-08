{
    "name": "SGC Email Signature",
    "version": "19.0.1.0.0",
    "summary": "Auto-generate branded email signature for internal users from employee records.",
    "description": "Automatically composes the SGC TECH AI branded email signature (HTML) from the linked employee record (name, job title, phone, email) and the company profile (address, website) and writes it to res.users.signature whenever an employee is created or updated. A server action allows regenerating all signatures in bulk.",
    "author": "SGC Tech",
    "license": "LGPL-3",
    "category": "Human Resources",
    "depends": [
        "base",
        "hr"
    ],
    "data": [
        "data/ir_actions_server.xml"
    ],
    "installable": True,
    "auto_install": False,
    "application": False
}