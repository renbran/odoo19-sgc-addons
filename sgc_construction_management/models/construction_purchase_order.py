# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConstructionPurchaseOrder(models.Model):
    """Local Purchase Order (LPO) with an RFQ stage.

    Workflow: RFQ -> RFQ Sent -> Purchase Order (LPO) -> Received -> Bill Created
    -> Posted -> Paid. A vendor bill (account.move, in_invoice) is created in
    Accounting with the project's analytic distribution, mirroring the proven
    construction.expense / construction.subcontract billing pattern. Cancelling
    the bill is reversible via "Reopen Bill".
    """
    _name = 'construction.purchase.order'
    _description = 'Construction Purchase Order / LPO'
    _inherit = ['mail.thread']
    _order = 'order_date desc, id desc'

    company_id = fields.Many2one('res.company', index=True, string='Company', required=True,
                                 default=lambda self: self.env.company)
    name = fields.Char(string='Title', required=True)
    ref = fields.Char(string='LPO No.', readonly=True, default='New', copy=False)
    project_id = fields.Many2one('construction.project', index=True, required=True)
    wbs_id = fields.Many2one('construction.wbs', index=True, domain="[('project_id','=',project_id)]")
    requisition_id = fields.Many2one('construction.material.requisition', index=True,
                                     string='Source Requisition', copy=False)
    vendor_id = fields.Many2one('res.partner', index=True, string='Vendor',
                                help="The awarded supplier. Optional at RFQ stage; required to confirm the LPO.")
    order_date = fields.Date(default=lambda self: fields.Date.context_today(self))
    expected_date = fields.Date(string='Expected Delivery')
    payment_terms = fields.Char()
    delivery_address = fields.Char()
    currency_id = fields.Many2one('res.currency', index=True, related='project_id.currency_id', store=True)
    notes = fields.Text()

    state = fields.Selection([
        ('rfq', 'Request for Quotation'),
        ('sent', 'RFQ Sent'),
        ('confirmed', 'Purchase Order'),
        ('received', 'Received'),
        ('bill_created', 'Bill Created'),
        ('posted', 'Posted'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], default='rfq', tracking=True, compute='_compute_state', store=True, readonly=False)

    line_ids = fields.One2many('construction.purchase.order.line', 'order_id', copy=True)
    move_id = fields.Many2one('account.move', index=True, string='Vendor Bill', readonly=True, copy=False)
    move_state = fields.Selection(related='move_id.state', string='Bill Status')
    payment_state = fields.Selection(related='move_id.payment_state', string='Payment Status')

    amount_untaxed = fields.Monetary(compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_tax = fields.Monetary(compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_total = fields.Monetary(compute='_compute_amounts', store=True, currency_field='currency_id')

    @api.depends('line_ids.price_subtotal', 'line_ids.price_tax', 'line_ids.price_total')
    def _compute_amounts(self):
        for rec in self:
            rec.amount_untaxed = sum(rec.line_ids.mapped('price_subtotal'))
            rec.amount_tax = sum(rec.line_ids.mapped('price_tax'))
            rec.amount_total = sum(rec.line_ids.mapped('price_total'))

    @api.depends('move_id', 'move_id.state', 'move_id.payment_state')
    def _compute_state(self):
        for rec in self:
            move = rec.move_id
            if move and move.state != 'cancel':
                if move.state == 'posted':
                    rec.state = 'paid' if move.payment_state in ('paid', 'in_payment') else 'posted'
                else:
                    rec.state = 'bill_created'
            elif rec.state in ('bill_created', 'posted', 'paid'):
                # Linked bill cancelled/unlinked: revert to the Purchase Order so
                # the bill can be recreated.
                rec.state = 'confirmed'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ref', 'New') == 'New':
                vals['ref'] = self.env['ir.sequence'].next_by_code('construction.purchase.order') or 'New'
        return super().create(vals_list)

    # ---- Workflow ---------------------------------------------------------
    def action_send_rfq(self):
        self.write({'state': 'sent'})

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("Add at least one line before confirming the Purchase Order."))
            if not rec.vendor_id:
                raise ValidationError(_("Select a Vendor before confirming the Purchase Order (LPO)."))
        self.write({'state': 'confirmed'})

    def action_receive(self):
        self.write({'state': 'received'})

    def action_create_bill(self):
        self.ensure_one()
        if self.move_id and self.move_id.state != 'cancel':
            return self.action_view_bill()
        if self.state != 'received':
            raise ValidationError(_("Items must be received before a bill can be created."))
        if not self.vendor_id:
            raise ValidationError(_("Select a Vendor before creating the bill."))
        if not self.line_ids:
            raise ValidationError(_("Cannot create a bill for an empty Purchase Order."))

        analytic_distribution = (
            {str(self.project_id.analytic_account_id.id): 100}
            if self.project_id.analytic_account_id else {}
        )
        invoice_lines = []
        for line in self.line_ids:
            line_vals = {
                'name': line.name or (line.product_id.display_name if line.product_id else self.name),
                'product_id': line.product_id.id or False,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
                'analytic_distribution': analytic_distribution or False,
            }
            if line.uom_id:
                line_vals['product_uom_id'] = line.uom_id.id
            if not line.product_id:
                # Product-less lines need an explicit account; fall back to any
                # expense account so the bill can post.
                line_vals['account_id'] = self._get_fallback_expense_account().id
            invoice_lines.append((0, 0, line_vals))

        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor_id.id,
            'invoice_date': fields.Date.context_today(self),
            'project_id': self.project_id.id,
            'invoice_origin': self.ref,
            'invoice_line_ids': invoice_lines,
        })
        self.write({'move_id': move.id, 'state': 'bill_created'})
        return self.action_view_bill()

    def _get_fallback_expense_account(self):
        account = self.env['account.account'].search([('account_type', '=', 'expense')], limit=1)
        if not account:
            raise ValidationError(_(
                "No expense account is configured. Please set a product on each "
                "line, or create an expense account in Accounting."))
        return account

    def action_view_bill(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bill'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
        }

    def action_cancel(self):
        # Cancel the PO/LPO itself (used before a bill is posted). Any linked
        # draft bill is cancelled too.
        for rec in self:
            if rec.move_id and rec.move_id.state == 'draft':
                rec.move_id.button_cancel()
            rec.state = 'cancelled'

    def action_cancel_bill(self):
        # Reversible: cancel the linked draft bill; the PO reverts to "Purchase
        # Order" (via _compute_state) and the cancelled bill stays linked so it
        # can be reopened.
        for rec in self:
            if rec.move_id and rec.move_id.state == 'draft':
                rec.move_id.button_cancel()

    def action_reopen_bill(self):
        # Undo a cancellation: reset the linked bill back to draft.
        for rec in self:
            if rec.move_id and rec.move_id.state == 'cancel':
                rec.move_id.button_draft()

    def action_reset(self):
        self.write({'state': 'rfq'})


class ConstructionPurchaseOrderLine(models.Model):
    _name = 'construction.purchase.order.line'
    _description = 'Construction Purchase Order Line'

    order_id = fields.Many2one('construction.purchase.order', index=True, ondelete='cascade', required=True)
    product_id = fields.Many2one('product.product', index=True, string='Product / Material')
    name = fields.Char(string='Description')
    uom_id = fields.Many2one('uom.uom', string='UOM')
    quantity = fields.Float(default=1.0, digits=(12, 3))
    price_unit = fields.Monetary(currency_field='currency_id')
    tax_ids = fields.Many2many('account.tax', string='Taxes',
                               domain="[('type_tax_use','=','purchase')]")
    currency_id = fields.Many2one('res.currency', related='order_id.currency_id', store=True)
    company_id = fields.Many2one('res.company', related='order_id.company_id', store=True)

    price_subtotal = fields.Monetary(compute='_compute_price', store=True, currency_field='currency_id')
    price_tax = fields.Monetary(compute='_compute_price', store=True, currency_field='currency_id')
    price_total = fields.Monetary(compute='_compute_price', store=True, currency_field='currency_id')

    @api.depends('quantity', 'price_unit', 'tax_ids')
    def _compute_price(self):
        for line in self:
            currency = line.currency_id or line.company_id.currency_id or self.env.company.currency_id
            taxes = line.tax_ids.compute_all(
                line.price_unit, currency=currency, quantity=line.quantity,
                product=line.product_id, partner=line.order_id.vendor_id)
            line.price_subtotal = taxes['total_excluded']
            line.price_total = taxes['total_included']
            line.price_tax = taxes['total_included'] - taxes['total_excluded']

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.uom_id = self.product_id.uom_id
            if not self.price_unit:
                self.price_unit = self.product_id.standard_price
            self.tax_ids = self.product_id.supplier_taxes_id.filtered(
                lambda t: not t.company_id or t.company_id == (self.company_id or self.env.company))
