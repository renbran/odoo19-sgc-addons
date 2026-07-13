# -*- coding: utf-8 -*-
"""
Migration 19.0.1.1.1 — add missing res_config_settings columns.

Odoo creates TransientModel columns lazily on first upgrade. If the module
was installed on an older DB that never ran the upgrade, these columns are
absent and every Settings save raises:
  psycopg2.errors.UndefinedColumn: column "genspark_api_secret" of relation
  "res_config_settings" does not exist
"""


def migrate(cr, version):
    columns = [
        "hf_token",
        "genspark_api_url",
        "genspark_api_secret",
        "genspark_model",
        "pexels_api_key",
        "cloudinary_cloud_name",
        "cloudinary_api_key",
        "cloudinary_api_secret",
    ]
    for col in columns:
        cr.execute(
            f"ALTER TABLE res_config_settings ADD COLUMN IF NOT EXISTS {col} varchar;"
        )
