"""Odoo -> KartaTap entitlement event contract (schema version 1).

Pure Python on purpose: no Odoo import, so the wire format, the signature and the
retry classification can be unit-tested without an Odoo server, and checked
byte-for-byte against KartaTap's receiver (src/lib/odoo-billing/entitlements.ts).

Signature: v1 = HMAC-SHA256(secret, "<timestamp>.<raw body>") as lowercase hex,
sent as `x-kartatap-signature: v1=<hex>` with `x-kartatap-timestamp: <epoch seconds>`.
The receiver rejects a timestamp outside a 5-minute window, so every delivery
attempt is signed with a FRESH timestamp over the SAME frozen body bytes: the
receiver's payload hash stays stable across retries (idempotency) while the
signature stays inside the replay window.
"""

import hashlib
import hmac
import json
import re

SCHEMA_VERSION = 1
SOURCE = "odoo"

EVENT_TYPES = frozenset(
    {
        "subscription.activated",
        "subscription.renewed",
        "subscription.past_due",
        "subscription.canceled",
    }
)
STATUS_FOR_EVENT = {
    "subscription.activated": "active",
    "subscription.renewed": "active",
    "subscription.past_due": "past_due",
    "subscription.canceled": "canceled",
}

PLANS = ("SOLO", "TEAM", "BUSINESS")
MIN_SEATS = {"SOLO": 1, "TEAM": 2, "BUSINESS": 2}
MAX_QUANTITY = 100

# Same patterns the receiver enforces; a payload that fails them would be
# rejected with a non-retryable 400, so it is refused here before it is queued.
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
COMPANY_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
REF_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

MIN_SECRET_LENGTH = 32  # the receiver ignores shorter keys

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
    event_type,
    occurred_at,
    kartatap_company_id,
    plan_code,
    quantity,
    odoo_partner_ref,
    odoo_subscription_ref,
    effective_period_end=None,
    reason_code=None,
):
    """Validate and return the event dict. Raises ContractError when invalid."""
    if event_type not in EVENT_TYPES:
        raise ContractError("unsupported event_type")
    if not EVENT_ID_RE.match(event_id or ""):
        raise ContractError("invalid event_id")
    if not COMPANY_ID_RE.match(kartatap_company_id or ""):
        raise ContractError("invalid kartatap_company_id")
    if plan_code not in PLANS:
        raise ContractError("invalid plan_code")
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        raise ContractError("quantity must be an integer")
    if quantity < MIN_SEATS[plan_code] or quantity > MAX_QUANTITY:
        raise ContractError("quantity out of range for plan")
    for name, value in (("odoo_partner_ref", odoo_partner_ref), ("odoo_subscription_ref", odoo_subscription_ref)):
        if value is not None and not REF_RE.match(value):
            raise ContractError("invalid %s" % name)
    if event_type in ("subscription.activated", "subscription.renewed") and not odoo_subscription_ref:
        # The receiver refuses a plan-changing event without a subscription reference.
        raise ContractError("a plan-changing event needs odoo_subscription_ref")
    if reason_code is not None and not re.match(r"^[A-Za-z0-9_.:-]{1,64}$", reason_code):
        raise ContractError("invalid reason_code")
    return {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": iso_utc(occurred_at),
        "source": SOURCE,
        "schema_version": SCHEMA_VERSION,
        "kartatap_company_id": kartatap_company_id,
        "plan_code": plan_code,
        "quantity": quantity,
        "status": STATUS_FOR_EVENT[event_type],
        "odoo_partner_ref": odoo_partner_ref,
        "odoo_subscription_ref": odoo_subscription_ref,
        "effective_period_end": iso_utc(effective_period_end) if effective_period_end else None,
        "reason_code": reason_code,
    }


def serialize(payload):
    """Canonical body bytes. Frozen at enqueue time and re-sent unchanged."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=True)


def sign(secret, timestamp, body):
    """Hex HMAC-SHA256 over "<timestamp>.<body>" (the receiver's computeSignature)."""
    message = ("%s.%s" % (timestamp, body)).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def headers(secret, timestamp, body, event_id):
    return {
        "content-type": "application/json",
        "x-kartatap-timestamp": str(timestamp),
        "x-kartatap-signature": "v1=%s" % sign(secret, str(timestamp), body),
        "x-kartatap-event-id": event_id,
        "user-agent": "KartaTap-OdooBridge/1.1",
    }


def classify(status_code):
    """Map a delivery outcome to 'sent' | 'retry' | 'reject'.

    None means the request never produced a response (timeout, DNS, TLS, reset).
    2xx (including the receiver's duplicate/stale/noop acknowledgements) is final.
    408/429/5xx and network faults are transient. Every other 4xx means the event
    itself was refused (bad signature, malformed payload, prohibited transition)
    and repeating the same bytes can never succeed.
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
