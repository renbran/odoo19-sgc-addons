from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    mailcow_mailbox_ids = fields.One2many(
        "mailcow.mailbox", "employee_id", string="Mailcow Mailboxes")
    mailcow_mailbox_count = fields.Integer(
        compute="_compute_mailcow_mailbox_count")

    def _compute_mailcow_mailbox_count(self):
        counts = dict(self.env["mailcow.mailbox"]._read_group(
            [("employee_id", "in", self.ids)],
            groupby=["employee_id"], aggregates=["__count"]))
        for rec in self:
            rec.mailcow_mailbox_count = counts.get(rec, 0)

    def action_open_mailcow_mailboxes(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": "Mailboxes",
            "res_model": "mailcow.mailbox",
            "context": {
                "default_employee_id": self.id,
                "default_name": self.name,
                "default_user_id": self.user_id.id,
                "default_local_part": (
                    self.work_email.split("@")[0].lower()
                    if self.work_email else False),
            },
        }
        if self.mailcow_mailbox_count == 1:
            action.update({
                "view_mode": "form",
                "res_id": self.mailcow_mailbox_ids[0].id,
            })
        elif self.mailcow_mailbox_count:
            action.update({
                "view_mode": "list,form",
                "domain": [("employee_id", "=", self.id)],
            })
        else:
            # No mailbox yet: open a prefilled creation form.
            action["view_mode"] = "form"
        return action
