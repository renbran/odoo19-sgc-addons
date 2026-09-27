"""Odoo -> tenant receiver event contract (schema version 1).

Pure Python on purpose (no Odoo import) so the wire format, the signature and the retry
classification can be unit-tested without a server and checked against the receiver.

Every event is a ``tenant.sync`` snapshot: the full state the tenant should be in, not a
transition. The receiver converges on the newest snapshot per tenant, so a lost or
reordered event can never leave a tenant in a state Odoo no longer wants.

Signature: v1 = HMAC-SHA256(secret, "<timestamp>.<raw body>") as lowercase hex, sent as
``x-sgc-signature: v1=<hex>`` with ``x-sgc-timestamp: <epoch seconds>``. The receiver
rejects a timestamp outside a 5-minute window, so each attempt is signed with a fresh
timestamp over the same frozen body bytes.
"""

import hashlib
import hmac
import json
import re

SCHEMA_VERSION = 1
SOURCE = "odoo"
EVENT_TYPE = "tenant.sync"

STATES = ("active", "grace", "read_only", "archive", "deleted")
REASONS = ("paid", "overdue", "cancelled", "retention_expired")
DOCS_STATUSES = ("pending", "submitted", "rejected", "approved", "expiring")

SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,28}[a-z0-9]$")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
REF_RE = re.compile(r"^[A-Za-z0-9_.:/-]{1,64}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,}$")

MIN_SECRET_LENGTH = 32

# Retry schedule in seconds; after the last step the event is dead-lettered.
BACKOFF_SECONDS = (60, 300, 1800, 7200, 21600, 43200, 86400)
MAX_ATTEMPTS = len(BACKOFF_SECONDS) + 1


class ContractError(ValueError):
    """The event cannot be expressed in the receiver's contract."""


def iso_utc(dt):
    """ISO-8601 UTC with millisecond precision and a Z suffix (naive = UTC)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (dt.microsecond // 1000)


def build_payload(
    event_id,
    occurred_at,
    tenant_slug,
    version,
    state,
    reason,
    docs_status,
    users,
    order_ref,
    company_name,
    billing_url=None,
    licence_expiry=None,
    provision=False,
    admin_email=None,
    admin_name=None,
):
    """Validate and return the event dict. Raises ContractError when invalid."""
    if not EVENT_ID_RE.match(event_id or ""):
        raise ContractError("invalid event_id")
    if not SLUG_RE.match(tenant_slug or ""):
        raise ContractError("invalid tenant_slug")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ContractError("version must be a positive integer")
    if state not in STATES:
        raise ContractError("invalid state")
    if reason not in REASONS:
        raise ContractError("invalid reason")
    if docs_status not in DOCS_STATUSES:
        raise ContractError("invalid docs_status")
    if not isinstance(users, int) or isinstance(users, bool) or not 1 <= users <= 1000:
        raise ContractError("users out of range")
    if not REF_RE.match(order_ref or ""):
        raise ContractError("invalid order_ref")
    if not company_name or len(company_name) > 120:
        raise ContractError("invalid company_name")
    if billing_url is not None and not billing_url.startswith("https://"):
        raise ContractError("billing_url must be https")
    if provision:
        if not EMAIL_RE.match(admin_email or ""):
            raise ContractError("provisioning needs a valid admin_email")
        if not admin_name:
            raise ContractError("provisioning needs admin_name")
    return {
        "event_id": event_id,
        "event_type": EVENT_TYPE,
        "occurred_at": iso_utc(occurred_at),
        "source": SOURCE,
        "schema_version": SCHEMA_VERSION,
        "tenant_slug": tenant_slug,
        "version": version,
        "state": state,
        "reason": reason,
        "docs_status": docs_status,
        "licence_expiry": licence_expiry.isoformat() if licence_expiry else None,
        "users": users,
        "order_ref": order_ref,
        "company_name": company_name,
        "billing_url": billing_url,
        "provision": bool(provision),
        "admin_email": admin_email if provision else None,
        "admin_name": admin_name if provision else None,
    }


def serialize(payload):
    """Canonical body bytes. Frozen at enqueue time and re-sent unchanged."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=True)


def sign(secret, timestamp, body):
    """Hex HMAC-SHA256 over "<timestamp>.<body>"."""
    message = ("%s.%s" % (timestamp, body)).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def headers(secret, timestamp, body, event_id):
    return {
        "content-type": "application/json",
        "x-sgc-timestamp": str(timestamp),
        "x-sgc-signature": "v1=%s" % sign(secret, str(timestamp), body),
        "x-sgc-event-id": event_id,
        "user-agent": "SGC-Layer3-Bridge/1.0",
    }


def classify(status_code):
    """Map a delivery outcome to 'sent' | 'retry' | 'reject'.

    None means no response (timeout, DNS, TLS, reset). 2xx is final (the receiver also
    acknowledges duplicates and stale versions with 2xx). 408/429/5xx and network faults
    are transient. Any other 4xx means these exact bytes can never succeed.
    """
    if status_code is None:
        return "retry"
    if 200 <= status_code < 300:
        return "sent"
    if status_code in (408, 429) or status_code >= 500:
        return "retry"
    return "reject"


def backoff_seconds(attempts):
    """Delay before the next attempt, given how many attempts have been made."""
    index = max(0, min(attempts - 1, len(BACKOFF_SECONDS) - 1))
    return BACKOFF_SECONDS[index]
