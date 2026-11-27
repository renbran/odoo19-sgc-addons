# Migration to Odoo 19.0

## Source and method

- Ported only `social_media_sync` from `OCA/social` `origin/18.0`
  (`40a49586d6ff5d30e9a75b67404e3ead524dc8a1`; module tip
  `f3936cc896b2c490addfa6a08b14b553d04839f5`).
- Imported all 12 module commits with the OCA history-preserving
  `git format-patch --keep-subject --stdout origin/19.0..origin/18.0 -- social_media_sync | git am -3 --keep`
  flow. Stale upstream migration PRs were not used as replacement trees.
- Depends on the existing `social_media_base` 19.0.1.0.0. Base and every other addon
  remain unchanged.

## Changes

- Bumped the manifest version to `19.0.1.0.0`.
- Changed the `/mail/message/post` controller route from `type="json"` to the Odoo 19
  `type="jsonrpc"` dispatcher.
- Updated `add_guest_to_context` to its Odoo 19 home in
  `odoo.addons.mail.tools.discuss`; the old `mail.models.discuss.mail_guest` import no
  longer exists. This was confirmed by the clean Odoo 19 rehearsal.
- Updated the standard-thread fallback test to Odoo 19's `message_id` plus `store_data`
  response contract instead of the removed `mail.message` result bucket. Production
  delegation to the core controller is unchanged.
- Passed `limit=None` to both empty-domain production account searches in
  `update_dashboard_posts` and `_update_posts`, preserving their unlimited recordset
  semantics.
- Renamed test-user `groups_id` values to the Odoo 19 `res.users.group_ids` field.
- Reviewed sync-owned models, security, views, controllers, OWL/JS assets and tests for
  the Odoo 19 constraint/index, group privilege, `Domain`, environment, grouped-read,
  route, search-view and asset API changes. No other adaptation was needed.
- Kept OAuth, external API, synchronization, media retention and frontend business
  behavior unchanged.

## Verification

- The required history import applied all 12 module commits without conflicts. A
  byte-preserving native pipe was used, and `git range-diff` reports every imported
  commit as patch-identical (`=`) to its 18.0 source commit.
- All 16 Python files compiled successfully with Python's `compile()` without writing
  bytecode artifacts.
- `git diff --check` passed.
- Static scans found no remaining sync-owned `groups_id`, `type="json"`, legacy SQL
  constraint, legacy API decorator, implicit unlimited empty-domain production search,
  legacy search-group attribute, or legacy web asset pattern.

## Risks / untestable items

- OCA pre-commit and Odoo 19 installation, module tests, HTTP controller tests and
  browser tours were intentionally left for centralized Linux verification; they were
  not run in this isolated Windows worktree.
- The controller and composer extend core `mail` APIs. Their Odoo 19 runtime integration
  still requires the centralized HTTP and browser test runs.
- No live social-media credentials, OAuth flows, external APIs or media downloads were
  exercised. Connector behavior was not changed, but live API compatibility remains
  outside this migration's static verification.
