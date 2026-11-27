# Migration to Odoo 19.0

## Source and method

- Ported only `social_media_linkedin_sync` from the current `OCA/social` `origin/18.0`
  (`40a49586d6ff5d30e9a75b67404e3ead524dc8a1`; module tip
  `b1dc4456126189b97aa4c13c1dd42056ee75b57e`).
- Imported all nine module commits with the OCA history-preserving
  `git format-patch --keep-subject --stdout origin/19.0..origin/18.0 -- social_media_linkedin_sync | git am -3 --keep`
  flow. No upstream 19.0 migration pull request exists for this module.
- Depends on the migrated `social_media_base`, `social_media_sync` and
  `social_media_linkedin` addons at 19.0.1.0.0. Those parents and every other addon
  remain unchanged.

## Changes

- Bumped the manifest version to `19.0.1.0.0`.
- Updated the generated OCA README and description branch links to 19.0.
- Reviewed every Python source and test, the inherited account form, OWL patches, tours
  and asset declarations against the migrated parents and the Odoo 19 ORM, HTTP and mail
  APIs. No production, test, view or JavaScript code adaptation was needed: the module
  has no legacy constraints/indexes, `res.users.groups_id`, group privilege/category
  assignments, `Domain` or expression imports, `_uid`/`_context`, grouped-read calls,
  JSON routes or legacy search-view groups, and its current APIs remain valid.
- Confirmed that the inherited form still finds the migrated LinkedIn statistics button
  and base sheet, and that the JavaScript patches still target classes and methods
  exported by the migrated base and sync assets.
- Confirmed the Odoo 19 core signatures of `mail.thread.message_post` with `partner_ids`
  and `bus.bus._sendone`. The module does not override the mail controller whose
  `add_guest_to_context` import moved in the parent sync migration.
- Kept OAuth, LinkedIn API versions, scopes, endpoints, feed pagination, statistics
  checkpoints, media download, comment/reaction and full-resync behavior unchanged.

## Verification

- The history import applied all nine module commits without conflicts. The imported
  module tree matched `origin/18.0` before the migration edits.
- Static Python compilation passed for all 16 Python files, XML parsing passed for the
  inherited view, and JavaScript syntax checking passed for all six JavaScript sources.
- Focused source scans cover the Odoo 19 constraint/index, user/group, `Domain`,
  environment, grouped-read, route, search-view, asset and core mail API changes.
- `git diff --check` passed, and the final diff is confined to this module's manifest,
  generated documentation and these migration notes.
- Runtime Odoo tests and pre-commit were not run, as required for this task.

## Risks / untestable items

- The Odoo 19 registry, inherited view, OWL patches, HTTP interaction and browser tours
  still need a runtime integration pass before deployment.
- OAuth association, feed import, media downloads, comments, reactions, statistics and
  full resynchronization were not exercised against LinkedIn; no live credentials were
  accessed.
- Generated documentation branch links were updated directly rather than by running the
  OCA documentation pre-commit hook. Translation catalogs retain their imported 18.0
  metadata and content for the normal OCA translation generation workflow.
