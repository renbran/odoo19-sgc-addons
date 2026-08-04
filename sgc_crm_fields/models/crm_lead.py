# -*- coding: utf-8 -*-
# SGC CRM Fields — custom fields on crm.lead for the signature pipeline.
# Field list MUST stay in sync with 10-signature/odoo-mapping.yaml.

from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # --- Zoho Sign envelope linkage -------------------------------------
    x_envelope_id = fields.Char(
        string='Zoho Sign Envelope ID',
        help='Envelope ID assigned by Zoho Sign when the proposal is sent for signature.',
        copy=False, index=True, tracking=True,
    )
    x_signed_pdf_hash = fields.Char(
        string='Signed PDF SHA-256',
        help='SHA-256 of the signed PDF as downloaded from Zoho Sign (hash chain verification).',
        copy=False,
    )
    x_frozen_pdf_hash = fields.Char(
        string='Frozen PDF SHA-256',
        help='SHA-256 of the frozen sent PDF (hash chain origin). Written at send time.',
        copy=False,
    )

    # --- Timeline --------------------------------------------------------
    x_sent_date = fields.Datetime(
        string='Sent for Signature',
        help='When the proposal envelope was sent to the signatories.',
        copy=False, tracking=True,
    )
    x_completed_date = fields.Datetime(
        string='Fully Executed At',
        help='When both the client and SGC signatories completed the envelope.',
        copy=False, tracking=True,
    )

    # --- Signatories -----------------------------------------------------
    x_signing_actor_client = fields.Char(
        string='Client Signatory',
        help='Name of the client signatory as recorded by Zoho Sign.',
        copy=False,
    )
    x_signing_actor_sgc = fields.Char(
        string='SGC Signatory',
        help='Name of the SGC authorised signatory who countersigned.',
        copy=False,
    )

    # --- Decline ---------------------------------------------------------
    x_decline_reason = fields.Text(
        string='Decline Reason',
        help='Reason provided when the proposal was declined, if any.',
        copy=False,
    )

    # --- Commercial terms (parsed from the executed Order Form) ----------
    x_contract_term_months = fields.Integer(
        string='Initial Term (months)',
        help='Initial subscription term in months from the Order Form.',
    )
    x_subscription_fee = fields.Float(
        string='Subscription Fee (AED)',
        help='Total monthly subscription fee (platform + recovery) from the Order Form.',
    )
    x_platform_fee = fields.Float(
        string='Platform Fee (AED)',
        help='Platform component of the monthly subscription fee.',
    )
    x_recovery_fee = fields.Float(
        string='Recovery Fee (AED)',
        help='Recovery component of the monthly subscription fee.',
    )
    x_mobilisation_amount = fields.Float(
        string='Mobilisation Amount (AED)',
        help='One-off mobilisation amount from the Order Form.',
    )
    x_cadence = fields.Selection(
        selection=[
            ('quarterly_in_advance', 'Quarterly in advance'),
            ('monthly_in_advance', 'Monthly in advance'),
            ('annual_in_advance', 'Annual in advance'),
        ],
        string='Payment Cadence',
        help='Payment cadence agreed in the Order Form.',
    )
    x_edition = fields.Selection(
        selection=[
            ('community', 'Odoo Community'),
            ('enterprise', 'Odoo Enterprise'),
        ],
        string='Odoo Edition',
        help='Edition offered in the proposal. Never describe Community as Enterprise (G36).',
    )
    x_upgrade_policy = fields.Text(
        string='Upgrade Policy',
        help='Community-to-Enterprise upgrade policy text from the Order Form.',
    )
    x_kickoff_date = fields.Date(
        string='Kickoff Date',
        help='Target delivery kickoff date from the Order Form.',
    )

    # --- Invoicing -------------------------------------------------------
    x_invoice_id = fields.Many2one(
        comodel_name='account.move',
        string='Mobilisation Invoice',
        help='Draft mobilisation invoice created at completion. Posted by a human (G51).',
        copy=False, readonly=True,
    )
