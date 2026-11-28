After importing channels, create a Social Media post and select one or more
Buffer accounts.

- **Post now** creates the Buffer post with `schedulingType: automatic` and
  `mode: addToQueue`, so Buffer chooses the next queue slot.
- **Schedule** creates it with `mode: customScheduled` and sends Odoo's schedule
  date as a UTC ISO 8601 `dueAt` value.

A successful call stores Buffer's post ID as the publication remote reference
and its `externalLink`, when Buffer already provides one. In this publishing
flow, **Posted** means Buffer accepted the post; queued and custom-scheduled
posts can still be awaiting delivery by Buffer.

A typed Buffer `MutationError` or a response without a post ID fails only the
affected publication. HTTP throttling, GraphQL errors, validation failures, and
connection errors are retained as readable failure reasons.

Phase 1 accepts no Odoo image or video attachments on Buffer posts. Host media
at a stable public HTTPS URL and use Buffer directly for media posts until URL
asset support is implemented.
