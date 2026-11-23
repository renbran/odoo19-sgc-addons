# -*- coding: utf-8 -*-
"""Fail-closed pre-upgrade guard for aml_compliance.

Same rationale as kyc_management/migrations/19.0.1.0.2/pre-migrate.py:
Odoo 19 logs a WARNING and silently skips constraint creation when
historical data conflicts with a new unique/check constraint, and the
module still reports exit 0. For AML controls that is not acceptable.
This script detects all four known conflict categories BEFORE the
upgrade proceeds and raises one deterministic exception listing every
category found, which rolls back the update transaction and makes the
CLI process exit non-zero. Only aggregate counts are reported -- no
country/code/name values appear in the exception message or the log.

Only runs on an actual upgrade (`version` is empty/None on a fresh
install, where there is nothing to check yet).
"""
import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", ("public." + table,))
    return cr.fetchone()[0] is not None


def migrate(cr, version):
    if not version:
        return

    dup_countries = 0
    dup_risk_codes = 0
    negative_weights = 0
    dup_sanctions = 0

    if _table_exists(cr, "aml_fatf_jurisdiction"):
        cr.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT country_id FROM aml_fatf_jurisdiction
                GROUP BY country_id HAVING COUNT(*) > 1
            ) conflicts
            """
        )
        dup_countries = cr.fetchone()[0]

    if _table_exists(cr, "aml_risk_factor"):
        cr.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT code FROM aml_risk_factor
                WHERE code IS NOT NULL AND code != ''
                GROUP BY code HAVING COUNT(*) > 1
            ) conflicts
            """
        )
        dup_risk_codes = cr.fetchone()[0]

        cr.execute("SELECT COUNT(*) FROM aml_risk_factor WHERE weight < 0")
        negative_weights = cr.fetchone()[0]

    if _table_exists(cr, "aml_sanctions_list"):
        cr.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT listed_name, list_source FROM aml_sanctions_list
                GROUP BY listed_name, list_source HAVING COUNT(*) > 1
            ) conflicts
            """
        )
        dup_sanctions = cr.fetchone()[0]

    if dup_countries or dup_risk_codes or negative_weights or dup_sanctions:
        message = (
            "AML_UPGRADE_BLOCKED: "
            "duplicate FATF countries=%s; "
            "duplicate risk-factor codes=%s; "
            "negative risk-factor weights=%s; "
            "duplicate sanctions name/source groups=%s; "
            "no records modified; "
            "approved remediation is required before retrying."
        ) % (dup_countries, dup_risk_codes, negative_weights, dup_sanctions)
        _logger.error(message)
        raise UserError(message)
