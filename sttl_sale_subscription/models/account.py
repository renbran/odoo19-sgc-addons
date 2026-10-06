from odoo import models, api, fields
from datetime import date
from dateutil.relativedelta import relativedelta
import calendar


class Account(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        # Post the invoice first — if posting fails, we must NOT advance the date
        result = super().action_post()

        for move in self:
            if not move.invoice_origin:
                continue
            sale_order = self.env['sale.order'].search(
                [('name', '=', move.invoice_origin)], limit=1
            )
            if not sale_order or not sale_order.recurrance_id:
                continue

            period = sale_order.recurrance_id
            current_date = sale_order.next_invoice_date or date.today()
            next_date = self._compute_next_invoice_date(current_date, period)

            if next_date:
                sale_order.next_invoice_date = next_date
                sale_order.subscription_status = 'b'

        return result

    @api.model
    def _compute_next_invoice_date(self, current_date, period):
        """Compute the next invoice date based on the subscription period.

        Uses dateutil.relativedelta for accurate calendar-month arithmetic
        instead of the approximate timedelta(days=365/12) approach.
        """
        if period.unit == 'days':
            return current_date + relativedelta(days=period.duration)
        elif period.unit == 'weeks':
            return current_date + relativedelta(weeks=period.duration)
        elif period.unit == 'month':
            return current_date + relativedelta(months=period.duration)
        elif period.unit == 'year':
            return current_date + relativedelta(years=period.duration)
        elif period.unit == 'semi_monthly':
            return self._compute_next_semi_monthly_date(
                current_date, period.day_1, period.day_2
            )
        return False

    @api.model
    def _compute_next_semi_monthly_date(self, current_date, day_1, day_2):
        """Compute the next billing date for semi-monthly recurrence.

        Given two days of the month (e.g. 14 and 24), returns the next
        billing date strictly after current_date.  Automatically caps days
        to the last calendar day of shorter months (e.g. Feb 28).
        """
        d1, d2 = min(day_1, day_2), max(day_1, day_2)
        year, month = current_date.year, current_date.month
        last_day = calendar.monthrange(year, month)[1]

        effective_d1 = min(d1, last_day)
        effective_d2 = min(d2, last_day)

        if current_date.day < effective_d1:
            return current_date.replace(day=effective_d1)
        elif current_date.day < effective_d2:
            return current_date.replace(day=effective_d2)
        else:
            # Both days this month have passed — move to day_1 of next month
            next_month = current_date + relativedelta(months=1)
            next_last = calendar.monthrange(next_month.year, next_month.month)[1]
            return date(next_month.year, next_month.month, min(d1, next_last))