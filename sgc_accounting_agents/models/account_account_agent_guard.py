# -*- coding: utf-8 -*-
import contextvars

from odoo import _, api, models
from odoo.exceptions import AccessError

TASK_ACCOUNT = "account.maintain"
INTAKE = "agent-01-intake"
# What an owner-approved Chart of Accounts change may set, and nothing else.
CREATE_FIELDS = {"code", "name", "account_type", "reconcile", "company_ids"}
WRITE_FIELDS = {"name", "account_type", "reconcile", "active"}

# Set only inside the guarded create below: Odoo stores the new account's code
# with an inner write, which an XML-RPC caller cannot reach this way.
_CREATING = contextvars.ContextVar("sgc_agent_account_create", default=False)


class AccountAccountAgentGuard(models.Model):
    """The intake agent may add, rename, retype or archive accounts of its own
    companies (the ir.rule), and nothing more: never recode an account, move
    it to another company, or touch its taxes, tags or currency, and never
    retype an account that already has journal items."""

    _inherit = "account.account"

    def _agent_refuse(self, message):
        self.env["sgc.agent.audit"].sudo().log_durable(
            TASK_ACCOUNT, self._name, self.ids, result="refused", details={"reason": message}
        )
        raise AccessError(message)

    @api.model_create_multi
    def create(self, vals_list):
        role = self.env.user.sgc_agent_role_id
        # No role at all means a normal human user: let them through. A role
        # whose record was deleted out from under the field would otherwise
        # compare equal to INTAKE and skip the guard entirely.
        if not role or role.code != INTAKE:
            return super().create(vals_list)
        for vals in vals_list:
            extra = sorted(set(vals) - CREATE_FIELDS)
            if extra:
                self._agent_refuse(_("An agent may not set %s on a new account.", ", ".join(extra)))
        token = _CREATING.set(True)
        try:
            accounts = super().create(vals_list)
        finally:
            _CREATING.reset(token)
        self.env["sgc.agent.audit"].sudo().log_durable(
            TASK_ACCOUNT, self._name, accounts.ids, details={"role": role.code, "action": "create"}
        )
        return accounts

    def write(self, vals):
        role = self.env.user.sgc_agent_role_id
        if role.code != INTAKE or _CREATING.get():
            return super().write(vals)
        extra = sorted(set(vals) - WRITE_FIELDS)
        if extra:
            self._agent_refuse(_("An agent may not change %s of an account.", ", ".join(extra)))
        if "account_type" in vals:
            retyped = self.sudo().filtered(lambda account: account.account_type != vals["account_type"])
            if retyped and self.env["account.move.line"].sudo().search_count(
                [("account_id", "in", retyped.ids)], limit=1
            ):
                self._agent_refuse(_("An account with journal items keeps its type; an accountant changes it."))
        result = super().write(vals)
        self.env["sgc.agent.audit"].sudo().log_durable(
            TASK_ACCOUNT, self._name, self.ids,
            details={"role": role.code, "action": "write", "fields": sorted(vals)},
        )
        return result
