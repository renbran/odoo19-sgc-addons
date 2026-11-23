# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Personal Information
    x_date_of_birth = fields.Date(
        string='Date of Birth',
        help="Date of birth of the contact"
    )
    x_place_of_birth = fields.Char(
        string='Place of Birth',
        help="Place where the contact was born"
    )
    x_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender', help="Gender of the contact")
    x_aliases = fields.Char(
        string='Aliases',
        help="Any aliases or alternative names"
    )

    # Passport Information
    x_passport_number = fields.Char(
        string='Passport Number',
        help="Passport number"
    )
    x_passport_country_id = fields.Many2one(
        'res.country',
        string='Passport Country of Issue',
        help="Country that issued the passport"
    )
    x_passport_issue_date = fields.Date(
        string='Passport Issue Date',
        help="Date when passport was issued"
    )
    x_passport_expiry_date = fields.Date(
        string='Passport Expiry Date',
        help="Date when passport expires"
    )
    x_nationality_id = fields.Many2one(
        'res.country',
        string='Nationality',
        help="Country of nationality"
    )

    # UAE Residency
    x_residency_visa_no = fields.Char(
        string='Residency Visa Number',
        help="UAE residency visa number"
    )
    x_emirates_id = fields.Char(
        string='Emirates ID Number',
        help="UAE Emirates ID number"
    )
    x_residency_expiry_date = fields.Date(
        string='Residency Expiry Date',
        help="Date when UAE residency expires"
    )
    x_passport_document = fields.Binary(
        string='Passport Document',
        attachment=True,
        help="Uploaded passport copy"
    )
    x_emirates_id_document = fields.Binary(
        string='Emirates ID Document',
        attachment=True,
        help="Uploaded Emirates ID copy"
    )
    x_proof_of_address_document = fields.Binary(
        string='Proof of Address',
        attachment=True,
        help="Proof of address document uploaded during KYC"
    )

    # Employment Details
    x_occupation = fields.Char(
        string='Occupation',
        help="Current occupation or job title"
    )
    x_years_in_role = fields.Integer(
        string='Years in Present Role',
        help="Number of years in current position"
    )
    x_employer_name = fields.Char(
        string='Employer/Establishment Name',
        help="Name of the employer or establishment"
    )
    x_employer_address = fields.Text(
        string='Employer/Establishment Address',
        help="Address of the employer or establishment"
    )

    # Financial Information
    x_currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help="Currency for financial amounts"
    )
    x_source_of_funds = fields.Many2many(
        'kyc.source.funds',
        'partner_source_funds_rel',
        'partner_id',
        'source_id',
        string='Source of Funds',
        help="Select all applicable sources of funds"
    )
    x_source_of_wealth = fields.Many2many(
        'kyc.source.wealth',
        'partner_source_wealth_rel',
        'partner_id',
        'source_id',
        string='Source of Wealth',
        help="Select all applicable sources of wealth"
    )
    x_annual_income = fields.Monetary(
        string='Annual Income',
        currency_field='x_currency_id',
        help="Annual income amount"
    )
    x_purpose_of_purchase = fields.Selection([
        ('end_use', 'End Use'),
        ('savings', 'Savings'),
        ('investment', 'Investment'),
        ('other', 'Other')
    ], string='Purpose of Purchase', help="Purpose for property purchase")
    x_payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('bank_transfer', 'Bank Transfer'),
        ('mortgage', 'Mortgage'),
        ('crypto', 'Crypto'),
        ('other', 'Other')
    ], string='Payment Method', help="Preferred payment method")
    x_politically_exposed_person = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
        ('other', 'Other')
    ], string='Politically Exposed Person',
       help="Are you currently or formerly a Politically Exposed Person?")
    x_is_pep = fields.Boolean(
        string='Is PEP',
        compute='_compute_is_pep',
        store=True,
        help="True if this person is a Politically Exposed Person"
    )
    x_pep_details = fields.Text(
        string='PEP Details',
        help="Details about PEP status if applicable"
    )

    # KYC Submission Information
    x_kyc_submission_date = fields.Date(
        string='KYC Submission Date',
        help="Date when KYC form was submitted"
    )
    x_kyc_signature = fields.Binary(
        string='KYC Signature',
        help="Digital signature from KYC form submission"
    )
    x_kyc_signature_pdf = fields.Binary(
        string='KYC Signature PDF',
        attachment=True,
        help="Generated PDF that embeds the submitted signature"
    )
    x_kyc_signed_at_location = fields.Char(
        string='KYC Signed At Location',
        help="Location where KYC form was signed"
    )
    x_kyc_document_id = fields.Char(
        string='KYC Document ID',
        help="Unique document identifier for KYC submission",
        copy=False
    )

    @api.depends('x_politically_exposed_person')
    def _compute_is_pep(self):
        """Compute boolean PEP status from selection field"""
        for record in self:
            record.x_is_pep = record.x_politically_exposed_person == 'yes'

    @api.constrains('x_passport_issue_date', 'x_passport_expiry_date')
    def _check_passport_dates(self):
        """Validate passport dates"""
        for record in self:
            if record.x_passport_issue_date and record.x_passport_expiry_date:
                if record.x_passport_issue_date >= record.x_passport_expiry_date:
                    raise ValidationError(_("Passport expiry date must be after issue date."))

    @api.constrains('x_date_of_birth')
    def _check_birth_date(self):
        """Validate birth date"""
        for record in self:
            if record.x_date_of_birth:
                if record.x_date_of_birth >= fields.Date.today():
                    raise ValidationError(_("Date of birth must be in the past."))

    @api.constrains('x_years_in_role')
    def _check_years_in_role(self):
        """Validate years in role"""
        for record in self:
            if record.x_years_in_role and record.x_years_in_role < 0:
                raise ValidationError(_("Years in role cannot be negative."))


class KycSourceFunds(models.Model):
    _name = 'kyc.source.funds'
    _description = 'KYC Source of Funds'
    _order = 'name'

    name = fields.Char(
        string='Source',
        required=True,
        help="Name of the source of funds"
    )
    description = fields.Text(
        string='Description',
        help="Detailed description of this source of funds"
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="If unchecked, this source will not be available for selection"
    )

    @api.constrains('name')
    def _check_name(self):
        """Validate source name"""
        for record in self:
            if not record.name or len(record.name.strip()) < 2:
                raise ValidationError(_("Source name must be at least 2 characters long."))


class KycSourceWealth(models.Model):
    _name = 'kyc.source.wealth'
    _description = 'KYC Source of Wealth'
    _order = 'name'

    name = fields.Char(
        string='Source',
        required=True,
        help="Name of the source of wealth"
    )
    description = fields.Text(
        string='Description',
        help="Detailed description of this source of wealth"
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="If unchecked, this source will not be available for selection"
    )

    @api.constrains('name')
    def _check_name(self):
        """Validate source name"""
        for record in self:
            if not record.name or len(record.name.strip()) < 2:
                raise ValidationError(_("Source name must be at least 2 characters long."))