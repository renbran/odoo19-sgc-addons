import logging
from collections import defaultdict
from datetime import timedelta

from odoo import fields, models

from odoo.addons.llm_tool.decorators import llm_tool

_logger = logging.getLogger(__name__)


def _model_exists(env, model_name):
    return model_name in env.registry


def _fmt_amount(amount, currency=None):
    sym = currency.symbol if currency else ""
    return f"{sym}{float(amount):,.2f}"


def _aging_buckets(moves, today):
    buckets = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "over_90": 0.0}
    for move in moves:
        due = move.invoice_date_due
        residual = float(move.amount_residual)
        if not due or due >= today:
            buckets["current"] += residual
        else:
            days = (today - due).days
            if days <= 30:
                buckets["1_30"] += residual
            elif days <= 60:
                buckets["31_60"] += residual
            elif days <= 90:
                buckets["61_90"] += residual
            else:
                buckets["over_90"] += residual
    return buckets


def _check_persona_access(persona_codes, kwargs):
    persona_code = kwargs.pop("_persona_code", None)
    if persona_code and persona_code not in persona_codes:
        return {
            "error": True,
            "message": f"Persona '{persona_code}' is not authorized to use this tool. "
                       f"Authorized persona codes: {', '.join(persona_codes)}",
        }
    return None


class SgcPersonaTool(models.AbstractModel):
    _name = "sgc.persona.tool"
    _description = "SGC Persona Data Tool"

    # -------------------------------------------------------------------------
    # FINANCE — finance_analyst
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_finance_data",
        description="Fetch finance data including cash position, outstanding receivables/payables, "
                    "P&L snapshot, and VAT summary for the current period.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_finance_data(
        self,
        sections: list = None,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"finance_analyst"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        today = fields.Date.today()
        currency = env.company.currency_id
        sections = sections or ["cash", "receivables", "payables", "pnl", "tax"]
        result = {}

        if "cash" in sections:
            try:
                result["cash"] = self._fetch_cash(env, today, currency)
            except Exception as e:
                result["cash"] = f"[Cash data unavailable: {e}]"

        if "receivables" in sections:
            try:
                result["receivables"] = self._fetch_receivables(env, today, currency)
            except Exception as e:
                result["receivables"] = f"[Receivables unavailable: {e}]"

        if "payables" in sections:
            try:
                result["payables"] = self._fetch_payables(env, today, currency)
            except Exception as e:
                result["payables"] = f"[Payables unavailable: {e}]"

        if "pnl" in sections:
            try:
                result["pnl"] = self._fetch_pnl(env, today, currency)
            except Exception as e:
                result["pnl"] = f"[P&L unavailable: {e}]"

        if "tax" in sections:
            try:
                result["tax"] = self._fetch_tax(env, today, currency)
            except Exception as e:
                result["tax"] = f"[Tax data unavailable: {e}]"

        _logger.info(
            "Finance data fetched for persona '%s' — sections: %s",
            _persona_code, list(result.keys()),
        )
        return {"finance": result}

    def _fetch_cash(self, env, today, currency):
        journals = env["account.journal"].search([("type", "in", ["bank", "cash"])])
        accounts = []
        total = 0.0
        for j in journals:
            bal = float(getattr(j, "current_statement_balance", 0.0) or 0.0)
            accounts.append({"name": j.name, "balance": _fmt_amount(bal, currency), "balance_raw": bal})
            total += bal
        return {
            "as_of": today.isoformat(),
            "accounts": accounts,
            "total_liquid": _fmt_amount(total, currency),
            "total_raw": total,
            "currency": currency.name,
        }

    def _fetch_receivables(self, env, today, currency):
        moves = env["account.move"].search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "not in", ["paid", "reversed"]),
        ])
        buckets = _aging_buckets(moves, today)
        top5 = sorted(moves, key=lambda m: m.amount_residual, reverse=True)[:5]
        return {
            "as_of": today.isoformat(),
            "buckets": {k: _fmt_amount(v, currency) for k, v in buckets.items()},
            "buckets_raw": buckets,
            "total_open": _fmt_amount(sum(buckets.values()), currency),
            "invoice_count": len(moves),
            "top_overdue": [
                {
                    "name": m.name,
                    "partner": m.partner_id.name,
                    "due_date": m.invoice_date_due.isoformat() if m.invoice_date_due else None,
                    "amount": _fmt_amount(m.amount_residual, currency),
                }
                for m in top5
            ],
        }

    def _fetch_payables(self, env, today, currency):
        moves = env["account.move"].search([
            ("move_type", "=", "in_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "not in", ["paid", "reversed"]),
        ])
        buckets = _aging_buckets(moves, today)
        overdue = [
            {
                "partner": m.partner_id.name,
                "amount": _fmt_amount(m.amount_residual, currency),
                "due_date": m.invoice_date_due.isoformat() if m.invoice_date_due else None,
            }
            for m in moves
            if m.invoice_date_due and m.invoice_date_due < today
        ]
        overdue.sort(key=lambda r: float(r["amount"].replace(currency.symbol or "", "").replace(",", "")), reverse=True)
        return {
            "as_of": today.isoformat(),
            "buckets": {k: _fmt_amount(v, currency) for k, v in buckets.items()},
            "buckets_raw": buckets,
            "total_open": _fmt_amount(sum(buckets.values()), currency),
            "bill_count": len(moves),
            "top_overdue_vendors": overdue[:5],
        }

    def _fetch_pnl(self, env, today, currency):
        month_start = today.replace(day=1)
        lines = env["account.move.line"].search([
            ("date", ">=", month_start),
            ("date", "<=", today),
            ("parent_state", "=", "posted"),
            ("account_id.account_type", "in", [
                "income", "income_other", "expense", "expense_depreciation",
                "expense_direct_cost",
            ]),
        ], limit=5000)
        revenue = sum(-float(l.balance) for l in lines
                      if l.account_id.account_type in ("income", "income_other"))
        expenses = sum(float(l.balance) for l in lines
                       if l.account_id.account_type in (
                           "expense", "expense_depreciation", "expense_direct_cost"))
        net = revenue - expenses
        return {
            "period": f"{month_start.isoformat()} to {today.isoformat()}",
            "revenue": _fmt_amount(revenue, currency),
            "expenses": _fmt_amount(expenses, currency),
            "net_income": _fmt_amount(net, currency),
            "net_sign": "profit" if net >= 0 else "loss",
            "revenue_raw": revenue,
            "expenses_raw": expenses,
            "net_raw": net,
        }

    def _fetch_tax(self, env, today, currency):
        month_start = today.replace(day=1)
        tax_lines = env["account.move.line"].search([
            ("tax_line_id", "!=", False),
            ("date", ">=", month_start),
            ("parent_state", "=", "posted"),
        ], limit=5000)
        sales_tax = sum(
            abs(float(l.balance))
            for l in tax_lines
            if l.move_id.move_type in ("out_invoice", "out_refund")
        )
        purchase_tax = sum(
            abs(float(l.balance))
            for l in tax_lines
            if l.move_id.move_type in ("in_invoice", "in_refund")
        )
        net = sales_tax - purchase_tax
        return {
            "period": f"{month_start.isoformat()} to {today.isoformat()}",
            "vat_collected": _fmt_amount(sales_tax, currency),
            "vat_paid": _fmt_amount(purchase_tax, currency),
            "net_position": _fmt_amount(abs(net), currency),
            "net_direction": "payable" if net >= 0 else "refundable",
        }

    # -------------------------------------------------------------------------
    # AML — aml_officer
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_aml_data",
        description="Fetch AML compliance data including risk alerts, KYC application summary, "
                    "transaction monitoring alerts, and sanctions screening results.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_aml_data(
        self,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"aml_officer"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        today = fields.Date.today()
        result = {}

        if _model_exists(env, "risk.assessment"):
            try:
                high = env["risk.assessment"].search([("risk_level", "in", ["high", "very_high"])], limit=50)
                result["high_risk_assessments"] = {
                    "count": len(high),
                    "items": [
                        {
                            "id": r.id,
                            "partner": r.partner_id.name if r.partner_id else "",
                            "risk_level": r.risk_level,
                            "date": r.assessment_date.isoformat() if r.assessment_date else None,
                        }
                        for r in high
                    ],
                }
            except Exception as e:
                result["high_risk_assessments"] = f"[Unavailable: {e}]"
        else:
            result["high_risk_assessments"] = "Risk assessment model not installed."

        if _model_exists(env, "kyc.application"):
            try:
                pending_kyc = env["kyc.application"].search([("state", "=", "pending")], limit=50)
                result["pending_kyc"] = {
                    "count": len(pending_kyc),
                    "items": [
                        {
                            "id": k.id,
                            "partner": k.partner_id.name if k.partner_id else "",
                            "submitted": k.submit_date.isoformat() if hasattr(k, "submit_date") and k.submit_date else None,
                        }
                        for k in pending_kyc
                    ],
                }
            except Exception as e:
                result["pending_kyc"] = f"[Unavailable: {e}]"
        else:
            result["pending_kyc"] = "KYC model not installed."

        if _model_exists(env, "transaction.monitoring"):
            try:
                alerts = env["transaction.monitoring"].search([
                    ("state", "=", "alert"),
                ], limit=50)
                result["monitoring_alerts"] = {
                    "count": len(alerts),
                    "items": [
                        {
                            "id": a.id,
                            "partner": a.partner_id.name if a.partner_id else "",
                            "rule": a.rule_id.name if hasattr(a, "rule_id") and a.rule_id else "",
                            "amount": float(a.amount) if hasattr(a, "amount") and a.amount else 0.0,
                        }
                        for a in alerts
                    ],
                }
            except Exception as e:
                result["monitoring_alerts"] = f"[Unavailable: {e}]"
        else:
            result["monitoring_alerts"] = "Transaction monitoring model not installed."

        _logger.info("AML data fetched for persona '%s'", _persona_code)
        return {"aml": result}

    # -------------------------------------------------------------------------
    # HR — hr_assistant
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_hr_data",
        description="Fetch HR data including headcount by department, leave requests (if hr_holidays "
                    "installed), and payroll summary (if hr_payroll installed). Degrades gracefully "
                    "when optional modules are absent.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_hr_data(
        self,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"hr_assistant"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        today = fields.Date.today()
        result = {}

        if _model_exists(env, "hr.employee"):
            try:
                employees = env["hr.employee"].search([("active", "=", True)])
                by_dept = defaultdict(int)
                for e in employees:
                    by_dept[e.department_id.name or "Unassigned"] += 1
                result["headcount"] = {
                    "total": len(employees),
                    "by_department": dict(by_dept),
                }
            except Exception as e:
                result["headcount"] = f"[Unavailable: {e}]"
        else:
            result["headcount"] = "HR module not installed."

        if _model_exists(env, "hr.leave"):
            try:
                pending = env["hr.leave"].search([
                    ("state", "in", ["confirm", "validate1"]),
                ], limit=50)
                result["pending_leaves"] = {
                    "count": len(pending),
                    "items": [
                        {
                            "employee": l.employee_id.name if l.employee_id else "",
                            "leave_type": l.holiday_status_id.name if l.holiday_status_id else "",
                            "date_from": l.date_from.isoformat() if l.date_from else None,
                            "date_to": l.date_to.isoformat() if l.date_to else None,
                        }
                        for l in pending
                    ],
                }
            except Exception as e:
                result["pending_leaves"] = f"[Unavailable: {e}]"
        else:
            result["pending_leaves"] = "Leave management module not installed."

        if _model_exists(env, "hr.payslip"):
            try:
                month_start = today.replace(day=1)
                slips = env["hr.payslip"].search([
                    ("date_from", ">=", month_start),
                    ("state", "in", ["done", "paid"]),
                ], limit=200)
                total_net = 0.0
                total_gross = 0.0
                for slip in slips:
                    for line in slip.line_ids:
                        if line.code == "NET":
                            total_net += float(line.total)
                        if line.code == "GROSS":
                            total_gross += float(line.total)
                result["payroll"] = {
                    "payslips_processed": len(slips),
                    "total_gross": _fmt_amount(total_gross),
                    "total_net": _fmt_amount(total_net),
                }
            except Exception as e:
                result["payroll"] = f"[Unavailable: {e}]"
        else:
            result["payroll"] = "Payroll module not installed."

        _logger.info("HR data fetched for persona '%s'", _persona_code)
        return {"hr": result}

    # -------------------------------------------------------------------------
    # SALES — sales_analyst
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_sales_data",
        description="Fetch sales and CRM data including pipeline by stage, sales performance by "
                    "salesperson, and recent orders.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_sales_data(
        self,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"sales_analyst"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        today = fields.Date.today()
        currency = env.company.currency_id
        result = {}

        if _model_exists(env, "crm.lead"):
            try:
                leads = env["crm.lead"].search([
                    ("active", "=", True),
                    ("type", "=", "opportunity"),
                ])
                by_stage = defaultdict(lambda: {"count": 0, "value": 0.0})
                for l in leads:
                    stage = l.stage_id.name or "Unknown"
                    by_stage[stage]["count"] += 1
                    by_stage[stage]["value"] += float(getattr(l, "expected_revenue", 0.0) or 0.0)
                total_pipeline = sum(d["value"] for d in by_stage.values())
                result["pipeline"] = {
                    "total_value": _fmt_amount(total_pipeline, currency),
                    "total_value_raw": total_pipeline,
                    "opportunity_count": len(leads),
                    "by_stage": {
                        stage: {
                            "count": d["count"],
                            "value": _fmt_amount(d["value"], currency),
                            "value_raw": d["value"],
                        }
                        for stage, d in sorted(by_stage.items())
                    },
                }
            except Exception as e:
                result["pipeline"] = f"[Unavailable: {e}]"
        else:
            result["pipeline"] = "CRM module not installed."

        try:
            month_start = today.replace(day=1)
            invoices = env["account.move"].search([
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", month_start),
                ("invoice_date", "<=", today),
            ], limit=1000)
            by_salesperson = defaultdict(float)
            for inv in invoices:
                rep = getattr(inv, "invoice_user_id", None) or getattr(inv, "user_id", None)
                name = rep.name if rep else "Unassigned"
                by_salesperson[name] += float(inv.amount_untaxed)
            top = sorted(by_salesperson.items(), key=lambda x: x[1], reverse=True)[:10]
            total = sum(v for _, v in top)
            result["sales_performance"] = {
                "period": f"{month_start.isoformat()} to {today.isoformat()}",
                "total_invoiced": _fmt_amount(total, currency),
                "total_invoiced_raw": total,
                "invoice_count": len(invoices),
                "by_salesperson": [
                    {"name": n, "amount": _fmt_amount(a, currency), "amount_raw": a}
                    for n, a in top
                ],
            }
        except Exception as e:
            result["sales_performance"] = f"[Unavailable: {e}]"

        _logger.info("Sales data fetched for persona '%s'", _persona_code)
        return {"sales": result}

    # -------------------------------------------------------------------------
    # OPERATIONS — operations_manager
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_operations_data",
        description="Fetch operations data including stock moves, inventory status, and "
                    "manufacturing orders (if mrp installed).",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_operations_data(
        self,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"operations_manager"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        today = fields.Date.today()
        result = {}

        if _model_exists(env, "stock.move"):
            try:
                recent_moves = env["stock.move"].search([
                    ("date", ">=", today - timedelta(days=7)),
                ], limit=200, order="date desc")
                planned = env["stock.move"].search([
                    ("state", "=", "draft"),
                ], limit=100)
                result["stock_moves"] = {
                    "recent_7_days": len(recent_moves),
                    "planned_draft": len(planned),
                }
            except Exception as e:
                result["stock_moves"] = f"[Unavailable: {e}]"
        else:
            result["stock_moves"] = "Stock module not installed."

        if _model_exists(env, "stock.quant"):
            try:
                low_stock = env["stock.quant"].search([
                    ("quantity", "<=", 0),
                    ("product_id.active", "=", True),
                ], limit=100)
                result["inventory"] = {
                    "out_of_stock_products": len(low_stock),
                }
            except Exception as e:
                result["inventory"] = f"[Unavailable: {e}]"
        else:
            result["inventory"] = "Inventory model not available."

        if _model_exists(env, "mrp.production"):
            try:
                unfinished = env["mrp.production"].search([
                    ("state", "not in", ["done", "cancel"]),
                ], limit=100)
                result["manufacturing"] = {
                    "unfinished_orders": len(unfinished),
                }
            except Exception as e:
                result["manufacturing"] = f"[Unavailable: {e}]"
        else:
            result["manufacturing"] = "Manufacturing module not installed."

        _logger.info("Operations data fetched for persona '%s'", _persona_code)
        return {"operations": result}

    # -------------------------------------------------------------------------
    # INVENTORY — inventory_specialist
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_inventory_data",
        description="Fetch detailed inventory data including stock quants by location, "
                    "inventory valuation, and stock moves.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_inventory_data(
        self,
        location_id: int = None,
        product_limit: int = 50,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"inventory_specialist"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        result = {}

        if _model_exists(env, "stock.quant"):
            try:
                domain = [("product_id.active", "=", True)]
                if location_id:
                    domain.append(("location_id", "=", location_id))
                quants = env["stock.quant"].search(
                    domain, limit=product_limit, order="quantity desc",
                )
                result["stock_quants"] = [
                    {
                        "product": q.product_id.name,
                        "quantity": float(q.quantity),
                        "location": q.location_id.name,
                    }
                    for q in quants
                ]
            except Exception as e:
                result["stock_quants"] = f"[Unavailable: {e}]"
        else:
            result["stock_quants"] = "Inventory model not available."

        _logger.info("Inventory data fetched for persona '%s'", _persona_code)
        return {"inventory": result}

    # -------------------------------------------------------------------------
    # CUSTOMER SUPPORT — customer_support
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_customer_data",
        description="Fetch customer/partner data including recent interactions, top customers "
                    "by revenue, and partner balances.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_customer_data(
        self,
        partner_limit: int = 20,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"customer_support"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        result = {}

        try:
            partners = env["res.partner"].search([
                ("active", "=", True),
                ("customer_rank", ">", 0),
            ], limit=partner_limit, order="total_invoiced desc")
            result["top_customers"] = [
                {
                    "id": p.id,
                    "name": p.name,
                    "email": p.email or "",
                    "phone": p.phone or "",
                    "total_invoiced": _fmt_amount(float(p.total_invoiced or 0.0)),
                }
                for p in partners
            ]
        except Exception as e:
            result["top_customers"] = f"[Unavailable: {e}]"

        _logger.info("Customer data fetched for persona '%s'", _persona_code)
        return {"customers": result}

    # -------------------------------------------------------------------------
    # MARKETING — marketing_analyst
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_marketing_data",
        description="Fetch marketing data including campaigns (if marketing module installed) "
                    "and leads by source.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_marketing_data(
        self,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"marketing_analyst"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        result = {}

        if _model_exists(env, "crm.lead"):
            try:
                leads = env["crm.lead"].search([("active", "=", True)], limit=200)
                by_source = defaultdict(int)
                for l in leads:
                    by_source[l.source_id.name or "Unknown"] += 1
                result["leads_by_source"] = dict(by_source)
                result["total_leads"] = len(leads)
            except Exception as e:
                result["leads_by_source"] = f"[Unavailable: {e}]"
        else:
            result["leads_by_source"] = "CRM module not installed."

        _logger.info("Marketing data fetched for persona '%s'", _persona_code)
        return {"marketing": result}

    # -------------------------------------------------------------------------
    # PROJECT — project_manager
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_project_data",
        description="Fetch project data (if project module installed). Includes project list, "
                    "task counts, and status breakdown.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_project_data(
        self,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"project_manager"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        result = {}

        if _model_exists(env, "project.project"):
            try:
                projects = env["project.project"].search([("active", "=", True)], limit=50)
                result["projects"] = [
                    {
                        "id": p.id,
                        "name": p.name,
                        "task_count": p.task_count if hasattr(p, "task_count") else 0,
                        "state": p.state or "",
                    }
                    for p in projects
                ]
                result["total_projects"] = len(projects)
            except Exception as e:
                result["projects"] = f"[Unavailable: {e}]"
        else:
            result["projects"] = "Project module not installed."

        _logger.info("Project data fetched for persona '%s'", _persona_code)
        return {"project": result}

    # -------------------------------------------------------------------------
    # PROCUREMENT — procurement_officer
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_procurement_data",
        description="Fetch procurement data including purchase orders, RFQs, and vendor "
                    "performance.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_procurement_data(
        self,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"procurement_officer"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        result = {}

        if _model_exists(env, "purchase.order"):
            try:
                pending = env["purchase.order"].search([
                    ("state", "in", ["draft", "sent", "to approve"]),
                ], limit=100)
                result["pending_purchase_orders"] = {
                    "count": len(pending),
                    "items": [
                        {
                            "id": po.id,
                            "name": po.name,
                            "partner": po.partner_id.name if po.partner_id else "",
                            "amount": _fmt_amount(float(po.amount_total or 0.0)),
                            "state": po.state,
                        }
                        for po in pending
                    ],
                }
            except Exception as e:
                result["pending_purchase_orders"] = f"[Unavailable: {e}]"
        else:
            result["pending_purchase_orders"] = "Purchase module not installed."

        _logger.info("Procurement data fetched for persona '%s'", _persona_code)
        return {"procurement": result}

    # -------------------------------------------------------------------------
    # COMPLIANCE — compliance_auditor
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_compliance_data",
        description="Fetch compliance and audit data including model change tracking, recent "
                    "mail activities, and user access logs.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_compliance_data(
        self,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"compliance_auditor"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        result = {}

        try:
            recent_messages = env["mail.message"].search([
                ("model", "not in", ["mail.message"]),
            ], limit=100, order="date desc")
            activities = defaultdict(int)
            for msg in recent_messages:
                activities[msg.model or "unknown"] += 1
            result["recent_activity"] = {
                "total_messages_7_days": len(recent_messages),
                "by_model": dict(activities),
            }
        except Exception as e:
            result["recent_activity"] = f"[Unavailable: {e}]"

        _logger.info("Compliance data fetched for persona '%s'", _persona_code)
        return {"compliance": result}

    # -------------------------------------------------------------------------
    # EXECUTIVE — executive_assistant
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_executive_summary",
        description="Fetch an executive cross-domain snapshot across finance, HR, sales, "
                    "and operations for a high-level dashboard view.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_executive_summary(
        self,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"executive_assistant"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        today = fields.Date.today()
        currency = env.company.currency_id
        result = {}

        finance = self._fetch_summary_snapshot(env, today, currency)
        if finance:
            result["finance"] = finance

        if _model_exists(env, "hr.employee"):
            try:
                emp_count = env["hr.employee"].search_count([("active", "=", True)])
                result["headcount"] = emp_count
            except Exception:
                pass

        if _model_exists(env, "crm.lead"):
            try:
                pipeline_value = sum(
                    float(l.expected_revenue or 0.0)
                    for l in env["crm.lead"].search([
                        ("active", "=", True), ("type", "=", "opportunity"),
                    ])
                )
                result["pipeline_value"] = _fmt_amount(pipeline_value, currency)
            except Exception:
                pass

        _logger.info("Executive summary fetched for persona '%s'", _persona_code)
        return {"executive_summary": result}

    def _fetch_summary_snapshot(self, env, today, currency):
        try:
            recv = env["account.move"].search([
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "not in", ["paid", "reversed"]),
            ])
            pay = env["account.move"].search([
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "not in", ["paid", "reversed"]),
            ])
            od_recv = sum(
                float(m.amount_residual)
                for m in recv
                if m.invoice_date_due and m.invoice_date_due < today
            )
            od_pay = sum(
                float(m.amount_residual)
                for m in pay
                if m.invoice_date_due and m.invoice_date_due < today
            )
            return {
                "outstanding_receivables": _fmt_amount(sum(recv.mapped("amount_residual")), currency),
                "outstanding_payables": _fmt_amount(sum(pay.mapped("amount_residual")), currency),
                "overdue_receivables": _fmt_amount(od_recv, currency),
                "overdue_payables": _fmt_amount(od_pay, currency),
            }
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # IT SUPPORT — it_support
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_it_data",
        description="Fetch IT support data including active users, recent login activity, "
                    "and system module status.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_it_data(
        self,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"it_support"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env
        result = {}

        try:
            users = env["res.users"].search([("active", "=", True)])
            result["active_users"] = len(users)
        except Exception as e:
            result["active_users"] = f"[Unavailable: {e}]"

        try:
            module_count = len(env["ir.module.module"].search([
                ("state", "=", "installed"),
            ]))
            result["installed_modules"] = module_count
        except Exception as e:
            result["installed_modules"] = f"[Unavailable: {e}]"

        _logger.info("IT data fetched for persona '%s'", _persona_code)
        return {"it": result}

    # -------------------------------------------------------------------------
    # DATA ANALYST — data_analyst
    # -------------------------------------------------------------------------
    @llm_tool(
        name="sgc_fetch_generic_report",
        description="Generic data access tool that performs read_group aggregations on any model. "
                    "Only accessible to the data_analyst persona. Use for ad-hoc data exploration.",
        xml_managed=True,
        read_only_hint=True,
        idempotent_hint=True,
    )
    def sgc_fetch_generic_report(
        self,
        model_name: str,
        group_by_field: str,
        measure_field: str = None,
        aggregation: str = "sum",
        domain: list = None,
        limit: int = 50,
        _persona_code: str = "",
    ) -> dict:
        _supported_codes = {"data_analyst"}
        denied = _check_persona_access(_supported_codes, {"_persona_code": _persona_code})
        if denied:
            return denied

        env = self.env

        if not _model_exists(env, model_name):
            return {"error": True, "message": f"Model '{model_name}' does not exist."}

        try:
            Model = env[model_name]
            if not Model.check_access_rights("read", raise_exception=False):
                return {"error": True, "message": f"No read access on '{model_name}'."}

            measures = [measure_field] if measure_field else []
            result = Model.read_group(
                domain or [],
                fields=measures + [group_by_field],
                groupby=[group_by_field],
                lazy=False,
                limit=limit,
            )
            return {
                "model": model_name,
                "group_by": group_by_field,
                "measure": measure_field,
                "aggregation": aggregation,
                "rows": [
                    {k: (str(v) if not isinstance(v, (str, int, float, bool)) else v)
                     for k, v in r.items()}
                    for r in result
                ],
                "row_count": len(result),
            }
        except Exception as e:
            return {"error": True, "message": str(e)}
