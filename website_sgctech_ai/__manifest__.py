# -*- coding: utf-8 -*-
{
    # ── Identity ────────────────────────────────────────────────────────────
    'name':     'SGC TECH AI — Premium Glassmorphism Website Theme',
    'version':  '19.0.1.1.8',
    'category': 'Website/Themes',
    'sequence': 1,
    'summary':  'Premium dark-space glassmorphism theme with particle animations for Odoo Website',

    'description': '''
SGC TECH AI Website Theme
==========================
A production-ready Odoo 19 website theme for SGC TECH AI (sgctech.ai /
store.sgctech.ai).  Built with a deep-space dark UI, glassmorphism cards,
and GPU-accelerated canvas animations.

Features
--------
* Deep-space dark UI  (#060E1A → #0A1628 palette)
* Glassmorphism cards  (backdrop-filter blur)
* Canvas particle network  (90-particle interactive hero)
* IntersectionObserver scroll-reveal  (fade · slide · scale)
* Animated stat counters  (easeOutQuart easing)
* Magnetic CTA button effect
* Typewriter headline  (data-typewriter JSON phrases)
* Parallax orb decorations
* Tech stack infinite ticker
* Full 10-section SGC homepage  at ``/sgctech-home``
* 5 drag-and-drop Website Builder snippets
* Mobile-first responsive  (480 → 1400 px breakpoints)
* Orbitron + Inter + Share Tech Mono typography via Google Fonts
* UAE / MENA optimised copy  (AED, VAT, Arabic-ready)
* AI product image generation via Google Imagen 3 (Gemini API)
* Optional Cloudinary CDN upload for generated images

Sections
--------
Hero · Trust Bar · Industries · Why Us · Stats ·
Pricing · Testimonials · Tech Ticker · CTA · Footer
    ''',

    # ── Ownership ────────────────────────────────────────────────────────────
    'author':      'SGC TECH AI — Scholarix Global Consultants',
    'website':     'https://sgctech.ai',
    'support':     'hello@sgctech.ai',
    'maintainer':  'SGC TECH AI',
    'license':     'LGPL-3',

    # ── Dependencies ─────────────────────────────────────────────────────────
    'depends': [
        'base',
        'web',
        'website',
        'website_sale',
        'crm',
        'auth_signup',       # sgctech_signup_form / sgctech_reset_form templates
        'base_setup',        # res.config.settings AI keys UI
    ],

    # ── Data files  (loaded in order) ────────────────────────────────────────
    'data': [
        # Security — must be first
        'security/ir.model.access.csv',
        # Static / seed data
        'data/utm_data.xml',
        'data/website_config.xml',
        # Backend views
        'views/res_config_settings_views.xml',
        'views/product_template_gemini_image_button.xml',
        # Website / frontend templates
        'views/website_templates.xml',
        'views/homepage.xml',
        'views/pages.xml',
        'views/tools_templates.xml',
        'views/snippets.xml',
        'views/store_templates.xml',
        'views/auth_templates.xml',
    ],

    # ── Frontend assets ──────────────────────────────────────────────────────
    'assets': {
        'web.assets_frontend': [
            # CSS — strict load order: tokens → base → layout → sections → JS
            'website_sgctech_ai/static/src/css/01_variables.css',
            'website_sgctech_ai/static/src/css/02_base.css',
            'website_sgctech_ai/static/src/css/03_layout.css',
            'website_sgctech_ai/static/src/css/04_hero.css',
            'website_sgctech_ai/static/src/css/05_sections.css',
            'website_sgctech_ai/static/src/css/06_components.css',
            'website_sgctech_ai/static/src/css/07_animations.css',
            'website_sgctech_ai/static/src/css/08_responsive.css',
            'website_sgctech_ai/static/src/css/09_ecommerce.css',
            'website_sgctech_ai/static/src/css/10_roi_calculator.css',
            'website_sgctech_ai/static/src/css/11_background_paths.css',
            'website_sgctech_ai/static/src/css/12_premium_animations.css',
            'website_sgctech_ai/static/src/css/particle_text_effect.css',
             # JS
            'website_sgctech_ai/static/src/js/sgctech.js',
            'website_sgctech_ai/static/src/js/premium_animations.js',
            'website_sgctech_ai/static/src/js/roi_calculator.js',
            'website_sgctech_ai/static/src/js/globe_hero.js',
            'website_sgctech_ai/static/src/js/interactive_grid.js',
        ],
    },

    # ── App Store ────────────────────────────────────────────────────────────
    'images': ['static/description/banner.png'],

    # ── Flags ────────────────────────────────────────────────────────────────
    'installable':    True,
    'auto_install':   False,
    'application':    False,
}
