# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ConstructionRABilling(models.Model):
    _name = 'construction.ra.billing'
    _description = 'Running Account Billing'
    _inherit = ['mail.thread']
    company_id = fields.Many2one('res.company', index=True, string='Company', required=True, default=lambda self: self.env.company)

    name = fields.Char(required=True)
    ref = fields.Char(readonly=True, default='New')
    ra_number = fields.Integer('RA No.', readonly=True)
    project_id = fields.Many2one('construction.project', index=True, required=True)
    billing_date = fields.Date(default=lambda self: fields.Date.context_today(self))
    billing_period_start = fields.Date()
    billing_period_end = fields.Date()
    line_ids = fields.One2many('construction.ra.billing.line', 'billing_id')
    total_amount = fields.Monetary(compute='_compute_total', store=True, currency_field='currency_id')
    previous_billed = fields.Monetary(currency_field='currency_id')
    net_amount = fields.Monetary(compute='_compute_net', store=True, currency_field='currency_id')
    retention_percent = fields.Float('Retention %', default=5.0)
    retention_amount = fields.Monetary(compute='_compute_retention', store=True, currency_field='currency_id')
    net_payable = fields.Monetary(compute='_compute_payable', store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', index=True, related='project_id.currency_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('invoice_created', 'Invoice Created'),
        ('posted', 'Posted'),
        ('paid', 'Paid'),
    ], default='draft', tracking=True, compute='_compute_state', store=True, readonly=False)
    move_id = fields.Many2one('account.move', index=True, string='Customer Invoice', readonly=True, copy=False)

    @api.depends('move_id', 'move_id.state', 'move_id.payment_state')
    def _compute_state(self):
        for rec in self:
            move = rec.move_id
            if move and move.state != 'cancel':
                if move.state == 'posted':
                    if move.payment_state in ('paid', 'in_payment'):
                        rec.state = 'paid'
                    else:
                        rec.state = 'posted'
                else:
                    rec.state = 'invoice_created'
            elif rec.state in ('invoice_created', 'posted', 'paid'):
                # The linked invoice was cancelled (or unlinked): drop back to
                # Approved so the invoice can be recreated.
                rec.state = 'approved'
    payment_state = fields.Selection(related='move_id.payment_state', string='Payment Status')
    move_state = fields.Selection(related='move_id.state', string='Invoice Status')
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ref', 'New') == 'New':
                vals['ref'] = self.env['ir.sequence'].next_by_code('construction.ra.billing') or 'New'
            if not vals.get('ra_number') and vals.get('project_id'):
                last_ra = self.search([('project_id', '=', vals['project_id'])], order='ra_number desc', limit=1)
                vals['ra_number'] = (last_ra.ra_number or 0) + 1
        return super().create(vals_list)

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('amount'))

    @api.depends('total_amount', 'previous_billed')
    def _compute_net(self):
        for rec in self:
            rec.net_amount = rec.total_amount - rec.previous_billed

    @api.depends('net_amount', 'retention_percent')
    def _compute_retention(self):
        for rec in self:
            rec.retention_amount = rec.net_amount * (rec.retention_percent / 100)

    @api.depends('net_amount', 'retention_amount')
    def _compute_payable(self):
        for rec in self:
            rec.net_payable = rec.net_amount - rec.retention_amount

    def action_submit(self):
        self.state = 'submitted'

    def action_approve(self):
        self.state = 'approved'

    def action_create_invoice(self):
        self.ensure_one()
        if self.move_id and self.move_id.state != 'cancel':
            # A live invoice already exists; just open it.
            return self.action_view_invoice()

        # Quality Gating: scoped to the WBS phases actually covered by this
        # billing's lines, so a defect on one phase doesn't freeze billing for
        # unrelated work. Project-wide checks (no WBS phase) still block always.
        wbs_ids = self.line_ids.boq_line_id.wbs_id.ids
        failed_checks = self.env['construction.quality.check']._get_blocking_failures(
            self.project_id.id, wbs_ids
        )
        if failed_checks:
            raise ValidationError(
                "Cannot create invoice: blocked by failed quality check(s): %s" %
                ', '.join(failed_checks.mapped('name'))
            )

        product = self.env.ref('%s.product_construction_progress_billing' % self._module, raise_if_not_found=False)
        retention_product = self.env.ref('%s.product_retention_deduction' % self._module, raise_if_not_found=False)

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.project_id.client_id.id,
            'invoice_date': self.billing_date,
            'project_id': self.project_id.id, # If we add project_id to account.move
            'invoice_line_ids': [],
        }

        # Main work line
        analytic_distribution = {str(self.project_id.analytic_account_id.id): 100} if self.project_id.analytic_account_id else {}

        invoice_vals['invoice_line_ids'].append((0, 0, {
            'name': self.name,
            'product_id': product.id if product else False,
            'quantity': 1,
            'price_unit': self.net_amount,
            'analytic_distribution': analytic_distribution,
        }))

        # Retention line
        if self.retention_amount > 0:
            invoice_vals['invoice_line_ids'].append((0, 0, {
                'name': 'Retention Deduction',
                'product_id': retention_product.id if retention_product else False,
                'quantity': 1,
                'price_unit': -self.retention_amount,
                'analytic_distribution': analytic_distribution,
                'tax_ids': [(5, 0, 0)], # Usually no tax on retention deduction
            }))

        move = self.env['account.move'].create(invoice_vals)
        self.write({
            'move_id': move.id,
            'state': 'invoice_created'
        })
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_out_invoice_type')
        form_view = [(self.env.ref('account.view_move_form').id, 'form')]
        if 'views' in action:
            action['views'] = form_view + [
                (vid, vt) for (vid, vt) in action['views'] if vt != 'form'
            ]
        else:
            action['views'] = form_view
        action['res_id'] = move.id
        return action

    def action_view_invoice(self):
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_out_invoice_type')
        form_view = [(self.env.ref('account.view_move_form').id, 'form')]
        if 'views' in action:
            action['views'] = form_view + [
                (vid, vt) for (vid, vt) in action['views'] if vt != 'form'
            ]
        else:
            action['views'] = form_view
        action['res_id'] = self.move_id.id
        return action

    def action_load_boq(self):
        self.ensure_one()
        if self.line_ids:
            return

        # Find latest approved BOQ for the project
        boq = self.env['construction.boq'].search([
            ('project_id', '=', self.project_id.id),
            ('state', '=', 'approved')
        ], order='date desc', limit=1)

        if not boq:
            return

        lines = []
        for line in boq.line_ids.filtered(lambda l: not l.is_section):
            # Compute previous billed qty
            prev_lines = self.env['construction.ra.billing.line'].search([
                ('billing_id.project_id', '=', self.project_id.id),
                ('billing_id.state', 'in', ('invoice_created', 'posted', 'paid')),
                ('boq_line_id', '=', line.id)
            ])
            qty_prev = sum(prev_lines.mapped('qty_current'))

            lines.append((0, 0, {
                'boq_line_id': line.id,
                'boq_line_description': line.description,
                'work_type': line.work_type,
                'uom_id': line.uom_id.id,
                'boq_qty': line.qty,
                'unit_rate': line.unit_rate,
                'qty_previous': qty_prev,
            }))
        self.write({'line_ids': lines})

    def action_pay(self):
        # This is now largely handled by the computed state, but we can keep it
        # as a manual override or just let it pass if already paid.
        if self.state != 'paid' and self.move_id.payment_state not in ('paid', 'in_payment'):
             # Logic to register payment could go here in Phase 3
             pass

    def action_cancel(self):
        # Cancel the linked draft invoice. The billing reverts to Approved (via
        # _compute_state) and the cancelled invoice stays linked, so an accidental
        # cancel can be undone with "Reopen Invoice". Posted invoices must be
        # reset to draft from Accounting first.
        for rec in self:
            if rec.move_id and rec.move_id.state == 'draft':
                rec.move_id.button_cancel()

    def action_reopen_invoice(self):
        # Undo a cancellation: reset the linked invoice back to draft, which
        # returns the billing to "Invoice Created" with the same invoice.
        for rec in self:
            if rec.move_id and rec.move_id.state == 'cancel':
                rec.move_id.button_draft()

    def action_reset(self):
        self.state = 'draft'


class ConstructionRABillingLine(models.Model):
    _name = 'construction.ra.billing.line'
    _description = 'RA Billing Line'

    billing_id = fields.Many2one('construction.ra.billing', index=True, ondelete='cascade')
    boq_line_id = fields.Many2one('construction.boq.line', index=True, string='BOQ Line')
    boq_line_description = fields.Char('Description', required=True)
    work_type = fields.Selection([
        ('civil', 'Civil'),
        ('structural', 'Structural'),
        ('electrical', 'Electrical'),
        ('plumbing', 'Plumbing/MEP'),
        ('finishing', 'Finishing'),
        ('external', 'External Works'),
        ('other', 'Other'),
    ], default='civil')
    uom_id = fields.Many2one('uom.uom', index=True)
    boq_qty = fields.Float('BOQ Qty', digits=(12, 3))
    qty_previous = fields.Float('Prev. Qty', digits=(12, 3))
    qty_current = fields.Float('Current Qty', digits=(12, 3))
    qty_cumulative = fields.Float(compute='_compute_cumulative', store=True, digits=(12, 3))
    unit_rate = fields.Monetary(currency_field='currency_id')
    amount = fields.Monetary(compute='_compute_amount', store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', index=True, related='billing_id.currency_id')

    def _is_percentage_uom(self):
        """Check if this line uses a percentage-based unit of measure."""
        self.ensure_one()
        if not self.uom_id:
            return False
        percent_category = self.env.ref('sgc_construction_management.uom_category_percentage', raise_if_not_found=False)
        return bool(percent_category and self.uom_id.category_id == percent_category)

    @api.depends('qty_previous', 'qty_current')
    def _compute_cumulative(self):
        for rec in self:
            rec.qty_cumulative = rec.qty_previous + rec.qty_current

    @api.constrains('qty_cumulative', 'boq_qty')
    def _check_qty_limit(self):
        for rec in self:
            if not rec.boq_line_id:
                continue
            if rec._is_percentage_uom():
                max_qty = 100.0
            else:
                max_qty = rec.boq_qty
            if rec.qty_cumulative > max_qty:
                raise ValidationError(
                    "Cumulative %s (%s) cannot exceed %s for item: %s" %
                    ("%" if rec._is_percentage_uom() else "quantity", rec.qty_cumulative, max_qty, rec.boq_line_description)
                )

    @api.onchange('boq_line_id')
    def _onchange_boq_line_id(self):
        if self.boq_line_id:
            self.boq_line_description = self.boq_line_id.description
            self.work_type = self.boq_line_id.work_type
            self.uom_id = self.boq_line_id.uom_id
            self.boq_qty = self.boq_line_id.qty
            self.unit_rate = self.boq_line_id.unit_rate

            # Fetch previous billed qty
            prev_lines = self.env['construction.ra.billing.line'].search([
                ('billing_id.project_id', '=', self.billing_id.project_id.id),
                ('billing_id.state', 'in', ('invoice_created', 'posted', 'paid')),
                ('boq_line_id', '=', self.boq_line_id.id),
                ('id', '!=', self._origin.id if self._origin else False)
            ])
            self.qty_previous = sum(prev_lines.mapped('qty_current'))

    @api.depends('qty_current', 'unit_rate', 'uom_id')
    def _compute_amount(self):
        for rec in self:
            if rec._is_percentage_uom():
                # Percentage: qty_current is the % complete, unit_rate is total value
                rec.amount = (rec.qty_current / 100.0) * rec.unit_rate
            else:
                rec.amount = rec.qty_current * rec.unit_rate


class ConstructionProgressBilling(models.Model):
    _name = 'construction.progress.billing'
    _description = 'Progress Billing'
    _inherit = ['mail.thread']
    company_id = fields.Many2one('res.company', index=True, string='Company', required=True, default=lambda self: self.env.company)

    name = fields.Char(required=True)
    ref = fields.Char(readonly=True, default='New')
    project_id = fields.Many2one('construction.project', index=True, required=True)
    billing_date = fields.Date(default=lambda self: fields.Date.context_today(self))
    contract_value = fields.Monetary(related='project_id.contract_value', currency_field='currency_id')
    percent_complete = fields.Float('% Complete')
    amount_earned = fields.Monetary(compute='_compute_earned', store=True, currency_field='currency_id')
    amount_previously_billed = fields.Monetary(currency_field='currency_id')
    amount_this_period = fields.Monetary(compute='_compute_this_period', store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', index=True, related='project_id.currency_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('invoice_created', 'Invoice Created'),
        ('posted', 'Posted'),
    ], default='draft', tracking=True, compute='_compute_state', store=True, readonly=False)
    move_id = fields.Many2one('account.move', index=True, string='Customer Invoice', readonly=True, copy=False)

    @api.depends('move_id', 'move_id.state', 'move_id.payment_state')
    def _compute_state(self):
        for rec in self:
            move = rec.move_id
            if move and move.state != 'cancel':
                if move.state == 'posted':
                    rec.state = 'posted'
                else:
                    rec.state = 'invoice_created'
            elif rec.state in ('invoice_created', 'posted'):
                # Linked invoice cancelled/unlinked: revert so it can be recreated.
                rec.state = 'approved'
    payment_state = fields.Selection(related='move_id.payment_state', string='Payment Status')
    move_state = fields.Selection(related='move_id.state', string='Invoice Status')
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ref', 'New') == 'New':
                vals['ref'] = self.env['ir.sequence'].next_by_code('construction.progress.billing') or 'New'
        return super().create(vals_list)

    @api.depends('contract_value', 'percent_complete')
    def _compute_earned(self):
        for rec in self:
            rec.amount_earned = rec.contract_value * (rec.percent_complete / 100)

    @api.depends('amount_earned', 'amount_previously_billed')
    def _compute_this_period(self):
        for rec in self:
            rec.amount_this_period = rec.amount_earned - rec.amount_previously_billed

    def action_approve(self):
        self.state = 'approved'

    def action_create_invoice(self):
        self.ensure_one()
        if self.move_id and self.move_id.state != 'cancel':
            return self.action_view_invoice()

        # Quality Gating
        failed_checks = self.env['construction.quality.check'].search_count([
            ('project_id', '=', self.project_id.id),
            ('state', '=', 'failed')
        ])
        if failed_checks > 0:
             raise ValidationError("Cannot create invoice: There are failed quality checks for this project.")

        product = self.env.ref('%s.product_construction_progress_billing' % self._module, raise_if_not_found=False)

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.project_id.client_id.id,
            'invoice_date': self.billing_date,
            'project_id': self.project_id.id,
            'invoice_line_ids': [],
        }

        analytic_distribution = {str(self.project_id.analytic_account_id.id): 100} if self.project_id.analytic_account_id else {}

        invoice_vals['invoice_line_ids'].append((0, 0, {
            'name': self.name,
            'product_id': product.id if product else False,
            'quantity': 1,
            'price_unit': self.amount_this_period,
            'analytic_distribution': analytic_distribution,
        }))

        move = self.env['account.move'].create(invoice_vals)
        self.write({
            'move_id': move.id,
            'state': 'invoice_created'
        })
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_out_invoice_type')
        form_view = [(self.env.ref('account.view_move_form').id, 'form')]
        if 'views' in action:
            action['views'] = form_view + [
                (vid, vt) for (vid, vt) in action['views'] if vt != 'form'
            ]
        else:
            action['views'] = form_view
        action['res_id'] = move.id
        return action

    def action_view_invoice(self):
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_out_invoice_type')
        form_view = [(self.env.ref('account.view_move_form').id, 'form')]
        if 'views' in action:
            action['views'] = form_view + [
                (vid, vt) for (vid, vt) in action['views'] if vt != 'form'
            ]
        else:
            action['views'] = form_view
        action['res_id'] = self.move_id.id
        return action

    def action_cancel(self):
        # Reversible cancel: cancel the linked draft invoice; reopen via
        # action_reopen_invoice. See RA Billing.action_cancel for details.
        for rec in self:
            if rec.move_id and rec.move_id.state == 'draft':
                rec.move_id.button_cancel()

    def action_reopen_invoice(self):
        for rec in self:
            if rec.move_id and rec.move_id.state == 'cancel':
                rec.move_id.button_draft()

    def action_reset(self):
        self.state = 'draft'
