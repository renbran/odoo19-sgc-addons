# Migration to Odoo 19.0

## Source and method

- Implemented as a new connector on the existing `social_media_base` 19.0.1.0.0
  publishing API; no pre-19.0 Buffer connector was imported.
- Existing `social_media_*` modules were used as references only and were not modified.

## Odoo 19 compatibility

- Declares manifest version `19.0.1.0.0` and depends only on `social_media_base` among
  Odoo addons.
- Uses `self.env._` named interpolation for translated messages, modern list views,
  related Selection extension through `social.media`, and the base `_publish_guard`,
  `_publish_attempt`, `_register_publish_success`, and `_register_publish_refused`
  contracts.
- Contains no `_sql_constraints`, `groups_id`, legacy expression imports, `type="json"`,
  OAuth flow, or JavaScript requiring migration.
- Stores no real Buffer account, organization, channel, or API key in module data or
  tests. All HTTP tests patch `requests.post` and fail immediately if a live request is
  attempted.

## Functional scope

- API-key configuration and idempotent Buffer channel import.
- Text-only queue and custom-scheduled `createPost` mutations.
- Per-publication success, typed mutation refusal, media rejection, HTTP 429, GraphQL
  error, and transport error handling.

## Verification

- `python -m compileall -q social_media_buffer`: passed.
- `git diff --check`: passed.
- OCA pre-commit on the new module and generated dependency metadata: passed.
- Clean install in the local `odoo:19.0` image with a disposable PostgreSQL 16 database:
  `social_media_base` and `social_media_buffer` installed successfully.
- Module-scoped Odoo tests with `--test-enable`: `social_media_buffer` reported 13
  tests; the selected run finished with 0 failures and 0 errors. Every Buffer HTTP
  request was mocked, including the channel import and both publishing modes.
- No live Buffer credentials or API calls were used. The Docker test containers and
  private network were removed after the run.
