# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import AccessError

from .account_move_agent_guard import TASK_CREATE_MOVE, TASK_POST_MOVE


class AccountPaymentAgentGuard(models.Model):
    """Agents may create draft payments (intake role) and nothing more.

    Confirming, validating, rejecting, cancelling or resetting a payment
    stays with an accountant: there is no approval flow for payments.
    """

    _inherit = "account.payment"

    def _refuse(self, message, task):
        role = self.env.user.sgc_agent_role_id
        self.env["sgc.agent.audit"].sudo().log_durable(
            task,
            self._name,
            self.ids,
            result="refused",
            details={"reason": message, "role": role.code or False},
        )
        raise AccessError(message)

    @api.model_create_multi
    def create(self, vals_list):
        role = self.env.user.sgc_agent_role_id
        if role:
            if not role.allows(TASK_CREATE_MOVE):
                self._refuse(
                    _("Your role %(role)s is not authorised to create payments.")
                    % {"role": role.code},
                    TASK_CREATE_MOVE,
                )
            companies = role.company_ids.ids
            for vals in vals_list:
                company = vals.get("company_id") or self.env.company.id
                if companies and company not in companies:
                    self._refuse(
                        _(
                            "Your role %(role)s is not authorised to work on "
                            "company %(company)s."
                        )
                        % {"role": role.code, "company": company},
                        TASK_CREATE_MOVE,
                    )
                if vals.get("state", "draft") != "draft":
                    self._refuse(
                        _("An agent may only create payments in draft state."),
                        TASK_CREATE_MOVE,
                    )
        payments = super().create(vals_list)
        if role:
            self.env["sgc.agent.audit"].sudo().log_durable(
                TASK_CREATE_MOVE,
                self._name,
                payments.ids,
                details={"role": role.code},
            )
        return payments

    def write(self, vals):
        if self.env.user.sgc_agent_role_id and {"state", "company_id", "move_id"} & set(
            vals
        ):
            self._refuse(
                _("An agent cannot change the state or company of a payment."),
                TASK_POST_MOVE,
            )
        return super().write(vals)

    def _refuse_agent_state_change(self):
        if self.env.user.sgc_agent_role_id:
            self._refuse(
                _(
                    "An agent cannot confirm, validate, reject, cancel or reset "
                    "a payment."
                ),
                TASK_POST_MOVE,
            )

    def action_post(self):
        self._refuse_agent_state_change()
        return super().action_post()

    def action_validate(self):
        self._refuse_agent_state_change()
        return super().action_validate()

    def action_reject(self):
        self._refuse_agent_state_change()
        return super().action_reject()

    def action_cancel(self):
        self._refuse_agent_state_change()
        return super().action_cancel()

    def button_request_cancel(self):
        self._refuse_agent_state_change()
        return super().button_request_cancel()

    def action_draft(self):
        self._refuse_agent_state_change()
        return super().action_draft()
