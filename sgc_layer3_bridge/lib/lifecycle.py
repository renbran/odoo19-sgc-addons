"""Layer 3 account-state rules (MSA SGC-MSA-2026-02 sections 5.4, 6 and 13).

Pure functions so the schedule is testable without Odoo and easy to compare with the
contract text:

* Grace      - days 1-7 after the oldest unpaid invoice's due date; full service.
* Read-only  - days 8-29; records viewable and exportable, nothing new.
* Archive    - day 30 onwards, or 30 days after a cancellation takes effect.
* Deleted    - once the archive period (days) has passed. Terminal.

The MSA's section 5.4 and its section 6 table disagree on the exact day numbers and
neither covers days 15-29; this follows the section 6 table and keeps Read-only until
day 29 (see the Layer 3 plan, section 02).
"""

from datetime import timedelta

GRACE_FROM_DAY = 1
READ_ONLY_FROM_DAY = 8
ARCHIVE_FROM_DAY = 30
EXIT_READ_ONLY_DAYS = 30
NOTICE_DAYS = 60


def target_state(today, activated, days_overdue, end_date, archive_since, archive_days):
    """Return (state, reason) for a tenant, or (None, None) before first payment.

    today         -- date of evaluation
    activated     -- True once the first payment has been received
    days_overdue  -- days since the oldest unpaid invoice fell due (0 when none)
    end_date      -- date a cancellation takes effect, or None
    archive_since -- date the tenant entered Archive, or None
    archive_days  -- how long Archive lasts before deletion
    """
    if not activated:
        return None, None
    if end_date and today >= end_date:
        archive_start = end_date + timedelta(days=EXIT_READ_ONLY_DAYS)
        if today < archive_start:
            return "read_only", "cancelled"
        if today >= archive_start + timedelta(days=archive_days):
            return "deleted", "retention_expired"
        return "archive", "cancelled"
    if days_overdue >= ARCHIVE_FROM_DAY:
        start = archive_since or today
        if today >= start + timedelta(days=archive_days):
            return "deleted", "retention_expired"
        return "archive", "overdue"
    if days_overdue >= READ_ONLY_FROM_DAY:
        return "read_only", "overdue"
    if days_overdue >= GRACE_FROM_DAY:
        return "grace", "overdue"
    return "active", "paid"


def notice_end_date(notice_date, cycle_end, next_cycle_end):
    """Date a cancellation takes effect (MSA 13.3).

    Effective at the end of the current billing cycle when that is at least 60 days after
    the notice; otherwise at the end of the following cycle. `next_cycle_end(d)` returns
    the cycle end that follows `d`.
    """
    end = cycle_end
    while (end - notice_date).days < NOTICE_DAYS:
        end = next_cycle_end(end)
    return end
