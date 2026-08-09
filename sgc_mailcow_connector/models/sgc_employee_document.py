from odoo import api, fields, models
import binascii

_ASSET_GROUPS = ("laptop", "mobile", "tablet", "access_card", "key", "monitor", "printer")

def _asset_fields():
    fields_list = []
    for group in _ASSET_GROUPS:
        fields_list.append(f"{group}_id")
        fields_list.append(f"{group}_condition")
        fields_list.append(f"{group}_issued_date")
        fields_list.append(f"{group}_returned_date")
        fields_list.append(f"{group}_remarks")
    return fields_list

SNAPSHOT_FIELDS = [
    "employee_name",
    "job_title",
    "department_id",
    "last_working_day",
    "nda_version",
    "nda_duration_years",
    "warning_letter_supervisor_id",
    "warning_letter_improvement_period",
] + _asset_fields()

_SNAPSHOT_SOURCES = {
    "employee_name": "name",
    "warning_letter_supervisor_id": "warning_letter_supervisor",
}

_REPORT_XMLIDS = {
    "nda": "sgc_mailcow_connector.action_report_nda",
    "warning_letter": "sgc_mailcow_connector.action_report_warning_letter",
    "asset_handover": "sgc_mailcow_connector.action_report_company_asset_handover",
}

_EMAIL_TEMPLATE_XMLIDS = {
    "nda": "sgc_mailcow_connector.email_template_nda",
    "warning_letter": "sgc_mailcow_connector.email_template_warning_letter",
    "asset_handover": "sgc_mailcow_connector.email_template_company_asset_handover",
}

class SgcEmployeeDocument(models.Model):
    _name = "sgc.employee.document"
    _description = "Employee Document"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "create_date desc"

    # New fields for signature
    signature = fields.Image(copy=False, attachment=True, max_width=1024, max_height=1024)
    signed_by = fields.Char(copy=False)
    signed_on = fields.Datetime(copy=False)

    # Existing fields...
    name = fields.Char("Document Number", readonly=True, copy=False)
    doc_type = fields.Selection([
        ("nda", "NDA"),
        ("warning_letter", "Warning Letter"),
        ("asset_handover", "Asset Handover"),
    ], string="Document Type", required=True)
    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, ondelete="cascade", index=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("signed", "Signed"),
    ], string="Status", default="draft", tracking=True)
    date = fields.Date("Document Date", default=fields.Date.context_today, readonly=True)
    # ... rest of existing fields

    _name_uniq = models.Constraint(
        "unique(name)",
        "Document number must be unique",
    )

    def _compute_access_url(self):
        for doc in self:
            doc.access_url = "/my/employee-documents/%s" % doc.id

    def _has_to_be_signed(self):
        return self.state == 'sent' and not self.signature

    def action_send(self):
        """ Opens a wizard to compose an email, with relevant mail template loaded by default """
        self.ensure_one()
        template_id = self.env.ref(self._EMAIL_TEMPLATE_XMLIDS[self.doc_type]).id
        ctx = {
            'default_model': 'sgc.employee.document',
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_template_id': template_id,
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'force_email': True,
            'mark_doc_as_sent': True,
            'hide_mail_template_management_options': True,
        }
        return {
            'name': _('Send'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'target': 'new',
            'context': ctx,
        }

    def message_post(self, **kwargs):
        if self.env.context.get('mark_doc_as_sent'):
            self.filtered(lambda d: d.state == 'draft').with_context(tracking_disable=True).write({'state': 'sent'})
        return super().message_post(**kwargs)

    # ... rest of existing methods
    @api.model_create_multi
    def create(self, vals_list):
        # ... existing create method unchanged

    def action_store_pdf(self):
        # ... existing unchanged
