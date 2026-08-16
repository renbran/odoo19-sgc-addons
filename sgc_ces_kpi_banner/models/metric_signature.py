# -*- coding: utf-8 -*-
"""Signed-proposal metric provider.

Three strategies, selectable per requirement via the ``signature_strategy``
parameter:

* ``native``   (DEFAULT) - ``sale.order.signed_on IS NOT NULL``, optionally
  restricted to orders that actually requested a signature
  (``require_signature``).  This is the only strategy backed by data that is
  genuinely written today.
* ``external`` - the external e-signature envelope fields on ``crm.lead``
  (``x_envelope_id`` / ``x_completed_date``), added by ``sgc_crm_fields`` and
  labelled in that module's source as *Zoho Sign*.  These fields have no
  write-back code anywhere in the estate today, so this strategy will read 0
  until a real webhook integration exists.  Selecting it when the fields are
  absent degrades to a zero result instead of raising.
* ``combined`` - a record counts if either source says signed.

Attribution: orders are attributed to a CES user through
``sale.order.user_id``; when ``require_opportunity`` is set, only orders with
a populated ``opportunity_id`` count (this is the strict, joinable subset -
currently ~7% of orders, see the verification addendum).
"""
from odoo import api, models

STRATEGIES = ("native", "external", "combined")


class SgcCesMetricSignature(models.AbstractModel):
    _name = "sgc.ces.metric.signature"
    _description = "SGC CES Signed Proposal Metric Provider"

    @api.model
    def _strategy(self, params):
        strategy = (params or {}).get("signature_strategy") or "native"
        return strategy if strategy in STRATEGIES else "native"

    @api.model
    def _native_domain(self, ctx):
        params = ctx.get("params") or {}
        domain = [
            ("user_id", "=", ctx["user_id"]),
            ("signed_on", "!=", False),
        ]
        if params.get("require_signature_only"):
            domain.append(("require_signature", "=", True))
        if params.get("require_opportunity"):
            domain.append(("opportunity_id", "!=", False))
        states = params.get("order_states") or "sale"
        allowed = [s.strip() for s in str(states).split(",") if s.strip()]
        if allowed:
            domain.append(("state", "in", allowed))
        if ctx.get("date_from"):
            domain.append(("signed_on", ">=", "%s 00:00:00" % ctx["date_from"]))
        if ctx.get("date_to"):
            domain.append(("signed_on", "<=", "%s 23:59:59" % ctx["date_to"]))
        if ctx.get("company_ids"):
            domain.append(("company_id", "in", list(ctx["company_ids"])))
        return domain

    @api.model
    def _external_domain(self, ctx):
        Lead = self.env["crm.lead"]
        if "x_envelope_id" not in Lead._fields:
            return None
        domain = [
            ("type", "=", "opportunity"),
            ("user_id", "=", ctx["user_id"]),
            ("x_envelope_id", "!=", False),
        ]
        date_field = "x_completed_date" if "x_completed_date" in Lead._fields else None
        if date_field:
            domain.append((date_field, "!=", False))
            if ctx.get("date_from"):
                domain.append((date_field, ">=", "%s 00:00:00" % ctx["date_from"]))
            if ctx.get("date_to"):
                domain.append((date_field, "<=", "%s 23:59:59" % ctx["date_to"]))
        if ctx.get("company_ids"):
            domain.append(("company_id", "in", list(ctx["company_ids"]) + [False]))
        return domain

    @api.model
    def _metric_signed_proposal_count(self, ctx):
        strategy = self._strategy(ctx.get("params"))
        total = 0.0
        detail = {"strategy": strategy}
        domain = None
        res_model = None
        if strategy in ("native", "combined"):
            domain = self._native_domain(ctx)
            res_model = "sale.order"
            native = self.env["sale.order"].sudo().search_count(domain)
            detail["native_count"] = native
            total += native
        if strategy in ("external", "combined"):
            external_domain = self._external_domain(ctx)
            if external_domain is None:
                detail["external_available"] = False
            else:
                detail["external_available"] = True
                external = self.env["crm.lead"].sudo().search_count(external_domain)
                detail["external_count"] = external
                total += external
                if strategy == "external":
                    domain = external_domain
                    res_model = "crm.lead"
        return {"value": float(total), "domain": domain, "res_model": res_model, "detail": detail}

    @api.model
    def _metric_signed_proposal_value(self, ctx):
        strategy = self._strategy(ctx.get("params"))
        detail = {"strategy": strategy}
        value = 0.0
        domain = None
        res_model = None
        if strategy in ("native", "combined"):
            domain = self._native_domain(ctx)
            res_model = "sale.order"
            groups = self.env["sale.order"].sudo()._read_group(domain, [], ["amount_untaxed:sum"])
            native_value = (groups[0][0] or 0.0) if groups else 0.0
            detail["native_value"] = native_value
            value += native_value
        if strategy in ("external", "combined"):
            external_domain = self._external_domain(ctx)
            if external_domain is None:
                detail["external_available"] = False
            else:
                detail["external_available"] = True
                groups = self.env["crm.lead"].sudo()._read_group(
                    external_domain, [], ["expected_revenue:sum"]
                )
                external_value = (groups[0][0] or 0.0) if groups else 0.0
                detail["external_value"] = external_value
                value += external_value
                if strategy == "external":
                    domain = external_domain
                    res_model = "crm.lead"
        return {"value": float(value), "domain": domain, "res_model": res_model, "detail": detail}
