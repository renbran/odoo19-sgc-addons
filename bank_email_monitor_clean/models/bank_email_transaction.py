import email
import email.header
import email.utils
import imaplib
import logging
import re
import ssl
import socket
import time

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BANK_KEYWORDS = frozenset([
    "transaction", "debit", "credit", "payment", "transfer",
    "withdrawal", "deposit", "account", "bank", "balance",
    "receipt", "invoice", "charge", "purchase", "refund",
    "amount", "paid", "received", "wire", "ach", "swift",
    "credited", "debited", "statement", "notification",
    "alert", "authorized", "declined", "approved", "cleared",
])

CREDIT_KEYWORDS = (
    "credit", "credited", "received", "deposit", "deposited", "refund",
    "incoming", "reversal",
)

DEBIT_KEYWORDS = (
    "debit", "debited", "paid", "purchase", "withdraw", "withdrawal",
    "charge", "charged", "payment", "spent", "transfer out",
)

NON_TRANSACTION_HINTS = (
    "otp", "one time password", "login", "signed in", "password reset",
    "promotional", "offer", "newsletter", "statement generated",
)

REF_PATTERNS = (
    r"(?:reference\s*(?:no|number)?|ref|txn\s*ref|transaction\s*(?:id|ref)|auth\s*code|approval\s*code|rrn|arn|trace\s*number|sequence\s*number)\s*[:#\-]?\s*([A-Za-z0-9\-]{6,})",
)


class BankEmailTransaction(models.Model):
    _name = "bank.email.transaction"
    _description = "Bank Email Transaction"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    # ── Core fields ──────────────────────────────────────────────────
    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default="/",
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("confirmed", "Confirmed"),
            ("posted", "Posted"),
            ("ignored", "Ignored"),
            ("error", "Error"),
        ],
        string="Status",
        default="pending",
        tracking=True,
        required=True,
        index=True,
    )

    # ── Email fields ─────────────────────────────────────────────────
    email_subject = fields.Char(string="Email Subject")
    email_from = fields.Char(string="Sender Email", index=True)
    email_date = fields.Datetime(string="Email Date")
    email_body = fields.Html(string="Email Body")
    email_message_id = fields.Char(string="Message-ID", index=True)

    # ── Parsing fields ───────────────────────────────────────────────
    ai_raw_response = fields.Text(string="Matched Rule")
    ai_confidence = fields.Float(string="Parser Confidence (0-100)")
    ai_notes = fields.Text(string="Parser Notes")
    ai_suggested_bank = fields.Char(string="Detected Bank")
    ai_suggested_partner = fields.Char(string="Detected Partner")
    ai_suggested_account = fields.Char(string="Suggested Account")

    # ── Transaction fields ───────────────────────────────────────────
    transaction_type = fields.Selection(
        selection=[("credit", "Credit"), ("debit", "Debit")],
        string="Transaction Type",
        tracking=True,
    )
    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    transaction_date = fields.Date(string="Transaction Date", index=True)
    transaction_ref = fields.Char(string="Transaction Reference", index=True)
    description = fields.Char(string="Description", tracking=True)

    card_last4 = fields.Char(string="Card Last 4 Digits")
    payment_method = fields.Selection(
        selection=[
            ("credit_card", "Credit Card"),
            ("debit_card", "Debit Card"),
            ("bank_transfer", "Bank Transfer"),
            ("cash_deposit", "Cash Deposit"),
            ("cheque", "Cheque"),
            ("other", "Other"),
        ],
        string="Payment Method",
    )
    expense_category = fields.Char(string="Expense Category")

    # ── Accounting links ─────────────────────────────────────────────
    bank_journal_id = fields.Many2one(
        "account.journal",
        string="Bank Journal",
        domain=[("type", "=", "bank")],
        tracking=True,
        check_company=True,
        ondelete="restrict",
    )
    partner_id = fields.Many2one("res.partner", string="Partner", ondelete="restrict")
    account_id = fields.Many2one(
        "account.account",
        string="Account",
        check_company=True,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company.id,
        required=True,
        index=True,
        ondelete="restrict",
    )
    bank_statement_line_id = fields.Many2one(
        "account.bank.statement.line",
        string="Bank Statement Line",
        readonly=True,
        check_company=True,
        ondelete="restrict",
    )
    parser_suggested_move_id = fields.Many2one(
        "account.move",
        string="Suggested Invoice/Bill",
        readonly=True,
        check_company=True,
        ondelete="set null",
    )
    parser_suggested_move_score = fields.Float(string="Match Score", readonly=True)
    parser_suggested_move_reason = fields.Char(string="Match Reason", readonly=True)
    parser_suggested_move_remark = fields.Char(string="Match Remark", readonly=True)
    parser_suggested_move_state = fields.Selection(
        [("none", "None"), ("suggested", "Suggested"), ("accepted", "Accepted"), ("rejected", "Rejected")],
        default="none",
        string="Reconciliation Hint",
        tracking=True,
    )
    learned_rule_id = fields.Many2one(
        "bank.vendor.rule",
        string="Learned Rule Draft",
        readonly=True,
        check_company=True,
        ondelete="set null",
    )

    _bank_email_message_id_uniq = models.Constraint(
        "unique(email_message_id)",
        "Each email can only be processed once (Message-ID must be unique).",
    )

    # ── CRUD overrides ───────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("bank.email.transaction")
                    or "/"
                )
        return super().create(vals_list)

    # ── Workflow actions ─────────────────────────────────────────────
    def action_confirm(self):
        for rec in self:
            if rec.state != "pending":
                raise UserError(_("Only pending transactions can be confirmed."))
            if not rec.bank_journal_id:
                raise UserError(_("Bank Journal must be set before confirming."))
            rec.state = "confirmed"
            rec._update_reconciliation_suggestion()
            rec._learn_rule_draft_from_transaction()
            rec.message_post(body=_("Transaction confirmed for review."))
        return True

    def action_post_to_accounting(self):
        for rec in self:
            if rec.state != "confirmed":
                raise UserError(
                    _("Only confirmed transactions can be posted.")
                )
            if not rec.bank_journal_id:
                raise UserError(_("Bank Journal is required."))
            if not rec.amount or rec.amount <= 0:
                raise UserError(_("Amount must be positive."))

            line_vals = {
                "date": rec.transaction_date or fields.Date.context_today(rec),
                "journal_id": rec.bank_journal_id.id,
                "amount": (
                    rec.amount if rec.transaction_type == "credit" else -rec.amount
                ),
                "payment_ref": rec.transaction_ref or rec.name,
                "partner_id": rec.partner_id.id or False,
                "currency_id": rec.currency_id.id,
                "company_id": rec.company_id.id,
            }
            statement_line = self.env["account.bank.statement.line"].create(
                line_vals
            )
            rec.write({
                "state": "posted",
                "bank_statement_line_id": statement_line.id,
            })
            rec._learn_rule_draft_from_transaction()
            rec.message_post(body=_("Transaction posted to accounting."))
        return True

    def action_suggest_reconciliation(self):
        for rec in self:
            rec._update_reconciliation_suggestion()
        return True

    def action_accept_reconciliation_hint(self):
        for rec in self:
            if rec.parser_suggested_move_id:
                rec.parser_suggested_move_state = "accepted"
                rec.message_post(
                    body=_("Reconciliation hint accepted: %s")
                    % rec.parser_suggested_move_id.display_name
                )
        return True

    def action_generate_learning_rule(self):
        for rec in self:
            rec._learn_rule_draft_from_transaction(force=True)
        return True

    def action_ignore(self):
        for rec in self:
            if rec.state in ("posted", "ignored"):
                raise UserError(
                    _("Cannot ignore a posted or already ignored transaction.")
                )
            rec.state = "ignored"
            rec.message_post(body=_("Transaction ignored."))
        return True

    def action_retry_ai(self):
        for rec in self:
            if rec.state not in ("pending", "error"):
                raise UserError(
                    _("Re-parse is only allowed for pending or error transactions.")
                )
            try:
                rec._parse_email_with_rules(
                    rec.email_subject,
                    rec.email_body,
                    rec.email_from,
                    rec.email_date,
                    rec.email_message_id,
                    force_update=True,
                )
                rec.message_post(body=_("Transaction parsing re-run with rules."))
            except Exception as e:
                _logger.exception("Parsing retry failed for %s: %s", rec.name, e)
                rec.state = "error"
                rec.message_post(body=_("Re-parse failed: %s") % str(e))
        return True

    @api.constrains("amount")
    def _check_amount_non_negative(self):
        for rec in self:
            if rec.amount is not False and rec.amount < 0:
                raise UserError(_("Amount must stay positive on staged transactions."))

    # ── Cron entry point ─────────────────────────────────────────────
    @api.model
    def _cron_fetch_bank_emails(self):
        """Called by ir.cron to poll the configured IMAP mailbox."""
        _logger.info("Bank Email Monitor: starting mailbox check.")
        imap = None
        try:
            imap = self._connect_imap()
            folder = self._get_param(
                "bank_monitor.imap_folder", "INBOX"
            )
            imap.select(folder)
            # Only fetch recent emails to avoid processing huge backlogs
            from datetime import datetime, timedelta
            lookback_days = self._safe_int(
                self._get_param("bank_monitor.lookback_days", "7"),
                default=7,
                min_value=1,
                max_value=90,
            )
            since_date = (
                datetime.now() - timedelta(days=lookback_days)
            ).strftime("%d-%b-%Y")
            status, data = imap.search(
                None, "UNSEEN", "SINCE", since_date
            )
            if status != "OK":
                _logger.warning("IMAP search failed: %s", status)
                return
            msg_nums = data[0].split() if data[0] else []
            _logger.info(
                "Bank Email Monitor: %d unseen emails since %s",
                len(msg_nums), since_date,
            )
            for num in msg_nums:
                try:
                    self._process_single_email(imap, num)
                    # Mark as read so we don't reprocess
                    imap.store(num, "+FLAGS", r"(\Seen)")
                except Exception:
                    _logger.exception(
                        "Error processing email uid %s", num
                    )
        except Exception:
            _logger.exception("Bank Email Monitor cron failed.")
        finally:
            if imap:
                try:
                    imap.logout()
                except Exception:
                    pass

    # ── IMAP helpers ─────────────────────────────────────────────────
    def _connect_imap(self):
        host = self._get_param("bank_monitor.imap_host")
        port = int(self._get_param("bank_monitor.imap_port", "993"))
        user = self._get_param("bank_monitor.imap_user")
        password = self._get_param("bank_monitor.imap_pass")
        if not all([host, user, password]):
            raise UserError(_("IMAP credentials are not fully configured."))

        context = ssl.create_default_context()
        socket.setdefaulttimeout(30)

        last_exc = None
        for attempt in range(3):
            try:
                conn = imaplib.IMAP4_SSL(host, port, ssl_context=context)
                conn.login(user, password)
                return conn
            except Exception as exc:
                last_exc = exc
                _logger.warning(
                    "IMAP connect attempt %d failed: %s", attempt + 1, exc
                )
                time.sleep(2 ** attempt)
        raise UserError(
            _("Failed to connect to IMAP after 3 attempts: %s") % last_exc
        )

    def _process_single_email(self, imap, num):
        status, data = imap.fetch(num, "(RFC822)")
        if status != "OK":
            _logger.warning("Failed to fetch email %s", num)
            return

        msg = email.message_from_bytes(data[0][1])

        # Decode subject
        raw_subject = email.header.decode_header(msg.get("Subject", ""))[0][0]
        if isinstance(raw_subject, bytes):
            raw_subject = raw_subject.decode(errors="ignore")
        subject = raw_subject or ""

        email_from = email.utils.parseaddr(msg.get("From", ""))[1]
        try:
            email_date = email.utils.parsedate_to_datetime(msg.get("Date", ""))
            # Odoo requires naive (UTC) datetimes
            if email_date.tzinfo is not None:
                from datetime import timezone
                email_date = email_date.astimezone(timezone.utc).replace(
                    tzinfo=None
                )
        except Exception:
            email_date = fields.Datetime.now()

        message_id = msg.get("Message-ID", "")
        body = self._extract_body(msg)

        if not self._is_bank_related(subject, body):
            _logger.info("Email %s skipped (not bank-related).", message_id)
            return

        self._parse_email_with_rules(
            subject, body, email_from, email_date, message_id
        )

    @staticmethod
    def _extract_body(msg):
        """Return the best text body from a MIME message."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get("Content-Disposition", ""))
                if "attachment" in cdispo:
                    continue
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                decoded = payload.decode(charset, errors="ignore")
                if ctype == "text/html":
                    return decoded  # prefer HTML
                if ctype == "text/plain" and not body:
                    body = decoded
        else:
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(charset, errors="ignore")
        return body

    @staticmethod
    def _html_to_text(html):
        """Naive HTML tag stripper."""
        return re.sub(r"<[^>]+>", "", html or "")

    @staticmethod
    def _is_bank_related(subject, body):
        text = ((subject or "") + " " + re.sub(r"<[^>]+>", "", body or "")).lower()
        return any(kw in text for kw in BANK_KEYWORDS)

    @staticmethod
    def _is_non_transaction_email(subject, body):
        text = ((subject or "") + " " + re.sub(r"<[^>]+>", "", body or "")).lower()
        return any(hint in text for hint in NON_TRANSACTION_HINTS)

    # ── Rule-based parsing ───────────────────────────────────────────
    def _parse_email_with_rules(
        self, subject, body, email_from, email_date, message_id,
        force_update=False,
    ):
        if not message_id:
            message_id = "no-id-%s" % fields.Datetime.now()

        existing = self.search(
            [("email_message_id", "=", message_id)], limit=1
        )
        if existing and not force_update:
            _logger.info("Duplicate email skipped: %s", message_id)
            return

        if self._is_non_transaction_email(subject, body):
            _logger.info("Email %s skipped (non-transactional notification).", message_id)
            return

        parsed = self._extract_transaction_data(subject, body, email_from, email_date)
        if not parsed:
            _logger.info("Email %s skipped (no transaction pattern matched).", message_id)
            return

        currency = (
            self.env["res.currency"].browse(parsed["currency_id"]).exists()
            if parsed.get("currency_id")
            else self._resolve_currency(parsed.get("currency"))
        )
        partner = (
            self.env["res.partner"].browse(parsed["partner_id"]).exists()
            if parsed.get("partner_id")
            else self._resolve_partner(parsed.get("partner_name"))
        )
        journal = (
            self.env["account.journal"].browse(parsed["journal_id"]).exists()
            if parsed.get("journal_id")
            else self._resolve_default_journal()
        )
        account = (
            self.env["account.account"].browse(parsed["account_id"]).exists()
            if parsed.get("account_id")
            else self._resolve_account(parsed.get("suggested_account_name"))
        )

        txn_ref = parsed.get("transaction_ref")

        # Dedup by transaction reference — the single source of truth
        if txn_ref and not force_update:
            dup = self.search(
                [("transaction_ref", "=", txn_ref)], limit=1
            )
            if dup:
                _logger.info(
                    "Duplicate transaction_ref %s skipped (existing: %s).",
                    txn_ref, dup.name,
                )
                return

        vals = {
            "state": "pending",
            "email_subject": subject,
            "email_from": email_from,
            "email_date": email_date,
            "email_body": body,
            "email_message_id": message_id,
            "ai_raw_response": parsed.get("rule_name"),
            "ai_confidence": parsed.get("confidence", 0),
            "ai_notes": parsed.get("notes"),
            "ai_suggested_bank": parsed.get("bank_name"),
            "ai_suggested_partner": parsed.get("partner_name"),
            "ai_suggested_account": parsed.get("suggested_account_name"),
            "transaction_type": parsed.get("transaction_type"),
            "amount": abs(float(parsed.get("amount", 0))),
            "currency_id": currency.id if currency else self.env.company.currency_id.id,
            "transaction_date": parsed.get("transaction_date")
                or fields.Date.context_today(self),
            "transaction_ref": txn_ref,
            "description": parsed.get("description"),
            "card_last4": parsed.get("card_last4"),
            "payment_method": parsed.get("payment_method"),
            "expense_category": parsed.get("expense_category"),
            "bank_journal_id": journal.id if journal else False,
            "partner_id": partner.id if partner else False,
            "account_id": (
                account.id if account
                else self._resolve_expense_account(
                    parsed.get("expense_category"),
                    parsed.get("transaction_type"),
                )
            ),
            "company_id": self.env.company.id,
        }

        if existing:
            existing.write(vals)
            existing.message_post(body=_("Parser re-processed this transaction."))
            record = existing
        else:
            record = self.create(vals)

        record._update_reconciliation_suggestion()
        self._apply_auto_workflow(record)

    def _apply_auto_workflow(self, record):
        threshold = int(self._get_param("bank_monitor.auto_post_threshold", "95"))
        confidence = record.ai_confidence or 0
        if record.state != "pending":
            return
        if not record.bank_journal_id:
            return
        if threshold > 100:
            return
        if confidence < threshold:
            return
        record.state = "confirmed"
        record.message_post(
            body=_(
                "Transaction auto-confirmed because parsing confidence (%s) met the threshold (%s)."
            ) % (confidence, threshold)
        )
        record.message_post(
            body=_("Auto-post is disabled. Transaction remains staged for manual posting.")
        )

    def _extract_transaction_data(self, subject, body, email_from, email_date):
        text_body = self._html_to_text(body)
        searchable = ((subject or "") + "\n" + (text_body or "")).strip()
        if not searchable:
            return {}

        rule = self._match_vendor_rule(searchable, email_from)
        txn_type = self._detect_transaction_type(searchable)
        if rule.get("transaction_type"):
            txn_type = rule["transaction_type"]

        amount = self._extract_amount(searchable)
        if not amount:
            return {}

        currency = self._extract_currency(searchable)
        txn_ref = self._extract_transaction_ref(searchable)
        card_last4 = self._extract_card_last4(searchable)
        description = rule.get("vendor_name") or (subject or "Bank email transaction")

        confidence = 20
        if rule.get("matched"):
            confidence += 35
        if txn_type:
            confidence += 25
        if amount:
            confidence += 20
        if txn_ref:
            confidence += 20

        note_parts = []
        if rule.get("matched"):
            note_parts.append("vendor rule matched")
        if txn_type:
            note_parts.append("transaction type from email text")
        if amount:
            note_parts.append("amount extracted")
        if txn_ref:
            note_parts.append("reference extracted")

        inferred_category = rule.get("expense_category") or self._infer_expense_category(
            searchable,
            txn_type or "debit",
        )

        return {
            "confidence": min(confidence, 100),
            "transaction_type": txn_type or "debit",
            "amount": amount,
            "currency": currency,
            "currency_id": rule.get("currency_id"),
            "transaction_date": fields.Date.to_date(email_date) if email_date else fields.Date.context_today(self),
            "transaction_ref": txn_ref or self._build_fallback_ref(email_date, amount, email_from, txn_type, card_last4),
            "description": description,
            "partner_name": rule.get("vendor_name"),
            "partner_id": rule.get("partner_id"),
            "bank_name": self._guess_bank_name(email_from),
            "card_last4": card_last4,
            "payment_method": rule.get("payment_method") or self._detect_payment_method(searchable),
            "expense_category": inferred_category,
            "suggested_account_name": rule.get("suggested_account_name"),
            "journal_id": rule.get("journal_id"),
            "account_id": rule.get("account_id"),
            "rule_name": rule.get("name"),
            "notes": ", ".join(note_parts) or "rule-based parse",
        }

    def _vendor_rules_from_config(self):
        rules = self._vendor_rules_from_model()
        if rules:
            return rules

        raw = self._get_param("bank_monitor.vendor_rules", "")
        fallback_rules = []
        for line in (raw or "").splitlines():
            clean = (line or "").strip()
            if not clean or clean.startswith("#"):
                continue
            parts = [p.strip() for p in clean.split("|")]
            if len(parts) < 2:
                continue
            fallback_rules.append({
                "name": parts[0],
                "vendor_name": parts[0],
                "pattern": parts[1],
                "transaction_type": parts[2] if len(parts) > 2 and parts[2] in ("credit", "debit") else False,
                "payment_method": parts[3] if len(parts) > 3 and parts[3] else False,
                "expense_category": parts[4] if len(parts) > 4 and parts[4] else False,
                "suggested_account_name": parts[5] if len(parts) > 5 and parts[5] else False,
                "sender_pattern": parts[6] if len(parts) > 6 and parts[6] else False,
            })
        return fallback_rules

    def _vendor_rules_from_model(self):
        rules = []
        records = self.env["bank.vendor.rule"].search(
            [
                ("active", "=", True),
                ("is_learning_draft", "=", False),
                ("company_id", "=", self.env.company.id),
            ],
            order="sequence, id",
        )
        for rec in records:
            rules.append({
                "name": rec.name,
                "vendor_name": rec.partner_id.name if rec.partner_id else rec.name,
                "pattern": rec.pattern,
                "transaction_type": rec.transaction_type or False,
                "payment_method": rec.payment_method or False,
                "expense_category": rec.expense_category or False,
                "suggested_account_name": rec.suggested_account_id.name if rec.suggested_account_id else False,
                "sender_pattern": rec.sender_pattern or False,
                "partner_id": rec.partner_id.id if rec.partner_id else False,
                "journal_id": rec.bank_journal_id.id if rec.bank_journal_id else False,
                "account_id": rec.suggested_account_id.id if rec.suggested_account_id else False,
                "currency_id": rec.currency_id.id if rec.currency_id else False,
            })
        return rules

    def _match_vendor_rule(self, text, email_from):
        for rule in self._vendor_rules_from_config():
            try:
                if re.search(rule["pattern"], text, flags=re.IGNORECASE):
                    sender_pattern = rule.get("sender_pattern")
                    if sender_pattern and not re.search(sender_pattern, email_from or "", flags=re.IGNORECASE):
                        continue
                    matched = dict(rule)
                    matched["matched"] = True
                    return matched
            except re.error:
                _logger.warning("Invalid vendor regex rule skipped: %s", rule.get("name"))
        return {"matched": False}

    @staticmethod
    def _detect_transaction_type(text):
        lower = (text or "").lower()
        credit_hits = sum(1 for kw in CREDIT_KEYWORDS if kw in lower)
        debit_hits = sum(1 for kw in DEBIT_KEYWORDS if kw in lower)
        if credit_hits > debit_hits and credit_hits > 0:
            return "credit"
        if debit_hits > credit_hits and debit_hits > 0:
            return "debit"
        return False

    @staticmethod
    def _extract_amount(text):
        haystack = text or ""
        prioritized_patterns = [
            r"(?:amount|amt|for|of)\s*(?:rs\.?|inr|usd|eur|gbp|sgd|myr|php|aud|cad|jpy|thb)?\s*[:=\-]?\s*(?:₹|\$)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
            r"(?:₹|\$)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
            r"\b(?:inr|usd|eur|gbp|sgd|myr|php|aud|cad|jpy|thb)\b\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        ]
        candidates = []
        for pattern in prioritized_patterns:
            candidates.extend(re.findall(pattern, haystack, flags=re.IGNORECASE))
        if not candidates:
            candidates.extend(re.findall(r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)", haystack))

        values = []
        for item in candidates:
            cleaned = item.replace(",", "").strip()
            try:
                val = float(cleaned)
            except ValueError:
                continue
            if 0 < val < 100000000:
                values.append(val)
        if not values:
            return 0.0
        return max(values)

    @staticmethod
    def _extract_currency(text):
        upper = (text or "").upper()
        for code in ("INR", "USD", "EUR", "GBP", "SGD", "MYR", "PHP", "AUD", "CAD", "JPY", "THB"):
            if code in upper:
                return code
        if "₹" in upper:
            return "INR"
        if "$" in upper:
            return "USD"
        return False

    @staticmethod
    def _extract_transaction_ref(text):
        for pattern in REF_PATTERNS:
            found = re.search(pattern, text or "", flags=re.IGNORECASE)
            if found:
                return found.group(1)
        return False

    @staticmethod
    def _extract_card_last4(text):
        found = re.search(r"(?:card|a/c|account)\D{0,8}(?:xx|x{2,}|\*{2,}|ending|last)?\D*([0-9]{4})", text or "", flags=re.IGNORECASE)
        return found.group(1) if found else False

    @staticmethod
    def _detect_payment_method(text):
        lower = (text or "").lower()
        if "credit card" in lower:
            return "credit_card"
        if "debit card" in lower or "pos" in lower:
            return "debit_card"
        if "cheque" in lower or "check" in lower:
            return "cheque"
        if "cash deposit" in lower:
            return "cash_deposit"
        if "transfer" in lower or "neft" in lower or "rtgs" in lower or "swift" in lower:
            return "bank_transfer"
        return "other"

    @staticmethod
    def _guess_bank_name(email_from):
        domain = (email_from or "").split("@")[-1].lower()
        return domain.split(".")[0].upper() if domain else False

    @staticmethod
    def _build_fallback_ref(email_date, amount, email_from, txn_type=None, card_last4=None):
        date_part = fields.Date.today()
        if email_date:
            try:
                date_part = fields.Date.to_date(email_date)
            except Exception:
                pass
        bank = (email_from or "mail").split("@")[-1].split(".")[0].upper() or "BANK"
        suffix = (card_last4 or "XXXX")
        kind = (txn_type or "txn").upper()
        return "%s-%s-%0.2f-%s-%s" % (
            bank,
            date_part.strftime("%Y%m%d"),
            amount or 0.0,
            kind,
            suffix,
        )

    @staticmethod
    def _infer_expense_category(text, txn_type):
        lower = (text or "").lower()
        if txn_type == "credit":
            credit_map = {
                "salary": "Salary Income",
                "refund": "Refund",
                "interest": "Interest Income",
                "commission": "Commission Income",
                "invoice": "Sales Income",
                "payment received": "Sales Income",
            }
            for key, category in credit_map.items():
                if key in lower:
                    return category
            return "Income"

        expense_map = {
            "meal": "Meals & Dining",
            "restaurant": "Meals & Dining",
            "cafe": "Meals & Dining",
            "fuel": "Fuel",
            "petrol": "Fuel",
            "diesel": "Fuel",
            "uber": "Travel",
            "taxi": "Travel",
            "airline": "Travel",
            "hotel": "Travel",
            "rent": "Rent",
            "lease": "Rent",
            "electric": "Utilities",
            "water": "Utilities",
            "internet": "Telecom",
            "mobile": "Telecom",
            "phone": "Telecom",
            "insurance": "Insurance",
            "hospital": "Medical",
            "pharmacy": "Medical",
            "clinic": "Medical",
            "office": "Office Supplies",
            "supplies": "Office Supplies",
            "software": "Subscriptions",
            "subscription": "Subscriptions",
            "netflix": "Subscriptions",
            "spotify": "Subscriptions",
            "tax": "Taxes",
            "gst": "Taxes",
            "charge": "Bank Charges",
            "fee": "Bank Charges",
            "emi": "Loan Repayment",
            "loan": "Loan Repayment",
            "payroll": "Payroll",
            "salary": "Payroll",
        }
        for key, category in expense_map.items():
            if key in lower:
                return category
        return "Other Expense"

    def _resolve_default_journal(self):
        journal_param = self._get_param("bank_monitor.default_bank_journal_id")
        if journal_param:
            try:
                journal = self.env["account.journal"].browse(int(journal_param)).exists()
                if journal and journal.type == "bank" and journal.company_id == self.env.company:
                    return journal
            except Exception:
                _logger.warning("Invalid configured default bank journal id: %s", journal_param)
        return self.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )

    # ── Resolution helpers ───────────────────────────────────────────
    def _resolve_partner(self, name):
        if not name:
            return self.env["res.partner"]
        return self.env["res.partner"].search(
            [("name", "ilike", name)], limit=1
        )

    def _resolve_account(self, name):
        if not name:
            return self.env["account.account"]
        return self.env["account.account"].search(
            [("name", "ilike", name)], limit=1
        )

    def _resolve_expense_account(self, category, txn_type):
        """Map parsed expense_category to an appropriate account.account ID."""
        if not category:
            return False
        Account = self.env["account.account"]
        # For credits (income), look for income accounts
        if txn_type == "credit":
            acct = Account.search(
                [("account_type", "in", ["income", "income_other"]),
                 ("name", "ilike", category)], limit=1,
            )
            if not acct:
                acct = Account.search(
                    [("account_type", "in", ["income", "income_other"])],
                    limit=1,
                )
            return acct.id if acct else False
        # For debits (expenses), map category keywords to expense accounts
        category_lower = (category or "").lower()
        keyword_map = {
            "meal": "meal", "dining": "meal", "food": "meal",
            "fuel": "fuel", "gas": "fuel", "petrol": "fuel",
            "travel": "travel", "transport": "travel", "taxi": "travel",
            "uber": "travel", "airline": "travel",
            "telecom": "telecom", "phone": "telecom", "internet": "telecom",
            "utility": "utilit", "electric": "utilit", "water": "utilit",
            "rent": "rent", "lease": "rent",
            "insurance": "insurance",
            "medical": "medical", "health": "medical",
            "salary": "salary", "wage": "salary",
            "supplies": "supplies", "office": "supplies",
        }
        search_term = None
        for kw, term in keyword_map.items():
            if kw in category_lower:
                search_term = term
                break
        if search_term:
            acct = Account.search(
                [("account_type", "in", ["expense", "expense_direct_cost"]),
                 ("name", "ilike", search_term)], limit=1,
            )
            if acct:
                return acct.id
        # Fallback: first general expense account
        acct = Account.search(
            [("account_type", "in", ["expense", "expense_direct_cost"])],
            limit=1,
        )
        return acct.id if acct else False

    def _resolve_currency(self, iso_code):
        if not iso_code:
            return self.env.company.currency_id
        currency = self.env["res.currency"].with_context(active_test=False).search(
            [("name", "=", iso_code.upper())], limit=1
        )
        if currency and not currency.active:
            currency.active = True
            _logger.info("Activated currency %s for bank transactions.", iso_code)
        return currency or self.env.company.currency_id

    def _update_reconciliation_suggestion(self):
        for rec in self:
            suggestion = rec._find_best_reconciliation_candidate()
            if not suggestion:
                rec.write({
                    "parser_suggested_move_id": False,
                    "parser_suggested_move_score": 0,
                    "parser_suggested_move_reason": False,
                    "parser_suggested_move_remark": "No reliable match found. Manual reconciliation required.",
                    "parser_suggested_move_state": "none",
                })
                continue
            rec.write({
                "parser_suggested_move_id": suggestion["move"].id,
                "parser_suggested_move_score": suggestion["score"],
                "parser_suggested_move_reason": suggestion["reason"],
                "parser_suggested_move_remark": self._build_reconciliation_remark(suggestion["score"]),
                "parser_suggested_move_state": "suggested",
            })

    def _find_best_reconciliation_candidate(self):
        self.ensure_one()
        if not self.amount:
            return {}

        domain = [
            ("state", "=", "posted"),
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", ("out_invoice", "out_refund", "in_invoice", "in_refund")),
            ("amount_residual", "!=", 0),
        ]
        if self.partner_id:
            domain.append(("partner_id", "=", self.partner_id.id))

        candidates = self.env["account.move"].search(domain, limit=30)
        if not candidates:
            return {}

        txn_amount = abs(self.amount)
        txn_ref = (self.transaction_ref or "").lower()
        desc = (self.description or "").lower()
        best = {"score": -1, "move": False, "reason": ""}

        for move in candidates:
            score = 0
            reason = []
            residual = abs(move.amount_residual)
            diff = abs(residual - txn_amount)
            if diff <= 0.01:
                score += 70
                reason.append("amount exact")
            elif diff <= 2:
                score += 45
                reason.append("amount close")
            elif diff <= 10:
                score += 20
                reason.append("amount approximate")

            move_ref_text = " ".join(
                part for part in [move.name, move.ref, move.payment_reference] if part
            ).lower()
            if txn_ref and txn_ref in move_ref_text:
                score += 25
                reason.append("reference match")
            if desc and desc[:20] and desc[:20] in move_ref_text:
                score += 10
                reason.append("description overlap")
            if self.partner_id and move.partner_id == self.partner_id:
                score += 20
                reason.append("partner match")

            if score > best["score"]:
                best = {
                    "score": score,
                    "move": move,
                    "reason": ", ".join(reason) or "heuristic match",
                }

        return best if best["move"] and best["score"] > 0 else {}

    @staticmethod
    def _build_reconciliation_remark(score):
        if score >= 90:
            return "Excellent match confidence. Safe to accept after quick review."
        if score >= 70:
            return "High confidence match. Verify reference and amount before acceptance."
        if score >= 50:
            return "Medium confidence match. Manual verification is recommended."
        return "Low confidence match. Do not accept without full manual reconciliation."

    def _learn_rule_draft_from_transaction(self, force=False):
        for rec in self:
            if not rec.email_from or not (rec.description or rec.email_subject):
                continue
            if rec.learned_rule_id and not force:
                continue

            pattern = rec._build_learning_pattern()
            if not pattern:
                continue

            sender_domain = (rec.email_from or "").split("@")[-1].lower()
            sender_pattern = r".*@%s$" % re.escape(sender_domain) if sender_domain else False

            existing_rule = self.env["bank.vendor.rule"].search([
                ("company_id", "=", rec.company_id.id),
                ("pattern", "=", pattern),
                ("sender_pattern", "=", sender_pattern),
            ], limit=1)
            if existing_rule:
                rec.learned_rule_id = existing_rule.id
                continue

            vendor_name = rec.partner_id.name or rec.description or rec.email_subject or "Learned Vendor"
            rule_vals = {
                "name": "LEARNED - %s" % vendor_name[:60],
                "active": False,
                "is_learning_draft": True,
                "sequence": 200,
                "company_id": rec.company_id.id,
                "pattern": pattern,
                "sender_pattern": sender_pattern,
                "transaction_type": rec.transaction_type,
                "payment_method": rec.payment_method,
                "expense_category": rec.expense_category,
                "partner_id": rec.partner_id.id or False,
                "bank_journal_id": rec.bank_journal_id.id or False,
                "suggested_account_id": rec.account_id.id or False,
                "currency_id": rec.currency_id.id or False,
                "source_transaction_id": rec.id,
                "learning_confidence": rec.ai_confidence or 0,
                "notes": "Auto-drafted from transaction %s. Review and activate if valid." % rec.name,
            }
            created_rule = self.env["bank.vendor.rule"].create(rule_vals)
            rec.learned_rule_id = created_rule.id
            rec.message_post(body=_("Learning rule draft created: %s") % created_rule.name)

    def _build_learning_pattern(self):
        self.ensure_one()
        base_text = (self.description or self.email_subject or "").lower()
        tokens = re.findall(r"[a-z0-9]{3,}", base_text)
        noise = {
            "bank", "credit", "debit", "transaction", "payment", "alert", "account",
            "card", "from", "with", "for", "your", "you", "has", "was", "the",
        }
        tokens = [t for t in tokens if t not in noise]
        if not tokens:
            return False
        unique_tokens = []
        for token in tokens:
            if token not in unique_tokens:
                unique_tokens.append(token)
            if len(unique_tokens) == 3:
                break
        escaped = [re.escape(t) for t in unique_tokens]
        return r".*%s.*" % r".*".join(escaped)

    @api.model
    def _get_param(self, key, default=None):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        return value or default

    @staticmethod
    def _safe_int(value, default=0, min_value=None, max_value=None):
        try:
            number = int(value)
        except Exception:
            number = default
        if min_value is not None and number < min_value:
            number = min_value
        if max_value is not None and number > max_value:
            number = max_value
        return number
