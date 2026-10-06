# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ConstructionSubcontract(models.Model):
    _name = 'construction.subcontract'
    _description = 'Subcontract'
    _inherit = ['mail.thread']
    company_id = fields.Many2one('res.company', index=True, string='Company', required=True, default=lambda self: self.env.company)

    name = fields.Char(required=True)
    ref = fields.Char(readonly=True, default='New')
    project_id = fields.Many2one('construction.project', index=True, required=True)
    wbs_id = fields.Many2one('construction.wbs', index=True, domain="[('project_id','=',project_id)]")
    subcontractor_id = fields.Many2one('res.partner', index=True, string='Subcontractor', required=True)
    scope_of_work = fields.Text()
    contract_value = fields.Monetary(currency_field='currency_id')
    amount_paid = fields.Monetary(currency_field='currency_id')
    amount_remaining = fields.Monetary(compute='_compute_remaining', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', index=True, related='project_id.currency_id')
    start_date = fields.Date()
    end_date = fields.Date()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('bill_created', 'Bill Created'),
        ('posted', 'Posted'),
        ('completed', 'Completed'),
        ('terminated', 'Terminated'),
    ], default='draft', tracking=True, compute='_compute_state', store=True, readonly=False)
    move_id = fields.Many2one('account.move', index=True, string='Vendor Bill', readonly=True, copy=False)
    move_state = fields.Selection(related='move_id.state', string='Bill Status')

    @api.depends('move_id', 'move_id.state')
    def _compute_state(self):
        for rec in self:
            move = rec.move_id
            if move and move.state != 'cancel':
                if move.state == 'posted':
                    rec.state = 'posted'
                else:
                    rec.state = 'bill_created'
            elif rec.state in ('bill_created', 'posted'):
                # Linked bill cancelled/unlinked: revert so it can be recreated.
                rec.state = 'active'

    payment_terms = fields.Text()
    retention_percent = fields.Float('Retention %', default=10.0)
    retention_amount = fields.Monetary(compute='_compute_retention', currency_field='currency_id')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ref', 'New') == 'New':
                vals['ref'] = self.env['ir.sequence'].next_by_code('construction.subcontract') or 'New'
        return super().create(vals_list)

    @api.depends('contract_value', 'amount_paid')
    def _compute_remaining(self):
        for rec in self:
            rec.amount_remaining = rec.contract_value - rec.amount_paid

    @api.depends('contract_value', 'retention_percent')
    def _compute_retention(self):
        for rec in self:
            rec.retention_amount = rec.contract_value * (rec.retention_percent / 100)

    def action_activate(self):
        self.state = 'active'

    def action_complete(self):
        self.state = 'completed'

    def action_terminate(self):
        self.state = 'terminated'

    def action_create_bill(self):
        self.ensure_one()
        if self.move_id and self.move_id.state != 'cancel':
            return self.action_view_bill()

        product = self.env.ref('%s.product_construction_progress_billing' % self._module, raise_if_not_found=False)
        retention_product = self.env.ref('%s.product_retention_deduction' % self._module, raise_if_not_found=False)

        bill_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.subcontractor_id.id,
            'invoice_date': fields.Date.context_today(self),
            'project_id': self.project_id.id,
            'invoice_line_ids': [],
        }

        analytic_distribution = {str(self.project_id.analytic_account_id.id): 100} if self.project_id.analytic_account_id else {}

        # Main work line (contract value for now, or we could add billing lines)
        bill_vals['invoice_line_ids'].append((0, 0, {
            'name': self.name,
            'product_id': product.id if product else False,
            'quantity': 1,
            'price_unit': self.contract_value,
            'analytic_distribution': analytic_distribution,
        }))

        # Retention line
        if self.retention_amount > 0:
            bill_vals['invoice_line_ids'].append((0, 0, {
                'name': 'Retention Deduction',
                'product_id': retention_product.id if retention_product else False,
                'quantity': 1,
                'price_unit': -self.retention_amount,
                'analytic_distribution': analytic_distribution,
                'tax_ids': [(5, 0, 0)],
            }))

        move = self.env['account.move'].create(bill_vals)
        self.write({
            'move_id': move.id,
            'state': 'bill_created'
        })
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_in_invoice_type')
        form_view = [(self.env.ref('account.view_move_form').id, 'form')]
        if 'views' in action:
            action['views'] = form_view + [
                (vid, vt) for (vid, vt) in action['views'] if vt != 'form'
            ]
        else:
            action['views'] = form_view
        action['res_id'] = move.id
        return action

    def action_view_bill(self):
        action = self.env['ir.actions.actions']._for_xml_id('account.action_move_in_invoice_type')
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
        # Reversible cancel: cancel the linked draft bill; the subcontract reverts
        # to Active and the cancelled bill stays linked so it can be reopened.
        for rec in self:
            if rec.move_id and rec.move_id.state == 'draft':
                rec.move_id.button_cancel()

    def action_reopen_bill(self):
        # Undo a cancellation: reset the linked bill back to draft.
        for rec in self:
            if rec.move_id and rec.move_id.state == 'cancel':
                rec.move_id.button_draft()

    def action_reset(self):
        self.state = 'draft'
