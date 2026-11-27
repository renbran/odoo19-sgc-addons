# Migration to Odoo 19.0

## Source and method

- Ported only `social_media_x_sync` from the current `OCA/social` `18.0` branch with the
  OCA history-preserving
  `git format-patch --keep-subject --stdout origin/19.0..origin/18.0 -- social_media_x_sync | git am -3 --keep`
  flow.
- Imported all six module commits without conflicts. A byte-preserving native pipe was
  used, and the imported module tree matched `origin/18.0` before the migration edits.
- Depends on the existing `social_media_sync` and `social_media_x` modules at
  `19.0.1.0.0`. Both parents and every other addon remain unchanged. No upstream 19.0
  migration pull request was available as a reference.

## Changes

- Bumped the manifest version to `19.0.1.0.0`.
- Updated the generated OCA README and description branch, Weblate, Runboat, image and
  issue links from 18.0 to 19.0 without changing their content.
- Reviewed every Python, XML and JavaScript source and test for the Odoo 19
  constraint/index, `res.users.group_ids`, `res.groups.privilege_id`, `Domain`,
  environment, grouped-read, JSON-RPC route, search-view, OWL/asset and mail API
  changes. No connector-owned code, test, view or asset adaptation was required beyond
  the version metadata.
- Confirmed the inherited X account form anchor (`x_api_secret`), publication search
  anchor (`with_impressions`), list anchor (`share_count`) and patched frontend classes
  and methods still exist in the migrated parent modules.
- Kept the current `env.context` comment-refresh flag and the `search_read` statistics
  test, which match the migrated parent implementation. The module has no legacy
  constraints, user-group writes, grouped reads, controllers, direct mail imports or
  search-view group declarations to migrate.
- Preserved the X API v2 timeline, recent-search, likes, reply, reaction and deletion
  behavior; import pagination and limits; media download behavior; and all `tweepy`
  usage. OAuth configuration, API versions and scopes are unchanged.

## Verification

- The required history import applied all six module commits and the resulting tree was
  byte-identical to `origin/18.0` before migration edits.
- Static Python compilation passed for all 12 Python files without writing bytecode
  artifacts.
- XML parsing passed for both XML view files.
- Focused source scans covered deprecated grouped reads, user/group fields, legacy
  constraints and decorators, `Domain`/expression imports, `_context`/`_uid`, JSON
  routes, search-view groups, OWL/JavaScript assets, inherited view anchors and core
  mail API usage.
- `git diff --check` passed.
- Odoo runtime installation, module tests and browser tours were not run, as required by
  the task constraints. Pre-commit was not run.

## Risks / untestable items

- The Odoo 19 registry, inherited views, ORM synchronization flows, frontend patches and
  browser tour still need the centralized runtime integration pass before deployment.
- Timeline import, comments, reactions, deletion, media downloads, rate limits and
  statistics were not exercised against X; no live credentials were used.
- Generated documentation branch links were updated directly rather than by running the
  OCA documentation pre-commit hook.
- Translation catalogs retain their imported project metadata and content; they can be
  refreshed by the normal OCA translation generation workflow.
