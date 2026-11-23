# -*- coding: utf-8 -*-
"""Post-upgrade constraint assertion for kyc_management.

Second line of defense: even if the pre-migration check (see
pre-migrate.py in this same directory) missed an unexpected condition,
this script verifies -- directly against PostgreSQL catalog metadata,
not ORM state -- that the required unique constraint actually exists
after the module has finished loading. Odoo's own schema layer only
logs a WARNING and continues when it cannot create a constraint over
conflicting data; this script turns that warning into a hard,
non-zero-exit failure so a partially-migrated database can never be
reported as a successful upgrade.
"""
import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

REQUIRED_CONSTRAINTS = ["kyc_application_kyc_id_unique"]


def migrate(cr, version):
    if not version:
        return

    cr.execute("SELECT to_regclass('public.kyc_application')")
    if cr.fetchone()[0] is None:
        return

    cr.execute(
        "SELECT conname FROM pg_constraint WHERE conname = ANY(%s)",
        (REQUIRED_CONSTRAINTS,),
    )
    present = {row[0] for row in cr.fetchall()}
    missing = [name for name in REQUIRED_CONSTRAINTS if name not in present]

    if missing:
        message = (
            "KYC_UPGRADE_POSTCHECK_FAILED: required constraint(s) absent "
            "after upgrade: %s"
        ) % ", ".join(missing)
        _logger.error(message)
        raise UserError(message)
