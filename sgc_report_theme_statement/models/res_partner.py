from odoo import models
from odoo.exceptions import ValidationError


class ResPartnerStatementSGC(models.Model):
    """Overrides action_print_pdf() specifically (the method the "Statement
    Report" print menu actually calls) rather than statement_report's
    shared main_query() - main_query() is reused by 8 different methods
    (XLSX export, email sharing, vendor statements...) via blind string
    concatenation (main_query += " AND move_type IN (...)"), so an
    earlier attempt to add ORDER BY there broke all of them with a SQL
    syntax error (ORDER BY followed by AND). Overriding just this one
    action keeps every other caller of main_query() completely
    unaffected.

    Adds two things the stock query never computed:
    - amount_paid: what has actually been paid on each invoice
      (amount_total_signed - amount_residual_signed - a standard,
      well-established Odoo accounting identity, not a new calculation
      method).
    - running_balance: a cumulative balance ordered chronologically
      (SUM(...) OVER (ORDER BY invoice_date, id)), matching how a real
      statement of account reads - each row shows the balance AFTER that
      transaction, not just that single invoice's own residual.

    Also selects `ref` (account_move's reference field), which the QWeb
    template already reads via line.get('ref', '-') but the original
    query never selected - Reference was always blank.

    2026-07-23: requested by the user after reviewing the rendered report -
    "properly show the payment made on each invoice and show actual
    balance ... mini summary on the top".
    """
    _inherit = 'res.partner'

    def action_print_pdf(self):
        if not self.customer_report_ids:
            raise ValidationError('There is no statement to print')

        query = """SELECT name, invoice_date, invoice_date_due, ref,
                    amount_total_signed AS sub_total,
                    amount_residual_signed AS amount_due,
                    amount_residual AS balance,
                    (amount_total_signed - amount_residual_signed) AS amount_paid,
                    SUM(amount_total_signed) OVER (
                        ORDER BY invoice_date ASC, id ASC
                    ) AS running_balance
            FROM account_move WHERE payment_state != 'paid'
            AND state ='posted' AND partner_id = %s
            AND company_id = %s
            AND move_type IN ('out_invoice')
            ORDER BY invoice_date ASC, id ASC """
        self.env.cr.execute(query, [self.id, self.env.company.id])
        main = self.env.cr.dictfetchall()

        amount_query, amount_params = self.amount_query()
        amount_query += """ AND move_type IN ('out_invoice')"""
        self.env.cr.execute(amount_query, amount_params)
        amount = self.env.cr.dictfetchall()

        data = {
            'customer': self.display_name,
            'street': self.street,
            'street2': self.street2,
            'city': self.city,
            'state': self.state_id.name,
            'zip': self.zip,
            'my_data': main,
            'total': amount[0]['total'],
            'balance': amount[0]['balance'],
            'currency': self.currency_id.symbol,
        }
        return self.env.ref(
            'statement_report.res_partner_action'
        ).report_action(self, data=data)
