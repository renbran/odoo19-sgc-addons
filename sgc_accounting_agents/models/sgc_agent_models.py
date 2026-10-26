# -*- coding: utf-8 -*-
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


def normalize_tasks(value):
    """Return a list of task codes from a list or a JSON string."""
    if value is None or value is False:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            value = json.loads(text)
        except ValueError:
            value = [part.strip() for part in text.split(",") if part.strip()]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value]


class SgcAgentRole(models.Model):
    """Job description of an accounting agent.

    A role owns one group.  The group holds the access rights and the record
    rules, so the job description and the technical access stay in one place.
    """

    _name = "sgc.agent.role"
    _description = "Accounting Agent Role"
    _order = "sequence, code"

    name = fields.Char(required=True)
    code = fields.Char(required=True, copy=False)
    sequence = fields.Integer(default=10)
    job_description = fields.Text(
        required=True,
        help="What this agent is allowed to do. Shown to accountants and auditors.",
    )
    allowed_tasks = fields.Json(
        required=True,
        default=lambda self: [],
        help="Task codes this agent may perform. Any other task is refused.",
    )
    denied_tasks = fields.Json(
        default=lambda self: [],
        help="Task codes this agent may never perform.",
    )
    group_id = fields.Many2one("res.groups", required=True, ondelete="restrict")
    company_ids = fields.Many2many(
        "res.company",
        "sgc_agent_role_company_rel",
        "role_id",
        "company_id",
        string="Client Companies",
        help="Companies this agent may work on. Empty means the agent is not "
        "allowed to touch any company until a client is assigned.",
    )
    can_post = fields.Boolean(
        help="Only this role may post journal entries, and only with an "
        "approved posting approval.",
    )
    max_auto_post_aed = fields.Float(
        string="Auto-post Ceiling (AED)",
        default=0.0,
        help="Upper amount the agent may post without an accountant review.",
    )
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint("unique(code)", "This agent role already exists.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["allowed_tasks"] = normalize_tasks(vals.get("allowed_tasks"))
            vals["denied_tasks"] = normalize_tasks(vals.get("denied_tasks"))
        return super().create(vals_list)

    def write(self, vals):
        if "allowed_tasks" in vals:
            vals["allowed_tasks"] = normalize_tasks(vals["allowed_tasks"])
        if "denied_tasks" in vals:
            vals["denied_tasks"] = normalize_tasks(vals["denied_tasks"])
        return super().write(vals)

    def allowed_task_list(self):
        self.ensure_one()
        return normalize_tasks(self.allowed_tasks)

    def denied_task_list(self):
        self.ensure_one()
        return normalize_tasks(self.denied_tasks)

    def allows(self, task):
        """Return True when the role may perform ``task``."""
        self.ensure_one()
        if task in self.denied_task_list():
            return False
        return task in self.allowed_task_list()


class SgcAgentCredential(models.Model):
    """One API key for one agent.

    The plaintext key never enters the database: Odoo stores the hash and only
    the lookup index is kept here, so a database leak cannot be replayed.
    """

    _name = "sgc.agent.credential"
    _description = "Accounting Agent API Credential"
    _order = "create_date desc"

    name = fields.Char(required=True)
    role_id = fields.Many2one("sgc.agent.role", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    key_index = fields.Char(
        required=True,
        readonly=True,
        help="First characters of the key. The key itself is never stored.",
    )
    scope = fields.Char(default="rpc", readonly=True)
    tasks = fields.Json(
        default=lambda self: [],
        help="Task codes this key is authorised for.",
    )
    expiration_date = fields.Datetime()
    state = fields.Selection(
        [("active", "Active"), ("revoked", "Revoked")],
        default="active",
        required=True,
    )
    last_used_at = fields.Datetime(readonly=True)
    use_count = fields.Integer(default=0)
    note = fields.Text()

    _index_uniq = models.Constraint(
        "unique(key_index)", "This credential index already exists."
    )

    def action_revoke(self):
        for credential in self:
            credential.user_id.sudo()._revoke_agent_keys(credential.key_index)
            credential.write({"state": "revoked"})
        return True

    def action_touch(self):
        self.write({"last_used_at": fields.Datetime.now()})
        self.write({"use_count": self.use_count + 1})
        return True


class SgcAgentAudit(models.Model):
    """Audit trail of everything an agent did."""

    _name = "sgc.agent.audit"
    _description = "Accounting Agent Audit"
    _order = "create_date desc, id desc"

    agent_user_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    role_id = fields.Many2one("sgc.agent.role", required=True, ondelete="restrict")
    task = fields.Char(required=True)
    model_name = fields.Char(required=True)
    res_ids = fields.Char()
    result = fields.Selection(
        [("allowed", "Allowed"), ("refused", "Refused")],
        default="allowed",
        required=True,
    )
    details = fields.Json()
    create_date = fields.Datetime(default=fields.Datetime.now, index=True)

    @api.model
    def log(
        self,
        task,
        model_name,
        res_ids=None,
        result="allowed",
        details=None,
    ):
        """Record an agent action, keeping the trail short and factual."""
        user = self.env.user
        role = user.sgc_agent_role_id
        if not role:
            return self.browse()
        return self.sudo().create(
            {
                "agent_user_id": user.id,
                "role_id": role.id,
                "task": task,
                "model_name": model_name,
                "res_ids": ",".join(str(value) for value in (res_ids or [])) or False,
                "result": result,
                "details": details or {},
            }
        )


class SgcAgentReport(models.Model):
    """Report produced by the reporting agent."""

    _name = "sgc.agent.report"
    _description = "Accounting Agent Report"
    _order = "create_date desc"

    name = fields.Char(required=True)
    role_id = fields.Many2one("sgc.agent.role", ondelete="set null")
    company_id = fields.Many2one("res.company", ondelete="set null")
    period_start = fields.Date()
    period_end = fields.Date()
    payload = fields.Json()
    note = fields.Text()
    create_date = fields.Datetime(default=fields.Datetime.now, index=True)


class SgcAgentPostingApproval(models.Model):
    """Approval that lets the posting agent post one journal entry.

    The intake agent creates the request, an accountant approves it, and only
    then may the posting agent post the entry.
    """

    _name = "sgc.agent.posting.approval"
    _description = "Accounting Agent Posting Approval"
    _order = "create_date desc"

    name = fields.Char(required=True, default=lambda self: _("Agent posting request"))
    move_id = fields.Many2one("account.move", required=True, ondelete="cascade")
    role_id = fields.Many2one("sgc.agent.role", ondelete="set null")
    agent_run_id = fields.Char()
    source_sha256 = fields.Char()
    checks = fields.Json(default=lambda self: {})
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    requested_by_id = fields.Many2one("res.users", ondelete="set null")
    approved_by_id = fields.Many2one("res.users", ondelete="set null")
    approved_at = fields.Datetime()
    note = fields.Text()
    create_date = fields.Datetime(default=fields.Datetime.now)

    def action_approve(self):
        for approval in self:
            if approval.state != "pending":
                raise UserError(
                    _("Only a pending posting request can be approved.")
                )
            if not self.env.user.has_group(
                "sgc_accounting_agents.group_sgc_agency_manager"
            ):
                raise UserError(
                    _("Only an agency manager can approve a posting request.")
                )
            approval.write(
                {
                    "state": "approved",
                    "approved_by_id": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                }
            )
        return True

    def action_reject(self):
        for approval in self:
            if not self.env.user.has_group(
                "sgc_accounting_agents.group_sgc_agency_manager"
            ):
                raise UserError(
                    _("Only an agency manager can reject a posting request.")
                )
            approval.write(
                {
                    "state": "rejected",
                    "approved_by_id": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                }
            )
        return True
