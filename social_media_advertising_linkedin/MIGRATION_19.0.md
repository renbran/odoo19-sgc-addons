# Migration to Odoo 19.0

## Source and method

- Ported from the current `OCA/social` branch `18.0` with the OCA history-preserving
  `git format-patch --keep-subject --stdout origin/19.0..origin/18.0 -- social_media_advertising_linkedin | git am -3 --keep`
  flow.
- Imported all seven module-specific commits; the imported tree matched `origin/18.0`
  byte-for-byte before the 19.0 compatibility changes.
- Depends on the migrated `social_media_advertising` and `social_media_linkedin`
  19.0.1.0.0 modules and their existing `social_media_base` 19.0.1.0.0 dependency.
  Parent modules were not changed.

## Changes

- Bumped the manifest version to `19.0.1.0.0`.
- Replaced `odoo.osv.expression.AND` with `odoo.fields.Domain.AND` in the sponsored-post
  campaign domain. The media, remote-reference and ad-format conditions are unchanged.
- Renamed the menu test assertions from `groups_id` to Odoo 19's `group_ids`. The module
  creates no `res.users` or `res.groups` records and declares no group privilege
  records, so no user or privilege data migration is needed; the XML `groups` menu
  attributes remain the applicable declaration API.
- Audited every Python model and test for legacy constraints and indexes, grouped-read
  and prefetch APIs, environment access, translation calls and action APIs. There are no
  legacy SQL constraints, `read_group` or `search_read` calls,
  `self._context`/`self._uid` accesses or other required adaptations. Existing
  `_read_group`-free `grouped` indexes, `env.context`, `env._` and `_for_xml_id` calls
  remain compatible.
- Audited all XML data and views against their migrated parents. The stage records match
  the current `social.stage` fields, inherited XPath anchors still exist, list view
  names and dynamic attributes already use Odoo 19 syntax, and the inherited search
  views carry the migrated group containers. No XML or data changes were required.
- Kept LinkedIn API version `202607`, all endpoints, OAuth scopes (`r_ads`, `rw_ads`,
  `r_ads_reporting`), advertising synchronization, pagination, publishing, archiving,
  deletion and statistics behavior unchanged.

## Verification

- All module Python files passed built-in source compilation.
- All module XML files passed XML parsing.
- Scoped deprecation scans found no remaining legacy constraint declarations,
  `groups_id`, `odoo.osv.expression`, `read_group`, `search_read`, obsolete search-group
  attributes, tree-view tags or legacy environment accessors.
- `git diff --check` passed and the working diff is restricted to
  `social_media_advertising_linkedin`.

## Risks / untestable items

- Runtime installation, database-backed tests and pre-commit were not run, as required
  for this task. The centralized Odoo 19 rehearsal should install the three-module
  dependency chain and run the existing post-install tests, including inherited-view
  validation and the `Domain` campaign filtering.
- LinkedIn advertising calls, OAuth reauthorization and API pagination were not
  exercised against LinkedIn; no live credentials were accessed. Their payloads and
  behavior are unchanged, but remain an integration release check.
