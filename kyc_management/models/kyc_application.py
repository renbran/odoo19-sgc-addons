# -*- coding: utf-8 -*-
"""
KYC Application Model
Main model for KYC Enhanced module
Handles KYC application lifecycle and approval workflow
"""

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from base64 import b64encode
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging
import secrets
import uuid

_logger = logging.getLogger(__name__)


class KYCApplication(models.Model):
    """
    KYC Application Model
    
    Main model for managing KYC (Know Your Customer) applications.
    Supports complete lifecycle from submission through approval.
    
    State Machine:
    - draft: Initial creation, editable
    - submitted: Form submitted, awaiting review
    - pending_review: Officer reviewing
    - approved: KYC approved
    - rejected: KYC rejected with reason
    """
    
    _name = 'kyc.application'
    _description = 'KYC Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date DESC'

    _kyc_id_unique = models.Constraint(
        'UNIQUE(kyc_id)',
        'KYC ID must be unique.',
    )
    
    # ==================== BASIC INFORMATION ====================
    
    # Unique Identifiers
    kyc_id = fields.Char(
        string='KYC ID',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: str(uuid.uuid4())[:12].upper(),
        help='Unique KYC Application Identifier'
    )
    
    # Applicant Information
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact/Partner',
        required=True,
        ondelete='cascade',
        help='Link to the contact record'
    )
    
    email = fields.Char(
        string='Email Address',
        required=True,
        help='Primary email for communication'
    )

    # CRM Integration
    lead_id = fields.Many2one(
        'crm.lead',
        string='CRM Lead',
        ondelete='set null',
        help='Auto-created CRM lead from portal submission'
    )

    phone = fields.Char(
        string='Phone Number',
        required=True,
        help='Primary phone number'
    )
    
    # ==================== PERSONAL INFORMATION ====================
    
    # Name & Demographics
    first_name = fields.Char(
        string='First Name',
        required=True,
        help='First name of applicant'
    )
    
    last_name = fields.Char(
        string='Last Name',
        help='Last name of applicant'
    )
    
    date_of_birth = fields.Date(
        string='Date of Birth',
        help='Birth date (must be 18+ years)'
    )
    
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer Not to Say'),
    ], string='Gender', help='Gender of applicant')
    
    nationality_id = fields.Many2one(
        'res.country',
        string='Nationality',
        help='Country of nationality'
    )
    
    # ==================== IDENTIFICATION ====================
    
    # Passport
    passport_number = fields.Char(
        string='Passport Number',
        help='International passport number'
    )
    
    passport_country_id = fields.Many2one(
        'res.country',
        string='Passport Issuing Country',
        help='Country that issued the passport'
    )
    
    passport_issue_date = fields.Date(
        string='Passport Issue Date',
        help='When the passport was issued'
    )
    
    passport_expiry_date = fields.Date(
        string='Passport Expiry Date',
        help='When the passport expires'
    )
    
    passport_document = fields.Binary(
        string='Passport Copy',
        attachment=True,
        help='Digital copy of passport'
    )
    
    # Residency / Visa
    residency_visa_no = fields.Char(
        string='Residency / Visa No.',
        help='Residency permit or visa number'
    )

    residency_expiry_date = fields.Date(
        string='Residency Expiry Date',
        help='Expiry date of residency permit or visa'
    )

    place_of_birth = fields.Char(
        string='Place of Birth',
        help='City / Country of birth'
    )

    aliases = fields.Char(
        string='Aliases / Other Names',
        help='Any other known names or aliases'
    )

    # Emirates ID (UAE Specific)
    emirates_id = fields.Char(
        string='Emirates ID Number',
        help='UAE-specific national ID number'
    )
    
    emirates_id_document = fields.Binary(
        string='Emirates ID Copy',
        attachment=True,
        help='Digital copy of Emirates ID'
    )
    
    # Address Proof
    proof_of_address_document = fields.Binary(
        string='Proof of Address',
        attachment=True,
        help='Utility bill, lease, or residential proof'
    )
    
    # ==================== ADDRESSES ====================
    
    residential_address = fields.Text(
        string='Residential Address',
        help='Full residential address'
    )
    
    residential_city = fields.Char(
        string='City',
        help='City of residence'
    )
    
    residential_state = fields.Char(
        string='State/Emirate',
        help='State or emirate'
    )
    
    residential_country_id = fields.Many2one(
        'res.country',
        string='Country of Residence',
        help='Country of current residence'
    )
    
    residential_postal_code = fields.Char(
        string='Postal Code',
        help='Postal/zip code'
    )
    
    # ==================== EMPLOYMENT ====================
    
    employment_status = fields.Selection([
        ('employed', 'Employed'),
        ('self_employed', 'Self Employed'),
        ('unemployed', 'Unemployed'),
        ('student', 'Student'),
        ('retired', 'Retired'),
        ('other', 'Other'),
    ], string='Employment Status', help='Current employment status')
    
    occupation = fields.Char(
        string='Occupation/Job Title',
        help='Current job title or profession'
    )
    
    employer_name = fields.Char(
        string='Employer Name',
        help='Name of employer/company'
    )
    
    employer_address = fields.Text(
        string='Employer Address',
        help='Address of workplace'
    )
    
    years_in_role = fields.Integer(
        string='Years in Current Role',
        help='Number of years in current position'
    )
    
    # ==================== FINANCIAL INFORMATION ====================
    
    annual_income = fields.Monetary(
        string='Annual Income',
        currency_field='currency_id',
        help='Approximate annual income'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help='Currency for monetary fields'
    )
    
    source_of_funds_ids = fields.Many2many(
        'kyc.source.funds',
        'kyc_application_source_funds_rel',
        'kyc_id',
        'source_id',
        string='Source(s) of Funds',
        help='Primary sources of funds'
    )
    
    source_of_wealth_ids = fields.Many2many(
        'kyc.source.wealth',
        'kyc_application_source_wealth_rel',
        'kyc_id',
        'source_id',
        string='Source(s) of Wealth',
        help='Primary sources of accumulated wealth'
    )
    
    purpose_of_transaction = fields.Selection([
        ('real_estate_investment', 'Real Estate Investment'),
        ('personal_use', 'Personal Use'),
        ('savings_investment', 'Savings/Investment'),
        ('business_purpose', 'Business Purpose'),
        ('other', 'Other'),
    ], string='Purpose of Transaction', help='Purpose for engaging with us')
    
    payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('cash', 'Cash'),
        ('credit_card', 'Credit Card'),
        ('wire_transfer', 'Wire Transfer'),
        ('other', 'Other'),
    ], string='Preferred Payment Method', help='Preferred method of payment')
    
    # ==================== RISK ASSESSMENT ====================
    
    politically_exposed_person = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
        ('previously', 'Previously'),
    ], string='Politically Exposed Person (PEP)',
       help='Is applicant or related to a politically exposed person?')
    
    pep_details = fields.Text(
        string='PEP Details',
        help='Details about PEP status if applicable'
    )
    
    # ==================== SIGNATURES & CONSENT ====================
    
    signature_image = fields.Binary(
        string='Digital Signature',
        attachment=True,
        help='Canvas-drawn or uploaded signature'
    )
    
    signature_timestamp = fields.Datetime(
        string='Signature Date/Time',
        help='When signature was captured'
    )
    
    signature_location = fields.Char(
        string='Signature Location',
        help='Geographic location where signed (if available)'
    )
    
    # Consents
    consent_terms_conditions = fields.Boolean(
        string='Terms & Conditions',
        help='Applicant agrees to terms and conditions'
    )
    
    consent_privacy_policy = fields.Boolean(
        string='Privacy Policy',
        help='Applicant agrees to privacy policy'
    )
    
    consent_data_processing = fields.Boolean(
        string='Data Processing',
        help='Applicant consents to data processing'
    )
    
    consent_aml_kyc = fields.Boolean(
        string='AML/KYC Verification',
        help='Applicant consents to AML/KYC verification'
    )
    
    # ==================== WORKFLOW STATE ====================
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('pending_review', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True, 
       ondelete='restrict', help='Application status', tracking=True)
    
    # ==================== APPROVAL INFORMATION ====================
    
    approver_id = fields.Many2one(
        'res.users',
        string='Approver Officer',
        readonly=True,
        help='Compliance officer who approved/rejected'
    )
    
    approver_signature = fields.Binary(
        string='Approver Signature',
        attachment=True,
        help='Digital signature of the compliance officer who approved'
    )
    
    approver_signature_timestamp = fields.Datetime(
        string='Approver Signature Date/Time',
        readonly=True,
        help='When the approver signed'
    )
    
    # ==================== TOKEN FIELDS (for email one-click actions) ====================
    
    approval_token = fields.Char(
        string='Approval Token',
        copy=False,
        readonly=True,
        help='Secure token for one-click email approve/reject'
    )
    
    token_expiry = fields.Datetime(
        string='Token Expiry',
        copy=False,
        readonly=True,
        help='When the approval token expires'
    )
    
    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True,
        help='When the application was approved/rejected'
    )
    
    rejection_reason = fields.Text(
        string='Rejection Reason',
        readonly=True,
        help='Why the application was rejected'
    )
    
    rejection_suggestions = fields.Text(
        string='Suggested Corrections',
        readonly=True,
        help='Suggestions for resubmission if rejected'
    )
    
    # Master Record
    is_migrated_to_contact = fields.Boolean(
        string='Migrated to Contact',
        readonly=True,
        help='Whether this KYC was migrated to contact record'
    )
    
    migration_date = fields.Datetime(
        string='Migration Date',
        readonly=True,
        help='When data was migrated to contact'
    )
    
    # ==================== SUBMISSION TIMESTAMP ====================
    
    submitted_date = fields.Datetime(
        string='Submission Date',
        readonly=True,
        help='When applicant submitted the form'
    )
    
    # ==================== COMPUTED FIELDS ====================
    
    age = fields.Integer(
        string='Age',
        compute='_compute_age',
        help='Calculated age based on date of birth'
    )
    
    is_passport_valid = fields.Boolean(
        string='Passport Valid',
        compute='_compute_passport_validity',
        help='Whether passport is currently valid'
    )
    
    is_kyc_complete = fields.Boolean(
        string='KYC Complete',
        compute='_compute_kyc_complete',
        help='Whether all required fields are filled'
    )
    
    days_pending = fields.Integer(
        string='Days Pending',
        compute='_compute_days_pending',
        help='Number of days application has been pending'
    )
    
    # ==================== AUDIT FIELDS ====================
    
    user_id = fields.Many2one(
        'res.users',
        string='Submitting User',
        readonly=True,
        help='User who submitted the application'
    )
    
    # ==================== COMPUTED METHODS ====================
    
    @api.depends('date_of_birth')
    def _compute_age(self):
        """Calculate age from date of birth"""
        today = datetime.now().date()
        for record in self:
            if record.date_of_birth:
                age = today.year - record.date_of_birth.year
                if (today.month, today.day) < (record.date_of_birth.month, record.date_of_birth.day):
                    age -= 1
                record.age = age
            else:
                record.age = 0
    
    @api.depends('passport_expiry_date')
    def _compute_passport_validity(self):
        """Check if passport is currently valid"""
        today = datetime.now().date()
        for record in self:
            if record.passport_expiry_date:
                record.is_passport_valid = record.passport_expiry_date >= today
            else:
                record.is_passport_valid = False
    
    @api.depends('first_name', 'email', 'date_of_birth', 'passport_number',
                'residential_address', 'signature_image', 'consent_terms_conditions',
                'partner_id', 'phone')
    def _compute_kyc_complete(self):
        """Check if minimum required fields are completed for submission"""
        for record in self:
            required_fields = [
                record.partner_id,
                record.first_name,
                record.email,
                record.phone,
                record.signature_image,
                record.consent_terms_conditions,
            ]
            record.is_kyc_complete = all(required_fields)
    
    @api.depends('submitted_date')
    def _compute_days_pending(self):
        """Calculate days pending since submission"""
        for record in self:
            if record.submitted_date and record.state in ('submitted', 'pending_review'):
                days = (datetime.now() - record.submitted_date).days
                record.days_pending = max(days, 0)
            else:
                record.days_pending = 0
    
    # ==================== CONSTRAINTS & VALIDATIONS ====================
    
    @api.constrains('date_of_birth')
    def _check_minimum_age(self):
        """Validate minimum age requirement (18+)"""
        for record in self:
            if record.date_of_birth:
                today = datetime.now().date()
                age = today.year - record.date_of_birth.year
                if (today.month, today.day) < (record.date_of_birth.month, record.date_of_birth.day):
                    age -= 1
                
                if age < 18:
                    raise ValidationError(_('Applicant must be at least 18 years old.'))
    
    @api.constrains('passport_issue_date', 'passport_expiry_date')
    def _check_passport_dates(self):
        """Validate passport date logic"""
        for record in self:
            if record.passport_issue_date and record.passport_expiry_date:
                if record.passport_issue_date >= record.passport_expiry_date:
                    raise ValidationError(
                        _('Passport expiry date must be after the issue date.')
                    )
    
    @api.constrains('email')
    def _check_email_format(self):
        """Validate email format"""
        _EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
        for record in self:
            if record.email and not _EMAIL_RE.match(record.email):
                raise ValidationError(_('Invalid email address format.'))

    @api.constrains(
        'consent_terms_conditions', 'consent_privacy_policy',
        'consent_data_processing', 'consent_aml_kyc', 'state'
    )
    def _check_consents_on_submit(self):
        """All four consents are mandatory when the application is submitted or beyond."""
        for record in self:
            if record.state not in ('draft',):
                if not (record.consent_terms_conditions and
                        record.consent_privacy_policy and
                        record.consent_data_processing and
                        record.consent_aml_kyc):
                    raise ValidationError(
                        _('All consent checkboxes (Terms & Conditions, Privacy Policy, '
                          'Data Processing, and AML/KYC Verification) must be accepted '
                          'before submitting the application.')
                    )

    @api.constrains('state', 'emirates_id', 'passport_number', 'passport_country_id')
    def _check_identity_minimum_for_submission(self):
        """For submitted+ records, require Emirates ID or Passport number+country."""
        for record in self:
            if record.state == 'draft':
                continue
            has_emirates_id = bool(record.emirates_id)
            has_passport_pair = bool(record.passport_number and record.passport_country_id)
            if not has_emirates_id and not has_passport_pair:
                raise ValidationError(
                    _('Provide Emirates ID, or Passport Number with Passport Issuing Country, before submission.')
                )

    @api.constrains('annual_income')
    def _check_annual_income(self):
        """Annual income must be non-negative."""
        for record in self:
            if record.annual_income is not None and record.annual_income < 0:
                raise ValidationError(_('Annual income cannot be negative.'))

    @api.constrains('years_in_role')
    def _check_years_in_role(self):
        """Years in role must be non-negative."""
        for record in self:
            if record.years_in_role and record.years_in_role < 0:
                raise ValidationError(_('Years in current role cannot be negative.'))
    
    # ==================== STATE TRANSITION METHODS ====================
    
    def action_submit(self):
        """Submit KYC application for review"""
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft applications can be submitted.'))
            
            if not record.is_kyc_complete:
                raise UserError(_('Please complete all required fields before submitting.'))
            
            # Require at least one identity document (passport copy or Emirates ID copy)
            if not record.passport_document and not record.emirates_id_document:
                raise UserError(
                    _('At least one identity document is required to submit your KYC application. '
                      'Please upload a Passport Copy or an Emirates ID Copy (or both).')
                )
            
            record.write({
                'state': 'submitted',
                'submitted_date': fields.Datetime.now(),
                'user_id': self.env.user.id,
            })
            
            # Generate approval token for email one-click links
            record._generate_approval_token()
            
            # Log activity
            record.message_post(
                body=_('KYC application submitted for review'),
                message_type='notification'
            )
            
            # Trigger notification to applicant
            record._notify_submission()
            
            # Auto-create kyc.approval record and notify compliance officer
            record._create_approval_and_notify_officer()
        
        return True
    
    def action_mark_pending_review(self):
        """Mark application as pending review (by officer)"""
        for record in self:
            if record.state != 'submitted':
                raise UserError(_('Only submitted applications can be marked as pending.'))
            
            record.write({
                'state': 'pending_review',
            })
            
            record.message_post(
                body=_('Application marked as pending review'),
                message_type='notification'
            )
    
    def action_approve(self):
        """Approve KYC application"""
        for record in self:
            if record.state not in ('submitted', 'pending_review'):
                raise UserError(_('Only submitted/pending applications can be approved.'))
            
            record.write({
                'state': 'approved',
                'approver_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })
            
            # Migrate to contact record
            record._migrate_to_contact()
            
            record.message_post(
                body=_('KYC application approved'),
                message_type='notification'
            )
            
            # Trigger approval notification
            record._notify_approval()
        
        return True
    
    def action_reject(self):
        """Open rejection wizard"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject KYC Application'),
            'res_model': 'kyc.rejection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_kyc_id': self.id},
        }

    def action_reset_to_draft(self):
        """Reset an approved or rejected application back to Draft for correction.

        Only KYC Admins can perform this action. Clears all approval/rejection
        data so the application can be edited and re-submitted.
        """
        for record in self:
            if record.state not in ('approved', 'rejected'):
                raise UserError(_('Only approved or rejected applications can be reset to draft.'))
            record.write({
                'state': 'draft',
                'approver_id': False,
                'approval_date': False,
                'rejection_reason': False,
                'rejection_suggestions': False,
                'submitted_date': False,
            })
            record.message_post(
                body=_('Application reset to Draft by %s for correction.') % self.env.user.name,
                message_type='notification',
            )
        return True

    # ==================== HELPER METHODS ====================
    
    def _migrate_to_contact(self):
        """Migrate approved KYC data to the linked contact record.

        This is the ONLY place where KYC form data is written to res.partner.
        It runs after an officer approves the application.
        """
        for record in self:
            partner = record.partner_id
            if not partner:
                continue

            # Build partner vals — only write non-empty values
            partner_vals = {}

            # Personal information
            if record.date_of_birth:
                partner_vals['x_date_of_birth'] = record.date_of_birth
            if record.gender and record.gender != 'prefer_not_to_say':
                partner_vals['x_gender'] = record.gender
            if record.nationality_id:
                partner_vals['x_nationality_id'] = record.nationality_id.id

            # Passport
            if record.passport_number:
                partner_vals['x_passport_number'] = record.passport_number
            if record.passport_country_id:
                partner_vals['x_passport_country_id'] = record.passport_country_id.id
            if record.passport_issue_date:
                partner_vals['x_passport_issue_date'] = record.passport_issue_date
            if record.passport_expiry_date:
                partner_vals['x_passport_expiry_date'] = record.passport_expiry_date
            if record.passport_document:
                partner_vals['x_passport_document'] = record.passport_document

            # Residency / Visa
            if record.residency_visa_no:
                partner_vals['x_residency_visa_no'] = record.residency_visa_no
            if record.residency_expiry_date:
                partner_vals['x_residency_expiry_date'] = record.residency_expiry_date
            if record.place_of_birth:
                partner_vals['x_place_of_birth'] = record.place_of_birth
            if record.aliases:
                partner_vals['x_aliases'] = record.aliases

            # UAE IDs
            if record.emirates_id:
                partner_vals['x_emirates_id'] = record.emirates_id
            if record.emirates_id_document:
                partner_vals['x_emirates_id_document'] = record.emirates_id_document
            if record.proof_of_address_document:
                partner_vals['x_proof_of_address_document'] = record.proof_of_address_document

            # Address — update partner address fields
            if record.residential_address:
                partner_vals['street'] = record.residential_address
            if record.residential_city:
                partner_vals['city'] = record.residential_city
            if record.residential_postal_code:
                partner_vals['zip'] = record.residential_postal_code
            if record.residential_country_id:
                partner_vals['country_id'] = record.residential_country_id.id

            # Employment
            if record.occupation:
                partner_vals['x_occupation'] = record.occupation
            if record.employer_name:
                partner_vals['x_employer_name'] = record.employer_name
            if record.employer_address:
                partner_vals['x_employer_address'] = record.employer_address
            if record.years_in_role:
                partner_vals['x_years_in_role'] = record.years_in_role

            # Financial
            if record.annual_income:
                partner_vals['x_annual_income'] = record.annual_income
            if record.source_of_funds_ids:
                partner_vals['x_source_of_funds'] = [(6, 0, record.source_of_funds_ids.ids)]
            if record.source_of_wealth_ids:
                partner_vals['x_source_of_wealth'] = [(6, 0, record.source_of_wealth_ids.ids)]
            if record.purpose_of_transaction:
                # Map kyc.application selection to res.partner selection
                purpose_map = {
                    'real_estate_investment': 'investment',
                    'personal_use': 'end_use',
                    'savings_investment': 'savings',
                    'business_purpose': 'investment',
                    'other': 'other',
                }
                partner_vals['x_purpose_of_purchase'] = purpose_map.get(record.purpose_of_transaction, 'other')
            if record.payment_method:
                partner_vals['x_payment_method'] = record.payment_method

            # PEP
            if record.politically_exposed_person:
                partner_vals['x_politically_exposed_person'] = record.politically_exposed_person
            if record.pep_details:
                partner_vals['x_pep_details'] = record.pep_details

            # Signature & KYC metadata
            if record.signature_image:
                partner_vals['x_kyc_signature'] = record.signature_image
            partner_vals['x_kyc_signature_pdf'] = record._generate_signed_pdf()
            if record.signature_location:
                partner_vals['x_kyc_signed_at_location'] = record.signature_location
            partner_vals['x_kyc_document_id'] = record.kyc_id
            partner_vals['x_kyc_submission_date'] = record.submitted_date

            partner.write(partner_vals)

            record.write({
                'is_migrated_to_contact': True,
                'migration_date': fields.Datetime.now(),
            })
            _logger.info(
                'KYC %s migrated to contact %s (partner_id=%s) upon approval.',
                record.kyc_id, partner.name, partner.id,
            )
    
    def _generate_signed_pdf(self):
        """Generate PDF with embedded applicant + approver signatures using QWeb report engine"""
        self.ensure_one()
        try:
            report = self.env.ref('kyc_management.kyc_application_report_template')
            if report:
                pdf_content, _content_type = self.env['ir.actions.report']._render_qweb_pdf(
                    report, self.ids
                )
                return b64encode(pdf_content)
        except Exception as e:
            _logger.warning('Failed to generate signed PDF for KYC %s: %s', self.kyc_id, e)
        return self.signature_image
    
    def _generate_approval_token(self):
        """Generate a secure, time-limited token for email one-click approve/reject"""
        self.ensure_one()
        token = secrets.token_urlsafe(32)
        self.write({
            'approval_token': token,
            'token_expiry': fields.Datetime.now() + timedelta(days=7),
        })
        return token
    
    def _validate_token(self, token):
        """Validate an approval token"""
        self.ensure_one()
        if not self.approval_token or self.approval_token != token:
            return False
        if self.token_expiry and fields.Datetime.now() > self.token_expiry:
            return False
        return True
    
    def _invalidate_token(self):
        """Clear the approval token after use"""
        self.write({
            'approval_token': False,
            'token_expiry': False,
        })
    
    def _get_base_url(self):
        """Get the base URL for this instance"""
        return self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
    
    def _get_approve_url(self):
        """Get the one-click approve URL for email templates"""
        self.ensure_one()
        if not self.approval_token:
            self._generate_approval_token()
        return f"{self._get_base_url()}/kyc/approve/{self.id}/{self.approval_token}"
    
    def _get_reject_url(self):
        """Get the one-click reject URL for email templates"""
        self.ensure_one()
        if not self.approval_token:
            self._generate_approval_token()
        return f"{self._get_base_url()}/kyc/reject/{self.id}/{self.approval_token}"
    
    def _notify_submission(self):
        """Send notification to applicant on submission"""
        template = self.env.ref('kyc_management.email_template_kyc_submitted', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
        # Telegram notification
        self._send_telegram_kyc_submitted()
    
    def _notify_approval(self):
        """Send notification to applicant on approval"""
        template = self.env.ref('kyc_management.email_template_kyc_approved', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
        # Telegram notification
        self._send_telegram_kyc_approved()
    
    def _notify_rejection(self):
        """Send notification to applicant on rejection"""
        template = self.env.ref(
            'kyc_management.email_template_kyc_rejected',
            raise_if_not_found=False,
        )
        if template:
            if not self.email:
                _logger.warning(
                    'KYC %s: rejection email skipped — no applicant email',
                    self.kyc_id,
                )
            else:
                try:
                    template.send_mail(self.id, force_send=True)
                    _logger.info(
                        'KYC %s: rejection email sent to %s',
                        self.kyc_id, self.email,
                    )
                except Exception as exc:
                    _logger.error(
                        'KYC %s: rejection email failed: %s',
                        self.kyc_id, exc,
                    )
        # Telegram notification
        self._send_telegram_kyc_rejected()

    # ==================== TELEGRAM HELPERS ====================

    def _load_env_file(self):
        """Load environment variables from .env file"""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        candidate_paths = [
            os.path.join(base_dir, '.env'),
            os.path.abspath(
                os.path.join(base_dir, os.pardir, os.pardir, '.env')
            ),
        ]
        env_path = next(
            (path for path in candidate_paths if os.path.exists(path)),
            None,
        )
        if not env_path:
            return
        try:
            with open(env_path, 'r', encoding='utf-8') as env_file:
                for line in env_file:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
        except Exception as exc:
            _logger.warning('KYC: Failed to load .env file: %s', exc)

    def _get_telegram_config(self):
        """Return (token, chat_id) from environment"""
        self._load_env_file()
        token = os.getenv('OSUS_TG_BOT_TOKEN')
        chat_id = os.getenv('OSUS_TG_CHAT_ID')
        return token, chat_id

    def _send_telegram_message(self, token, chat_id, message):
        """Send a Telegram message via Bot API"""
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
        }
        encoded_data = urllib.parse.urlencode(data).encode('utf-8')
        request = urllib.request.Request(url, data=encoded_data)
        try:
            response = urllib.request.urlopen(request, timeout=10)
            payload = json.loads(response.read().decode('utf-8'))
            if not payload.get('ok'):
                _logger.warning('KYC Telegram API error: %s', payload)
            else:
                _logger.info('KYC Telegram message sent successfully')
            return payload.get('ok', False)
        except Exception as exc:
            _logger.error('KYC Telegram notification failed: %s', exc)
            return False

    # ==================== TELEGRAM KYC NOTIFICATIONS ====================

    def _send_telegram_kyc_submitted(self):
        """Send Telegram notification when a KYC application is submitted"""
        self.ensure_one()
        token, chat_id = self._get_telegram_config()
        if not token or not chat_id:
            _logger.info('KYC Telegram config missing — skipping submitted notification')
            return

        applicant_name = ' '.join(filter(None, [self.first_name, self.last_name])) or 'N/A'
        nationality = self.nationality_id.name if self.nationality_id else 'N/A'
        country = self.residential_country_id.name if self.residential_country_id else 'N/A'
        emp_status = dict(self._fields['employment_status'].selection).get(
            self.employment_status, 'N/A'
        ) if self.employment_status else 'N/A'
        pep_label = dict(self._fields['politically_exposed_person'].selection).get(
            self.politically_exposed_person, 'N/A'
        ) if self.politically_exposed_person else 'N/A'

        message = (
            f"\U0001F4CB <b>New KYC Application Submitted</b>\n"
            f"\n"
            f"<b>KYC ID:</b> {self.kyc_id}\n"
            f"<b>Applicant:</b> {applicant_name}\n"
            f"<b>Email:</b> {self.email or 'N/A'}\n"
            f"<b>Phone:</b> {self.phone or 'N/A'}\n"
            f"<b>Nationality:</b> {nationality}\n"
            f"<b>Country of Residence:</b> {country}\n"
            f"<b>Employment Status:</b> {emp_status}\n"
            f"<b>Occupation:</b> {self.occupation or 'N/A'}\n"
            f"<b>PEP Status:</b> {pep_label}\n"
            f"\n"
            f"\u23F3 <i>Awaiting compliance officer review</i>"
        )
        self._send_telegram_message(token, chat_id, message)

    def _send_telegram_kyc_approved(self):
        """Send Telegram notification when a KYC application is approved,
        including risk assessment details if available."""
        self.ensure_one()
        token, chat_id = self._get_telegram_config()
        if not token or not chat_id:
            _logger.info('KYC Telegram config missing — skipping approval notification')
            return

        applicant_name = ' '.join(filter(None, [self.first_name, self.last_name])) or 'N/A'
        nationality = self.nationality_id.name if self.nationality_id else 'N/A'
        country = self.residential_country_id.name if self.residential_country_id else 'N/A'
        emp_status = dict(self._fields['employment_status'].selection).get(
            self.employment_status, 'N/A'
        ) if self.employment_status else 'N/A'
        pep_label = dict(self._fields['politically_exposed_person'].selection).get(
            self.politically_exposed_person, 'N/A'
        ) if self.politically_exposed_person else 'N/A'
        approver = self.approver_id.name if self.approver_id else 'N/A'
        income = f"{self.annual_income:,.2f} {self.currency_id.name}" if self.annual_income else 'N/A'
        purpose = dict(self._fields['purpose_of_transaction'].selection).get(
            self.purpose_of_transaction, 'N/A'
        ) if self.purpose_of_transaction else 'N/A'
        payment = dict(self._fields['payment_method'].selection).get(
            self.payment_method, 'N/A'
        ) if self.payment_method else 'N/A'

        # Source of funds / wealth
        sof = ', '.join(self.source_of_funds_ids.mapped('name')) if self.source_of_funds_ids else 'N/A'
        sow = ', '.join(self.source_of_wealth_ids.mapped('name')) if self.source_of_wealth_ids else 'N/A'

        message = (
            f"\u2705 <b>KYC Application Approved</b>\n"
            f"\n"
            f"<b>KYC ID:</b> {self.kyc_id}\n"
            f"<b>Applicant:</b> {applicant_name}\n"
            f"<b>Email:</b> {self.email or 'N/A'}\n"
            f"<b>Phone:</b> {self.phone or 'N/A'}\n"
            f"<b>Nationality:</b> {nationality}\n"
            f"<b>Country of Residence:</b> {country}\n"
            f"<b>Employment Status:</b> {emp_status}\n"
            f"<b>Occupation:</b> {self.occupation or 'N/A'}\n"
            f"<b>Approved By:</b> {approver}\n"
            f"\n"
            f"\U0001F4B0 <b>Financial Profile</b>\n"
            f"<b>Annual Income:</b> {income}\n"
            f"<b>Source of Funds:</b> {sof}\n"
            f"<b>Source of Wealth:</b> {sow}\n"
            f"<b>Purpose of Transaction:</b> {purpose}\n"
            f"<b>Payment Method:</b> {payment}\n"
            f"<b>PEP Status:</b> {pep_label}\n"
        )

        # Append risk assessment info if available (from aml_compliance)
        risk_section = self._build_telegram_risk_section()
        if risk_section:
            message += risk_section

        self._send_telegram_message(token, chat_id, message)

    def _send_telegram_kyc_rejected(self):
        """Send Telegram notification when a KYC application is rejected"""
        self.ensure_one()
        token, chat_id = self._get_telegram_config()
        if not token or not chat_id:
            _logger.info(
                'KYC Telegram config missing — skipping rejection notification',
            )
            return

        applicant_name = ' '.join(
            filter(None, [self.first_name, self.last_name]),
        ) or 'N/A'
        rejector = self.approver_id.name if self.approver_id else 'N/A'

        message = (
            f"\u274C <b>KYC Application Rejected</b>\n"
            f"\n"
            f"<b>KYC ID:</b> {self.kyc_id}\n"
            f"<b>Applicant:</b> {applicant_name}\n"
            f"<b>Email:</b> {self.email or 'N/A'}\n"
            f"<b>Phone:</b> {self.phone or 'N/A'}\n"
            f"<b>Rejected By:</b> {rejector}\n"
            f"\n"
            f"\U0001F4DD <b>Rejection Reason:</b>\n"
            f"{self.rejection_reason or 'N/A'}\n"
        )
        if self.rejection_suggestions:
            message += (
                f"\n\U0001F4A1 <b>Suggested Corrections:</b>\n"
                f"{self.rejection_suggestions}\n"
            )
        self._send_telegram_message(token, chat_id, message)

    def _build_telegram_risk_section(self):
        """Build the risk assessment section for Telegram message.
        Returns empty string if aml_compliance is not installed or no assessment exists."""
        self.ensure_one()
        if not hasattr(self, 'risk_assessment_ids'):
            return ''
        assessments = self.risk_assessment_ids.filtered(
            lambda r: r.state in ('approved', 'reviewed', 'computed')
        ).sorted('assessment_date', reverse=True)
        if not assessments:
            return '\n\u26A0\uFE0F <i>No risk assessment completed yet</i>\n'

        latest = assessments[0]
        risk_emoji = {
            'low': '\U0001F7E2',
            'medium': '\U0001F7E1',
            'high': '\U0001F7E0',
            'very_high': '\U0001F534',
        }
        level_label = dict(latest._fields['final_risk_level'].selection).get(
            latest.final_risk_level, 'N/A'
        )
        emoji = risk_emoji.get(latest.final_risk_level, '')
        overridden = ' (Overridden)' if latest.is_overridden else ''

        section = (
            f"\n\U0001F6E1 <b>Risk Assessment</b>\n"
            f"<b>Risk Level:</b> {emoji} {level_label}{overridden}\n"
            f"<b>Risk Score:</b> {latest.computed_risk_score:.1f}/100\n"
            f"<b>Assessment Type:</b> {dict(latest._fields['assessment_type'].selection).get(latest.assessment_type, 'N/A')}\n"
            f"<b>Requires EDD:</b> {'Yes' if latest.requires_edd else 'No'}\n"
        )
        if latest.override_reason:
            section += f"<b>Override Reason:</b> {latest.override_reason}\n"
        return section
    
    def _create_approval_and_notify_officer(self):
        """Create a kyc.approval record for the first KYC Compliance Officer and notify them.
        Also sends a direct officer notification email (bound to kyc.application model).
        """
        self.ensure_one()
        import logging
        _logger = logging.getLogger(__name__)
        
        # Find the first KYC Compliance Officer
        approver_group = self.env.ref('kyc_management.group_kyc_approver', raise_if_not_found=False)
        if not approver_group:
            _logger.warning('KYC: group_kyc_approver not found, skipping officer notification for app %s', self.kyc_id)
            return
        
        officers = self.env['res.users'].sudo().search([
            ('group_ids', 'in', [approver_group.id]),
            ('active', '=', True),
        ], limit=5)
        
        if not officers:
            _logger.warning('KYC: No active KYC Compliance Officers found, skipping officer notification for app %s', self.kyc_id)
            return
        
        KYCApproval = self.env['kyc.approval'].sudo()
        
        # ── Collect attachments for officer emails ──────────────────────
        attachment_ids = self._collect_kyc_attachments_for_email()

        for officer in officers:
            # Create kyc.approval record (ties a specific officer to this application)
            try:
                approval = KYCApproval.create({
                    'kyc_application_id': self.id,
                    'approver_id': officer.id,
                    'approval_step': 'initial_check',
                    'status': 'pending',
                })
                _logger.info('KYC: Created kyc.approval id=%s for officer %s (app %s)',
                             approval.id, officer.login, self.kyc_id)
                
                # Send the officer notification email (via kyc.approval template) with attachments
                approval._notify_approval(attachment_ids=attachment_ids)
            except Exception as e:
                _logger.error('KYC: Failed to create approval/notify officer %s for app %s: %s',
                              officer.login, self.kyc_id, str(e))
        
        # Also send the direct officer notification template (bound to kyc.application)
        # This uses email_values to set email_to dynamically
        officer_template = self.env.ref(
            'kyc_management.email_template_kyc_officer_notification', raise_if_not_found=False
        )
        if officer_template:
            officer_emails = ','.join(o.email for o in officers if o.email)
            if officer_emails:
                try:
                    officer_template.send_mail(
                        self.id,
                        force_send=True,
                        email_values={
                            'email_to': officer_emails,
                            'attachment_ids': attachment_ids,
                        },
                    )
                    _logger.info('KYC: Sent officer notification email to %s for app %s (with %d attachments)',
                                 officer_emails, self.kyc_id, len(attachment_ids))
                except Exception as e:
                    _logger.error('KYC: Failed to send officer notification email for app %s: %s',
                                  self.kyc_id, str(e))
    
    def _collect_kyc_attachments_for_email(self):
        """Generate the KYC PDF report and collect uploaded identity documents.
        Returns a list of ir.attachment IDs that can be passed to send_mail().
        """
        self.ensure_one()
        Attachment = self.env['ir.attachment'].sudo()
        attachment_ids = []

        # 1) Generate the KYC Application PDF report
        try:
            report = self.env.ref('kyc_management.kyc_application_report_template', raise_if_not_found=False)
            if report:
                pdf_content, _content_type = self.env['ir.actions.report']._render_qweb_pdf(
                    report, self.ids
                )
                pdf_att = Attachment.create({
                    'name': f'KYC_Application_{self.kyc_id}.pdf',
                    'datas': b64encode(pdf_content),
                    'mimetype': 'application/pdf',
                    'res_model': 'kyc.application',
                    'res_id': self.id,
                })
                attachment_ids.append(pdf_att.id)
                _logger.info('KYC: Generated PDF attachment id=%s for app %s', pdf_att.id, self.kyc_id)
        except Exception as e:
            _logger.warning('KYC: Could not generate PDF for app %s: %s', self.kyc_id, e)

        # 2) Attach uploaded identity documents (passport, emirates ID, proof of address)
        doc_fields = [
            ('passport_document', f'Passport_Copy_{self.kyc_id}'),
            ('emirates_id_document', f'Emirates_ID_{self.kyc_id}'),
            ('proof_of_address_document', f'Proof_of_Address_{self.kyc_id}'),
        ]
        for field_name, att_name in doc_fields:
            data = getattr(self, field_name, False)
            if data:
                try:
                    # Check if an ir.attachment already exists for this field on this record
                    existing = Attachment.search([
                        ('res_model', '=', 'kyc.application'),
                        ('res_id', '=', self.id),
                        ('res_field', '=', field_name),
                    ], limit=1)
                    if existing:
                        attachment_ids.append(existing.id)
                    else:
                        doc_att = Attachment.create({
                            'name': att_name,
                            'datas': data,
                            'mimetype': 'application/octet-stream',
                            'res_model': 'kyc.application',
                            'res_id': self.id,
                        })
                        attachment_ids.append(doc_att.id)
                except Exception as e:
                    _logger.warning('KYC: Could not attach %s for app %s: %s', field_name, self.kyc_id, e)

        return attachment_ids

    # ==================== OVERRIDE METHODS ====================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set defaults and validate"""
        records = super().create(vals_list)
        for record in records:
            # Auto-fill from partner if creating from contact
            if record.partner_id:
                record._prefill_from_partner()
        return records
    
    def _prefill_from_partner(self):
        """Pre-fill empty fields from partner record (does not overwrite controller-supplied data)"""
        partner = self.partner_id
        vals = {}
        if not self.first_name and partner.name:
            vals['first_name'] = partner.name.split()[0]
        if not self.last_name and partner.name and len(partner.name.split()) > 1:
            vals['last_name'] = ' '.join(partner.name.split()[1:])
        if not self.email and partner.email:
            vals['email'] = partner.email
        if not self.phone and partner.phone:
            vals['phone'] = partner.phone
        if not self.residential_country_id and partner.country_id:
            vals['residential_country_id'] = partner.country_id.id
        if vals:
            self.write(vals)
    
    def unlink(self):
        """Prevent deletion of approved/rejected applications"""
        for record in self:
            if record.state in ('approved', 'rejected'):
                raise UserError(
                    _('Cannot delete approved or rejected KYC applications.')
                )
        return super().unlink()
    
    # ==================== CRON METHODS ====================
    
    @api.model
    def _send_pending_reminders(self):
        """Cron: Send daily reminders for applications pending review > 3 days"""
        threshold = fields.Datetime.now() - timedelta(days=3)
        pending = self.search([
            ('state', 'in', ('submitted', 'pending_review')),
            ('submitted_date', '<=', threshold),
        ])
        for app in pending:
            # Post internal note as reminder
            app.message_post(
                body=_(
                    'Reminder: This KYC application has been pending review for %d days.'
                ) % app.days_pending,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        _logger.info('KYC pending reminders sent for %d applications.', len(pending))

    @api.model
    def _send_sla_escalations(self):
        """Cron: Escalate KYC files pending > 5 days to senior compliance officers."""
        threshold = fields.Datetime.now() - timedelta(days=5)
        overdue = self.search([
            ('state', 'in', ('submitted', 'pending_review')),
            ('submitted_date', '<=', threshold),
        ])

        senior_group = self.env.ref('kyc_management.group_kyc_senior_officer', raise_if_not_found=False)
        assignee = senior_group.users[:1] if senior_group and senior_group.users else self.env.user

        created = 0
        for app in overdue:
            existing = self.env['mail.activity'].search([
                ('res_model', '=', 'kyc.application'),
                ('res_id', '=', app.id),
                ('summary', '=', 'KYC SLA Escalation'),
                ('date_deadline', '>=', fields.Date.today()),
            ], limit=1)
            if existing:
                continue

            app.activity_schedule(
                'mail.mail_activity_data_todo',
                summary='KYC SLA Escalation',
                note=_(
                    'KYC application %s (%s) has been pending for %d days and requires immediate escalation review.',
                    app.kyc_id,
                    app.partner_id.name,
                    app.days_pending,
                ),
                user_id=assignee.id,
                date_deadline=fields.Date.today(),
            )
            created += 1

        _logger.info('KYC SLA escalation activities created: %d', created)
        return created


# Note: kyc.source.funds and kyc.source.wealth are defined in models.py
