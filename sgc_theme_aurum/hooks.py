def post_init_hook(env):
    """Apply the Aurum homepage content to the live '/' page of any
    website whose domain contains sgctech.ai, replacing the arch of the
    already-published (possibly website-specific COW'd) view in place so
    the new theme renders immediately without depending on inheritance
    resolution against a customized homepage.
    """
    template = env.ref("sgc_theme_aurum.homepage_content", raise_if_not_found=False)
    if not template:
        return

    websites = env["website"].sudo().search([("domain", "ilike", "sgctech.ai")])
    if not websites:
        websites = env["website"].sudo().search([], limit=1)

    for website in websites:
        page = env["website.page"].sudo().search(
            [("url", "=", "/"), ("website_id", "=", website.id), ("active", "=", True)],
            limit=1,
        )
        if not page:
            page = env["website.page"].sudo().search(
                [("url", "=", "/"), ("website_id", "=", False), ("active", "=", True)],
                limit=1,
            )
        if page and page.view_id:
            page.view_id.sudo().with_context(no_save_prev=True).write(
                {"arch_db": template.arch_db}
            )

        _apply_aurum_menu(env, website)


def _apply_aurum_menu(env, website):
    Menu = env["website.menu"].sudo()
    root = Menu.search([("website_id", "=", website.id), ("url", "=", "#")], limit=1)
    if not root:
        return

    existing = Menu.search([("parent_id", "=", root.id)])
    for m in existing:
        m.sequence += 10

    new_items = [
        ("About", "/about-us", 10),
        ("Services", "/services", 20),
        ("Industries", "/our-industries", 30),
        ("Approach", "/our-approach", 40),
        ("Pricing", "/engagement-pricing", 50),
        ("Contact", "/contact-us", 60),
    ]
    for name, url, seq in new_items:
        already = Menu.search(
            [("parent_id", "=", root.id), ("url", "=", url), ("website_id", "=", website.id)],
            limit=1,
        )
        if already:
            already.write({"sequence": seq})
            continue
        Menu.create(
            {
                "name": name,
                "url": url,
                "parent_id": root.id,
                "website_id": website.id,
                "sequence": seq,
            }
        )
