# -*- coding: utf-8 -*-
"""Gatekeeper document validation.

Implements the ``document.validate`` task for the ``agent-00-gatekeeper``
role. The gatekeeper runs **before** a document is booked into the client
database and checks:

* **Completeness** — required columns are present and non-empty.
* **Numeric integrity** — amounts parse as numbers, dates parse as dates.
* **Totals consistency** — line items sum to the stated total (where
  applicable).
* **Duplicate detection** — same document number within the same workspace.
* **TRN presence** — UAE-registered parties must have a TRN when the client
  requires it.

Documents that pass validation are marked ``accepted`` and queued for
booking. Documents that fail are marked ``rejected`` with a structured
rejection reason, and the customer is notified via the portal.
"""
import logging
from collections import Counter

from odoo import _, api, fields, models

from .accounting_bucket import (
    BUCKETS_BY_CODE,
    DATE_COLUMNS,
    NUMERIC_COLUMNS,
)

_logger = logging.getLogger(__name__)

TASK_GATEKEEPER = "document.validate"

# The column lists are derived from the bucket definitions rather than typed
# out here: the customer downloads the sample CSV built from the very same
# definition, so a hardcoded list would drift from the format guide and start
# rejecting files that match it.

# Buckets whose rows are validated as documents (the others are free-form or
# need a review before they become entries).
VALIDATED_BUCKETS = (
    "customer_invoices",
    "vendor_bills",
    "credit_notes",
    "payments",
    "bank_statements",
    "payroll_journals",
    "expense_receipts",
)


def _bucket_columns(doc_type):
    """Return the required columns of ``doc_type`` as a list."""
    spec = BUCKETS_BY_CODE.get(doc_type) or {}
    return list(spec.get("required") or [])


def _numeric_columns(doc_type):
    """Return the columns of ``doc_type`` that hold numbers."""
    return list(NUMERIC_COLUMNS.get(doc_type) or [])


def _date_columns(doc_type):
    """Return the columns of ``doc_type`` that hold dates."""
    return list(DATE_COLUMNS.get(doc_type) or [])


class SgcAccountingGatekeeperCheck(models.Model):
    """A gatekeeper validation run for an upload."""

    _name = "sgc.accounting.gatekeeper.check"
    _description = "Gatekeeper Validation Check"
    _order = "create_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    upload_id = fields.Many2one(
        "sgc.accounting.upload", required=True, ondelete="cascade", index=True,
    )
    client_id = fields.Many2one(related="upload_id.client_id", store=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("passed", "Passed"),
            ("rejected", "Rejected"),
            ("warning", "Passed with warnings"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    checks_run = fields.Integer(readonly=True)
    checks_passed = fields.Integer(readonly=True)
    checks_failed = fields.Integer(readonly=True)
    warnings = fields.Integer(readonly=True)
    findings = fields.Json(readonly=True)
    rejection_reason = fields.Text(readonly=True)
    validated_at = fields.Datetime(readonly=True)

    @api.depends("upload_id.name", "upload_id.doc_type")
    def _compute_name(self):
        for check in self:
            check.name = "%s - %s" % (
                check.upload_id.doc_type or _("Unknown"),
                check.upload_id.name or str(check.upload_id.id),
            )

    def action_run_checks(self):
        for check in self:
            check._validate_upload()

    def _validate_upload(self):
        self.ensure_one()
        upload = self.upload_id
        findings = {"doc_type": upload.doc_type, "file_name": upload.filename, "checks": []}
        passed = failed = warnings = 0

        def _record(name, status, detail=None):
            nonlocal passed, failed, warnings
            entry = {"check": name, "status": status}
            if detail:
                entry["detail"] = detail
            findings["checks"].append(entry)
            if status == "pass":
                passed += 1
            elif status == "fail":
                failed += 1
            elif status == "warning":
                warnings += 1

        # 1. Parse the source file using the same reader as the booking cron.
        import base64
        try:
            from .accounting_bucket import MAX_UPLOAD_ROWS, find_column, read_rows
            raw = base64.b64decode(upload.file) if upload.file else b""
            source = read_rows(upload.doc_type, upload.filename, raw, limit=MAX_UPLOAD_ROWS)
            rows = source.get("rows", []) if source else []
            headers = source.get("headers", []) if source else []
        except Exception as exc:
            _record("file_parse", "fail", str(exc)[:500])
            self._finish("rejected", findings, 1, 0, 1, 0,
                         _("File could not be parsed: %s") % str(exc)[:500])
            upload._finish("failed", _("Gatekeeper rejected: file unreadable."))
            return False

        if not rows:
            _record("file_empty", "fail", "No data rows found.")
            self._finish("rejected", findings, 1, 0, 1, 0, _("File contains no data rows."))
            upload._finish("failed", _("Gatekeeper: empty file."))
            return False
        _record("file_parse", "pass", "%d rows" % len(rows))

        # 2. Required columns. Headers are canonicalised by read_rows, so a
        # logical label is resolved through the same alias chain the booking
        # code uses (find_column) instead of a plain string compare.
        required = _bucket_columns(upload.doc_type)
        resolved = {
            label: find_column(headers, label) for label in required
        }
        missing_cols = [label for label, key in resolved.items() if not key]
        if missing_cols:
            _record("required_columns", "fail",
                    _("Missing columns: %s") % ", ".join(missing_cols))
        else:
            _record("required_columns", "pass")

        def _value(row, label):
            key = resolved.get(label) or find_column(headers, label)
            return row.get(key) if key else None

        # 3. Empty required cells.
        empty_cells = 0
        for row in rows:
            for label in required:
                if resolved.get(label):
                    val = _value(row, label)
                    if val is None or str(val).strip() == "":
                        empty_cells += 1
        if empty_cells:
            _record("required_values", "fail", _("%d empty required cell(s).") % empty_cells)
        else:
            _record("required_values", "pass")

        # 4. Numeric columns.
        numeric_cols = _numeric_columns(upload.doc_type)
        bad_numbers = 0
        for row in rows:
            for label in numeric_cols:
                if find_column(headers, label):
                    val = _value(row, label)
                    if val is None or str(val).strip() == "":
                        continue
                    try:
                        float(str(val).replace(",", ""))
                    except (ValueError, TypeError):
                        bad_numbers += 1
        if bad_numbers:
            _record("numeric_values", "fail",
                    _("%d cell(s) could not be parsed as numbers.") % bad_numbers)
        else:
            _record("numeric_values", "pass")

        # 5. Date columns.
        date_cols = _date_columns(upload.doc_type)
        bad_dates = 0
        for row in rows:
            for label in date_cols:
                if find_column(headers, label):
                    val = _value(row, label)
                    if val is None or str(val).strip() == "":
                        continue
                    if not self._try_parse_date(str(val)):
                        bad_dates += 1
        if bad_dates:
            _record("date_values", "fail",
                    _("%d cell(s) could not be parsed as dates.") % bad_dates)
        else:
            _record("date_values", "pass")

        # 6. Duplicate document numbers within the file.
        number_col = None
        for label in ("Invoice Number", "Bill Number", "Credit Note Number",
                      "Reference", "Receipt Number"):
            number_col = find_column(headers, label)
            if number_col:
                break
        if number_col:
            numbers = []
            for row in rows:
                val = row.get(number_col)
                if val and str(val).strip():
                    numbers.append(str(val).strip())
            dupes = {k: v for k, v in Counter(numbers).items() if v > 1}
            if dupes:
                _record("duplicate_numbers", "warning",
                        _("Duplicate document numbers: %s") % ", ".join(list(dupes.keys())[:5]))
            else:
                _record("duplicate_numbers", "pass")

        # 7. Totals consistency.
        if upload.doc_type in ("customer_invoices", "vendor_bills", "credit_notes"):
            amount_col = find_column(headers, "Amount")
            total_col = find_column(headers, "Total")
            tax_col = find_column(headers, "Tax Amount")
            if amount_col and total_col:
                mismatches = 0
                for row in rows:
                    try:
                        amount = float(str(row.get(amount_col, "0")).replace(",", "") or 0)
                        total = float(str(row.get(total_col, "0")).replace(",", "") or 0)
                        tax = 0.0
                        if tax_col:
                            tax = float(str(row.get(tax_col, "0")).replace(",", "") or 0)
                        if abs((amount + tax) - total) > 0.01:
                            mismatches += 1
                    except (ValueError, TypeError):
                        pass
                if mismatches:
                    _record("totals_consistency", "warning",
                            _("%d row(s) where Amount + Tax != Total.") % mismatches)
                else:
                    _record("totals_consistency", "pass")

        # 8. TRN presence.
        if upload.client_id.require_trn and upload.doc_type in (
            "customer_invoices", "vendor_bills", "credit_notes",
        ):
            trn_col = None
            for label in ("TRN", "Tax Registration Number", "VAT Number"):
                trn_col = find_column(headers, label)
                if trn_col:
                    break
            if trn_col is None:
                _record("trn_presence", "warning",
                        _("TRN column not found but client requires TRN."))
            else:
                missing_trn = sum(
                    1 for row in rows
                    if not str(row.get(trn_col, "")).strip()
                )
                if missing_trn:
                    _record("trn_presence", "warning",
                            _("%d row(s) missing TRN.") % missing_trn)
                else:
                    _record("trn_presence", "pass")

        total = passed + failed + warnings
        state = "rejected" if failed > 0 else ("warning" if warnings > 0 else "passed")
        reason = "; ".join(
            c.get("detail", "") for c in findings["checks"] if c["status"] == "fail"
        ) if failed else False
        self._finish(state, findings, total, passed, failed, warnings, reason)
        if state == "rejected":
            upload._finish("failed", _("Gatekeeper: %s") % reason)
            upload.client_id.message_post(body=_(
                "Document %(name)s was rejected by the gatekeeper: %(reason)s",
                name=upload.filename, reason=reason,
            ))
        else:
            # Validated: hand it to the booking cron. An upload already parked
            # in "waiting" (no client database linked yet) stays parked so the
            # booking cron does not retry an unreachable client every cycle.
            if upload.booking_state in (False, "failed"):
                upload.sudo().write({"booking_state": "pending"})
            upload._log(
                "gatekeeper",
                _("Gatekeeper validation passed: %(passed)s check(s) passed, "
                  "%(warnings)s warning(s).") % {
                    "passed": passed,
                    "warnings": warnings,
                },
            )
        return True

    def _finish(self, state, findings, total, passed, failed, warnings, reason):
        self.write({
            "state": state,
            "checks_run": total,
            "checks_passed": passed,
            "checks_failed": failed,
            "warnings": warnings,
            "findings": findings,
            "rejection_reason": reason,
            "validated_at": fields.Datetime.now(),
        })

    @staticmethod
    def _try_parse_date(value):
        from datetime import datetime
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d",
                     "%d.%m.%Y", "%b %d, %Y", "%d %b %Y"):
            try:
                datetime.strptime(str(value).strip(), fmt)
                return True
            except ValueError:
                continue
        return False

    @api.model
    def _cron_validate_pending_uploads(self):
        """Run gatekeeper checks on uploads that haven't been validated yet.

        Runs before the booking cron picks the file up: a rejected upload is
        moved to ``failed`` so ``_cron_book_pending`` never books it. Uploads
        already parked in ``waiting`` (no client database linked yet) are
        validated too, so the check is never skipped for them.
        """
        Upload = self.env["sgc.accounting.upload"]
        uploads = Upload.search([
            ("booking_state", "in", ("pending", "waiting")),
            ("gatekeeper_check_id", "=", False),
        ], limit=50, order="create_date, id")
        for upload in uploads:
            check = self.create({"upload_id": upload.id})
            upload.sudo().write({"gatekeeper_check_id": check.id})
            try:
                check._validate_upload()
            except Exception:
                _logger.exception(
                    "Gatekeeper check failed for upload %s", upload.id
                )
        return True
