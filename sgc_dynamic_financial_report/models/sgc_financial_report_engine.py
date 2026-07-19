# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

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

    def _query_account_balances_sql(self, wizard, include_comparison=False):
        """Execute raw SQL to get account-level debit/credit/balance.

        Returns list of dicts:
            [{account_id, code, name, account_type, financial_section,
              debit, credit, balance, comp_debit, comp_credit, comp_balance}]

        This uses raw SQL for performance with large datasets.
        """
        # account.account.name is translate=True (JSONB, keyed by lang code)
        # and .code is a compute over code_store, a company_dependent field
        # (JSONB keyed by company id as string) - both need JSON extraction
        # rather than plain column access.
        company_id_str = str(wizard.company_id.id)
        lang = self.env.lang or "en_US"
        self.env.cr.execute("""
            SELECT
                a.id AS account_id,
                a.code_store ->> %s AS code,
                COALESCE(a.name ->> %s, a.name ->> 'en_US') AS name,
                a.account_type AS account_type,
                COALESCE(m.financial_section, 'other') AS financial_section,
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
            LEFT JOIN sgc_dfr_account_type m ON m.account_type = a.account_type
                AND m.active = TRUE
                AND (m.company_id IS NULL OR m.company_id = %s)
            GROUP BY a.id, a.code_store, a.name, a.account_type, m.financial_section
            ORDER BY a.code_store ->> %s
        """, (company_id_str, lang, wizard.company_id.id, wizard.date_from, wizard.date_to,
              wizard.company_id.id, wizard.company_id.id, company_id_str))

        rows = self.env.cr.dictfetchall()

        if include_comparison and wizard.enable_comparison:
            self.env.cr.execute("""
                SELECT
                    aml.account_id AS account_id,
                    COALESCE(SUM(aml.debit), 0.0) AS comp_debit,
                    COALESCE(SUM(aml.credit), 0.0) AS comp_credit,
                    COALESCE(SUM(aml.debit - aml.credit), 0.0) AS comp_balance
                FROM account_move_line aml
                WHERE aml.date >= %s
                  AND aml.date <= %s
                  AND aml.company_id = %s
                GROUP BY aml.account_id
            """, (wizard.comparison_date_from, wizard.comparison_date_to,
                  wizard.company_id.id))

            comp_map = {r["account_id"]: r for r in self.env.cr.dictfetchall()}
            for row in rows:
                comp = comp_map.get(row["account_id"], {})
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

        return rows

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

        # Compute final balances
        for acc in accounts_data.values():
            acc["period_balance"] = acc["period_debit"] - acc["period_credit"]
            acc["final_balance"] = acc["opening_balance"] + acc["period_balance"]

        return {
            "accounts": sorted(accounts_data.values(), key=lambda x: x["account_code"]),
            "lines": lines_data,
        }

    # ── HTML rendering helpers ────────────────────────────────────────

    def _fmt(self, amount, wizard=None):
        """Format a monetary amount for display."""
        if amount is None:
            return ""
        precision = 2
        if wizard and wizard.company_id.sgc_dfr_decimal_precision:
            precision = wizard.company_id.sgc_dfr_decimal_precision
        formatted = f"{amount:,.{precision}f}"
        if amount < 0 and wizard and wizard.company_id.sgc_dfr_negative_format == "parentheses":
            formatted = f"({formatted[1:]})"
        return formatted

    def _build_html_table(self, columns, rows, totals=None, css_class=""):
        """Build an HTML table string for report display.

        Args:
            columns: list of column header strings.
            rows: list of dicts, each keyed by column name.
            totals: optional dict of column -> total value.
            css_class: extra CSS class for the table.

        Returns:
            str: HTML string.
        """
        html = [f'<div class="sgc-report {css_class}">']
        html.append('<table class="table table-bordered table-sm o_sgc_report_table">')

        # Header
        html.append('<thead><tr class="table-primary">')
        for col in columns:
            html.append(f'<th>{col}</th>')
        html.append('</tr></thead>')

        # Body
        html.append('<tbody>')
        for row in rows:
            row_class = row.pop("css_class", "")
            if row_class:
                html.append(f'<tr class="{row_class}">')
            else:
                html.append("<tr>")
            for col in columns:
                val = row.get(col, "")
                if isinstance(val, float):
                    val = self._fmt(val)
                if val and isinstance(val, (int, float)) and val < 0:
                    html.append(f'<td class="negative">{val}</td>')
                else:
                    html.append(f"<td>{val}</td>")
            html.append("</tr>")
        html.append("</tbody>")

        # Totals
        if totals:
            html.append('<tfoot><tr class="total-row">')
            for col in columns:
                val = totals.get(col, "")
                if isinstance(val, float):
                    val = self._fmt(val)
                html.append(f"<td>{val}</td>")
            html.append("</tr></tfoot>")

        html.append("</table></div>")
        return "\n".join(html)

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
        return html

    def _parse_aging_buckets(self, buckets_str):
        """Parse aging bucket string like '0-30,31-60,61-90,91-180,>180'.

        Returns list of dicts: [{'label': '0-30', 'min': 0, 'max': 30}, ...]
        """
        buckets = []
        for part in buckets_str.split(","):
            part = part.strip()
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
        """
        _logger.info("SGC DFR: Generating Balance Sheet for company %s", wizard.company_id.name)
        rows = self._query_account_balances_sql(wizard, include_comparison=True)

        # Filter to BS sections only (assets, liabilities, equity)
        bs_sections = {"assets", "liabilities", "equity"}
        bs_rows = [r for r in rows if r.get("financial_section") in bs_sections]

        if not wizard.show_zero_balance:
            bs_rows = [r for r in bs_rows if abs(r.get("balance", 0)) > 0.001]

        # Group by financial section
        sections = {}
        for row in bs_rows:
            section = row["financial_section"]
            if section not in sections:
                sections[section] = []
            sections[section].append(row)

        # Build HTML
        html = self._build_report_header_html(wizard, "Balance Sheet")
        has_comparison = wizard.enable_comparison and wizard.comparison_date_from

        for section_key in sorted(bs_sections, key=lambda x: SECTION_ORDER.get(x, 99)):
            section_rows = sections.get(section_key, [])
            if not section_rows:
                continue

            html += f'<h4 class="sgc_section_title">{SECTION_LABELS.get(section_key, section_key.title())}</h4>'

            columns = ["Code", "Account Name"]
            if has_comparison:
                columns += ["Comp. Balance"]
            columns += ["Debit", "Credit", "Balance"]
            if has_comparison:
                columns.append("Variance")

            display_rows = []
            section_total = {"debit": 0.0, "credit": 0.0, "balance": 0.0}
            if has_comparison:
                section_total["comp_balance"] = 0.0

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

            html += self._build_html_table(columns, display_rows, totals)

        # Grand total: Assets = Liabilities + Equity
        assets_total = sum(r["natural_balance"] for r in bs_rows if r["financial_section"] == "assets")
        liab_eq_total = sum(r["natural_balance"] for r in bs_rows if r["financial_section"] in ("liabilities", "equity"))
        html += f"""
        <div class="sgc-report">
            <table class="table table-bordered table-sm o_sgc_report_table">
                <tr class="grand-total">
                    <td><strong>TOTAL ASSETS</strong></td>
                    <td><strong>{self._fmt(assets_total, wizard)}</strong></td>
                    <td></td><td></td><td></td>
                </tr>
                <tr class="grand-total">
                    <td><strong>TOTAL LIABILITIES + EQUITY</strong></td>
                    <td><strong>{self._fmt(liab_eq_total, wizard)}</strong></td>
                    <td></td><td></td><td></td>
                </tr>
            </table>
        </div>
        """

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
        """
        _logger.info("SGC DFR: Generating Profit & Loss for company %s", wizard.company_id.name)
        rows = self._query_account_balances_sql(wizard, include_comparison=True)

        pl_sections = {"revenue", "expenses"}
        pl_rows = [r for r in rows if r.get("financial_section") in pl_sections]

        if not wizard.show_zero_balance:
            pl_rows = [r for r in pl_rows if abs(r.get("balance", 0)) > 0.001]

        sections = {}
        for row in pl_rows:
            section = row["financial_section"]
            if section not in sections:
                sections[section] = []
            sections[section].append(row)

        html = self._build_report_header_html(wizard, "Profit & Loss Statement")
        has_comparison = wizard.enable_comparison and wizard.comparison_date_from

        grand_totals = {"revenue": 0.0, "expenses": 0.0}

        for section_key in sorted(pl_sections, key=lambda x: SECTION_ORDER.get(x, 99)):
            section_rows = sections.get(section_key, [])
            if not section_rows:
                continue

            html += f'<h4 class="sgc_section_title">{SECTION_LABELS.get(section_key, section_key.title())}</h4>'

            columns = ["Code", "Account Name"]
            if has_comparison:
                columns.append("Comp. Balance")
            columns += ["Debit", "Credit", "Balance"]

            display_rows = []
            section_total = {"debit": 0.0, "credit": 0.0, "balance": 0.0}

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

                section_total["debit"] += row["debit"]
                section_total["credit"] += row["credit"]
                section_total["balance"] += row["natural_balance"]
                display_rows.append(display_row)

            grand_totals[section_key] = section_total["balance"]

            totals = {
                "Code": f"Total {SECTION_LABELS.get(section_key, section_key.title())}",
                "Debit": self._fmt(section_total["debit"], wizard),
                "Credit": self._fmt(section_total["credit"], wizard),
                "Balance": self._fmt(section_total["balance"], wizard),
            }
            if has_comparison:
                totals["Comp. Balance"] = ""

            html += self._build_html_table(columns, display_rows, totals)

        net_income = grand_totals["revenue"] - grand_totals["expenses"]
        html += f"""
        <div class="sgc-report">
            <table class="table table-bordered table-sm o_sgc_report_table">
                <tr class="grand-total">
                    <td><strong>NET {'INCOME' if net_income >= 0 else 'LOSS'}</strong></td>
                    <td><strong>{self._fmt(net_income, wizard)}</strong></td>
                    <td></td><td></td><td></td>
                </tr>
            </table>
        </div>
        """

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
            if not wizard.show_zero_balance and abs(row["balance"]) < 0.001:
                continue
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
            html += f'<h4 class="sgc_section_title">{activity_name}</h4>'
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
            html += self._build_html_table(columns, display_rows, totals)

        net_cash = sum(activity_totals.values())
        html += f"""
        <div class="sgc-report">
            <table class="table table-bordered table-sm o_sgc_report_table">
                <tr class="grand-total">
                    <td><strong>NET CHANGE IN CASH</strong></td>
                    <td><strong>{self._fmt(net_cash, wizard)}</strong></td>
                    <td></td>
                </tr>
            </table>
        </div>
        """

        return {
            "html": html,
            "data": {"activities": activities, "totals": activity_totals, "net_cash": net_cash},
        }

    def _build_trial_balance(self, wizard):
        """Build Trial Balance report.

        Shows all accounts with debit, credit, and balance.
        Validates that total debits = total credits.
        """
        _logger.info("SGC DFR: Generating Trial Balance for company %s", wizard.company_id.name)
        rows = self._query_account_balances_sql(wizard, include_comparison=True)

        if not wizard.show_zero_balance:
            rows = [r for r in rows if abs(r.get("balance", 0)) > 0.001]

        has_comparison = wizard.enable_comparison and wizard.comparison_date_from

        html = self._build_report_header_html(wizard, "Trial Balance")

        columns = ["Code", "Account Name", "Account Type"]
        if has_comparison:
            columns.append("Comp. Balance")
        columns += ["Debit", "Credit", "Balance"]

        display_rows = []
        total_debit = 0.0
        total_credit = 0.0
        total_balance = 0.0

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

            total_debit += row["debit"]
            total_credit += row["credit"]
            total_balance += row["balance"]
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

        html += self._build_html_table(columns, display_rows, totals)

        # Difference check
        diff = total_debit - total_credit
        if abs(diff) > 0.01:
            html += f'<div class="alert alert-warning mt-2"><strong>Note:</strong> Debit-Credit difference: {self._fmt(diff, wizard)}</div>'

        return {
            "html": html,
            "data": {
                "rows": rows,
                "totals": {"debit": total_debit, "credit": total_credit, "balance": total_balance},
            },
        }

    def _build_general_ledger(self, wizard):
        """Build General Ledger report with opening balance and line details."""
        _logger.info("SGC DFR: Generating General Ledger for company %s", wizard.company_id.name)
        data = self._query_general_ledger_sql(wizard)

        html = self._build_report_header_html(wizard, "General Ledger")
        columns = ["Date", "Journal Entry", "Description", "Partner", "Debit", "Credit", "Balance"]

        # Summary by account
        html += '<h4 class="sgc_section_title">Account Summary</h4>'
        summary_cols = ["Account Code", "Account Name", "Opening Bal.", "Period Debit", "Period Credit", "Period Bal.", "Final Balance"]
        summary_rows = []
        for acc in data["accounts"]:
            if not wizard.show_zero_balance and abs(acc["final_balance"]) < 0.001 and abs(acc["period_balance"]) < 0.001:
                continue
            summary_rows.append({
                "Account Code": acc["account_code"],
                "Account Name": acc["account_name"],
                "Opening Bal.": self._fmt(acc["opening_balance"], wizard),
                "Period Debit": self._fmt(acc["period_debit"], wizard),
                "Period Credit": self._fmt(acc["period_credit"], wizard),
                "Period Bal.": self._fmt(acc["period_balance"], wizard),
                "Final Balance": self._fmt(acc["final_balance"], wizard),
            })
        html += self._build_html_table(summary_cols, summary_rows)

        # Detail lines
        html += '<h4 class="sgc_section_title">Journal Entry Details</h4>'
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
        html += self._build_html_table(columns, detail_rows)

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
        html += '<h4 class="sgc_section_title">Partner Summary</h4>'
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
        html += self._build_html_table(summary_cols, summary_rows, totals)

        # Detail per partner
        html += '<h4 class="sgc_section_title">Transaction Details</h4>'
        detail_cols = ["Date", "Journal Entry", "Description", "Account", "Debit", "Credit"]
        for pid, pdata in sorted(partner_lines.items(), key=lambda x: x[1]["partner_name"]):
            html += f'<h5 class="sgc_section_title">{pdata["partner_name"]}'
            if pdata["partner_ref"]:
                html += f' ({pdata["partner_ref"]})'
            html += '</h5>'
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
            html += self._build_html_table(detail_cols, detail_rows, partner_totals)

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

        html += self._build_html_table(columns, display_rows, totals)

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

        html += self._build_html_table(columns, display_rows, totals)

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
            html += f'<h4 class="sgc_section_title">{label}</h4>'
            display_rows = []
            section_net = 0.0
            section_tax = 0.0
            for t in taxes:
                display_rows.append({
                    "Tax Name": t["tax_name"],
                    "Description": t["tax_description"],
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
            html += self._build_html_table(columns, display_rows, totals)

        net_tax_due = grand_tax
        html += f"""
        <div class="sgc-report">
            <table class="table table-bordered table-sm o_sgc_report_table">
                <tr class="grand-total">
                    <td><strong>TOTAL TAX</strong></td>
                    <td><strong>Net: {self._fmt(grand_net, wizard)}</strong></td>
                    <td><strong>Tax: {self._fmt(grand_tax, wizard)}</strong></td>
                    <td></td><td></td>
                </tr>
            </table>
        </div>
        """

        return {
            "html": html,
            "data": {"taxes": tax_data, "total_net": grand_net, "total_tax": grand_tax},
        }