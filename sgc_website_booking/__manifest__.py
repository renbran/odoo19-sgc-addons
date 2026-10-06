# -*- coding: utf-8 -*-
{
    'name': 'SGC Website Online Booking',
    'version': '19.0.2.0.0',
    'category': 'Website/Website',
    'summary': 'Public website page where visitors pick a real available slot to '
               'book an online session, wired to Resource Booking + SGC Meeting AI.',
    'description': '''
SGC Website Online Booking
==========================
Adds a public "Book a Session" page (and top-nav menu) to the SGC website where
any visitor can:

* See a calendar of **real** available slots computed by ``resource_booking``
  (working hours, slot duration, no double-booking).
* Pick a date/time and submit their name + email (no login required).

On confirmation it creates a ``resource.booking`` (confirmed), a ``crm.lead`` for
follow-up, and attaches an ``sgc.meeting.session`` so the AI notetaker bot joins
the call and produces notes.
''',
    'author': 'SGC TECH AI — Scholarix Global Consultants',
    'website': 'https://sgctech.ai',
    'license': 'LGPL-3',

    'depends': [
        'website',
        'resource_booking',
        'sgc_meeting_ai',
        'crm',
        'website_sgctech_ai',
    ],

    'data': [
        'data/booking_data.xml',
        'data/mail_templates.xml',
        'data/cron.xml',
        'views/res_config_settings_views.xml',
        'views/booking_templates.xml',
    ],

    'assets': {
        'web.assets_frontend': [
            'sgc_website_booking/static/src/scss/booking.scss',
            'sgc_website_booking/static/src/js/booking_calendar.js',
        ],
    },

    'installable': True,
    'application': False,
    'auto_install': False,
}
