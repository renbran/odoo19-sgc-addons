"""Give the homepage industry cards their per-industry CSS class.

The live homepage does not render `sgc_theme_aurum.homepage_content` directly:
post_init_hook copies that arch into the website-specific (COW'd)
`website.homepage` view, and the site serves that copy. So editing the theme
template alone never reaches the page.

Until now the six card background photos were matched by position only. That is
fragile: reordering the list in the website builder would silently move the
photos onto the wrong industries. This migration adds the same `t-attf-class`
the template uses, so each card names its own industry.

Deliberately a surgical replace rather than re-copying the whole arch: the
COW'd view also carries website-builder edits (background shapes, etc.) that
must not be destroyed. Idempotent - re-running changes nothing.
"""

import json
import logging

_logger = logging.getLogger(__name__)

OLD = '<div class="aurum-industry">'
NEW = (
    '<div t-attf-class="aurum-industry '
    "aurum-industry-#{industry.lower().replace(' ', '-')}\">"
)


def migrate(cr, version):
    if not version:
        return

    # arch_db is jsonb (one entry per language) in Odoo 19, so patch each value
    # in Python: a replace on the ::text form would have to match backslash
    # escaped quotes and is easy to get subtly wrong.
    cr.execute(
        "SELECT id, arch_db FROM ir_ui_view WHERE arch_db::text LIKE %s",
        ["%aurum-industry-list%"],
    )
    rows = cr.fetchall()

    patched = 0
    for view_id, arch in rows:
        if isinstance(arch, str):          # plain text column (older setups)
            if OLD not in arch:
                continue
            cr.execute(
                "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
                [arch.replace(OLD, NEW), view_id],
            )
        elif isinstance(arch, dict):       # jsonb translations
            new_arch = {
                lang: (val.replace(OLD, NEW) if isinstance(val, str) else val)
                for lang, val in arch.items()
            }
            if new_arch == arch:
                continue
            cr.execute(
                "UPDATE ir_ui_view SET arch_db = %s::jsonb WHERE id = %s",
                [json.dumps(new_arch), view_id],
            )
        else:
            continue

        patched += 1
        _logger.info(
            "sgc_theme_aurum: added per-industry classes to ir.ui.view %s", view_id
        )

    _logger.info(
        "sgc_theme_aurum: industry class patch touched %s of %s candidate view(s)",
        patched,
        len(rows),
    )
