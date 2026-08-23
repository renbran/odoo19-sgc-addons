# -*- coding: utf-8 -*-
{
    "name": "SGC - CRM Lead Deduplication",
    "version": "19.0.1.0.0",
    "category": "Sales/CRM",
    "summary": "Detects, tiers and safely merges duplicate CRM leads; maintains an intermediary-identity blocklist",
    "description": """
CRM Lead Deduplication
=======================
Community edition has no data_merge/data_cleaning/data_recycle, so this module
is permanent infrastructure, not scaffolding:

- Overrides crm.lead._sort_by_confidence_level so the merge survivor is chosen
  by pipeline stage first (highest stage sequence wins), not by Odoo's default
  type/active-before-sequence order.
- Maintains crm.lead.dedup.blocklist: phone/email values shared by an
  intermediary (broker/agency switchboard) across many unrelated leads,
  refreshed by a daily cron using a frequency threshold plus a small
  structural check for boilerplate/scraped values.
- Provides crm.lead.dedup.cluster / crm.lead.dedup.cluster.line as the
  reviewed working queue for duplicate clusters that are not safe to
  auto-merge.
- Flags new/edited leads whose email or phone hits the blocklist so data
  entry can be corrected at the source instead of merged after the fact.
""",
    "author": "SGC",
    "company": "SGC",
    "maintainer": "SGC",
    "website": "https://sgctech.ai",
    "depends": ["crm"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/crm_lead_dedup_blocklist_views.xml",
        "views/crm_lead_dedup_cluster_views.xml",
        "wizard/crm_lead_dedup_merge_views.xml",
        "views/crm_lead_dedup_menus.xml",
    ],
    "license": "AGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
