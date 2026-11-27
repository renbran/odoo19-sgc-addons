# Migration to Odoo 19.0

## Source and method

- Ported from `OCA/social` branch `18.0` with the OCA history-preserving
  `git format-patch --keep-subject --stdout origin/19.0..origin/18.0 -- social_media_advertising | git am -3 --keep`
  flow.
- Imported all eight module-specific commits; the imported tree matched `origin/18.0`
  byte-for-byte before the 19.0 compatibility changes.
- Depends on the existing `social_media_base` 19.0.1.0.0; base and all other modules
  remain unchanged.

## Changes

- Bumped the manifest version to `19.0.1.0.0`.
- Replaced the five `_sql_constraints` declarations on `social.stage`,
  `social.advertising.campaign.group`, `social.advertising.campaign`,
  `social.advertising.ad` and `social.advertising.account` with `models.Constraint`. The
  constraint names, SQL definitions and messages are unchanged, so their uniqueness
  semantics and constraint XML IDs are kept.
- Renamed test-user `groups_id` values to the Odoo 19 `group_ids` field. This module
  declares no `res.groups` records, so no privilege-record migration is needed; its menu
  and rule references already use the applicable APIs.
- Removed the obsolete `expand="0" string="Group By"` attributes from the five
  search-view group containers without changing their filters.
- Audited the Python models and tests, XML security/data/views, and OWL kanban files
  against the Odoo 19 upgrade guidance and the migrated base module. Existing
  `_read_group`, `search_fetch`, list view mode, `env._`, action, QWeb and
  kanban-controller APIs required no further adaptation.

## Verification

- All module Python files passed built-in source compilation.
- All module XML files passed XML parsing.
- Scoped deprecation scans found no remaining legacy constraint declarations, user
  `groups_id`, obsolete search-group attributes, `read_group` calls or `toggle_active`
  buttons.
- `git diff --check` passed and the working diff is restricted to
  `social_media_advertising`.

## Risks / untestable items

- Runtime installation, database-backed tests and pre-commit were not run, as required
  for this task. A clean Odoo 19 install and the existing module test suite should
  therefore remain release-gate checks.
- Kanban bus notifications and synchronization actions still require a live Odoo 19
  backend/browser check. Their implementation is unchanged after the static API audit.
