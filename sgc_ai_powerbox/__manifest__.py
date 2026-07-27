{
    'name': 'SGC AI Powerbox Command',
    'version': '1.3.0',
    'category': 'Tools',
    'summary': 'Add /sgcai command to Odoo Powerbox for custom SGC AI integration',
    'author': 'SGC TECH AI',
    'website': 'https://sgctech.ai',
    'license': 'LGPL-3',
    'depends': ['web'],
    'data': [],
    'installable': True,
    'application': False,
    'assets': {
        'web.assets_backend': [
            'sgc_ai_powerbox/static/src/js/powerbox.js',
        ],
    },
}
