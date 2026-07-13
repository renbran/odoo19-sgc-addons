# -*- coding: utf-8 -*-
import logging
import re

from odoo import api, models

_logger = logging.getLogger(__name__)


def _normalize_email(value):
    """Lowercase + strip. Returns the original value if it is falsy."""
    if not value or not isinstance(value, str):
        return value
    cleaned = value.strip()
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", cleaned)
    return cleaned.lower()


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "email" in vals and vals["email"]:
                original = vals["email"]
                normalized = _normalize_email(original)
                if normalized != original:
                    _logger.info(
                        "sgc_user_hygiene: lowercased partner email on create: %r -> %r",
                        original, normalized,
                    )
                    vals["email"] = normalized
        return super().create(vals_list)

    def write(self, vals):
        if "email" in vals and vals["email"]:
            original = vals["email"]
            normalized = _normalize_email(original)
            if normalized != original:
                _logger.info(
                    "sgc_user_hygiene: lowercased partner email on write for partners %s: %r -> %r",
                    self.ids, original, normalized,
                )
                vals["email"] = normalized
        return super().write(vals)
