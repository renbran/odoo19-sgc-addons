# -*- coding: utf-8 -*-
{
    "name": "SGC - E-Learning",
    'version': '19.0.1.0.0',
    "category": "Education",
    "summary": "Sequential learning paths for real estate operations with quizzes, badges, and certificates",
    "description": "Guided learning for rental, sales, commissions, accounting, and HR with quizzes and certification.",
    "author": "SmartClinic",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/learning_views.xml",
        "views/learning_menus.xml",
        "views/res_users_views.xml",
        "data/ces_quiz_data.xml",
    ],
    "installable": True,
    "application": True,
}
