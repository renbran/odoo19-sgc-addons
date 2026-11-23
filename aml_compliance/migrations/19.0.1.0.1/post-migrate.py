# -*- coding: utf-8 -*-
"""Post-upgrade constraint assertion for aml_compliance.

Second line of defense -- see
kyc_management/migrations/19.0.1.0.2/post-migrate.py for the full
rationale. Verifies, directly against PostgreSQL catalog metadata,
that all four required constraints exist after the module has
finished loading, and fails the upgrade (non-zero exit) if any are
missing.
"""
import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

REQUIRED_CONSTRAINTS = [
    "aml_fatf_jurisdiction_country_uniq",
    "aml_risk_factor_code_uniq",
    "aml_risk_factor_weight_positive",
    "aml_sanctions_list_name_source_uniq",
]


def migrate(cr, version):
    if not version:
        return

    cr.execute("SELECT to_regclass('public.aml_fatf_jurisdiction')")
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
            "AML_UPGRADE_POSTCHECK_FAILED: required constraint(s) absent "
            "after upgrade: %s"
        ) % ", ".join(missing)
        _logger.error(message)
        raise UserError(message)
