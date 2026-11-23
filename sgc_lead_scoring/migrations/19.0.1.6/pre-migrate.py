# -*- coding: utf-8 -*-
"""Pre-migrate for 19.0.1.6: no schema changes needed before module load
(new models are created by ORM registry sync); this hook exists so
post-migrate has a matching pair and the migration step is documented."""


def migrate(cr, version):
    return
