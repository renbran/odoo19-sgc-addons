# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ConstructionExpenseCategory(models.Model):
    _name = 'construction.expense.category'
    _description = 'Construction Expense Category'

    name = fields.Char(required=True)
    property_account_expense_id = fields.Many2one('account.account', index=True,
        string="Expense Account",
        company_dependent=True,
        domain="[('active', '=', True)]",
        help="This account will be used as the default for vendor bills created from expenses of this category.")


class ConstructionExpense(models.Model):
    _name = 'construction.expense'
    _description = 'Construction Expense'
    _inherit = ['mail.thread']
    company_id = fields.Many2one('res.company', index=True, string='Company', required=True, default=lambda self: self.env.company)

    name = fields.Char(required=True)
    ref = fields.Char(readonly=True, default='New')
    project_id = fields.Many2one('construction.project', index=True, required=True)
    wbs_id = fields.Many2one('construction.wbs', index=True, domain="[('project_id','=',project_id)]")
    date = fields.Date(default=lambda self: fields.Date.context_today(self))
    category_id = fields.Many2one('construction.expense.category', index=True, string='Category', required=True)
    amount = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', index=True, related='project_id.currency_id')
    employee_id = fields.Many2one('res.users', index=True, string='Incurred By')
    approved_by = fields.Many2one('res.users', index=True)
    description = fields.Text()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('bill_created', 'Bill Created'),
        ('posted', 'Posted'),
        ('rejected', 'Rejected'),
    ], default='draft', tracking=True, compute='_compute_state', store=True, readonly=False)
    move_id = fields.Many2one('account.move', index=True, string='Vendor Bill', readonly=True, copy=False)
    move_state = fields.Selection(related='move_id.state', string='Bill Status')
    partner_id = fields.Many2one('res.partner', index=True, string='Vendor')

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
                rec.state = 'approved'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ref', 'New') == 'New':
                vals['ref'] = self.env['ir.sequence'].next_by_code('construction.expense') or 'New'
        return super().create(vals_list)

    def action_submit(self):
        self.state = 'submitted'

    def action_approve(self):
        self.write({'state': 'approved', 'approved_by': self.env.user.id})

    def action_create_bill(self):
        self.ensure_one()
        if self.move_id and self.move_id.state != 'cancel':
            return self.action_view_bill()

        account_id = self.category_id.property_account_expense_id.id
        if not account_id:
             raise ValidationError("Cannot create bill: No expense account configured for category: %s" % self.category_id.name)

        bill_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': self.date,
            'project_id': self.project_id.id,
            'invoice_line_ids': [],
        }

        analytic_distribution = {str(self.project_id.analytic_account_id.id): 100} if self.project_id.analytic_account_id else {}

        line_vals = {
            'name': self.name,
            'quantity': 1,
            'price_unit': self.amount,
            'account_id': account_id,
            'analytic_distribution': analytic_distribution,
        }

        bill_vals['invoice_line_ids'].append((0, 0, line_vals))

        move = self.env['account.move'].create(bill_vals)
        self.write({
            'move_id': move.id,
            'state': 'bill_created'
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
        }

    def action_view_bill(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
        }

    def action_reject(self):
        self.state = 'rejected'

    def action_cancel(self):
        # Reversible cancel: cancel the linked draft bill; the expense reverts to
        # Approved and the cancelled bill stays linked so it can be reopened.
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
