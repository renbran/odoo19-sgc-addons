Connect Odoo's Social Media application to Buffer. Import Buffer channels as
social accounts, then publish immediately through the channel queue or schedule
posts for a specific date without leaving Odoo.

The connector uses Buffer's GraphQL API with an account API key. It does not
implement OAuth, synchronization, statistics, or remote deletion.

Phase 1 supports text-only posts. Buffer requires publicly hosted media URLs;
private Odoo image and video attachments are therefore rejected with a clear
publication error instead of being uploaded or exposed.
