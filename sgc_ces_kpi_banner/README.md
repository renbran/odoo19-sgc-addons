# SGC - CES KPI & Gate Banner (`sgc_ces_kpi_banner`)

Odoo 19 addon. Gives Customer Engagement Specialists (CES) a floating,
collapsible KPI banner showing gate progress, daily/monthly KPI targets and a
deterministic "next recommended action", plus a fully configurable, versioned
gate framework and a manager review workflow.

---

## 1. Purpose

CES ramp performance is currently invisible until someone runs a report. This
module makes it continuously visible to the specialist, reviewable by their
manager, and configurable by an administrator - without changing how anyone
uses the CRM.

**v1 is informational only.** It never blocks a CRM write, a stage change or a
login; it never auto-sets Won/Lost; it never touches quotations, invoices or
payments; it sends no email unless email is explicitly enabled.

## 2. What is installed

| Model | Purpose |
|---|---|
| `sgc.ces.gate.plan` | Versioned plan; one active default plan per company (no routing); freeze-on-assign |
| `sgc.ces.gate.template` | One gate's schedule and outcome policy |
| `sgc.ces.gate.requirement` | Generic metric + comparator + target + window |
| `sgc.ces.gate.assignment` | Employee to plan binding (draft by default) |
| `sgc.ces.gate.instance` | Snapshotted per-employee gate occurrence |
| `sgc.ces.gate.requirement.result` | Snapshotted definition + live measurement |
| `sgc.ces.gate.review` | Manager review record and decision |
| `sgc.ces.gate.consideration` | Additive waiver / extension / target adjustment |
| `sgc.ces.kpi.target` | Daily and monthly KPI targets |
| `sgc.ces.kpi.service` | Central server-side calculation and RPC surface |
| `sgc.ces.identity` | CES identity, manager and stage resolution |
| `sgc.ces.metric.*` | Metric providers, dispatched by explicit code lookup |

## 3. Safety properties

* **No dynamic evaluation.** Configuration never stores an expression, a
  domain or SQL. Metrics are dispatched through the explicit
  `METRIC_DISPATCH` table in `models/metric_registry.py`. A test performs a
  static source scan of the whole metric layer to enforce this.
* **No hard-coded production ids.** The CES `hr.job` and every CRM stage are
  resolved through `ir.config_parameter`, then XML-ID, then name, and degrade
  to an empty result. Same pattern `sgc_sales_playbook` already uses.
* **Accounting non-disclosure.** The payment metric returns aggregates only;
  its drill-down targets `sale.order`, never `account.move`.
* **Server-side only.** The JS layer contains no formula and builds no domain;
  drill-down actions are generated server side and whitelisted to
  `crm.lead` / `sale.order`.
* **Namespacing.** Model names `sgc.ces.*`, XML-IDs under this module, CSS
  prefix `.o_sgc_ces_kpi_`, JS service key `sgc_ces_kpi_service`, main
  component key `sgc_ces_kpi_banner.Banner`. Nothing collides with
  `sgc_sales_playbook`, `sgc_lead_scoring`, `sgc_executive_dashboard`,
  `sgc_crm_dashboard`, `crm_executive_dashboard`, `sgc_app_home`,
  `sgc_crm_outreach_popup`, `sgc_crm_fields` or Gamification.

## 4. Gate scheduling formula

```
anchor        = CES start date (per the plan's start-date strategy)
period_start  = anchor + relativedelta(months = offset_months)
period_end    = anchor + relativedelta(months = offset_months + duration_months)
due_date      = period_end                     (or last day of that month)
due_date      = working_day_adjust(due_date)   (none | next | previous)
review_date   = due_date - review_lead_days
```

`relativedelta` clamps day overflow, so 31 Jan + 1 month is 28 Feb (29 Feb in
a leap year), never 3 March. Working-day adjustment moves Saturday/Sunday to
the next or previous weekday; public holidays are not modelled.

## 5. Metric definitions

| Code | Definition |
|---|---|
| `pipeline_qualified_value` | `SUM(expected_revenue)` of the user's open opportunities excluding configured dead-end and Won stages |
| `pipeline_qualified_count` | Same population, counted |
| `staleness_stale_count` | Opportunities whose source date is strictly older than `stale_days` |
| `staleness_stale_ratio` | `stale / (total - unknown) * 100` |
| `signed_proposal_count` | `sale.order` owned by the user with `signed_on` set |
| `paid_deal_count` | `sale.order` owned by the user reachable from a posted invoice in a qualifying `payment_state` via `sale_order_line_invoice_rel` |
| `activity_*` | Opportunities touched / stage advances / logged messages in the window |

Day-boundary rule for staleness: an opportunity last touched *exactly*
`stale_days` ago is **not** stale; one more day and it is.

## 6. Manager resolution

1. `hr.version.hr_responsible_id` of the current version
2. `hr.employee.parent_id.user_id`
3. `hr.department.manager_id.user_id`
4. `ir.config_parameter` `sgc_ces_kpi_banner.fallback_manager_uid`
5. Empty - the gate simply has no reviewer, nothing raises

"Current version" is `MAX(date_version) WHERE date_version <= today`, applied
generically so multi-version employee histories work.

## 7. Review alerts

An hourly `ir.cron` creates a review at `due_date - review_lead_days`.

* Idempotent on `(instance, alert_type, alert_scheduled_date)` - enforced by a
  database unique constraint as well as by a pre-check.
* Catch-up safe: a review date that passed during downtime still fires once.
* Bounded batch, per-record `try/except`, rollback on failure.
* Waived gates raise no alert.
* Overdue escalation is a separate, equally idempotent alert type.

The notification includes the gate, the specialist, the due date, the days
remaining, the requirement list with target/current/met, and the score. It
excludes customer names, deal names, invoice numbers, payment references and
any contract or salary data.

## 8. Considerations

Waivers, extensions and target adjustments are **additive**. The instance's
`due_date` and the result's `original_target` are never rewritten; the
effective values are computed by layering approved considerations on top.
Approved considerations are immutable - revoke and create a new one.

## 9. Security

Three groups, each implying the previous one:

* **CES KPI User** - own banner, own gates, read-only configuration.
* **CES KPI Manager** - additionally the gates and summaries of the
  specialists whose resolved manager they are, plus reviews and
  consideration approval.
* **CES KPI Administrator** - full configuration.

Record rules scope gate instances, results, reviews, considerations and
assignments to the specialist or their resolved reviewer, with a separate
global multi-company rule on every model that carries `company_id`.
`get_ces_kpi_summary(user_id)` re-checks manager scope server side, so the RPC
cannot be used to read another rep's numbers.

## 10. Install / upgrade / test

```bash
# install (staging)
docker exec odoo19-sgc-staging odoo -d sgc_staging \
  --db_host=postgres-prod --db_user=odoo --db_password=odoo \
  --addons-path=/mnt/staging-addons,/mnt/extra-addons \
  -i sgc_ces_kpi_banner --stop-after-init --no-http

# upgrade
... -u sgc_ces_kpi_banner --stop-after-init --no-http

# test
... -u sgc_ces_kpi_banner --test-enable --test-tags /sgc_ces_kpi_banner \
    --stop-after-init --http-port=8099
```

## 11. Rollback

```bash
# 1. uninstall through the UI (Apps > CES KPI & Gate Banner > Uninstall) or:
docker exec odoo19-sgc-staging odoo shell -d sgc_staging ... \
  -c "env['ir.module.module'].search([('name','=','sgc_ces_kpi_banner')]).button_immediate_uninstall()"
# 2. remove the folder from the addons path
rm -rf /opt/staging/odoo19-sgc-feature/sgc_ces_kpi_banner
# 3. restart the container
```

Uninstalling drops only this module's own tables and its three groups. It
never touches `crm.lead`, `sale.order`, `account.move` or any other module's
data, because the module only ever reads them.

## 12. Known limitations

1. **Signed-proposal and paid-deal metrics read ~0 today.** No sale order in
   the estate has `signed_on` set, and only ~7% of orders carry
   `opportunity_id`. The external envelope fields on `crm.lead` are labelled
   for Zoho Sign in `sgc_crm_fields` and have no write-back code anywhere.
   Until the business decides between Zoho Sign and DocuSeal and a real
   webhook is built, these gates cannot measure anything. The configuration
   health check surfaces this explicitly.
2. **Staleness defaults to `date_last_stage_update`**, not
   `x_last_activity_date` (only written by enrichment crons, so it means
   "last enrichment run"). `x_days_since_activity` is excluded entirely - it
   is declared but never written by any code path.
3. **No production deployment.** This module has been installed and tested on
   staging (`odoo19-sgc-staging` / `sgc_staging`) only.
