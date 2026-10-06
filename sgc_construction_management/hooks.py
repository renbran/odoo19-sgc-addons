# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

MODULE_NAME = 'sgc_construction_management'


def post_init_hook(env):
    """Assign Odoo system admins to the Construction Administrator group on install."""
    admin_group = env.ref('%s.group_construction_admin' % MODULE_NAME, raise_if_not_found=False)
    if admin_group:
        system_group = env.ref('base.group_system', raise_if_not_found=False)
        if system_group:
            admin_users = env['res.users'].search([
                ('group_ids', 'in', [system_group.id]),
                ('group_ids', 'not in', [admin_group.id]),
            ])
            if admin_users:
                env.cr.execute(
                    "INSERT INTO res_groups_users_rel (gid, uid) "
                    "SELECT %s, uid FROM unnest(%s::int[]) AS uid "
                    "ON CONFLICT DO NOTHING",
                    (admin_group.id, admin_users.ids),
                )

    _ensure_company_currency_active(env)
    _assign_default_expense_accounts(env)
    _wire_demo_integrations(env)


def _ensure_company_currency_active(env):
    """The demo-wiring step below posts real invoices/bills in the company
    currency. If that currency is inactive (e.g. AED disabled on a fresh
    Odoo install where only USD/EUR ship active by default), every
    action_create_invoice/action_create_bill call below fails with
    'cannot validate a document with an inactive currency' - caught by the
    broad except blocks and only logged as a warning, leaving total_billed/
    total_expenses silently stuck at zero with no visible error. Activate it
    up front so the financial KPIs actually populate."""
    currency = env.company.currency_id
    if currency and not currency.active:
        currency.write({'active': True})
        _logger.info("Activated currency %s for company %s so demo invoices/bills can post.",
                     currency.name, env.company.name)


def _assign_default_expense_accounts(env):
    """Expense categories need a default expense account before action_create_bill
    can turn an approved expense into a vendor bill. Pick any expense-type account
    on the current company so this works out of the box on any chart of accounts."""
    categories = env['construction.expense.category'].search([('property_account_expense_id', '=', False)])
    if not categories:
        return
    account = env['account.account'].search([('account_type', '=', 'expense')], limit=1)
    if account:
        categories.write({'property_account_expense_id': account.id})
    else:
        _logger.warning("No expense-type account found; construction.expense.category records "
                         "were left without a default property_account_expense_id.")


def _wire_demo_integrations(env):
    """If demo data is present, run the real business actions on it so the demo
    dataset ships with live cross-model links (invoices/bills) instead of just
    isolated draft records. Moves are also posted so the project dashboard's
    financial KPIs (total_billed/total_expenses/margin/budget_consumed), which
    only read posted account.move.line rows, are populated from real data."""
    ref = lambda xid: env.ref('%s.%s' % (MODULE_NAME, xid), raise_if_not_found=False)

    def _post_move(record, xid):
        if record.move_id and record.move_id.state == 'draft':
            record.move_id.action_post()

    def _invoice(record, xid, prep=None):
        if not record or record.move_id:
            return
        try:
            if prep:
                prep(record)
            record.action_create_invoice()
            _post_move(record, xid)
        except Exception:
            _logger.warning("Could not auto-create/post invoice for demo record %s", xid, exc_info=True)

    def _bill(record, xid):
        if not record or record.move_id:
            return
        try:
            record.action_create_bill()
            _post_move(record, xid)
        except Exception:
            _logger.warning("Could not auto-create/post vendor bill for demo record %s", xid, exc_info=True)

    def _approve_ra_billing(record):
        if record.state == 'draft':
            record.action_submit()
        if record.state == 'submitted':
            record.action_approve()

    def _approve_progress_billing(record):
        if record.state == 'draft':
            record.action_approve()

    _invoice(ref('demo_rab_1'), 'demo_rab_1', _approve_ra_billing)

    # Al Noor: the steel subcontract is billed progressively (interim
    # certificates against work actually done), not as a single lump-sum bill
    # for the full contract value - real subcontract billing doesn't front-load
    # the entire contract before the work is complete.
    for exp_xid in (
        'demo_exp_equipment', 'demo_exp_labour', 'demo_exp_overhead', 'demo_exp_material',
        'demo_exp_alnoor_steel_progress',
    ):
        _bill(ref(exp_xid), exp_xid)

    _invoice(ref('demo_progress_billing_bridge'), 'demo_progress_billing_bridge', _approve_progress_billing)
    _invoice(ref('demo_rab_2'), 'demo_rab_2')

    for exp_xid in ('demo_exp_bridge_equipment', 'demo_exp_bridge_labour', 'demo_exp_bridge_material'):
        _bill(ref(exp_xid), exp_xid)

    # Marina Heights: this RA bill is EXPECTED to fail - a failed quality check on
    # the project blocks invoicing. The exception is the demo, not a bug, so it's
    # logged at info level and the record is left in its blocked 'approved' state.
    rab_marina = ref('demo_rab_marina_1')
    if rab_marina and not rab_marina.move_id:
        try:
            rab_marina.action_create_invoice()
        except Exception:
            _logger.info("Demo RA billing %s intentionally blocked by failed quality check.", rab_marina.name)

    for exp_xid in (
        'demo_exp_marina_subcontract_progress', 'demo_exp_marina_legal', 'demo_exp_marina_rework',
        'demo_exp_alkhail_equipment', 'demo_exp_alkhail_labour', 'demo_exp_alkhail_material',
    ):
        _bill(ref(exp_xid), exp_xid)

    _invoice(ref('demo_progress_billing_alkhail'), 'demo_progress_billing_alkhail', _approve_progress_billing)
