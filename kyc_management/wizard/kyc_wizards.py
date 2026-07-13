# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class KycRejectionWizard(models.TransientModel):
    _name = 'kyc.rejection.wizard'
    _description = 'KYC Rejection Wizard'

    kyc_id = fields.Many2one('kyc.application', string='KYC Application', readonly=True)
    approval_id = fields.Many2one('kyc.approval', string='Approval', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason', required=True)
    rejection_suggestions = fields.Text(string='Suggestions for Resubmission')

    def action_confirm_rejection(self):
        self.ensure_one()
        approval = self.approval_id
        kyc = self.kyc_id or (approval.kyc_application_id if approval else False)
        if not approval and not kyc:
            raise UserError(_('No KYC application or approval linked.'))
        if approval:
            approval.write({
                'status': 'rejected',
                'rejection_reason': self.rejection_reason,
                'rejection_suggestions': self.rejection_suggestions,
                'rejection_date': fields.Datetime.now(),
                'rejected_by_id': self.env.user.id,
            })
            approval._notify_rejection()
        if kyc:
            kyc.write({
                'state': 'rejected',
                'rejection_reason': self.rejection_reason,
                'rejection_suggestions': self.rejection_suggestions,
            })
        return {'type': 'ir.actions.act_window_close'}


class KycClarificationWizard(models.TransientModel):
    _name = 'kyc.clarification.wizard'
    _description = 'KYC Clarification Request Wizard'

    approval_id = fields.Many2one('kyc.approval', string='Approval', readonly=True)
    clarification_details = fields.Text(string='Clarification Details', required=True)
    deadline_days = fields.Integer(string='Deadline (Days)', default=7)

    def action_send_clarification(self):
        self.ensure_one()
        approval = self.approval_id
        if not approval:
            raise UserError(_('No approval linked to this clarification request.'))
        approval.write({
            'status': 'needs_clarification',
            'clarification_details': self.clarification_details,
            'clarification_requested': True,
            'clarification_request_date': fields.Datetime.now(),
        })
        approval._notify_clarification_request()
        return {'type': 'ir.actions.act_window_close'}


class KycEscalationWizard(models.TransientModel):
    _name = 'kyc.escalation.wizard'
    _description = 'KYC Escalation Wizard'

    approval_id = fields.Many2one('kyc.approval', string='Approval', readonly=True)
    escalated_to_id = fields.Many2one('res.users', string='Escalate To', required=True)
    escalation_reason = fields.Text(string='Escalation Reason', required=True)

    def action_escalate(self):
        self.ensure_one()
        approval = self.approval_id
        if not approval:
            raise UserError(_('No approval linked to this escalation.'))
        approval.write({
            'requires_escalation': True,
            'escalated_to_id': self.escalated_to_id.id,
            'escalation_reason': self.escalation_reason,
            'escalation_date': fields.Datetime.now(),
        })
        approval.message_post(
            body=_('Escalated to %s by %s. Reason: %s') % (
                self.escalated_to_id.name,
                self.env.user.name,
                self.escalation_reason,
            ),
            message_type='notification',
        )
        return {'type': 'ir.actions.act_window_close'}
