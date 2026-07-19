# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

import logging

_logger = logging.getLogger(__name__)

# Mapping of standard Odoo account types (account.account.account_type
# selection values) to financial statement sections. Odoo removed the
# standalone account.account.type model in v17; account types are now a
# plain selection field directly on account.account, so this dict is the
# single source of truth for every value that model can hold.
ACCOUNT_TYPE_SECTION_MAPPING = {
    # ── Assets ──
    "asset_receivable": "assets",
    "asset_current": "assets",
    "asset_prepayments": "assets",
    "asset_fixed": "assets",
    "asset_non_current": "assets",
    "asset_cash": "assets",
    # ── Liabilities ──
    "liability_payable": "liabilities",
    "liability_credit_card": "liabilities",
    "liability_current": "liabilities",
    "liability_non_current": "liabilities",
    # ── Equity ──
    "equity": "equity",
    "equity_unaffected": "equity",
    # ── Revenue ──
    "income": "revenue",
    "income_other": "revenue",
    # ── Expenses ──
    "expense": "expenses",
    "expense_depreciation": "expenses",
    "expense_direct_cost": "expenses",
    # ── Other ──
    "off_balance": "other",
}


def post_init_hook_function(env):
    """Create default account type → financial statement section mappings.

    This hook runs after module installation. It creates one global
    (company-independent) ``sgc.dfr.account.type`` record per entry in
    ``ACCOUNT_TYPE_SECTION_MAPPING``. Existing mappings are skipped so the
    hook is idempotent across upgrades.

    Args:
        env: The Odoo environment (from the registry's cursor).
    """
    _logger.info("SGC DFR: Starting post-init hook – creating default account type mappings")

    SgcAccountType = env["sgc.dfr.account.type"]

    created_count = 0
    skipped_count = 0

    for account_type, section in ACCOUNT_TYPE_SECTION_MAPPING.items():
        existing = SgcAccountType.search([
            ("account_type", "=", account_type),
            ("company_id", "=", False),
        ], limit=1)

        if existing:
            skipped_count += 1
            _logger.debug(
                "SGC DFR: Mapping already exists for account type '%s' – skipping",
                account_type,
            )
            continue

        try:
            SgcAccountType.create({
                "account_type": account_type,
                "financial_section": section,
                "sequence": 10,
                "active": True,
                "company_id": False,
            })
            created_count += 1
            _logger.debug(
                "SGC DFR: Created mapping for '%s' → section '%s'",
                account_type,
                section,
            )
        except Exception as exc:
            _logger.error(
                "SGC DFR: Failed to create mapping for account type '%s': %s",
                account_type,
                exc,
            )

    _logger.info(
        "SGC DFR: Post-init hook completed – %d mappings created, %d skipped",
        created_count,
        skipped_count,
    )