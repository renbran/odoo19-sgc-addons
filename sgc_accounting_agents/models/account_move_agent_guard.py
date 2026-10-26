# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

TASK_CREATE_MOVE = "move.create_draft"
TASK_POST_MOVE = "move.post"
TASK_GL_MAP = "gl.map"
TASK_REQUEST_APPROVAL = "approval.request"


class AccountMoveAgentGuard(models.Model):
    """Keep accounting agents inside their job description.

    Odoo access rights are coarse: a user who may post may also create and
    delete.  These guards add the missing layer, so an agent can only do the
    work its role allows.
    """

    _inherit = "account.move"

    def _agent_role(self):
        """Return the role of the current user, if the user is an agent."""
        return self.env.user.sgc_agent_role_id

    def _refuse(self, message, task):
        """Refuse an operation and record it in the audit trail."""
        role = self._agent_role()
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
                self.env["sgc.agent.audit"].sudo().log_durable(
                    TASK_CREATE_MOVE,
                    self._name,
                    result="refused",
                    details={
                        "reason": "role %s may not create journal entries"
                        % role.code
                    },
                )
                raise AccessError(
                    _(
                        "Your role %(role)s is not authorised to create journal "
                        "entries."
                    )
                    % {"role": role.code}
                )
            companies = role.company_ids.ids
            for vals in vals_list:
                company = vals.get("company_id") or self.env.company.id
                if companies and company not in companies:
                    raise AccessError(
                        _(
                            "Your role %(role)s is not authorised to work on "
                            "company %(company)s."
                        )
                        % {"role": role.code, "company": company}
                    )
                if vals.get("state") and vals["state"] != "draft":
                    raise AccessError(
                        _("An agent may only create entries in draft state.")
                    )
        moves = super().create(vals_list)
        if role:
            self.env["sgc.agent.audit"].sudo().log_durable(
                TASK_CREATE_MOVE,
                self._name,
                moves.ids,
                details={"role": role.code},
            )
        return moves

    def write(self, vals):
        role = self._agent_role()
        if role:
            internal = self.env.context.get("sgc_agent_posting")
            if "state" in vals and not internal and vals["state"] != "draft":
                self._refuse(
                    _(
                        "An agent cannot change the state of a journal entry "
                        "directly. Use the posting flow with an approval."
                    ),
                    TASK_POST_MOVE,
                )
            if {"company_id"} & set(vals):
                self._refuse(
                    _("An agent cannot move a journal entry to another company."),
                    TASK_CREATE_MOVE,
                )
        return super().write(vals)

    def unlink(self):
        role = self._agent_role()
        if role:
            protected = self.filtered(
                lambda move: move.state == "posted"
                or (move.name and move.name not in ("/",))
            )
            if protected:
                self._refuse(
                    _("An agent cannot delete a posted journal entry."),
                    TASK_POST_MOVE,
                )
        return super().unlink()

    def action_post(self):
        role = self._agent_role()
        if role:
            if not role.can_post or not role.allows(TASK_POST_MOVE):
                self._refuse(
                    _(
                        "Your role %(role)s is not authorised to post journal "
                        "entries."
                    )
                    % {"role": role.code},
                    TASK_POST_MOVE,
                )
            approvals = self.env["sgc.agent.posting.approval"].sudo().search(
                [("move_id", "in", self.ids), ("state", "=", "approved")]
            )
            approved_moves = approvals.mapped("move_id")
            missing = self - approved_moves
            if missing:
                self._refuse(
                    _(
                        "Journal entries %(moves)s have no approved posting "
                        "request."
                    )
                    % {"moves": ", ".join(missing.mapped("display_name"))},
                    TASK_POST_MOVE,
                )
        moves = super(
            AccountMoveAgentGuard, self.with_context(sgc_agent_posting=True)
        ).action_post()
        if role:
            self.env["sgc.agent.audit"].sudo().log_durable(
                TASK_POST_MOVE,
                self._name,
                self.ids,
                details={"role": role.code},
            )
        return moves

    def button_draft(self):
        role = self._agent_role()
        if role and any(move.state == "posted" for move in self):
            self._refuse(
                _("An agent cannot reset a posted entry to draft."),
                TASK_POST_MOVE,
            )
        return super().button_draft()

    def button_cancel(self):
        role = self._agent_role()
        if role and any(move.state == "posted" for move in self):
            self._refuse(
                _("An agent cannot cancel a posted journal entry."),
                TASK_POST_MOVE,
            )
        return super().button_cancel()
