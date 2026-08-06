# -*- coding: utf-8 -*-
{
    'name': 'SGC Quiz Passmark',
    'version': '19.0.1.0.0',
    'category': 'Website/eLearning',
    'summary': 'Show the achieved score after quiz submission and only complete the quiz from 80% correct',
    'description': """
SGC Quiz Passmark
=================
- Adds a configurable "Passing Score (%)" field on quiz slides (default 80%).
- The quiz is only marked as completed when the user reaches the passing
  score. If the score is below it, the quiz stays open so the user can retry.
- After clicking "Check your answers", the achieved score is clearly
  displayed to the user in percent, with a success message when passed and a
  clear failure message (score + required score) when not passed.
    """,
    'author': 'SGC Tech AI',
    'website': 'https://www.scholarixglobal.com',
    'depends': ['website_slides'],
    'data': [
        'views/website_slides_templates_lesson.xml',
        'views/slide_slide_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'sgc_quiz_passmark/static/src/js/quiz_score_display.js',
            'sgc_quiz_passmark/static/src/xml/quiz_validation.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}