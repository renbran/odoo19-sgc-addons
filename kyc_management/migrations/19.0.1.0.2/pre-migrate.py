# -*- coding: utf-8 -*-
"""Fail-closed pre-upgrade guard for kyc_management.

Runs before Odoo attempts to (re)create the `kyc_application_kyc_id_unique`
constraint. If historical data already contains duplicate, non-empty
`kyc_id` values, Odoo 19's schema layer logs a WARNING and silently
leaves the constraint absent -- the module still reports a successful
(exit 0) upgrade. That is a fail-open migration path for a compliance
control, which is not acceptable here.

This script detects that condition BEFORE the upgrade proceeds and
raises, which rolls back the update transaction and makes the CLI
process exit non-zero. No records are read, logged, or modified beyond
the aggregate COUNT(*) needed to report conflict counts -- no kyc_id
values or any other PII appear in the exception message or the log.

Only runs on an actual upgrade (`version` is the previously-installed
version, empty/None on a fresh install, where there is nothing to
check yet).
"""
import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("SELECT to_regclass('public.kyc_application')")
    if cr.fetchone()[0] is None:
        return

    cr.execute(
        """
        SELECT COUNT(*) AS dup_groups, COALESCE(SUM(grp_count), 0)::bigint AS affected_rows
        FROM (
            SELECT kyc_id, COUNT(*) AS grp_count
            FROM kyc_application
            WHERE kyc_id IS NOT NULL AND kyc_id != ''
            GROUP BY kyc_id
            HAVING COUNT(*) > 1
        ) conflicts
        """
    )
    dup_groups, affected_rows = cr.fetchone()

    if dup_groups:
        message = (
            "KYC_UPGRADE_BLOCKED: "
            "duplicate kyc_id groups=%s; "
            "affected rows=%s; "
            "no records modified; "
            "run the approved KYC data-remediation process before retrying."
        ) % (dup_groups, affected_rows)
        _logger.error(message)
        raise UserError(message)
