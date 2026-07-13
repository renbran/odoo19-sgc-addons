# -*- coding: utf-8 -*-
"""Install hooks for production-safe website bootstrap."""


def post_init_hook(env):
    """Point the default website homepage at the branded /home route."""
    website = env.ref('website.default_website', raise_if_not_found=False)
    if website and website.homepage_url != '/home':
        website.write({'homepage_url': '/home'})
