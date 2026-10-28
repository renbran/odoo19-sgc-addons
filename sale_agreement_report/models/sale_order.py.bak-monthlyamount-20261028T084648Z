# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    agreement_ids = fields.One2many(
        'sale.agreement',
        'sale_order_id',
        string='Yearly Agreements',
    )
    agreement_count = fields.Integer(
        string='Agreement Count',
        compute='_compute_agreement_count',
    )

    # -------------------------------------------------------------------------
    # Agreement Fields - Quotation Details
    # (name, date_order, validity_date, user_id are standard Odoo fields)
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Agreement Fields - Project Details
    # (partner_id provides: company name, contact, email, phone, address)
    # -------------------------------------------------------------------------
    agreement_contact_person = fields.Char(
        string="Agreement Contact Person",
        help="Contact person name for the agreement (if different from partner contact)",
    )
    agreement_job_title = fields.Char(
        string="Contact Job Title",
        help="Job title of the contact person",
    )
    agreement_date = fields.Date(
        string="Agreement Date",
        default=fields.Date.context_today,
        help="Date when the agreement is signed",
    )
    project_start_date = fields.Date(
        string="Project Start Date",
        help="Expected project start date",
    )
    golive_date = fields.Date(
        string="Go-Live Target Date",
        help="Target date for system go-live",
    )
    num_users = fields.Integer(
        string="Number of Users",
        default=1,
        help="Number of users for the Odoo system",
    )
    odoo_modules = fields.Text(
        string="Odoo Modules Required",
        help="List of Odoo modules to be implemented (e.g., Sales, Inventory, Accounting, CRM)",
    )

    monthly_subscription_amount = fields.Monetary(
        string="Monthly Subscription Amount",
        compute='_compute_monthly_subscription_amount',
        store=True,
        currency_field='currency_id',
        help="Current monthly commercial amount fetched from the sales order total.",
    )

    # -------------------------------------------------------------------------
    # Agreement Fields - Signature
    # -------------------------------------------------------------------------
    client_signer_name = fields.Char(
        string="Client Signer Name",
        help="Name and title of the person signing on behalf of client",
    )
    client_sign_date = fields.Date(
        string="Client Signature Date",
        help="Date when client signed the agreement",
    )
    provider_signer_name = fields.Char(
        string="Provider Signer Name",
        default="SGC TECH AI - Authorized Representative",
        help="Name and title of the person signing on behalf of SGC TECH AI",
    )
    provider_sign_date = fields.Date(
        string="Provider Signature Date",
        help="Date when provider signed the agreement",
    )

    # -------------------------------------------------------------------------
    # Agreement Fields - Value Proposition
    # -------------------------------------------------------------------------
    value_items = fields.Text(
        string="Value Proposition Items",
        default="""AI-Native Odoo system - Production-ready
14-Day Deployment - 10x faster than industry
150-200% ROI Guaranteed
Complete data migration with AI validation
User training included
2 custom AI-powered integrations
Ongoing priority support
Enterprise-grade architecture
40-80 hours saved monthly
90%+ error reduction""",
        help="List of value proposition items (one per line)",
    )

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------
    @api.depends('amount_total')
    def _compute_monthly_subscription_amount(self):
        for order in self:
            order.monthly_subscription_amount = order.amount_total or 0.0

    # -------------------------------------------------------------------------
    # Onchange Methods
    # -------------------------------------------------------------------------
    @api.onchange('partner_id')
    def _onchange_partner_agreement_fields(self):
        """Auto-fill agreement contact fields from partner."""
        if self.partner_id:
            # Use partner's contact name if available
            if self.partner_id.child_ids:
                contact = self.partner_id.child_ids[0]
                self.agreement_contact_person = contact.name
                self.agreement_job_title = contact.function or ''
            else:
                self.agreement_contact_person = self.partner_id.name
                self.agreement_job_title = self.partner_id.function or ''

    @api.onchange('project_start_date')
    def _onchange_project_start_date(self):
        """Auto-calculate go-live date (14 business days from start)."""
        if self.project_start_date:
            # Add 14 calendar days (approximately 14 business days)
            from datetime import timedelta
            self.golive_date = self.project_start_date + timedelta(days=21)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    def _get_value_items_list(self):
        """Return value proposition items as a list."""
        self.ensure_one()
        if self.value_items:
            return [item.strip() for item in self.value_items.split('\n') if item.strip()]
        return []

    def _get_modules_list(self):
        """Return Odoo modules as a list."""
        self.ensure_one()
        if self.odoo_modules:
            # Split by comma or newline
            modules = self.odoo_modules.replace('\n', ',').split(',')
            return [m.strip() for m in modules if m.strip()]
        return []

    def _get_service_term_text(self):
        self.ensure_one()
        start_date = self.project_start_date or self.agreement_date or fields.Date.context_today(self)
        end_date = self.golive_date or self.validity_date or False
        if end_date:
            return '%s to %s' % (start_date, end_date)
        return 'Commencing on %s and continuing on a recurring monthly basis until terminated in accordance with this Agreement.' % start_date

    def _compute_agreement_count(self):
        for order in self:
            order.agreement_count = len(order.agreement_ids)

    def action_view_agreements(self):
        self.ensure_one()
        action = self.env.ref('sale_agreement_report.action_sale_agreement').read()[0]
        action['domain'] = [('sale_order_id', '=', self.id)]
        action['context'] = {
            'default_partner_id': self.partner_id.commercial_partner_id.id,
            'default_sale_order_id': self.id,
            'default_agreement_year': (self.agreement_date or fields.Date.context_today(self)).year,
        }
        return action
