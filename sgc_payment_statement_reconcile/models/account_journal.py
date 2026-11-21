# -*- coding: utf-8 -*-
"""Payment-based bank/cash reconciliation.

Each posted, not-yet-matched payment of a bank/cash journal becomes one statement line (same date, amount,
partner, reference). The statement line's suspense leg is re-pointed to the payment's outstanding account and
reconciled with the payment's outstanding line, so both the statement line and the payment end up reconciled.
The generated statement carries a CSV export of its lines (the "exported payments" bank/cash statement).
"""
import base64
import csv
import io

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _unmatched_payment_lines(self, date_to):
        """Outstanding (unreconciled) lines of posted payments of this journal up to date_to."""
        self.ensure_one()
        payments = self.env['account.payment'].search([
            ('journal_id', '=', self.id),
            ('date', '<=', date_to),
            ('move_id.state', '=', 'posted'),
            ('is_matched', '=', False),
        ], order='date, id')
        lines = self.env['account.move.line']
        for pay in payments:
            lines |= pay.move_id.line_ids.filtered(
                lambda l: l.account_id == pay.outstanding_account_id and not l.reconciled)
        return lines

    def _reconcile_from_payments(self, date_to=None):
        """Create one statement for this journal from its unmatched payments and reconcile it.

        Returns a dict with ``statement_count`` and ``lines_reconciled`` so the
        agency-side reconciliation runner can report results.
        """
        self.ensure_one()
        if self.type not in ('bank', 'cash'):
            raise UserError(_('Only bank and cash journals can be reconciled from payments.'))
        date_to = date_to or fields.Date.context_today(self)
        pay_lines = self._unmatched_payment_lines(date_to)
        if not pay_lines:
            return {"statement_count": 0, "lines_reconciled": 0}
        statement = self.env['account.bank.statement'].create({
            'name': _('PAY-REC/%(journal)s/%(date)s', journal=self.code, date=date_to),
            'journal_id': self.id,
        })
        no_sync = dict(skip_account_move_synchronization=True, check_move_validity=False)
        lines_reconciled = 0
        for pay_line in pay_lines:
            st_line = self.env['account.bank.statement.line'].create({
                'statement_id': statement.id,
                'journal_id': self.id,
                'date': pay_line.date,
                'amount': pay_line.balance,
                'partner_id': pay_line.partner_id.id,
                'payment_ref': pay_line.move_id.name if not pay_line.move_id.ref
                else '%s - %s' % (pay_line.move_id.name, pay_line.move_id.ref),
            })
            _liquidity, suspense, _other = st_line._seek_for_lines()
            move = st_line.move_id
            move.with_context(**no_sync).button_draft()
            suspense.with_context(**no_sync).write({'account_id': pay_line.account_id.id, 'partner_id': pay_line.partner_id.id})
            move.with_context(skip_account_move_synchronization=True).action_post()
            (suspense | pay_line).reconcile()
            lines_reconciled += 1
        # account.bank.statement has no chatter in Community: attach the export directly.
        statement.attachment_ids = [(0, 0, {
            'name': '%s.csv' % statement.name.replace('/', '_'),
            'raw': statement._payment_statement_csv(),
            'mimetype': 'text/csv',
            'res_model': 'account.bank.statement',
            'res_id': statement.id,
        })]
        # Log to the agent audit trail if the current user is an agent.
        role = self.env.user.sgc_agent_role_id if hasattr(self.env.user, 'sgc_agent_role_id') else False
        if role:
            self.env['sgc.agent.audit'].sudo().log(
                'reconcile.write',
                'account.bank.statement',
                res_ids=[statement.id],
                details={
                    'role': role.code,
                    'journal': self.code,
                    'lines_reconciled': lines_reconciled,
                },
            )
        return {"statement_count": 1, "lines_reconciled": lines_reconciled}

    def action_reconcile_from_payments(self):
        statements = self.env['account.bank.statement']
        for journal in self:
            result = journal._reconcile_from_payments()
            if isinstance(result, dict) and result.get('statement_count'):
                # The statement was created inside _reconcile_from_payments;
                # find it by the most recent one on this journal.
                latest = self.env['account.bank.statement'].search(
                    [('journal_id', '=', journal.id)],
                    order='id desc', limit=1,
                )
                statements |= latest
        if not statements:
            raise UserError(_('No unmatched registered payments to reconcile.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payment-based statements'),
            'res_model': 'account.bank.statement',
            'view_mode': 'list,form',
            'domain': [('id', 'in', statements.ids)],
        }

    @api.model
    def _cron_reconcile_from_payments(self):
        for journal in self.search([('type', 'in', ('bank', 'cash'))]):
            journal.with_company(journal.company_id)._reconcile_from_payments()

    def action_reconcile_payments_agent(self, date_to=None):
        """Reconcile this journal from its unmatched payments.

        Public entry point for the ``agent-03-reconciliation`` service user:
        Odoo refuses to call private (``_``-prefixed) methods over XML-RPC, so
        the agency-side reconciliation runner calls this wrapper instead. It
        returns a plain dict so the caller can aggregate results without
        needing the created record ids.
        """
        self.ensure_one()
        result = self._reconcile_from_payments(date_to=date_to)
        if isinstance(result, dict):
            return result
        # Older implementations returned the statement recordset.
        return {
            "statement_count": len(result) if result else 0,
            "lines_reconciled": sum(
                len(statement.line_ids) for statement in (result or [])
            ),
        }


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    def _payment_statement_csv(self):
        self.ensure_one()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['date', 'reference', 'partner', 'amount', 'reconciled'])
        for line in self.line_ids:
            w.writerow([line.date, line.payment_ref, line.partner_id.display_name or '', line.amount, line.is_reconciled])
        return buf.getvalue().encode()
