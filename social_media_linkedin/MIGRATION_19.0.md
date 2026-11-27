# Migration to Odoo 19.0

## Source and method

- Ported from the current `OCA/social` branch `18.0` with the OCA history-preserving
  `git format-patch | git am -3 --keep` flow. All eight module commits were imported,
  and the imported tree matched `origin/18.0` before the 19.0 changes were applied.
- Used PR #1790 migration commit `ff10919cd563f07c62b7e44e4db1aac8f443b326` as a
  reference only. Its older implementation was not used to replace the newer 18.0
  connector.
- Depends on the existing `social_media_base` 19.0.1.0.0; base and all other modules
  were left unchanged.

## Changes

- Bumped the manifest version to `19.0.1.0.0`.
- Ported the PR's `search_fetch` adaptation to the current OAuth wizard lookup, fetching
  the LinkedIn client credentials while preserving the state-token, creator and
  single-record filters.
- Renamed the test users' `groups_id` values to Odoo 19's `group_ids` field.
- Updated the generated OCA README and description links to the 19.0 branch.
- Kept the current 18.0 translation calls, which already use `self.env._` with Odoo
  19-compatible interpolation. The module contains no `read_group` calls, legacy
  constraints, expression imports, `_context`/`_uid`, JavaScript or OWL components
  requiring migration. Its HTTP callback, views and uninstall hook already use
  compatible APIs.
- Kept OAuth behavior, LinkedIn API version `202607`, scopes, endpoints, publishing,
  deletion, statistics and retry behavior unchanged.

## Verification

- Static Python compilation passed for all 22 Python files.
- XML parsing passed for all three XML data/view files.
- Focused source scans covered deprecated `read_group`, `groups_id`, `category_id`,
  legacy constraints, expression imports, `_context`/`_uid`, translation interpolation,
  route types, search-view group attributes, JavaScript/OWL and base hooks.
- Runtime Odoo tests and pre-commit were not run, as required for this task.

## Risks / untestable items

- The OAuth callback and ORM prefetch behavior still need confirmation on a live Odoo 19
  registry.
- Publishing, token renewal, statistics, deletion recovery and video uploads were not
  exercised against LinkedIn; no live credentials were accessed.
- Generated documentation branch links were updated directly rather than by running the
  OCA documentation pre-commit hook.
