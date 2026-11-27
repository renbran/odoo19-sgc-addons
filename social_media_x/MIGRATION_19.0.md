# Migration to Odoo 19.0

## Source and method

- Ported the current `OCA/social` 18.0 module with the OCA history-preserving
  `git format-patch | git am -3 --keep` flow. The imported tree matched `origin/18.0`
  before the migration edits.
- Used PR #1791 migration commit `c6a2b87155a085d19b9acefb006bea27640af963` as a
  reference only. Its relevant Odoo 19 fixes were applied manually to the newer 18.0
  implementation; its stale source tree was not copied.
- Depends on the existing `social_media_base` 19.0.1.0.0. Base and every other module
  are unchanged.

## Changes

- Bumped the manifest version to `19.0.1.0.0`.
- Changed the OAuth wizard lookup to `search_fetch`, explicitly fetching `x_api_key` and
  `x_api_secret`. The request-token and creator restrictions, single-record limit,
  callback behavior, and credential fallback are unchanged.
- Kept the current `_read_group` implementation with the `__count` aggregate and
  duplicate filter, together with its tuple-based caller and named translation
  placeholders. It already implements the Odoo 19 API; the older dictionary result shape
  from the reference migration was not reintroduced.
- Renamed the test user field from `groups_id` to Odoo 19's `group_ids`.
- Updated generated OCA README and description links from the 18.0 branch to 19.0
  without replacing the newer documentation content.
- Reviewed all Python, XML, routes, constraints, hooks, views, and static files. No
  additional view, asset, constraint, controller, or base-hook adaptation was required.
  The module has no JavaScript sources or asset bundle declarations.
- Preserved OAuth 1.0a, X API v2 behavior, v1.1 media uploads, API scopes and endpoints,
  publication and statistics behavior, and the `tweepy` and `requests_oauthlib` external
  dependencies.

## Verification

- Python syntax compilation: passed for all 21 Python files.
- XML parsing: passed for all 4 XML files.
- `git diff --check`: passed.
- Targeted static scans covered deprecated `read_group`, user/group field names, SQL
  constraints, expression imports, `_uid`/`_context`, translation formatting, JSON
  routes, search-view group attributes, OWL/JavaScript files, and hooks.
- Odoo runtime installation and module tests were not run, as required by the task
  constraints. Pre-commit was not run.

## Risks / untestable items

- The Odoo 19 registry, view inheritance, HTTP callback, and tests still need a runtime
  integration pass before deployment.
- OAuth association, posting, deletion, rate limits, and statistics were not exercised
  against X; no live credentials were used.
- Translation catalogs retain their imported 18.0 project metadata and content; they can
  be refreshed by the normal OCA translation generation workflow.
