from odoo import models


class ResPartnerStatementSGC(models.Model):
    """Extends statement_report's own res.partner.main_query() rather than
    editing that module's file directly - same non-destructive,
    inheritance-only principle used for the QWeb theming work.

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

    def main_query(self):
        _, params = super().main_query()
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
            ORDER BY invoice_date ASC, id ASC """
        return query, params
