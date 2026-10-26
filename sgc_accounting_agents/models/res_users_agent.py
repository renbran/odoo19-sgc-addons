# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsersAgent(models.Model):
    """Link a service user to its agent role."""

    _inherit = "res.users"

    sgc_agent_role_id = fields.Many2one(
        "sgc.agent.role",
        string="Agent Role",
        ondelete="set null",
        help="Set only for service users that run an accounting agent.",
    )

    def _revoke_agent_keys(self, key_index):
        """Remove the API key that matches ``key_index``.

        Odoo keeps only the hash of an API key, so the row is located through
        the public lookup index and deleted directly.
        """
        if not key_index:
            return True
        table = self.env["res.users.apikeys"]._table
        for user in self:
            self.env.cr.execute(
                "DELETE FROM %s WHERE user_id = %%s AND index = %%s" % table,
                (user.id, key_index),
            )
        self.env.registry.clear_cache()
        return True
