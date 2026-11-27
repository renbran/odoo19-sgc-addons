# Migration to Odoo 19.0

## Source and method

- Ported from `OCA/social` branch `18.0` with the OCA history-preserving
  `git format-patch | git am -3 --keep` flow.
- Reused the migration intent and version bump from PR #1789
  (`22ed4b6fa2ae11f1c3b7b7f62cae616e13719688e`), but resolved it against the current
  18.0 module instead of replacing the newer implementation with the older PR tree.
- Depends on the existing `social_media_base` 19.0.1.0.0; base was not modified.

## Changes

- Bumped the manifest version to `19.0.1.0.0`.
- Regenerated OCA README metadata for the 19.0 branch with the repository's OCA
  pre-commit configuration.
- Kept the calendar model, view, JS class, scheduling behavior, colors and tests
  unchanged. The module already used Odoo 19-compatible ORM and view APIs, so no
  behavioral adaptation was required.

## Verification

- OCA pre-commit: passed on Ubuntu 24.04 / Python 3.12 with the repository's pinned OCA
  hook set.
- Clean Odoo 19 CE install with demo data: passed; `social_media_base` and
  `social_media_calendar` installed at `19.0.1.0.0`.
- Existing tests: `social_media_base` 401/401 and `social_media_calendar` 14/14 passed.
  The targeted calendar upgrade run reported 0 failures and 0 errors.

## Risks / untestable items

- Browser calendar interactions still require a live Odoo 19 backend and a supported
  browser; server-side tests cover the view architecture and date computations.
- A full stock-core `--test-enable` run in the minimal Odoo image exposed unrelated
  packaging gaps (`odoo-bin` absent and `websocket-client` absent). Module-scoped test
  runs are clean; no calendar or base test failed.
