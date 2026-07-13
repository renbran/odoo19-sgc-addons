# -*- coding: utf-8 -*-
"""
Enhanced Due Diligence (EDD) Wizard

Wizard for conducting EDD questionnaire for high/very high risk
customers as required by UAE CBUAE regulations.

Captures:
  - Source of funds verification
  - Source of wealth verification
  - Business activities review
  - Political exposure check
  - Adverse media check
  - Ultimate beneficial owner verification
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class EDDWizard(models.TransientModel):
    """Enhanced Due Diligence questionnaire wizard."""

    _name = 'aml.edd.wizard'
    _description = 'EDD Questionnaire Wizard'

    kyc_application_id = fields.Many2one(
        'kyc.application',
        string='KYC Application',
        required=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
    )

    risk_level = fields.Selection([
        ('high', 'High'),
        ('very_high', 'Very High'),
    ], string='Risk Level', required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ], string='Status', default='draft')

    questionnaire_complete = fields.Boolean(
        string='Questionnaire Completed',
        default=False,
    )

    edd_date = fields.Date(
        string='EDD Date',
        default=fields.Date.today,
    )

    edd_officer_id = fields.Many2one(
        'res.users',
        string='EDD Officer',
        default=lambda self: self.env.user,
    )

    sof_verified = fields.Selection([
        ('verified', 'Verified'),
        ('not_verified', 'Not Verified'),
        ('pending', 'Pending'),
        ('not_applicable', 'N/A'),
    ], string='Source of Funds Verified', default='pending')

    sof_details = fields.Text(
        string='Source of Funds Details',
    )

    sow_verified = fields.Selection([
        ('verified', 'Verified'),
        ('not_verified', 'Not Verified'),
        ('pending', 'Pending'),
        ('not_applicable', 'N/A'),
    ], string='Source of Wealth Verified', default='pending')

    sow_details = fields.Text(
        string='Source of Wealth Details',
    )

    business_activity_verified = fields.Selection([
        ('verified', 'Verified'),
        ('not_verified', 'Not Verified'),
        ('pending', 'Pending'),
        ('not_applicable', 'N/A'),
    ], string='Business Activity Verified', default='pending')

    business_activity_details = fields.Text(
        string='Business Activity Details',
    )

    pep_check_performed = fields.Boolean(
        string='PEP Check Performed',
        default=False,
    )

    pep_result = fields.Selection([
        ('clear', 'Clear'),
        ('positive', 'Positive Match'),
        ('partial', 'Partial Match'),
    ], string='PEP Check Result')

    pep_details = fields.Text(
        string='PEP Check Details',
    )

    adverse_media_check = fields.Boolean(
        string='Adverse Media Check Performed',
        default=False,
    )

    adverse_media_result = fields.Selection([
        ('clear', 'Clear'),
        ('negative', 'Negative Articles Found'),
    ], string='Adverse Media Result')

    adverse_media_details = fields.Text(
        string='Adverse Media Details',
    )

    ubo_verification = fields.Selection([
        ('verified', 'Verified'),
        ('not_verified', 'Not Verified'),
        ('pending', 'Pending'),
        ('not_applicable', 'N/A'),
    ], string='UBO Verification', default='pending')

    ubo_details = fields.Text(
        string='UBO Details',
    )

    risk_rating_confirmed = fields.Boolean(
        string='Risk Rating Confirmed',
        default=False,
    )

    additional_notes = fields.Text(
        string='Additional Notes',
    )

    overall_assessment = fields.Selection([
        ('approved', 'Approved'),
        ('approved_conditions', 'Approved with Conditions'),
        ('rejected', 'Rejected'),
        ('further_review', 'Further Review Required'),
    ], string='Overall Assessment')

    def action_start_questionnaire(self):
        """Start the questionnaire."""
        self.write({'state': 'in_progress'})
        return {
            'type': 'ir.actions.act_window',
            'res_id': self.id,
            'res_model': 'aml.edd.wizard',
            'view_mode': 'form',
            'target': 'current',
        }

    def action_complete_questionnaire(self):
        """Validate and complete the questionnaire."""
        self.ensure_one()

        if not self.questionnaire_complete:
            if not self.sof_verified or not self.business_activity_verified:
                raise UserError(_('Please complete the required verification fields.'))

        self.write({
            'state': 'completed',
            'questionnaire_complete': True,
        })

        self._create_edd_response_record()

        return {
            'type': 'ir.actions.act_window_close',
        }

    def _create_edd_response_record(self):
        """Create a permanent EDD response record."""
        response = self.env['aml.edd.response'].create({
            'kyc_application_id': self.kyc_application_id.id,
            'partner_id': self.partner_id.id,
            'risk_level': self.risk_level,
            'edd_date': self.edd_date,
            'edd_officer_id': self.edd_officer_id.id,
            'sof_verified': self.sof_verified,
            'sof_details': self.sof_details,
            'sow_verified': self.sow_verified,
            'sow_details': self.sow_details,
            'business_activity_verified': self.business_activity_verified,
            'business_activity_details': self.business_activity_details,
            'pep_check_performed': self.pep_check_performed,
            'pep_result': self.pep_result,
            'pep_details': self.pep_details,
            'adverse_media_check': self.adverse_media_check,
            'adverse_media_result': self.adverse_media_result,
            'adverse_media_details': self.adverse_media_details,
            'ubo_verification': self.ubo_verification,
            'ubo_details': self.ubo_details,
            'additional_notes': self.additional_notes,
            'overall_assessment': self.overall_assessment,
        })

        self.kyc_application_id.message_post(
            body=_('EDD questionnaire completed by %s. Assessment: %s',
                   self.edd_officer_id.name, self.overall_assessment),
            message_type='notification',
        )

        return response


class EDDResponse(models.Model):
    """Permanent record of EDD questionnaire responses."""

    _name = 'aml.edd.response'
    _description = 'EDD Response'
    _rec_name = 'id'
    _order = 'edd_date desc'

    kyc_application_id = fields.Many2one(
        'kyc.application',
        string='KYC Application',
        required=True,
        index=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
    )

    risk_level = fields.Selection([
        ('high', 'High'),
        ('very_high', 'Very High'),
    ], string='Risk Level', required=True)

    edd_date = fields.Date(
        string='EDD Date',
        default=fields.Date.today,
        required=True,
    )

    edd_officer_id = fields.Many2one(
        'res.users',
        string='EDD Officer',
        required=True,
    )

    sof_verified = fields.Selection([
        ('verified', 'Verified'),
        ('not_verified', 'Not Verified'),
        ('pending', 'Pending'),
        ('not_applicable', 'N/A'),
    ], string='Source of Funds Verified')

    sof_details = fields.Text(string='Source of Funds Details')

    sow_verified = fields.Selection([
        ('verified', 'Verified'),
        ('not_verified', 'Not Verified'),
        ('pending', 'Pending'),
        ('not_applicable', 'N/A'),
    ], string='Source of Wealth Verified')

    sow_details = fields.Text(string='Source of Wealth Details')

    business_activity_verified = fields.Selection([
        ('verified', 'Verified'),
        ('not_verified', 'Not Verified'),
        ('pending', 'Pending'),
        ('not_applicable', 'N/A'),
    ], string='Business Activity Verified')

    business_activity_details = fields.Text(string='Business Activity Details')

    pep_check_performed = fields.Boolean(string='PEP Check Performed')

    pep_result = fields.Selection([
        ('clear', 'Clear'),
        ('positive', 'Positive Match'),
        ('partial', 'Partial Match'),
    ], string='PEP Check Result')

    pep_details = fields.Text(string='PEP Check Details')

    adverse_media_check = fields.Boolean(string='Adverse Media Check Performed')

    adverse_media_result = fields.Selection([
        ('clear', 'Clear'),
        ('negative', 'Negative Articles Found'),
    ], string='Adverse Media Result')

    adverse_media_details = fields.Text(string='Adverse Media Details')

    ubo_verification = fields.Selection([
        ('verified', 'Verified'),
        ('not_verified', 'Not Verified'),
        ('pending', 'Pending'),
        ('not_applicable', 'N/A'),
    ], string='UBO Verification')

    ubo_details = fields.Text(string='UBO Details')

    additional_notes = fields.Text(string='Additional Notes')

    overall_assessment = fields.Selection([
        ('approved', 'Approved'),
        ('approved_conditions', 'Approved with Conditions'),
        ('rejected', 'Rejected'),
        ('further_review', 'Further Review Required'),
    ], string='Overall Assessment')

    def name_get(self):
        return [(rec.id, f"EDD {rec.edd_date}") for rec in self]