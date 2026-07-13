from odoo import models

# All modules that are pycache-only recoveries (no .py source files, only .pyc).
# Their DB records (views, security, rules, assets, data) must NOT be deleted
# during --update all, because their manifests have empty data:[] lists.
# Remove a module from this set only once its full source and XML data files
# have been reconstructed and verified.
_PYCACHE_ONLY_MODULES = frozenset({
    # Core protected modules (originally hardened)
    'kyc_management', 'formio',
    # pycache-only modules from osus17 extra-addons
    'account_debit_note', 'account_line_view', 'account_reconcile_model_oca',
    'account_reconcile_oca', 'account_statement_base', 'accounting_pdf_reports',
    'ace_remove_powered_by_odoo', 'all_in_one_dynamic_custom_fields',
    'announcement_banner', 'auto_database_backup', 'base_account_budget',
    'commission_ax', 'commission_lines', 'comprehensive_greetings',
    'contact_validation', 'crm_dashboard', 'custom_background',
    'dark_mode_knk', 'database_cleanup', 'gsk_automatic_mail_server',
    'hide_menu_user', 'hr_appraisal_questionnaire', 'hr_employment_certificate',
    'hr_leave_application', 'hr_memos', 'hr_payroll_account_community',
    'hr_payroll_community', 'hr_uae', 'ingenuity_invoice_qr_code',
    'invoice_report_for_realestate', 'ks_dynamic_financial_report', 'le_sale_type',
    'muk_web_appsbar', 'muk_web_chatter', 'muk_web_colors', 'muk_web_dialog',
    'muk_web_theme', 'om_account_accountant_v17', 'om_account_followup',
    'order_invoice_manual_link', 'osus_order_report', 'osus_pdf_global_fixes',
    'osus_report_header_footer', 'payment_account_enhanced', 'pretty_buttons',
    'rental_management', 'rental_portal_syndication', 'report_xlsx',
    'sale_deal_tracking', 'sale_invoice_detail', 'sale_invoice_due_date_reminder',
    'sale_order_invoicing_qty_percentage', 'sales_invoice_fix',
    'statement_report', 'tk_partner_ledger', 'upper_unicity_partner_product',
    'web_login_styles', 'webhook_crm',
})


class IrModelData(models.Model):
    _inherit = 'ir.model.data'

    def _process_end_unlink_record(self, record):
        # `record` is the real ORM record about to be deleted (any model).
        # `self` is the ir.model.data entry that references it.
        if record._name == 'res.groups' and record.exists():
            self.env.cr.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM rule_group_rel WHERE group_id = %s
                ) OR EXISTS (
                    SELECT 1 FROM ir_model_access WHERE group_id = %s
                )
                """,
                (record.id, record.id),
            )
            if self.env.cr.fetchone()[0]:
                return None

        # Recovered modules currently restore only a verified subset of their
        # source data. Keep ALL their owned records until the full source tree
        # is reconstructed, instead of letting update cleanup purge live data.
        if self and getattr(self, 'module', None) in _PYCACHE_ONLY_MODULES:
            return None
        return super()._process_end_unlink_record(record)

