# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

import html
import re
import pytz
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

# ── Financial section ordering for BS and P&L ──────────────────────────
SECTION_ORDER = {
    "assets": 10,
    "liabilities": 20,
    "equity": 30,
    "revenue": 40,
    "expenses": 50,
    "other": 99,
}

SECTION_LABELS = {
    "assets": _("Assets"),
    "liabilities": _("Liabilities"),
    "equity": _("Equity"),
    "revenue": _("Revenue"),
    "expenses": _("Expenses"),
    "other": _("Other"),
}


class SgcFinancialReportEngine(models.AbstractModel):
    """Abstract engine that provides shared data-retrieval logic for all
    SGC Dynamic Financial Reports.

    Concrete report generators (XLSX, QWeb) should inherit from this model
    (via mixin or ``_inherit``) and call the public helper methods to build
    their output.  As an AbstractModel it has no backing table and is never
    created - callers use ``env['sgc.financial.report.engine']`` directly
    (an empty recordset is enough to call its methods on).

    Architecture:
        wizard.action_generate_report()
            -> engine._generate_report(wizard)
                -> engine._build_balance_sheet(wizard)  (dispatch table)
                    -> _query_account_balances()          (shared SQL)
                    -> _build_html_table()               (shared renderer)
    """

    _name = "sgc.financial.report.engine"
    _description = "SGC Financial Report Engine (Abstract)"

    # ── Public API ───────────────────────────────────────────────────

    def _generate_report(self, wizard):
        """Dispatch to the correct report builder based on ``wizard.report_type``.

        Args:
            wizard: ``sgc.financial.report.wizard`` recordset (size 1).

        Returns:
            dict with at least an ``'html'`` key containing the rendered
            report HTML, and optional ``'data'`` key with the raw data
            structure for XLSX consumers.
        """
        dispatch = {
            "balance_sheet": self._build_balance_sheet,
            "profit_loss": self._build_profit_loss,
            "cash_flow": self._build_cash_flow,
            "trial_balance": self._build_trial_balance,
            "general_ledger": self._build_general_ledger,
            "partner_ledger": self._build_partner_ledger,
            "aged_receivable": self._build_aged_receivable,
            "aged_payable": self._build_aged_payable,
            "tax_report": self._build_tax_report,
            "budget_vs_actual": self._build_budget_vs_actual,
        }
        builder = dispatch.get(wizard.report_type)
        if not builder:
            raise UserError(
                _("Unknown report type: %s") % wizard.report_type
            )
        return builder(wizard)

    # ── Common query builder ─────────────────────────────────────────

    def _get_base_domain(self, wizard):
        """Return the common domain for account.move.line queries.

        Args:
            wizard: The wizard record.

        Returns:
            list: Odoo search domain.
        """
        domain = [
            ("company_id", "=", wizard.company_id.id),
            ("date", ">=", wizard.date_from),
            ("date", "<=", wizard.date_to),
        ]
        if wizard.target_move == "posted":
            domain.append(("parent_state", "=", "posted"))
        elif wizard.target_move == "draft":
            domain.append(("parent_state", "=", "draft"))

        if wizard.journal_ids:
            domain.append(("journal_id", "in", wizard.journal_ids.ids))

        if wizard.account_ids:
            domain.append(("account_id", "in", wizard.account_ids.ids))

        if wizard.analytic_account_ids:
            # account.move.line no longer has a plain analytic_account_id
            # field - Odoo 17+ moved to a JSON `analytic_distribution` field
            # with `distribution_analytic_account_ids` as its searchable
            # computed Many2many counterpart.
            domain.append(("distribution_analytic_account_ids", "in", wizard.analytic_account_ids.ids))

        return domain

    def _get_comparison_domain(self, wizard):
        """Return domain for the comparison period."""
        if not wizard.enable_comparison or not wizard.comparison_date_from or not wizard.comparison_date_to:
            return None
        domain = [
            ("company_id", "=", wizard.company_id.id),
            ("date", ">=", wizard.comparison_date_from),
            ("date", "<=", wizard.comparison_date_to),
        ]
        if wizard.target_move == "posted":
            domain.append(("parent_state", "=", "posted"))
        if wizard.journal_ids:
            domain.append(("journal_id", "in", wizard.journal_ids.ids))
        return domain

    def _get_account_type_mapping(self, company_id=None):
        """Return a dict mapping ``account.account.account_type`` -> financial section.

        Returns:
            dict: {account_type_string: financial_section_string}
        """
        mappings = self.env["sgc.dfr.account.type"].search([
            ("active", "=", True),
        ])
        return {m.account_type: m.financial_section for m in mappings}

    # ── Raw SQL helpers (performance-critical) ────────────────────────

    def _query_account_balances_sql(self, wizard, include_comparison=False, cumulative_all=False):
        """Execute raw SQL to get account-level debit/credit/balance.

        Returns list of dicts:
            [{account_id, company_id, company_name, code, name,
              account_type, financial_section,
              debit, credit, balance, comp_debit, comp_credit, comp_balance,
              natural_balance, comp_natural_balance,
              currency_rate, original_currency_id}]

        ``cumulative_all``: when True, every account (not just BS-section
        ones) is cumulative-to-``date_to`` with no ``date_from`` cutoff.
        Trial Balance needs this — it lists every account together and its
        own debit=credit invariant only holds when ALL accounts share one
        scope; mixing "cumulative BS, period-filtered P&L" (the default,
        correct for Balance Sheet / Profit & Loss) breaks that invariant
        for Trial Balance specifically, since revenue/expense move lines
        outside the period would be excluded while their offsetting
        asset/liability entries remain included.

        When ``wizard.consolidate_companies`` is True the SQL aggregates
        across the wizard's company plus every child company (the
        ``child_of`` hierarchy via ``res.company.parent_id``).  In that
        case the GROUP BY includes ``aml.company_id`` so each
        ``(account, company)`` pair is a distinct row — required to apply
        per-company currency conversion after the fetch.  Single-company
        callers get the original one-row-per-account shape and the
        amounts are returned unchanged.

        All SQL parameters are bound through psycopg2 placeholders so
        user-controlled values (dates, ids, bucket strings, etc.) can
        never reach the SQL text.
        """
        company_ids = self._get_company_ids(wizard)
        target_currency = self._get_target_currency(wizard)
        company_id_str = str(wizard.company_id.id)
        lang = self.env.lang or "en_US"
        consolidating = len(company_ids) > 1

        # BS-section accounts (assets/liabilities/equity) are point-in-time
        # cumulative balances - a real balance sheet only cuts off at
        # date_to, it never excludes pre-period history via date_from.
        # Revenue/expense accounts are period flows and correctly keep the
        # date_from/date_to window. Since the account->financial_section
        # mapping is data (sgc_dfr_account_type), not a hardcoded account_type
        # list, it's resolved once via a CTE so the aml join's ON clause can
        # branch on it per-account.
        #
        # target_move mirrors _get_base_domain()'s existing semantics
        # ('posted' / 'draft' / unset-meaning-all) - this query previously
        # ignored it entirely, silently including draft entries in every
        # "final" balance sheet / P&L / trial balance figure.
        target_move_filter = wizard.target_move if wizard.target_move in ("posted", "draft") else None

        # account.account.name is translate=True (JSONB, keyed by lang code)
        # and .code is a compute over code_store, a company_dependent field
        # (JSONB keyed by company id as string) - both need JSON extraction
        # rather than plain column access.
        if consolidating:
            # Per-(account, company) rows so currency conversion is exact
            # — mixing different currencies inside a single SUM() is the
            # classic consolidation bug.
            self.env.cr.execute("""
                WITH acct_sections AS (
                    SELECT
                        a.id AS account_id,
                        a.code_store AS code_store,
                        a.name AS name,
                        a.account_type AS account_type,
                        COALESCE(m.financial_section, 'other') AS financial_section
                    FROM account_account a
                    JOIN account_account_res_company_rel acr ON acr.account_account_id = a.id
                        AND acr.res_company_id = ANY(%s)
                    LEFT JOIN sgc_dfr_account_type m ON m.account_type = a.account_type
                        AND m.active = TRUE
                        AND (m.company_id IS NULL OR m.company_id = %s)
                )
                SELECT
                    acct_sections.account_id AS account_id,
                    aml_company.id AS company_id,
                    aml_company.name AS company_name,
                    rc_cur.id AS source_currency_id,
                    rc_cur.name AS source_currency_name,
                    acct_sections.code_store ->> %s AS code,
                    COALESCE(acct_sections.name ->> %s, acct_sections.name ->> 'en_US') AS name,
                    acct_sections.account_type AS account_type,
                    acct_sections.financial_section AS financial_section,
                    COALESCE(SUM(aml.debit), 0.0) AS debit,
                    COALESCE(SUM(aml.credit), 0.0) AS credit,
                    COALESCE(SUM(aml.debit - aml.credit), 0.0) AS balance
                FROM acct_sections
                LEFT JOIN account_move_line aml ON aml.account_id = acct_sections.account_id
                    AND aml.company_id = ANY(%s)
                    AND aml.date <= %s
                    AND (
                        %s
                        OR acct_sections.financial_section IN ('assets', 'liabilities', 'equity')
                        OR aml.date >= %s
                    )
                    AND (%s::text IS NULL OR aml.parent_state = %s)
                LEFT JOIN res_company aml_company ON aml_company.id = aml.company_id
                LEFT JOIN res_currency rc_cur ON rc_cur.id = aml_company.currency_id
                GROUP BY acct_sections.account_id, aml_company.id, aml_company.name,
                         rc_cur.id, rc_cur.name,
                         acct_sections.code_store, acct_sections.name,
                         acct_sections.account_type, acct_sections.financial_section
                ORDER BY acct_sections.code_store ->> %s, aml_company.name
            """, (list(company_ids), wizard.company_id.id,
                  company_id_str, lang,
                  list(company_ids), wizard.date_to, cumulative_all, wizard.date_from,
                  target_move_filter, target_move_filter,
                  company_id_str))
        else:
            # Single-company path - same acct_sections CTE, without the
            # multi-company/currency-conversion columns.
            company_id = company_ids[0]
            self.env.cr.execute("""
                WITH acct_sections AS (
                    SELECT
                        a.id AS account_id,
                        a.code_store AS code_store,
                        a.name AS name,
                        a.account_type AS account_type,
                        COALESCE(m.financial_section, 'other') AS financial_section
                    FROM account_account a
                    JOIN account_account_res_company_rel acr ON acr.account_account_id = a.id
                        AND acr.res_company_id = %s
                    LEFT JOIN sgc_dfr_account_type m ON m.account_type = a.account_type
                        AND m.active = TRUE
                        AND (m.company_id IS NULL OR m.company_id = %s)
                )
                SELECT
                    acct_sections.account_id AS account_id,
                    rc.id AS company_id,
                    rc.name AS company_name,
                    rc.currency_id AS source_currency_id,
                    cur.name AS source_currency_name,
                    acct_sections.code_store ->> %s AS code,
                    COALESCE(acct_sections.name ->> %s, acct_sections.name ->> 'en_US') AS name,
                    acct_sections.account_type AS account_type,
                    acct_sections.financial_section AS financial_section,
                    COALESCE(SUM(aml.debit), 0.0) AS debit,
                    COALESCE(SUM(aml.credit), 0.0) AS credit,
                    COALESCE(SUM(aml.debit - aml.credit), 0.0) AS balance
                FROM acct_sections
                LEFT JOIN account_move_line aml ON aml.account_id = acct_sections.account_id
                    AND aml.company_id = %s
                    AND aml.date <= %s
                    AND (
                        %s
                        OR acct_sections.financial_section IN ('assets', 'liabilities', 'equity')
                        OR aml.date >= %s
                    )
                    AND (%s::text IS NULL OR aml.parent_state = %s)
                LEFT JOIN res_company rc ON rc.id = %s
                LEFT JOIN res_currency cur ON cur.id = rc.currency_id
                GROUP BY acct_sections.account_id, rc.id, rc.name, rc.currency_id, cur.name,
                         acct_sections.code_store, acct_sections.name,
                         acct_sections.account_type, acct_sections.financial_section
                ORDER BY acct_sections.code_store ->> %s
            """, (company_id, company_id,
                  company_id_str, lang,
                  company_id, wizard.date_to, cumulative_all, wizard.date_from,
                  target_move_filter, target_move_filter,
                  company_id, company_id_str))

        rows = self.env.cr.dictfetchall()

        if include_comparison and wizard.enable_comparison:
            self.env.cr.execute("""
                SELECT
                    aml.account_id AS account_id,
                    aml.company_id AS company_id,
                    COALESCE(SUM(aml.debit), 0.0) AS comp_debit,
                    COALESCE(SUM(aml.credit), 0.0) AS comp_credit,
                    COALESCE(SUM(aml.debit - aml.credit), 0.0) AS comp_balance
                FROM account_move_line aml
                WHERE aml.date >= %s
                  AND aml.date <= %s
                  AND aml.company_id = ANY(%s)
                GROUP BY aml.account_id, aml.company_id
            """, (wizard.comparison_date_from, wizard.comparison_date_to,
                  list(company_ids)))

            comp_rows = self.env.cr.dictfetchall()
            # Map (account_id, company_id) -> comparison row so multi-
            # company rows stay distinguishable during conversion.
            comp_map = {(r["account_id"], r["company_id"]): r for r in comp_rows}
            for row in rows:
                key = (row["account_id"], row.get("company_id"))
                comp = comp_map.get(key, {})
                row["comp_debit"] = comp.get("comp_debit", 0.0)
                row["comp_credit"] = comp.get("comp_credit", 0.0)
                row["comp_balance"] = comp.get("comp_balance", 0.0)
        else:
            for row in rows:
                row["comp_debit"] = 0.0
                row["comp_credit"] = 0.0
                row["comp_balance"] = 0.0

        # `balance` (debit - credit) matches the natural sign of asset/
        # expense accounts, but liabilities/equity/revenue normally carry a
        # credit balance, so debit-credit comes out negative for them. BS/PL
        # display and totals need the "natural" (always-positive-for-normal-
        # balance) sign; Trial Balance intentionally keeps the raw one.
        for row in rows:
            sign = -1.0 if row["financial_section"] in ("liabilities", "equity", "revenue") else 1.0
            row["natural_balance"] = row["balance"] * sign
            row["comp_natural_balance"] = row["comp_balance"] * sign

        # Currency conversion is applied last so the natural-balance sign
        # flip above stays arithmetically correct (multiplying by the
        # rate is the only post-sign operation).  When target == source
        # and there's only one company this is a 1.0 pass-through.
        self._apply_currency_conversion(rows, wizard, target_currency)

        return rows

    def _compute_current_year_earnings(self, wizard, as_of_date=None):
        """Return cumulative Revenue - Expenses since inception through
        ``as_of_date`` (defaults to ``wizard.date_to``) - never filtered by
        ``date_from``.

        This is the retained-earnings component the Equity section needs
        so Assets = Liabilities + Equity holds (standard double-entry
        requirement). This module has no fiscal-year-close/rollover
        concept, so "current year earnings" here means "all undistributed
        net income since the ledger's first entry as of this date", not
        strictly the current calendar year - there is no other correct
        cutover point without adding fiscal-year-close machinery this
        module doesn't model.
        """
        as_of_date = as_of_date or wizard.date_to
        company_ids = self._get_company_ids(wizard)
        target_move_filter = wizard.target_move if wizard.target_move in ("posted", "draft") else None

        self.env.cr.execute("""
            SELECT m.financial_section AS financial_section,
                   COALESCE(SUM(aml.debit - aml.credit), 0.0) AS balance
            FROM account_move_line aml
            JOIN account_account a ON a.id = aml.account_id
            JOIN sgc_dfr_account_type m ON m.account_type = a.account_type
                AND m.active = TRUE
                AND (m.company_id IS NULL OR m.company_id = %s)
            WHERE aml.company_id = ANY(%s)
              AND aml.date <= %s
              AND (%s::text IS NULL OR aml.parent_state = %s)
              AND m.financial_section IN ('revenue', 'expenses')
            GROUP BY m.financial_section
        """, (wizard.company_id.id, list(company_ids), as_of_date,
              target_move_filter, target_move_filter))

        totals = {"revenue": 0.0, "expenses": 0.0}
        for row in self.env.cr.dictfetchall():
            totals[row["financial_section"]] = row["balance"]

        # Sign flip to natural, matching _query_account_balances_sql's
        # convention: revenue is credit-normal (sign -1), expenses stay
        # debit-normal (sign +1).
        revenue_natural = -totals["revenue"]
        expenses_natural = totals["expenses"]
        net_income = revenue_natural - expenses_natural

        target_currency = self._get_target_currency(wizard)
        company_currency = wizard.company_id.currency_id
        if target_currency != company_currency:
            rate = self._get_currency_conversion_rate(
                company_currency, target_currency, as_of_date,
            )
            net_income *= rate

        return net_income

    def _get_company_ids(self, wizard):
        """Return the list of company ids the engine should aggregate.

        When ``wizard.consolidate_companies`` is True this is the wizard's
        company plus every descendant under it (the ``child_of`` operator
        walks ``res.company.parent_id``).  Otherwise it's just the
        wizard's single company.

        The ORM search respects the current user's access rights — a user
        who cannot read a child company will simply not see its data.
        """
        if wizard.consolidate_companies:
            children = self.env["res.company"].search([
                ("id", "child_of", wizard.company_id.id),
            ])
            return children.ids
        return [wizard.company_id.id]

    def _get_target_currency(self, wizard):
        """Return the ``res.currency`` the engine should report amounts in."""
        return wizard.currency_id or wizard.company_id.currency_id

    def _get_currency_conversion_rate(self, source_currency, target_currency, date):
        """Return the rate to multiply ``source_currency`` amounts by to
        obtain ``target_currency`` amounts on ``date``.

        Returns 1.0 when the two currencies match or when conversion
        isn't possible (no rate defined, currency archived, ...) so the
        caller never has to special-case the no-op path.
        """
        if (not source_currency or not target_currency
                or source_currency == target_currency):
            return 1.0
        if not source_currency.active:
            return 1.0
        try:
            return source_currency._convert(
                1.0, target_currency, self.env.company, date, round=False,
            )
        except Exception:  # noqa: BLE001 - defensive guard for missing rates
            _logger.warning(
                "SGC DFR: currency conversion %s -> %s on %s failed; "
                "falling back to 1.0",
                source_currency.name, target_currency.name, date,
            )
            return 1.0

    def _apply_currency_conversion(self, rows, wizard, target_currency):
        """Convert each row's amounts into ``target_currency``.

        Single-company, same-currency callers take the no-op path so the
        historical amounts are byte-identical to the legacy report.

        The original amounts are preserved as ``*_original`` for audit,
        and ``currency_rate`` plus ``original_currency_id`` are stamped
        on every row.
        """
        target_id = target_currency.id
        root_currency_id = wizard.company_id.currency_id.id
        needs_conversion = bool(
            wizard.consolidate_companies
            or (wizard.currency_id and wizard.currency_id.id != root_currency_id)
        )

        if not needs_conversion:
            for row in rows:
                row["currency_rate"] = 1.0
                row["original_currency_id"] = target_id
                row["debit_original"] = row["debit"]
                row["credit_original"] = row["credit"]
                row["balance_original"] = row["balance"]
                if "comp_balance" in row:
                    row["comp_balance_original"] = row["comp_balance"]
            return

        company_currency_cache = {}
        rate_cache = {}

        def _currency_for_company(company_id):
            if company_id not in company_currency_cache:
                company = self.env["res.company"].sudo().browse(company_id)
                currency = (
                    company.currency_id if company.exists()
                    else wizard.company_id.currency_id
                )
                company_currency_cache[company_id] = currency
            return company_currency_cache[company_id]

        for row in rows:
            row_company_id = row.get("company_id")
            if row_company_id:
                src_currency = _currency_for_company(row_company_id)
            else:
                # No move lines joined - fall back to the wizard's root
                # company so the rate is at least internally consistent.
                src_currency = wizard.company_id.currency_id

            cache_key = (src_currency.id, target_id)
            if cache_key not in rate_cache:
                rate_cache[cache_key] = self._get_currency_conversion_rate(
                    src_currency, target_currency, wizard.date_from,
                )
            rate = rate_cache[cache_key]

            row["currency_rate"] = rate
            row["original_currency_id"] = src_currency.id
            row["debit_original"] = row["debit"]
            row["credit_original"] = row["credit"]
            row["balance_original"] = row["balance"]
            row["debit"] = row["debit"] * rate
            row["credit"] = row["credit"] * rate
            row["balance"] = row["balance"] * rate
            if "comp_balance" in row:
                row["comp_balance_original"] = row["comp_balance"]
                row["comp_debit"] = row["comp_debit"] * rate
                row["comp_credit"] = row["comp_credit"] * rate
                row["comp_balance"] = row["comp_balance"] * rate

    def _query_partner_balances_sql(self, wizard):
        """Execute raw SQL to get partner-level balances.

        Returns list of dicts with partner_id, partner_name, debit, credit, balance.
        """
        domain_filters = []
        params = [wizard.date_from, wizard.date_to, wizard.company_id.id]

        if wizard.partner_ids:
            domain_filters.append("AND p.id IN %s")
            params.append(tuple(wizard.partner_ids.ids))

        if wizard.partner_category_id:
            domain_filters.append("""
                AND p.id IN (
                    SELECT cp.partner_id FROM res_partner_category_rel cp
                    WHERE cp.category_id = %s
                )
            """)
            params.append(wizard.partner_category_id.id)

        extra_where = " ".join(domain_filters)

        self.env.cr.execute(f"""
            SELECT
                p.id AS partner_id,
                COALESCE(p.name, 'Unknown') AS partner_name,
                COALESCE(p.ref, '') AS partner_ref,
                COALESCE(SUM(aml.debit), 0.0) AS debit,
                COALESCE(SUM(aml.credit), 0.0) AS credit,
                COALESCE(SUM(aml.debit - aml.credit), 0.0) AS balance
            FROM res_partner p
            INNER JOIN account_move_line aml ON aml.partner_id = p.id
                AND aml.date >= %s
                AND aml.date <= %s
                AND aml.company_id = %s
            INNER JOIN account_account a ON a.id = aml.account_id
                AND a.account_type IN ('asset_receivable', 'liability_payable')
                {extra_where}
            GROUP BY p.id, p.name, p.ref
            ORDER BY p.name
        """, params)

        return self.env.cr.dictfetchall()

    def _query_aged_balances_sql(self, wizard, receivable=True):
        """Execute SQL for aged receivable/payable report.

        Returns list of dicts with partner info and bucket amounts.
        """
        account_type_filter = "asset_receivable" if receivable else "liability_payable"
        as_of_date = wizard.date_to

        # Parse aging buckets from company settings
        buckets_str = wizard.company_id.sgc_dfr_aging_buckets or "0-30,31-60,61-90,91-180,>180"
        buckets = self._parse_aging_buckets(buckets_str)

        # Build CASE WHEN for each bucket using positional aliases (b0, b1, ...)
        # rather than the user-configurable bucket label. The label comes from
        # a free-text company setting (``sgc_dfr_aging_buckets``) and must
        # never be spliced directly into a SQL identifier - min/max bounds are
        # int()-validated by _parse_aging_buckets so they're safe to inline.
        case_clauses = []
        for idx, bucket in enumerate(buckets):
            alias = f"b{idx}"
            if bucket["min"] is not None and bucket["max"] is not None:
                case_clauses.append(
                    f"SUM(CASE WHEN (days >= {int(bucket['min'])} AND days <= {int(bucket['max'])}) "
                    f"THEN balance ELSE 0.0 END) AS {alias}"
                )
            else:  # >min (open-ended)
                case_clauses.append(
                    f"SUM(CASE WHEN days > {int(bucket['min'])} "
                    f"THEN balance ELSE 0.0 END) AS {alias}"
                )

        bucket_selects = ",\n            ".join(case_clauses) if case_clauses else "0.0 AS b0"

        # aml.balance (debit - credit) is naturally positive for receivables
        # (asset, normal debit balance) but naturally negative for payables
        # (liability, normal credit balance) - flip sign for payables so
        # "amount owed" displays as a positive number, as users expect.
        balance_expr = "aml.balance" if receivable else "-aml.balance"

        self.env.cr.execute(f"""
            WITH lines AS (
                SELECT
                    p.id AS partner_id,
                    p.name AS partner_name,
                    p.ref AS partner_ref,
                    aml.id AS aml_id,
                    {balance_expr} AS balance,
                    (%s::date - aml.date) AS days
                FROM res_partner p
                INNER JOIN account_move_line aml ON aml.partner_id = p.id
                    AND aml.company_id = %s
                INNER JOIN account_account a ON aml.account_id = a.id
                WHERE a.account_type = %s
                  AND aml.date <= %s
                  AND aml.balance != 0.0
                  AND aml.parent_state = 'posted'
            )
            SELECT
                partner_id,
                COALESCE(MAX(partner_name), 'Unknown') AS partner_name,
                COALESCE(MAX(partner_ref), '') AS partner_ref,
                COUNT(DISTINCT aml_id) AS invoice_count,
                {bucket_selects},
                COALESCE(SUM(balance), 0.0) AS total_balance
            FROM lines
            GROUP BY partner_id
            HAVING ABS(COALESCE(SUM(balance), 0.0)) > 0.001
            ORDER BY MAX(partner_name)
        """, (as_of_date, wizard.company_id.id, account_type_filter, as_of_date))

        rows = self.env.cr.dictfetchall()
        # Map positional bucket aliases (b0, b1, ...) back to their
        # configured labels for the caller/renderer.
        for row in rows:
            for idx, bucket in enumerate(buckets):
                row[bucket["label"]] = row.pop(f"b{idx}", 0.0)
        return rows, buckets

    def _query_tax_report_sql(self, wizard):
        """Execute SQL for tax report.

        Returns list of dicts with tax info, net, tax, total amounts.
        """
        # account.tax.name/description are translate=True (JSONB, keyed by
        # lang code), same as account.account.name above. Also computed via
        # two separate CTEs rather than one joined-and-grouped query: a tax
        # line can be linked to several base lines (and vice versa) through
        # account_move_line_account_tax_rel, so joining both sides at once
        # and SUM()-ing would multiply-count (fan-out).
        lang = self.env.lang or "en_US"
        self.env.cr.execute("""
            WITH tax_lines AS (
                SELECT tax_line_id AS tax_id, SUM(balance) AS tax_amount
                FROM account_move_line
                WHERE tax_line_id IS NOT NULL
                  AND date >= %s AND date <= %s
                  AND company_id = %s AND parent_state = 'posted'
                GROUP BY tax_line_id
            ),
            base_lines AS (
                SELECT rel.account_tax_id AS tax_id, SUM(aml.balance) AS net_amount
                FROM account_move_line aml
                JOIN account_move_line_account_tax_rel rel ON rel.account_move_line_id = aml.id
                WHERE aml.date >= %s AND aml.date <= %s
                  AND aml.company_id = %s AND aml.parent_state = 'posted'
                GROUP BY rel.account_tax_id
            )
            SELECT
                t.id AS tax_id,
                COALESCE(t.name ->> %s, t.name ->> 'en_US', 'No Tax') AS tax_name,
                COALESCE(t.description ->> %s, t.description ->> 'en_US', '') AS tax_description,
                t.amount AS tax_rate,
                t.type_tax_use AS tax_type,
                COALESCE(bl.net_amount, 0.0) AS net_amount,
                COALESCE(tl.tax_amount, 0.0) AS tax_amount
            FROM account_tax t
            LEFT JOIN tax_lines tl ON tl.tax_id = t.id
            LEFT JOIN base_lines bl ON bl.tax_id = t.id
            WHERE t.company_id = %s
              AND (ABS(COALESCE(tl.tax_amount, 0.0)) > 0.001
                   OR ABS(COALESCE(bl.net_amount, 0.0)) > 0.001)
            ORDER BY t.type_tax_use, t.name ->> %s
        """, (wizard.date_from, wizard.date_to, wizard.company_id.id,
              wizard.date_from, wizard.date_to, wizard.company_id.id,
              lang, lang, wizard.company_id.id, lang))

        return self.env.cr.dictfetchall()

    def _query_general_ledger_sql(self, wizard):
        """Execute SQL for general ledger with opening balance.

        Returns dict with 'lines' and 'accounts' keys.
        """
        # Get opening balance per account (all moves before date_from)
        self.env.cr.execute("""
            SELECT
                aml.account_id,
                COALESCE(SUM(aml.debit), 0.0) AS opening_debit,
                COALESCE(SUM(aml.credit), 0.0) AS opening_credit,
                COALESCE(SUM(aml.debit - aml.credit), 0.0) AS opening_balance
            FROM account_move_line aml
            WHERE aml.date < %s
              AND aml.company_id = %s
              AND aml.parent_state = 'posted'
            GROUP BY aml.account_id
        """, (wizard.date_from, wizard.company_id.id))

        opening_map = {r["account_id"]: r for r in self.env.cr.dictfetchall()}

        # Get period lines
        domain = self._get_base_domain(wizard)
        domain.append(("parent_state", "=", "posted"))
        aml_ids = self.env["account.move.line"].search(domain, order="date, move_name, id")
        company_currency = wizard.company_id.currency_id

        accounts_data = {}
        lines_data = []

        for aml in aml_ids:
            acct_id = aml.account_id.id
            if acct_id not in accounts_data:
                opening = opening_map.get(acct_id, {
                    "opening_debit": 0.0, "opening_credit": 0.0, "opening_balance": 0.0
                })
                accounts_data[acct_id] = {
                    "account_id": acct_id,
                    "account_code": aml.account_id.code,
                    "account_name": aml.account_id.name,
                    "opening_debit": opening.get("opening_debit", 0.0),
                    "opening_credit": opening.get("opening_credit", 0.0),
                    "opening_balance": opening.get("opening_balance", 0.0),
                    "period_debit": 0.0,
                    "period_credit": 0.0,
                    "period_balance": 0.0,
                    "final_balance": 0.0,
                }

            acc = accounts_data[acct_id]
            acc["period_debit"] += aml.debit
            acc["period_credit"] += aml.credit

            lines_data.append({
                "date": fields.Date.to_string(aml.date),
                "move_name": aml.move_id.name or "",
                "entry_name": aml.name or "",
                "partner_name": aml.partner_id.name or "",
                "account_code": aml.account_id.code,
                "account_name": aml.account_id.name,
                "debit": aml.debit,
                "credit": aml.credit,
                "balance": aml.balance,
            })

        # Full account mapping: every account belonging to the company
        # always appears in the summary (explicitly showing 0), never
        # omitted for zero activity. The loop above only ever creates an
        # entry for accounts with at least one period line, so an account
        # with zero period activity (whether or not it carries an opening
        # balance) needs to be filled in here.
        lang = self.env.lang or "en_US"
        self.env.cr.execute("""
            SELECT a.id AS account_id,
                   a.code_store ->> %s AS code,
                   COALESCE(a.name ->> %s, a.name ->> 'en_US') AS name
            FROM account_account a
            JOIN account_account_res_company_rel acr ON acr.account_account_id = a.id
                AND acr.res_company_id = %s
        """, (str(wizard.company_id.id), lang, wizard.company_id.id))
        for r in self.env.cr.dictfetchall():
            if r["account_id"] not in accounts_data:
                opening = opening_map.get(r["account_id"], {
                    "opening_debit": 0.0, "opening_credit": 0.0, "opening_balance": 0.0
                })
                accounts_data[r["account_id"]] = {
                    "account_id": r["account_id"],
                    "account_code": r["code"],
                    "account_name": r["name"],
                    "opening_debit": opening.get("opening_debit", 0.0),
                    "opening_credit": opening.get("opening_credit", 0.0),
                    "opening_balance": opening.get("opening_balance", 0.0),
                    "period_debit": 0.0,
                    "period_credit": 0.0,
                    "period_balance": 0.0,
                    "final_balance": 0.0,
                }

        # Compute final balances
        for acc in accounts_data.values():
            acc["period_balance"] = acc["period_debit"] - acc["period_credit"]
            acc["final_balance"] = acc["opening_balance"] + acc["period_balance"]

        return {
            "accounts": sorted(accounts_data.values(), key=lambda x: x["account_code"]),
            "lines": lines_data,
        }

    # ── Drill-down helpers (BI / AJAX) ───────────────────────────────

    def _get_drilldown_data(self, wizard, account_id):
        """Return structured drill-down data for a single account.

        Reuses the same opening-balance + period-line logic as
        ``_query_general_ledger_sql`` but scoped to one account.  Designed
        for AJAX/BI drill-down endpoints that need machine-readable data
        (not HTML).

        Args:
            wizard: ``sgc.financial.report.wizard`` recordset (size 1).
                Provides ``date_from``, ``date_to``, ``company_id`` and
                (optionally) ``target_move`` / filter fields.
            account_id: ``account.account`` ID to scope the query to.

        Returns:
            dict with the following keys (or ``None`` if the account does
            not belong to the wizard's company):

            * ``account_id``, ``account_code``, ``account_name``,
              ``account_type``
            * ``opening_debit``, ``opening_credit``, ``opening_balance``
            * ``period_debit``, ``period_credit``, ``period_balance``,
              ``final_balance``
            * ``move_lines``: list of dicts, each with ``move_line_id``,
              ``date``, ``ref``, ``move_id``, ``partner_id``,
              ``partner_name``, ``label``, ``account_id``,
              ``account_code``, ``debit``, ``credit``, ``balance``.
        """
        account_id = int(account_id)

        # Validate account belongs to the wizard's company (defence-in-depth
        # in addition to the controller's group/company check).
        account = self.env["account.account"].with_company(
            wizard.company_id
        ).browse(account_id)
        if not account.exists() or wizard.company_id not in account.company_ids:
            return None

        # Opening balance: posted lines strictly before date_from, scoped
        # to this account and the wizard's company.  Mirrors the prefix
        # query in _query_general_ledger_sql.
        self.env.cr.execute(
            """
            SELECT
                COALESCE(SUM(aml.debit), 0.0) AS opening_debit,
                COALESCE(SUM(aml.credit), 0.0) AS opening_credit,
                COALESCE(SUM(aml.debit - aml.credit), 0.0) AS opening_balance
            FROM account_move_line aml
            WHERE aml.account_id = %s
              AND aml.date < %s
              AND aml.company_id = %s
              AND aml.parent_state = 'posted'
            """,
            (account_id, wizard.date_from, wizard.company_id.id),
        )
        opening_row = self.env.cr.dictfetchone() or {
            "opening_debit": 0.0,
            "opening_credit": 0.0,
            "opening_balance": 0.0,
        }

        # Period lines: reuse _get_base_domain and just narrow by account.
        domain = self._get_base_domain(wizard)
        domain.append(("account_id", "=", account_id))
        domain.append(("parent_state", "=", "posted"))
        aml_ids = self.env["account.move.line"].search(
            domain, order="date, move_name, id"
        )

        lines_data = []
        period_debit = 0.0
        period_credit = 0.0
        running_balance = opening_row.get("opening_balance", 0.0) or 0.0

        for aml in aml_ids:
            period_debit += aml.debit
            period_credit += aml.credit
            running_balance += aml.debit - aml.credit
            lines_data.append({
                "move_line_id": aml.id,
                "date": fields.Date.to_string(aml.date) if aml.date else False,
                "ref": aml.move_id.name or "",
                "move_id": aml.move_id.id,
                "partner_id": aml.partner_id.id or False,
                "partner_name": aml.partner_id.name or "",
                "label": aml.name or "",
                "account_id": aml.account_id.id,
                "account_code": aml.account_id.code or "",
                "debit": aml.debit,
                "credit": aml.credit,
                "balance": running_balance,
            })

        period_balance = period_debit - period_credit
        final_balance = (opening_row.get("opening_balance", 0.0) or 0.0) + period_balance

        return {
            "account_id": account_id,
            "account_code": account.code or "",
            "account_name": account.name or "",
            "account_type": account.account_type or "",
            "opening_debit": opening_row.get("opening_debit", 0.0) or 0.0,
            "opening_credit": opening_row.get("opening_credit", 0.0) or 0.0,
            "opening_balance": opening_row.get("opening_balance", 0.0) or 0.0,
            "period_debit": period_debit,
            "period_credit": period_credit,
            "period_balance": period_balance,
            "final_balance": final_balance,
            "move_lines": lines_data,
        }

    # ── Budget vs Actual ──────────────────────────────────────────────

    def _query_budget_vs_actual_sql(self, wizard):
        """Return ``{account_id: budget_amount}`` for the wizard's period.

        Joins ``sgc_dfr_budget`` filtered by the multi-company set and the
        fiscal year extracted from ``wizard.date_from``.  When the header
        ``amount`` is set, that's used; otherwise the engine sums the
        matching ``sgc_dfr.budget.line`` rows as a fallback (lets users
        enter per-month budgets without touching the yearly header).

        Conversion to ``wizard.currency_id`` happens here so the BS/PL
        builders can compare apples to apples.  All parameters are bound
        through psycopg2 placeholders - even the fiscal_year string is
        parameterised so a crafted wizard value cannot reach the SQL text.
        """
        company_ids = self._get_company_ids(wizard)
        target_currency = self._get_target_currency(wizard)
        fiscal_year = str(wizard.date_from.year)

        # COALESCE the line subquery with 0 so a header with unset
        # amount + no lines still yields 0 (not NULL) in the SUM below.
        self.env.cr.execute("""
            SELECT
                b.account_id AS account_id,
                b.currency_id AS source_currency_id,
                COALESCE(SUM(
                    CASE WHEN COALESCE(b.amount, 0.0) != 0.0
                         THEN b.amount
                         ELSE COALESCE((
                             SELECT SUM(bl.amount)
                             FROM sgc_dfr_budget_line bl
                             WHERE bl.budget_id = b.id
                         ), 0.0)
                    END
                ), 0.0) AS budget_amount
            FROM sgc_dfr_budget b
            WHERE b.company_id = ANY(%s)
              AND b.fiscal_year = %s
            GROUP BY b.account_id, b.currency_id
        """, (list(company_ids), fiscal_year))

        rows = self.env.cr.dictfetchall()

        result = {}
        for r in rows:
            src_currency = self.env["res.currency"].browse(r["source_currency_id"])
            rate = self._get_currency_conversion_rate(
                src_currency, target_currency, wizard.date_from,
            )
            converted = r["budget_amount"] * rate
            result[r["account_id"]] = result.get(r["account_id"], 0.0) + converted

        return result

    def _compute_budget_vs_actual(self, wizard, rows):
        """Stamp each row with budget / variance data in place.

        ``natural_balance`` is the canonical "actual" figure for BS/PL
        (debit-credit flipped for credit-normal sections).  For accounts
        with no budget line, every field is 0.0 so the calling builder
        can render an empty budget column without special-casing.
        """
        budgets = self._query_budget_vs_actual_sql(wizard)
        for row in rows:
            budget_amount = budgets.get(row["account_id"], 0.0)
            actual_amount = row.get("natural_balance", row.get("balance", 0.0))
            variance = actual_amount - budget_amount
            variance_pct = (variance / budget_amount * 100.0) if budget_amount else 0.0
            row["budget_amount"] = budget_amount
            row["variance"] = variance
            row["variance_pct"] = variance_pct
        return rows

    def _budget_columns(self):
        """Return the standard budget column header list."""
        return ["Budget", "Actual", "Variance", "Variance %"]

    def _budget_row_cells(self, row, wizard):
        """Return the four-cell map for the budget columns of a single row."""
        return {
            "Budget": self._fmt(row.get("budget_amount", 0.0), wizard),
            "Actual": self._fmt(row.get("natural_balance", 0.0), wizard),
            "Variance": self._fmt(row.get("variance", 0.0), wizard),
            "Variance %": (
                f"{row.get('variance_pct', 0.0):.2f}%"
                if row.get("budget_amount") else ""
            ),
        }

    def _build_budget_vs_actual(self, wizard):
        """Build the Budget vs Actual report.

        Reuses ``_query_account_balances_sql`` so multi-company and
        currency-conversion behavior is identical to the rest of the
        suite.  Returns the same ``{html, data}`` shape as every other
        builder so the wizard / XLSX controllers don't need to know
        which report type they got back.
        """
        _logger.info(
            "SGC DFR: Generating Budget vs Actual for company %s",
            wizard.company_id.name,
        )
        rows = self._query_account_balances_sql(wizard, include_comparison=False)

        pl_sections = {"revenue", "expenses"}
        pl_rows = [r for r in rows if r.get("financial_section") in pl_sections]

        budgets = self._query_budget_vs_actual_sql(wizard)
        if not wizard.show_zero_balance:
            pl_rows = [
                r for r in pl_rows
                if abs(r.get("balance", 0)) > 0.001
                or abs(budgets.get(r["account_id"], 0.0)) > 0.001
            ]

        self._compute_budget_vs_actual(wizard, pl_rows)
        pl_rows.sort(key=lambda r: (
            SECTION_ORDER.get(r.get("financial_section"), 99),
            r.get("code") or "",
        ))

        html = self._build_report_header_html(wizard, "Budget vs Actual")
        columns = ["Code", "Account Name"] + self._budget_columns()

        section_totals = {
            section_key: {"budget": 0.0, "actual": 0.0, "variance": 0.0}
            for section_key in pl_sections
        }

        for section_key in sorted(pl_sections, key=lambda x: SECTION_ORDER.get(x, 99)):
            section_rows = [r for r in pl_rows if r["financial_section"] == section_key]
            if not section_rows:
                continue
            html += (
                f'<h4 class="sgc_section_title">'
                f'{SECTION_LABELS.get(section_key, section_key.title())}</h4>'
            )
            display_rows = []
            for row in section_rows:
                display_row = {
                    "Code": row.get("code") or "",
                    "Account Name": row.get("name") or "",
                }
                display_row.update(self._budget_row_cells(row, wizard))
                if row.get("variance", 0.0) < 0:
                    display_row["css_class"] = "negative"
                elif row.get("variance", 0.0) > 0:
                    display_row["css_class"] = "positive"
                display_rows.append(display_row)
                section_totals[section_key]["budget"] += row.get("budget_amount", 0.0)
                section_totals[section_key]["actual"] += row.get("natural_balance", 0.0)
                section_totals[section_key]["variance"] += row.get("variance", 0.0)

            totals = {
                "Code": f"Total {SECTION_LABELS.get(section_key, section_key.title())}",
                "Account Name": "",
            }
            totals.update(self._budget_row_cells(
                {
                    "budget_amount": section_totals[section_key]["budget"],
                    "natural_balance": section_totals[section_key]["actual"],
                    "variance": section_totals[section_key]["variance"],
                },
                wizard,
            ))
            html += self._build_html_table(columns, display_rows, totals, wizard=wizard)

        net_variance = (
            section_totals["revenue"]["variance"]
            - section_totals["expenses"]["variance"]
        )
        net_actual = (
            section_totals["revenue"]["actual"]
            - section_totals["expenses"]["actual"]
        )
        net_budget = (
            section_totals["revenue"]["budget"]
            - section_totals["expenses"]["budget"]
        )
        html += self._build_grand_total_html([
            ("NET VARIANCE (Actual - Budget)", self._fmt(net_variance, wizard)),
            ("Net Actual / Net Budget", self._fmt(net_actual, wizard), self._fmt(net_budget, wizard)),
        ])

        return {
            "html": html,
            "data": {
                "rows": pl_rows,
                "sections": section_totals,
                "net_variance": net_variance,
            },
        }

    # ── HTML rendering helpers ────────────────────────────────────────

    def _fmt(self, amount, wizard=None):
        """Format a monetary amount for display."""
        if amount is None:
            return ""
        precision = 2
        if wizard and wizard.company_id.sgc_dfr_decimal_precision:
            precision = wizard.company_id.sgc_dfr_decimal_precision
        # Normalize IEEE-754 negative zero (e.g. 0.0 * -1 in the sign-flip
        # for credit-normal sections) so full account mapping shows "0.00"
        # for zero-balance rows, never the confusing "-0.00".
        if amount == 0:
            amount = 0.0
        formatted = f"{amount:,.{precision}f}"
        if amount < 0 and wizard and wizard.company_id.sgc_dfr_negative_format == "parentheses":
            formatted = f"({formatted[1:]})"
        return formatted

    def _strip_html_tags(self, value):
        """Strip markup from free-text fields (e.g. ``account.tax.description``)
        that may contain stray HTML from a rich-text source, so reports show
        clean text instead of literal tags."""
        if not value:
            return value
        text = re.sub(r"<[^>]+>", "", value)
        text = html.unescape(text)
        return text.strip()

    def _wrap_collapsible(self, title, body_html, open_by_default=False):
        """Wrap a report section (title + table) in a native, JS-free
        collapsible ``<details>`` element.

        ``open_by_default`` controls only the initial on-screen state.
        When rendering for print/PDF (``sgc_dfr_for_print`` in context,
        set by ``action_print_pdf`` via ``action_generate_report(for_print=True)``),
        every section is forced open here at generation time — a PDF has
        no click events, so collapse state has to be correct in the raw
        HTML itself rather than relying on ``@media print`` CSS to force
        it visible, which is not something every wkhtmltopdf build/version
        honors consistently.

        ``title`` is escaped here (not by the caller) since section titles
        are frequently built from user data (partner names, tax names) —
        the same class of untrusted string that caused the ``html`` module
        shadowing bug this file was already fixed for.
        """
        safe_title = html.escape(str(title))
        if self.env.context.get("sgc_dfr_for_print"):
            # wkhtmltopdf's bundled Qt WebKit does not reliably render
            # <details> content even with the `open` attribute present
            # (verified live: PDF rendered only the <summary> titles with
            # every section's table missing entirely). A PDF never needs
            # collapse behavior anyway, so print rendering skips <details>
            # altogether and emits a plain, always-visible section block.
            return (
                f'<div class="sgc_section_block">'
                f'<h4 class="sgc_section_title">{safe_title}</h4>'
                f'{body_html}'
                f'</div>'
            )
        open_attr = " open" if open_by_default else ""
        return (
            f'<details class="sgc_collapsible_section"{open_attr}>'
            f'<summary class="sgc_section_title">{safe_title}</summary>'
            f'{body_html}'
            f'</details>'
        )

    def _build_collapse_toggle_bar(self):
        """Return the 'Expand All / Collapse All' control shown once per
        report, above its collapsible sections.

        Omitted entirely when rendering for print (``sgc_dfr_for_print``)
        since the PDF has no click events and every section is already
        forced open by ``_wrap_collapsible`` - showing dead buttons in a
        static document would look broken, not just unnecessary.

        Plain inline ``onclick`` handlers (not a ``<script>`` tag) are used
        deliberately: this HTML string is injected via ``t-out``/``t-raw``,
        which sets it through ``innerHTML`` — browsers do not execute
        ``<script>`` tags inserted that way, but element attributes like
        ``onclick`` still bind normally. Unscoped ``document.querySelectorAll``
        is safe here because only one report's HTML is ever mounted into the
        page at a time (the OWL client action replaces the whole container
        on every Generate click; a PDF export renders exactly one report
        with no JS execution at all).
        """
        if self.env.context.get("sgc_dfr_for_print"):
            return ""
        return (
            '<div class="sgc_collapse_toggle_bar">'
            '<button type="button" class="btn btn-sm btn-outline-secondary sgc_expand_all_btn" '
            'onclick="document.querySelectorAll(&quot;.sgc_collapsible_section&quot;)'
            '.forEach(function(d){d.open=true;})">Expand All</button> '
            '<button type="button" class="btn btn-sm btn-outline-secondary sgc_collapse_all_btn" '
            'onclick="document.querySelectorAll(&quot;.sgc_collapsible_section&quot;)'
            '.forEach(function(d){d.open=false;})">Collapse All</button>'
            '</div>'
        )

    def _build_grand_total_html(self, rows):
        """Build a clean summary table for report grand totals.

        ``rows`` is a list of ``(label, *value_strings)`` tuples. Unlike
        the old inline f-string tables, this only ever emits as many
        ``<td>`` cells as each row actually has values for — the previous
        code padded every grand-total row out to a fixed column count
        with empty ``<td></td>`` cells (to visually "align" with the
        wider account table above it), which rendered as a row of dangling
        blank boxes in the PDF export where that alignment doesn't matter.
        """
        html_parts = ['<div class="sgc-report sgc_grand_total">',
                      '<table class="table table-bordered table-sm o_sgc_report_table o_sgc_grand_total_table">']
        for row in rows:
            label, values = row[0], row[1:]
            html_parts.append('<tr class="grand-total">')
            html_parts.append(f"<td><strong>{label}</strong></td>")
            for val in values:
                html_parts.append(f"<td><strong>{val}</strong></td>")
            html_parts.append("</tr>")
        html_parts.append("</table></div>")
        return "".join(html_parts)

    _NUMERIC_CELL_RE = re.compile(r"^\(?-?[\d,]+(\.\d+)?\)?$")

    def _text_columns(self, columns, rows, totals=None):
        """Decide which columns hold text (account codes/names/descriptions,
        left-aligned) vs formatted numbers (right-aligned, the default).

        A column is "text" if any of its actual values (across body rows and
        the totals row) don't look like a formatted number - e.g. "1,234.56"
        or "(500.00)". Columns with no values default to numeric/right-align,
        matching prior behaviour. This inspects real content instead of
        assuming column position, since the same column index means
        different things across this file's report layouts (e.g. column 2
        is "Account Name" in the balance sheet but a dollar amount in some
        grand-total rows).
        """
        text_columns = set()
        for col in columns:
            values = [row.get(col) for row in rows if row.get(col) not in ("", None)]
            if totals and totals.get(col) not in ("", None):
                values.append(totals.get(col))
            if values and not all(self._NUMERIC_CELL_RE.match(str(v).strip()) for v in values):
                text_columns.add(col)
        return text_columns

    def _build_html_table(self, columns, rows, totals=None, css_class="", wizard=None):
        """Build an HTML table string for report display.

        Args:
            columns: list of column header strings.
            rows: list of dicts, each keyed by column name.
            totals: optional dict of column -> total value.
            css_class: extra CSS class for the table.
            wizard: optional ``sgc.financial.report.wizard`` recordset used
                to drive rendering flags (``analytic_breakdown``).

        Returns:
            str: HTML string.
        """
        analytic_columns = self._build_analytic_breakdown_columns(wizard)
        text_columns = self._text_columns(columns, rows, totals)

        html_parts = [f'<div class="sgc-report {css_class}">']
        html_parts.append('<table class="table table-bordered table-sm o_sgc_report_table">')

        # Header
        html_parts.append('<thead><tr class="table-primary">')
        for col in columns:
            th_class = ' class="sgc-col-text"' if col in text_columns else ""
            html_parts.append(f"<th{th_class}>{col}</th>")
        if analytic_columns:
            html_parts.append('<th colspan="%d" class="text-center">Analytic Breakdown</th>' % len(analytic_columns))
            html_parts.append('</tr><tr class="table-primary">')
            for col in columns:
                html_parts.append(f'<th></th>')
            for col in analytic_columns:
                html_parts.append(f'<th>{col}</th>')
        html_parts.append('</tr></thead>')

        # Body
        html_parts.append('<tbody>')
        for row in rows:
            row_class = row.pop("css_class", "")
            analytic_values = row.pop("_analytic_values", None)
            # Drill-down wiring: every account row gets a data-account-id
            # attribute so the OWL client-action JS can fetch and render
            # /sgc/dfr/drilldown/<wid>/<aid> move lines inline when the
            # row is clicked. Rows without account_id (e.g. partner
            # aggregations or <tfoot> section totals) get no attribute,
            # so they stay non-clickable.
            row_attrs = []
            _acct_id = row.get("account_id")
            if _acct_id:
                row_attrs.append("data-account-id=\"" + str(int(_acct_id)) + "\"")
            attrs_str = (" " + " ".join(row_attrs)) if row_attrs else ""
            if row_class:
                html_parts.append("<tr class=\"" + row_class + "\"" + attrs_str + ">")
            elif attrs_str:
                html_parts.append("<tr" + attrs_str + ">")
            else:
                html_parts.append("<tr>")
            for col in columns:
                val = row.get(col, "")
                if isinstance(val, float):
                    val = self._fmt(val)
                if isinstance(val, str):
                    val = html.escape(val)
                cell_class = "sgc-col-text" if col in text_columns else ""
                if val and isinstance(val, (int, float)) and val < 0:
                    cell_class = f"{cell_class} negative".strip()
                if cell_class:
                    html_parts.append(f'<td class="{cell_class}">{val}</td>')
                else:
                    html_parts.append(f"<td>{val}</td>")
            if analytic_columns:
                if analytic_values is None:
                    analytic_values = [0.0] * len(analytic_columns)
                for val in analytic_values:
                    formatted = self._fmt(val, wizard) if val else ""
                    if val and val < 0:
                        html_parts.append(f'<td class="negative analytic-cell">{formatted}</td>')
                    else:
                        html_parts.append(f'<td class="analytic-cell">{formatted}</td>')
            html_parts.append("</tr>")
        html_parts.append("</tbody>")

        # Totals
        if totals:
            html_parts.append('<tfoot><tr class="total-row">')
            for col in columns:
                val = totals.get(col, "")
                if isinstance(val, float):
                    val = self._fmt(val)
                td_class = ' class="sgc-col-text"' if col in text_columns else ""
                html_parts.append(f"<td{td_class}>{val}</td>")
            if analytic_columns:
                for col in analytic_columns:
                    html_parts.append('<td class="analytic-total"></td>')
            html_parts.append('</tr></tfoot>')

        html_parts.append("</table></div>")
        return "\n".join(html_parts)

    def _build_analytic_breakdown_columns(self, wizard):
        """Return the list of analytic-column headers for an HTML table.

        Returns an empty list when ``analytic_breakdown`` is False or no
        analytic accounts are available; the caller appends zero such
        columns and the table is rendered exactly as before.
        """
        if not wizard or not getattr(wizard, "analytic_breakdown", False):
            return []
        analytic_accounts = wizard.analytic_account_ids
        if analytic_accounts:
            return [a.name or a.code or f"Account {a.id}" for a in analytic_accounts]
        return ["Analytic"]  # placeholder column when no filter is set

    def _build_report_header_html(self, wizard, title):
        """Build the report header HTML block."""
        company = wizard.company_id
        header = company.sgc_dfr_report_header or ""
        html = '<div class="sgc_report_header">'
        if header:
            html += f'<p class="sgc_custom_header">{header}</p>'
        html += f"<h2>{company.name}</h2>"
        html += f"<h3>{title}</h3>"
        html += f"<p>From {fields.Date.to_string(wizard.date_from)} to {fields.Date.to_string(wizard.date_to)}</p>"
        currency = company.currency_id
        if company.sgc_dfr_show_currency_symbol:
            html += f'<p>All amounts in {currency.name} ({currency.symbol})</p>'
        html += "</div>"
        html += self._build_collapse_toggle_bar()
        return html

    def _parse_aging_buckets(self, buckets_str):
        """Parse aging bucket string like '0-30,31-60,61-90,91-180,>180'.

        Returns list of dicts: [{'label': '0-30', 'min': 0, 'max': 30}, ...]
        """
        import re
        buckets = []
        for part in buckets_str.split(","):
            part = part.strip()
            if not re.match(r"^(?:\d+-\d+|>\d+)$", part):
                continue
            if part.startswith(">"):
                min_val = int(part[1:])
                buckets.append({"label": part, "min": min_val, "max": None})
            elif "-" in part:
                parts = part.split("-")
                min_val = int(parts[0])
                max_val = int(parts[1])
                buckets.append({"label": part, "min": min_val, "max": max_val})
        return buckets

    # ── Report builders ───────────────────────────────────────────────

    def _build_balance_sheet(self, wizard):
        """Build Balance Sheet report data and HTML.

        Structure:
            ASSETS
              - Current Assets (account type groupings)
              - Non-Current Assets
            LIABILITIES
              - Current Liabilities
              - Non-Current Liabilities
            EQUITY
              - Retained Earnings, Share Capital, etc.

        Comparison columns are added when enable_comparison is True.
        Budget columns are added when show_budget_vs_actual is True.
        """
        _logger.info("SGC DFR: Generating Balance Sheet for company %s", wizard.company_id.name)
        rows = self._query_account_balances_sql(wizard, include_comparison=True)

        # Filter to BS sections only (assets, liabilities, equity)
        bs_sections = {"assets", "liabilities", "equity"}
        # Full account mapping: every account mapped to a BS section always
        # renders (explicitly showing 0), never omitted for a zero balance -
        # the underlying query already LEFT JOINs from account_account, so
        # every mapped account is present in `rows` regardless of activity.
        bs_rows = [r for r in rows if r.get("financial_section") in bs_sections]

        has_comparison = wizard.enable_comparison and wizard.comparison_date_from

        # Current Year Earnings (Revenue - Expenses since inception through
        # date_to) is a synthetic Equity line, not a real GL account -
        # without it Assets never equals Liabilities + Equity for any
        # period with trading activity, a core double-entry requirement.
        current_year_earnings = self._compute_current_year_earnings(wizard)
        cye_comp_balance = 0.0
        if has_comparison:
            cye_comp_balance = self._compute_current_year_earnings(
                wizard, as_of_date=wizard.comparison_date_to,
            )
        bs_rows.append({
            "account_id": None,
            "code": "",
            "name": _("Current Year Earnings"),
            "financial_section": "equity",
            "debit": 0.0 if current_year_earnings >= 0 else -current_year_earnings,
            "credit": current_year_earnings if current_year_earnings >= 0 else 0.0,
            "natural_balance": current_year_earnings,
            "comp_natural_balance": cye_comp_balance,
        })

        budget_active = bool(wizard.show_budget_vs_actual)
        if budget_active:
            self._compute_budget_vs_actual(wizard, bs_rows)

        # Group by financial section
        sections = {}
        for row in bs_rows:
            section = row["financial_section"]
            if section not in sections:
                sections[section] = []
            sections[section].append(row)

        # Build HTML
        html = self._build_report_header_html(wizard, "Balance Sheet")

        for section_key in sorted(bs_sections, key=lambda x: SECTION_ORDER.get(x, 99)):
            section_rows = sections.get(section_key, [])
            if not section_rows:
                continue

            section_label = SECTION_LABELS.get(section_key, section_key.title())

            columns = ["Code", "Account Name"]
            if has_comparison:
                columns += ["Comp. Balance"]
            columns += ["Debit", "Credit", "Balance"]
            if has_comparison:
                columns.append("Variance")
            if budget_active:
                columns += self._budget_columns()

            display_rows = []
            section_total = {"debit": 0.0, "credit": 0.0, "balance": 0.0}
            if has_comparison:
                section_total["comp_balance"] = 0.0
            if budget_active:
                section_total["budget"] = 0.0

            for row in section_rows:
                display_row = {
                    "Code": row["code"],
                    "Account Name": row["name"],
                    "Debit": self._fmt(row["debit"], wizard),
                    "Credit": self._fmt(row["credit"], wizard),
                    "Balance": self._fmt(row["natural_balance"], wizard),
                }
                if has_comparison:
                    display_row["Comp. Balance"] = self._fmt(row["comp_natural_balance"], wizard)
                    variance = row["natural_balance"] - row["comp_natural_balance"]
                    display_row["Variance"] = self._fmt(variance, wizard)
                    if variance:
                        display_row["css_class"] = "positive" if variance > 0 else "negative"
                    section_total["comp_balance"] += row["comp_natural_balance"]

                if budget_active:
                    display_row.update(self._budget_row_cells(row, wizard))
                    section_total["budget"] += row.get("budget_amount", 0.0)

                section_total["debit"] += row["debit"]
                section_total["credit"] += row["credit"]
                section_total["balance"] += row["natural_balance"]
                display_rows.append(display_row)

            totals = {
                "Code": f"Total {SECTION_LABELS.get(section_key, section_key.title())}",
                "Debit": self._fmt(section_total["debit"], wizard),
                "Credit": self._fmt(section_total["credit"], wizard),
                "Balance": self._fmt(section_total["balance"], wizard),
            }
            if has_comparison:
                totals["Comp. Balance"] = self._fmt(section_total["comp_balance"], wizard)
                variance = section_total["balance"] - section_total["comp_balance"]
                totals["Variance"] = self._fmt(variance, wizard)
            if budget_active:
                totals.update(self._budget_row_cells(
                    {
                        "budget_amount": section_total["budget"],
                        "natural_balance": section_total["balance"],
                    },
                    wizard,
                ))

            section_table_html = self._build_html_table(columns, display_rows, totals, wizard=wizard)
            html += self._wrap_collapsible(section_label, section_table_html)

        # Grand total: Assets = Liabilities + Equity
        assets_total = sum(r["natural_balance"] for r in bs_rows if r["financial_section"] == "assets")
        liab_eq_total = sum(r["natural_balance"] for r in bs_rows if r["financial_section"] in ("liabilities", "equity"))
        html += self._build_grand_total_html([
            ("TOTAL ASSETS", self._fmt(assets_total, wizard)),
            ("TOTAL LIABILITIES + EQUITY", self._fmt(liab_eq_total, wizard)),
        ])

        return {
            "html": html,
            "data": {
                "sections": sections,
                "rows": bs_rows,
                "totals": {"assets": assets_total, "liabilities_equity": liab_eq_total},
            },
        }

    def _build_profit_loss(self, wizard):
        """Build Profit & Loss report data and HTML.

        Structure:
            REVENUE
              - Income accounts
            EXPENSES
              - Expense accounts
            NET INCOME = Revenue Total - Expense Total

        Budget columns are added when show_budget_vs_actual is True.
        """
        _logger.info("SGC DFR: Generating Profit & Loss for company %s", wizard.company_id.name)
        rows = self._query_account_balances_sql(wizard, include_comparison=True)

        pl_sections = {"revenue", "expenses"}
        # Full account mapping: every revenue/expense account always
        # renders (explicitly showing 0), never omitted for zero activity.
        pl_rows = [r for r in rows if r.get("financial_section") in pl_sections]

        budget_active = bool(wizard.show_budget_vs_actual)
        if budget_active:
            self._compute_budget_vs_actual(wizard, pl_rows)

        sections = {}
        for row in pl_rows:
            section = row["financial_section"]
            if section not in sections:
                sections[section] = []
            sections[section].append(row)

        html = self._build_report_header_html(wizard, "Profit & Loss Statement")
        has_comparison = wizard.enable_comparison and wizard.comparison_date_from

        grand_totals = {"revenue": 0.0, "expenses": 0.0}
        if budget_active:
            grand_totals = {k: {"balance": 0.0, "budget": 0.0, "variance": 0.0}
                            for k in grand_totals}

        for section_key in sorted(pl_sections, key=lambda x: SECTION_ORDER.get(x, 99)):
            section_rows = sections.get(section_key, [])
            if not section_rows:
                continue

            section_label = SECTION_LABELS.get(section_key, section_key.title())

            columns = ["Code", "Account Name"]
            if has_comparison:
                columns.append("Comp. Balance")
            columns += ["Debit", "Credit", "Balance"]
            if budget_active:
                columns += self._budget_columns()

            display_rows = []
            section_total = {"debit": 0.0, "credit": 0.0, "balance": 0.0}
            if budget_active:
                section_total["budget"] = 0.0

            for row in section_rows:
                display_row = {
                    "Code": row["code"],
                    "Account Name": row["name"],
                    "Debit": self._fmt(row["debit"], wizard),
                    "Credit": self._fmt(row["credit"], wizard),
                    "Balance": self._fmt(row["natural_balance"], wizard),
                }
                if has_comparison:
                    display_row["Comp. Balance"] = self._fmt(row["comp_natural_balance"], wizard)
                if budget_active:
                    display_row.update(self._budget_row_cells(row, wizard))

                section_total["debit"] += row["debit"]
                section_total["credit"] += row["credit"]
                section_total["balance"] += row["natural_balance"]
                if budget_active:
                    section_total["budget"] += row.get("budget_amount", 0.0)
                display_rows.append(display_row)

            if budget_active:
                grand_totals[section_key]["balance"] = section_total["balance"]
                grand_totals[section_key]["budget"] = section_total["budget"]
                grand_totals[section_key]["variance"] = (
                    section_total["balance"] - section_total["budget"]
                )
            else:
                grand_totals[section_key] = section_total["balance"]

            totals = {
                "Code": f"Total {SECTION_LABELS.get(section_key, section_key.title())}",
                "Debit": self._fmt(section_total["debit"], wizard),
                "Credit": self._fmt(section_total["credit"], wizard),
                "Balance": self._fmt(section_total["balance"], wizard),
            }
            if has_comparison:
                totals["Comp. Balance"] = ""
            if budget_active:
                totals.update(self._budget_row_cells(
                    {
                        "budget_amount": section_total["budget"],
                        "natural_balance": section_total["balance"],
                    },
                    wizard,
                ))

            section_table_html = self._build_html_table(columns, display_rows, totals, wizard=wizard)
            html += self._wrap_collapsible(section_label, section_table_html)

        if budget_active:
            net_income = (
                grand_totals["revenue"]["balance"] - grand_totals["expenses"]["balance"]
            )
            net_budget = (
                grand_totals["revenue"]["budget"] - grand_totals["expenses"]["budget"]
            )
            net_variance = net_income - net_budget
            html += self._build_grand_total_html([
                (
                    "NET INCOME" if net_income >= 0 else "NET LOSS",
                    self._fmt(net_income, wizard),
                    f"Budget: {self._fmt(net_budget, wizard)}",
                    f"Variance: {self._fmt(net_variance, wizard)}",
                ),
            ])
        else:
            net_income = grand_totals["revenue"] - grand_totals["expenses"]
            html += self._build_grand_total_html([
                ("NET INCOME" if net_income >= 0 else "NET LOSS", self._fmt(net_income, wizard)),
            ])

        return {
            "html": html,
            "data": {
                "sections": sections,
                "rows": pl_rows,
                "net_income": net_income,
                "totals": grand_totals,
            },
        }

    def _build_cash_flow(self, wizard):
        """Build Cash Flow Statement report.

        Uses indirect method:
            Operating Activities = Net Income + non-cash adjustments
            Investing Activities = changes in non-current assets
            Financing Activities = changes in non-current liabilities + equity
        """
        _logger.info("SGC DFR: Generating Cash Flow for company %s", wizard.company_id.name)
        rows = self._query_account_balances_sql(wizard, include_comparison=False)

        # Get comparison period balances for changes
        comp_rows = []
        if wizard.enable_comparison and wizard.comparison_date_from:
            # Build domain for comparison and query
            self.env.cr.execute("""
                SELECT
                    a.id AS account_id,
                    COALESCE(SUM(aml.debit), 0.0) AS debit,
                    COALESCE(SUM(aml.credit), 0.0) AS credit,
                    COALESCE(SUM(aml.debit - aml.credit), 0.0) AS balance
                FROM account_account a
                JOIN account_account_res_company_rel acr ON acr.account_account_id = a.id
                    AND acr.res_company_id = %s
                LEFT JOIN account_move_line aml ON aml.account_id = a.id
                    AND aml.date >= %s
                    AND aml.date <= %s
                    AND aml.company_id = %s
                GROUP BY a.id
            """, (wizard.company_id.id, wizard.comparison_date_from, wizard.comparison_date_to,
                  wizard.company_id.id))
            comp_rows = self.env.cr.dictfetchall()

        comp_map = {r["account_id"]: r for r in comp_rows} if comp_rows else {}

        # Classify cash flow activities
        operating_accounts = {"income", "income_other", "expense", "expense_depreciation", "expense_direct_cost"}
        investing_accounts = {"asset_fixed", "asset_non_current"}
        financing_accounts = {"liability_non_current", "equity", "equity_unaffected"}
        cash_accounts = {"asset_cash", "asset_current"}

        activities = {
            "Operating Activities": [],
            "Investing Activities": [],
            "Financing Activities": [],
        }

        classification_map = {}
        for at in operating_accounts:
            classification_map[at] = "Operating Activities"
        for at in investing_accounts:
            classification_map[at] = "Investing Activities"
        for at in financing_accounts:
            classification_map[at] = "Financing Activities"

        activity_totals = {"Operating Activities": 0.0, "Investing Activities": 0.0, "Financing Activities": 0.0}

        for row in rows:
            acct_type = row.get("account_type", "")
            activity = classification_map.get(acct_type)
            if not activity:
                continue
            # Full account mapping: every classified account always renders
            # (explicitly showing 0), never omitted for zero activity.
            change = row["balance"]
            comp = comp_map.get(row["account_id"], {})
            if comp:
                change = row["balance"] - comp.get("balance", 0.0)
            # By the accounting identity (assets = liabilities + equity, at
            # all times), the change in cash must equal the negative of the
            # combined change in every non-cash account. `balance` is raw
            # debit-credit, so every category here needs the same sign flip
            # to read as a cash inflow(+)/outflow(-), regardless of whether
            # the underlying account is normally debit- or credit-balanced.
            change = -change
            activities[activity].append({
                "code": row["code"],
                "name": row["name"],
                "amount": change,
            })
            activity_totals[activity] += change

        # Build HTML
        html = self._build_report_header_html(wizard, "Cash Flow Statement")
        columns = ["Code", "Description", "Amount"]

        for activity_name, activity_rows in activities.items():
            if not activity_rows:
                continue
            display_rows = []
            for r in activity_rows:
                display_rows.append({
                    "Code": r["code"],
                    "Description": r["name"],
                    "Amount": self._fmt(r["amount"], wizard),
                })
            totals = {
                "Code": f"Net {activity_name}",
                "Description": "",
                "Amount": self._fmt(activity_totals[activity_name], wizard),
            }
            section_table_html = self._build_html_table(columns, display_rows, totals, wizard=wizard)
            html += self._wrap_collapsible(activity_name, section_table_html)

        net_cash = sum(activity_totals.values())
        html += self._build_grand_total_html([
            ("NET CHANGE IN CASH", self._fmt(net_cash, wizard)),
        ])

        return {
            "html": html,
            "data": {"activities": activities, "totals": activity_totals, "net_cash": net_cash},
        }

    def _build_trial_balance(self, wizard):
        """Build Trial Balance report.

        Shows all accounts with debit, credit, and balance.
        Validates that total debits = total credits.
        Budget columns are added when show_budget_vs_actual is True.
        """
        _logger.info("SGC DFR: Generating Trial Balance for company %s", wizard.company_id.name)
        # cumulative_all=True: Trial Balance lists every account together,
        # and its own debit=credit invariant only holds when every account
        # (BS and P&L alike) shares one scope - see
        # _query_account_balances_sql's cumulative_all docstring.
        rows = self._query_account_balances_sql(wizard, include_comparison=True, cumulative_all=True)
        # Full account mapping: every account always renders (explicitly
        # showing 0), never omitted for zero activity - removing zero rows
        # is a no-op on the debit=credit total either way.

        has_comparison = wizard.enable_comparison and wizard.comparison_date_from
        budget_active = bool(wizard.show_budget_vs_actual)
        if budget_active:
            self._compute_budget_vs_actual(wizard, rows)

        html = self._build_report_header_html(wizard, "Trial Balance")

        columns = ["Code", "Account Name", "Account Type"]
        if has_comparison:
            columns.append("Comp. Balance")
        columns += ["Debit", "Credit", "Balance"]
        if budget_active:
            columns += self._budget_columns()

        display_rows = []
        total_debit = 0.0
        total_credit = 0.0
        total_balance = 0.0
        total_budget = 0.0

        for row in rows:
            display_row = {
                "Code": row["code"],
                "Account Name": row["name"],
                "Account Type": row.get("account_type") or "",
                "Debit": self._fmt(row["debit"], wizard),
                "Credit": self._fmt(row["credit"], wizard),
                "Balance": self._fmt(row["balance"], wizard),
            }
            if has_comparison:
                display_row["Comp. Balance"] = self._fmt(row["comp_balance"], wizard)
            if budget_active:
                display_row.update(self._budget_row_cells(row, wizard))

            total_debit += row["debit"]
            total_credit += row["credit"]
            total_balance += row["balance"]
            if budget_active:
                total_budget += row.get("budget_amount", 0.0)
            display_rows.append(display_row)

        totals = {
            "Code": "TOTAL",
            "Account Name": f"{len(rows)} accounts",
            "Account Type": "",
            "Debit": self._fmt(total_debit, wizard),
            "Credit": self._fmt(total_credit, wizard),
            "Balance": self._fmt(total_balance, wizard),
        }
        if has_comparison:
            totals["Comp. Balance"] = ""
        if budget_active:
            totals.update(self._budget_row_cells(
                {
                    "budget_amount": total_budget,
                    "natural_balance": total_balance,
                },
                wizard,
            ))

        section_table_html = self._build_html_table(columns, display_rows, totals, wizard=wizard)
        html += self._wrap_collapsible("Account Balances", section_table_html)

        # Difference check
        diff = total_debit - total_credit
        if abs(diff) > 0.01:
            html += f'<div class="alert alert-warning mt-2"><strong>Note:</strong> Debit-Credit difference: {self._fmt(diff, wizard)}</div>'

        return {
            "html": html,
            "data": {
                "rows": rows,
                "totals": {
                    "debit": total_debit,
                    "credit": total_credit,
                    "balance": total_balance,
                    "budget": total_budget,
                },
            },
        }

    def _build_general_ledger(self, wizard):
        """Build General Ledger report with opening balance and line details."""
        _logger.info("SGC DFR: Generating General Ledger for company %s", wizard.company_id.name)
        data = self._query_general_ledger_sql(wizard)

        html = self._build_report_header_html(wizard, "General Ledger")
        columns = ["Date", "Journal Entry", "Description", "Partner", "Debit", "Credit", "Balance"]

        # Summary by account. Full account mapping: every account always
        # renders (explicitly showing 0), never omitted for zero activity -
        # _query_general_ledger_sql already guarantees every company
        # account has an entry in data["accounts"].
        summary_cols = ["Account Code", "Account Name", "Opening Bal.", "Period Debit", "Period Credit", "Period Bal.", "Final Balance"]
        summary_rows = []
        for acc in data["accounts"]:
            summary_rows.append({
                "Account Code": acc["account_code"],
                "Account Name": acc["account_name"],
                "Opening Bal.": self._fmt(acc["opening_balance"], wizard),
                "Period Debit": self._fmt(acc["period_debit"], wizard),
                "Period Credit": self._fmt(acc["period_credit"], wizard),
                "Period Bal.": self._fmt(acc["period_balance"], wizard),
                "Final Balance": self._fmt(acc["final_balance"], wizard),
            })
        summary_table_html = self._build_html_table(summary_cols, summary_rows, wizard=wizard)
        html += self._wrap_collapsible("Account Summary", summary_table_html)

        # Detail lines
        detail_rows = []
        for line in data["lines"]:
            detail_rows.append({
                "Date": line["date"],
                "Journal Entry": line["move_name"],
                "Description": line["entry_name"],
                "Partner": line["partner_name"],
                "Debit": self._fmt(line["debit"], wizard),
                "Credit": self._fmt(line["credit"], wizard),
                "Balance": self._fmt(line["balance"], wizard),
            })
        detail_table_html = self._build_html_table(columns, detail_rows, wizard=wizard)
        html += self._wrap_collapsible("Journal Entry Details", detail_table_html)

        return {
            "html": html,
            "data": data,
        }

    def _build_partner_ledger(self, wizard):
        """Build Partner Ledger report showing all transactions per partner."""
        _logger.info("SGC DFR: Generating Partner Ledger for company %s", wizard.company_id.name)
        partner_balances = self._query_partner_balances_sql(wizard)

        # Get detailed lines per partner - restricted to receivable/payable
        # control accounts, same as _query_partner_balances_sql above.
        # Without this, every line tagged with the partner (including e.g.
        # the revenue line of an invoice) is included, and since debits
        # always equal credits across a fully-recorded move, the partner's
        # "balance" would net to zero for every partner in every case.
        domain = self._get_base_domain(wizard)
        domain.append(("parent_state", "=", "posted"))
        domain.append(("account_id.account_type", "in", ["asset_receivable", "liability_payable"]))
        if wizard.partner_ids:
            domain.append(("partner_id", "in", wizard.partner_ids.ids))
        if wizard.partner_category_id:
            cat_partners = self.env["res.partner"].search([
                ("category_id", "child_of", wizard.partner_category_id.id),
            ])
            domain.append(("partner_id", "in", cat_partners.ids))

        lines = self.env["account.move.line"].search(
            domain, order="partner_id, date, id"
        )

        # Group lines by partner
        partner_lines = {}
        for line in lines:
            pid = line.partner_id.id or 0
            if pid not in partner_lines:
                partner_lines[pid] = {
                    "partner_id": pid,
                    "partner_name": line.partner_id.name or "Unknown",
                    "partner_ref": line.partner_id.ref or "",
                    "lines": [],
                    "total_debit": 0.0,
                    "total_credit": 0.0,
                }
            pl = partner_lines[pid]
            pl["lines"].append({
                "date": fields.Date.to_string(line.date),
                "move_name": line.move_id.name or "",
                "entry_name": line.name or "",
                "account_code": line.account_id.code,
                "debit": line.debit,
                "credit": line.credit,
            })
            pl["total_debit"] += line.debit
            pl["total_credit"] += line.credit

        html = self._build_report_header_html(wizard, "Partner Ledger")

        # Summary table
        summary_cols = ["Partner", "Ref", "Debit", "Credit", "Balance"]
        summary_rows = []
        for pb in partner_balances:
            summary_rows.append({
                "Partner": pb["partner_name"],
                "Ref": pb["partner_ref"],
                "Debit": self._fmt(pb["debit"], wizard),
                "Credit": self._fmt(pb["credit"], wizard),
                "Balance": self._fmt(pb["balance"], wizard),
            })
        totals = {
            "Partner": f"TOTAL ({len(partner_balances)} partners)",
            "Ref": "",
            "Debit": self._fmt(sum(p["debit"] for p in partner_balances), wizard),
            "Credit": self._fmt(sum(p["credit"] for p in partner_balances), wizard),
            "Balance": self._fmt(sum(p["balance"] for p in partner_balances), wizard),
        }
        summary_table_html = self._build_html_table(summary_cols, summary_rows, totals, wizard=wizard)
        html += self._wrap_collapsible("Partner Summary", summary_table_html)

        # Detail per partner
        detail_cols = ["Date", "Journal Entry", "Description", "Account", "Debit", "Credit"]
        for pid, pdata in sorted(partner_lines.items(), key=lambda x: x[1]["partner_name"]):
            partner_title = pdata["partner_name"]
            if pdata["partner_ref"]:
                partner_title += f' ({pdata["partner_ref"]})'
            detail_rows = []
            for line in pdata["lines"]:
                detail_rows.append({
                    "Date": line["date"],
                    "Journal Entry": line["move_name"],
                    "Description": line["entry_name"],
                    "Account": line["account_code"],
                    "Debit": self._fmt(line["debit"], wizard),
                    "Credit": self._fmt(line["credit"], wizard),
                })
            partner_totals = {
                "Date": "Total",
                "Journal Entry": "",
                "Description": "",
                "Account": "",
                "Debit": self._fmt(pdata["total_debit"], wizard),
                "Credit": self._fmt(pdata["total_credit"], wizard),
            }
            partner_table_html = self._build_html_table(detail_cols, detail_rows, partner_totals, wizard=wizard)
            html += self._wrap_collapsible(partner_title, partner_table_html)

        return {
            "html": html,
            "data": {
                "partner_balances": partner_balances,
                "partner_lines": partner_lines,
            },
        }

    def _build_aged_receivable(self, wizard):
        """Build Aged Receivable report."""
        _logger.info("SGC DFR: Generating Aged Receivable for company %s", wizard.company_id.name)
        rows, buckets = self._query_aged_balances_sql(wizard, receivable=True)

        html = self._build_report_header_html(wizard, "Aged Receivable Report")

        # Column headers
        columns = ["Partner", "Ref", "# Invoices"]
        for bucket in buckets:
            columns.append(bucket["label"])
        columns.append("Total Balance")

        display_rows = []
        grand_total = {"total_balance": 0.0}
        for bucket in buckets:
            grand_total[bucket["label"]] = 0.0

        for row in rows:
            display_row = {
                "Partner": row["partner_name"],
                "Ref": row["partner_ref"],
                "# Invoices": row["invoice_count"],
            }
            for bucket in buckets:
                val = self._fmt(row.get(bucket["label"], 0.0), wizard)
                display_row[bucket["label"]] = val
                grand_total[bucket["label"]] += row.get(bucket["label"], 0.0)

            display_row["Total Balance"] = self._fmt(row["total_balance"], wizard)
            grand_total["total_balance"] += row["total_balance"]
            display_rows.append(display_row)

        totals = {"Partner": f"TOTAL ({len(rows)} partners)", "Ref": "", "# Invoices": ""}
        for bucket in buckets:
            totals[bucket["label"]] = self._fmt(grand_total[bucket["label"]], wizard)
        totals["Total Balance"] = self._fmt(grand_total["total_balance"], wizard)

        section_table_html = self._build_html_table(columns, display_rows, totals, wizard=wizard)
        html += self._wrap_collapsible("Aging Detail", section_table_html)

        return {
            "html": html,
            "data": {"rows": rows, "buckets": buckets, "totals": grand_total},
        }

    def _build_aged_payable(self, wizard):
        """Build Aged Payable report."""
        _logger.info("SGC DFR: Generating Aged Payable for company %s", wizard.company_id.name)
        rows, buckets = self._query_aged_balances_sql(wizard, receivable=False)

        html = self._build_report_header_html(wizard, "Aged Payable Report")

        columns = ["Partner", "Ref", "# Invoices"]
        for bucket in buckets:
            columns.append(bucket["label"])
        columns.append("Total Balance")

        display_rows = []
        grand_total = {"total_balance": 0.0}
        for bucket in buckets:
            grand_total[bucket["label"]] = 0.0

        for row in rows:
            display_row = {
                "Partner": row["partner_name"],
                "Ref": row["partner_ref"],
                "# Invoices": row["invoice_count"],
            }
            for bucket in buckets:
                val = self._fmt(row.get(bucket["label"], 0.0), wizard)
                display_row[bucket["label"]] = val
                grand_total[bucket["label"]] += row.get(bucket["label"], 0.0)

            display_row["Total Balance"] = self._fmt(row["total_balance"], wizard)
            grand_total["total_balance"] += row["total_balance"]
            display_rows.append(display_row)

        totals = {"Partner": f"TOTAL ({len(rows)} partners)", "Ref": "", "# Invoices": ""}
        for bucket in buckets:
            totals[bucket["label"]] = self._fmt(grand_total[bucket["label"]], wizard)
        totals["Total Balance"] = self._fmt(grand_total["total_balance"], wizard)

        section_table_html = self._build_html_table(columns, display_rows, totals, wizard=wizard)
        html += self._wrap_collapsible("Aging Detail", section_table_html)

        return {
            "html": html,
            "data": {"rows": rows, "buckets": buckets, "totals": grand_total},
        }

    def _build_tax_report(self, wizard):
        """Build Tax Report showing tax collected and paid."""
        _logger.info("SGC DFR: Generating Tax Report for company %s", wizard.company_id.name)
        tax_data = self._query_tax_report_sql(wizard)

        html = self._build_report_header_html(wizard, "Tax Report")

        # Group by tax type
        tax_types = {
            "sale": ("Sales Taxes (Output)", []),
            "purchase": ("Purchase Taxes (Input)", []),
        }

        for row in tax_data:
            tax_type = row.get("tax_type", "sale")
            if tax_type in tax_types:
                tax_types[tax_type][1].append(row)
            else:
                if "other" not in tax_types:
                    tax_types["other"] = ("Other Taxes", [])
                tax_types["other"][1].append(row)

        columns = ["Tax Name", "Description", "Rate %", "Net Amount", "Tax Amount"]

        grand_net = 0.0
        grand_tax = 0.0

        for tax_type, (label, taxes) in tax_types.items():
            if not taxes:
                continue
            display_rows = []
            section_net = 0.0
            section_tax = 0.0
            for t in taxes:
                display_rows.append({
                    "Tax Name": t["tax_name"],
                    "Description": self._strip_html_tags(t["tax_description"]),
                    "Rate %": f"{t['tax_rate']:.2f}%",
                    "Net Amount": self._fmt(t["net_amount"], wizard),
                    "Tax Amount": self._fmt(t["tax_amount"], wizard),
                })
                section_net += t["net_amount"]
                section_tax += t["tax_amount"]

            grand_net += section_net
            grand_tax += section_tax

            totals = {
                "Tax Name": f"Total {label}",
                "Description": f"{len(taxes)} tax(es)",
                "Rate %": "",
                "Net Amount": self._fmt(section_net, wizard),
                "Tax Amount": self._fmt(section_tax, wizard),
            }
            section_table_html = self._build_html_table(columns, display_rows, totals, wizard=wizard)
            html += self._wrap_collapsible(label, section_table_html)

        net_tax_due = grand_tax
        html += self._build_grand_total_html([
            (
                "TOTAL TAX",
                f"Net: {self._fmt(grand_net, wizard)}",
                f"Tax: {self._fmt(grand_tax, wizard)}",
            ),
        ])

        return {
            "html": html,
            "data": {"taxes": tax_data, "total_net": grand_net, "total_tax": grand_tax},
        }