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
        the public lookup index and deleted directly. The table name is bound
        as a SQL identifier rather than formatted into the statement, so it
        can never be interpreted as SQL.
        """
        if not key_index:
            return True
        from psycopg2 import sql
        table = sql.Identifier(self.env["res.users.apikeys"]._table)
        for user in self:
            self.env.cr.execute(
                sql.SQL("DELETE FROM {} WHERE user_id = %s AND index = %s").format(
                    table
                ),
                (user.id, key_index),
            )
        self.env.registry.clear_cache()
        return True
