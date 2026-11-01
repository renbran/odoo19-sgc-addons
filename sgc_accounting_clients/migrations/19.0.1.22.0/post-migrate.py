# -*- coding: utf-8 -*-
"""Give every existing subscription its one portal owner, and put Chart of
Accounts uploads that were only skipped in front of that owner for approval."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Users = env["res.users"]  # active logins only: an archived one owns nothing
    clients = env["sgc.accounting.client"].with_context(active_test=False).search(
        [("owner_user_id", "=", False)]
    )
    for client in clients:
        logins = Users.search([
            ("partner_id.commercial_partner_id", "=", client.partner_id.commercial_partner_id.id),
            ("share", "=", True),
        ])
        # The verified owner of the database link wins; otherwise the only one.
        owner = logins.filtered(lambda user: user.login.lower() == (client.link_owner_login or "")) or (
            logins if len(logins) == 1 else Users
        )
        if owner:
            client.owner_user_id = owner
        else:
            client.message_post(body=(
                "No portal owner was set (%s portal logins). Set Portal Owner to the login "
                "this subscription was registered with; until then nobody can open it in "
                "the portal." % len(logins)
            ))
    cr.execute(
        "UPDATE sgc_accounting_upload SET booking_state = 'approval' "
        "WHERE doc_type = 'chart_of_accounts' "
        "AND (booking_state IS NULL OR booking_state IN ('pending', 'waiting', 'skipped'))"
    )
