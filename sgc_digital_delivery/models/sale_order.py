# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    digital_delivery_state = fields.Selection(
        selection=[
            ('none',    'No Digital Products'),
            ('pending', 'Pending Delivery'),
            ('sent',    'Files Sent'),
            ('partial', 'Partially Sent'),
            ('error',   'Delivery Error'),
        ],
        string='Digital Delivery',
        default='none',
        readonly=True,
        copy=False,
        tracking=True,
        help='Tracks whether download links have been emailed to the buyer.',
    )
    digital_delivery_date = fields.Datetime(
        string='Delivery Sent On',
        readonly=True,
        copy=False,
    )

    # ── Hook: fire delivery on confirmation ──────────────────────────────────

    def action_confirm(self):
        result = super().action_confirm()
        for order in self:
            digital_lines = order._get_digital_lines()
            if digital_lines:
                order.digital_delivery_state = 'pending'
                # Only auto-deliver for ecommerce orders where payment is
                # already confirmed (transaction in done/authorized state).
                # B2B / backend orders keep state='pending' so the sales
                # manager can use the manual "Resend Digital Files" button
                # once payment is confirmed.
                if order._digital_payment_confirmed():
                    order._send_digital_products()
        return result

    def _digital_payment_confirmed(self):
        """Return True when at least one linked payment transaction is done.

        For website_sale + any payment provider the transaction is marked
        'done' before action_confirm() is called, so ecommerce buyers get
        their files immediately.  Manual / invoice-later orders return False.
        """
        self.ensure_one()
        return self.env['payment.transaction'].sudo().search_count([
            ('sale_order_ids', 'in', self.id),
            ('state', 'in', ('done', 'authorized')),
        ]) > 0

    # ── Manual resend (sale managers only — enforced in view via groups) ─────

    def action_resend_digital_products(self):
        self.ensure_one()
        if not self._get_digital_lines():
            raise UserError(_('This order has no digital products to deliver.'))
        self._send_digital_products(force=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Digital Files Resent'),
                'message': _('Download links have been resent to %s.') % self.partner_id.email,
                'type': 'success',
                'sticky': False,
            },
        }

    # ── Core delivery logic ───────────────────────────────────────────────────

    def _get_digital_lines(self):
        """Return order lines that have a digital file attached."""
        return self.order_line.filtered(
            lambda l: l.product_id.is_digital
            and l.product_id.product_tmpl_id.digital_file
        )

    def _send_digital_products(self, force=False):
        """Email a secure download link (+ file attachment) to the buyer.

        Uses the standard mail.template.send_mail() API so that Odoo's mail
        queue handles retries and logging.  Attachment IDs are passed via
        email_values so the original ir.attachment on the product is NOT
        duplicated or modified.

        Download count is NOT incremented here — the controller increments it
        only when the buyer actually clicks the download link.
        """
        template = self.env.ref(
            'sgc_digital_delivery.mail_template_digital_delivery',
            raise_if_not_found=False,
        )
        if not template:
            _logger.error(
                'SGC Digital Delivery: mail template '
                'sgc_digital_delivery.mail_template_digital_delivery not found.'
            )
            return

        for order in self:
            # Guard: skip already-sent unless forced
            if not force and order.digital_delivery_state == 'sent':
                _logger.info(
                    'SGC Digital: order %s already delivered, skipping.', order.name
                )
                continue

            # Ensure the portal access token exists BEFORE building the email
            # URL.  For orders created in the backend the token is never
            # auto-generated, so access_token would be False/None and every
            # download link in the email would be broken.
            order.sudo()._portal_ensure_token()

            # Guard: must have a buyer email
            if not order.partner_id.email:
                _logger.warning(
                    'SGC Digital: order %s partner has no email — cannot deliver.',
                    order.name,
                )
                order.write({'digital_delivery_state': 'error'})
                continue

            digital_lines = order._get_digital_lines()
            if not digital_lines:
                continue

            try:
                # Wrap risky operations in a savepoint so that a DB error
                # during send does not break the parent transaction cursor,
                # allowing the error state write to succeed.
                with self.env.cr.savepoint():
                    # Verify all digital products have their files present;
                    # log warnings for missing ones so ops can investigate.
                    missing = []
                    for line in digital_lines:
                        tmpl = line.product_id.product_tmpl_id
                        if not tmpl.digital_file:
                            missing.append(tmpl.name)
                            _logger.warning(
                                'SGC Digital: no file found for product "%s"',
                                tmpl.name,
                            )

                    if len(missing) == len(digital_lines):
                        # Every product is missing its file — nothing to deliver
                        _logger.error(
                            'SGC Digital: order %s — no files found at all, aborting.',
                            order.name,
                        )
                        order.write({'digital_delivery_state': 'error'})
                        continue

                    # ── Send via standard Odoo template API ───────────────────
                    # Send ONLY the secure download LINK — do NOT attach the
                    # binary to the email.  Email providers (Mailjet, etc.)
                    # impose strict size limits (~10 MB) and attaching large
                    # ZIPs causes "error" delivery state.  The mail template
                    # already contains a signed /shop/digital/download URL.
                    template.with_context(
                        lang=order.partner_id.lang,
                    ).send_mail(
                        order.id,
                        force_send=True,
                        raise_exception=True,
                    )

                state = 'partial' if missing else 'sent'
                order.write({
                    'digital_delivery_state': state,
                    'digital_delivery_date': fields.Datetime.now(),
                })
                _logger.info(
                    'SGC Digital: sent download link(s) to %s for order %s (state=%s)',
                    order.partner_id.email, order.name, state,
                )

            except Exception:
                _logger.exception(
                    'SGC Digital: delivery failed for order %s', order.name
                )
                order.write({'digital_delivery_state': 'error'})

