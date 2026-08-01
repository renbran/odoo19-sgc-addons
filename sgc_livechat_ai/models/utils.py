# -*- coding: utf-8 -*-
import re
from markupsafe import Markup
from odoo.tools import html2plaintext


def html_to_text(body):
    """Convert a (possibly HTML) message body to clean plain text for the LLM."""
    if not body:
        return ""
    text = html2plaintext(str(body))
    text = re.sub(r"\s+\n", "\n", text)
    return text.strip()


def as_markup(html_body):
    """Return a safe Markup for posting an assistant reply into a channel."""
    if html_body is None:
        return Markup("")
    if isinstance(html_body, Markup):
        return html_body
    return Markup(html_body)
