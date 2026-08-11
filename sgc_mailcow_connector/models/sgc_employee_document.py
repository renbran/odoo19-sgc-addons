from odoo import api, fields, models, _
import binascii

_ASSET_GROUPS = ("laptop", "mobile", "tablet", "access_card", "key", "monitor", "printer")


def _asset_fields():
    fields_list = []
    for group in _ASSET_GROUPS:
        fields_list.append(f"{group}_id")
        fields_list.append(f"{group}_model")
        fields_list.append(f"{group}_condition")
        fields_list.append(f"{group}_issued_date")
        fields_list.append(f"{group}_returned_date")
        fields_list.append(f"{group}_estimated_value")
        fields_list.append(f"{group}_remarks")
    return fields_list


SNAPSHOT_FIELDS = [
    "employee_name",
    "job_title",
    "department_id",
    "last_working_day",
    "nda_version",
    "nda_duration_years",
    "warning_letter_type",
    "warning_letter_reason",
    "warning_letter_supervisor_id",
    "warning_letter_improvement_period",
] + _asset_fields()

_SNAPSHOT_SOURCES = {
    "employee_name": "name",
    "warning_letter_supervisor_id": "warning_letter_supervisor",
}


class SgcEmployeeDocument(models.Model):
    _name = "sgc.employee.document"
    _description = "Employee Document"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "create_date desc"

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

    # Frozen snapshot of the report-relevant employee data, copied at creation.
    employee_name = fields.Char("Employee Name", readonly=True)
    job_title = fields.Char("Job Title", readonly=True)
    department_id = fields.Many2one("hr.department", string="Department", readonly=True)
    last_working_day = fields.Date("Last Working Day", readonly=True)
    nda_version = fields.Char("NDA Version", readonly=True)
    nda_duration_years = fields.Integer("NDA Duration (Years)", readonly=True)
    warning_letter_type = fields.Selection([
        ("verbal", "Verbal Warning"),
        ("first_written", "First Written Warning"),
        ("final_written", "Final Written Warning"),
        ("dismissal", "Notice of Dismissal"),
    ], string="Warning Type", readonly=True)
    warning_letter_reason = fields.Text("Reason for Warning", readonly=True)
    warning_letter_body = fields.Html(
        string="Warning Letter Body",
        sanitize=False,
        help="Customizable HTML body content for the warning letter. If empty, the default template content will be used.")
    warning_letter_supervisor_id = fields.Many2one(
        "hr.employee", string="Supervisor", readonly=True)
    warning_letter_improvement_period = fields.Integer(
        "Improvement Period (Days)", readonly=True)

    laptop_id = fields.Char("Laptop ID/Serial", readonly=True)
    laptop_model = fields.Char("Laptop Model", readonly=True)
    laptop_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Laptop Condition", readonly=True)
    laptop_issued_date = fields.Date("Laptop Issued Date", readonly=True)
    laptop_returned_date = fields.Date("Laptop Returned Date", readonly=True)
    laptop_estimated_value = fields.Monetary("Laptop Estimated Value", readonly=True, currency_field="company_currency_id")
    laptop_remarks = fields.Text("Laptop Remarks", readonly=True)

    mobile_id = fields.Char("Mobile ID/Serial", readonly=True)
    mobile_model = fields.Char("Mobile Model", readonly=True)
    mobile_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Mobile Condition", readonly=True)
    mobile_issued_date = fields.Date("Mobile Issued Date", readonly=True)
    mobile_returned_date = fields.Date("Mobile Returned Date", readonly=True)
    mobile_estimated_value = fields.Monetary("Mobile Estimated Value", readonly=True, currency_field="company_currency_id")
    mobile_remarks = fields.Text("Mobile Remarks", readonly=True)

    tablet_id = fields.Char("Tablet/iPad ID/Serial", readonly=True)
    tablet_model = fields.Char("Tablet/iPad Model", readonly=True)
    tablet_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Tablet Condition", readonly=True)
    tablet_issued_date = fields.Date("Tablet Issued Date", readonly=True)
    tablet_returned_date = fields.Date("Tablet Returned Date", readonly=True)
    tablet_estimated_value = fields.Monetary("Tablet/iPad Estimated Value", readonly=True, currency_field="company_currency_id")
    tablet_remarks = fields.Text("Tablet Remarks", readonly=True)

    access_card_id = fields.Char("Access Card ID", readonly=True)
    access_card_model = fields.Char("Access Card Type/Model", readonly=True)
    access_card_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Access Card Condition", readonly=True)
    access_card_issued_date = fields.Date("Access Card Issued Date", readonly=True)
    access_card_returned_date = fields.Date("Access Card Returned Date", readonly=True)
    access_card_estimated_value = fields.Monetary("Access Card Estimated Value", readonly=True, currency_field="company_currency_id")
    access_card_remarks = fields.Text("Access Card Remarks", readonly=True)

    key_id = fields.Char("Key ID", readonly=True)
    key_model = fields.Char("Key Type/Label", readonly=True)
    key_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Key Condition", readonly=True)
    key_issued_date = fields.Date("Key Issued Date", readonly=True)
    key_returned_date = fields.Date("Key Returned Date", readonly=True)
    key_estimated_value = fields.Monetary("Key Estimated Value", readonly=True, currency_field="company_currency_id")
    key_remarks = fields.Text("Key Remarks", readonly=True)

    monitor_id = fields.Char("Monitor ID/Serial", readonly=True)
    monitor_model = fields.Char("Monitor Model", readonly=True)
    monitor_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Monitor Condition", readonly=True)
    monitor_issued_date = fields.Date("Monitor Issued Date", readonly=True)
    monitor_returned_date = fields.Date("Monitor Returned Date", readonly=True)
    monitor_estimated_value = fields.Monetary("Monitor Estimated Value", readonly=True, currency_field="company_currency_id")
    monitor_remarks = fields.Text("Monitor Remarks", readonly=True)

    printer_id = fields.Char("Printer/Scanner ID/Serial", readonly=True)
    printer_model = fields.Char("Printer/Scanner Model", readonly=True)
    printer_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Printer/Scanner Condition", readonly=True)
    printer_issued_date = fields.Date("Printer/Scanner Issued Date", readonly=True)
    printer_returned_date = fields.Date("Printer/Scanner Returned Date", readonly=True)
    printer_estimated_value = fields.Monetary("Printer/Scanner Estimated Value", readonly=True, currency_field="company_currency_id")
    printer_remarks = fields.Text("Printer/Scanner Remarks", readonly=True)

    company_currency_id = fields.Many2one(
        "res.currency", related="employee_id.company_id.currency_id", readonly=True)

    pdf_attachment_id = fields.Many2one(
        "ir.attachment", string="PDF Document", readonly=True, copy=False,
        ondelete="set null")

    _name_uniq = models.Constraint(
        "unique(name)",
        "Document number must be unique",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") and vals.get("doc_type"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "sgc.employee.document." + vals["doc_type"])
            if vals.get("employee_id"):
                emp = self.env["hr.employee"].browse(vals["employee_id"])
                if emp:
                    for fname in SNAPSHOT_FIELDS:
                        if fname not in vals:
                            source = _SNAPSHOT_SOURCES.get(fname, fname)
                            value = emp[source]
                            if isinstance(emp._fields[source], fields.Many2one):
                                value = value.id
                            vals[fname] = value
        return super().create(vals_list)

    def _compute_access_url(self):
        for doc in self:
            doc.access_url = "/my/employee-documents/%s" % doc.id

    def _has_to_be_signed(self):
        return self.state == 'sent' and not self.signature

    def action_send(self):
        """ Opens a wizard to compose an email, with relevant mail template loaded by default """
        self.ensure_one()
        # Get email template reference safely

        email_template_xmlid = self._EMAIL_TEMPLATE_XMLIDS.get(self.doc_type)

        if not email_template_xmlid:

            raise ValueError(_("No email template configured for document type: %s") % self.doc_type)

        template_id = self.env.ref(email_template_xmlid).id
        # the composer resolves recipients from partner_ids, not from the
        # template's email_to; hr.employee has no partner_id of its own, so
        # without this the wizard silently sends to nobody.
        recipient_partner = self.employee_id.work_contact_id or self.employee_id.user_id.partner_id
        if not recipient_partner:
            raise ValueError(_(
                "Employee %s has no work contact or user account to send this document to."
            ) % self.employee_id.name)
        # admin is added as a second, separate recipient (Odoo sends each
        # partner their own individual copy through the notification system,
        # so this behaves like a BCC: admin gets confirmation the send worked
        # without either party seeing the other on their copy).
        recipient_ids = [recipient_partner.id]
        admin_partner = self.env['res.partner'].search([('email', '=', 'bran@sgctech.ai')], limit=1)
        if admin_partner and admin_partner.id != recipient_partner.id:
            recipient_ids.append(admin_partner.id)
        ctx = {
            'default_model': 'sgc.employee.document',
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_template_id': template_id,
            'default_partner_ids': [(6, 0, recipient_ids)],
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
            # the composer routes recipients through each partner's own
            # notification preference (inbox vs email), so admin does not
            # reliably get an actual email even when added as a recipient.
            # Build the exact same rendered email (subject, body, report
            # attachment) the employee received and send admin a real,
            # standalone copy of it, independent of any notification prefs.
            for doc in self:
                email_template_xmlid = self._EMAIL_TEMPLATE_XMLIDS.get(doc.doc_type)
                if not email_template_xmlid:
                    continue
                template = self.env.ref(email_template_xmlid).sudo()
                generated = template._generate_template(
                    [doc.id], ['subject', 'body_html', 'report_template_ids']
                ).get(doc.id, {})
                attachment_ids = list(generated.get('attachment_ids') or [])
                for attach_name, attach_data in (generated.get('attachments') or []):
                    attachment = self.env['ir.attachment'].sudo().create({
                        'name': attach_name,
                        'datas': attach_data,
                        'res_model': 'mail.message',
                        'type': 'binary',
                    })
                    attachment_ids.append(attachment.id)
                self.env['mail.mail'].sudo().create({
                    'subject': _('[Admin copy] %s') % (generated.get('subject') or doc.name),
                    'body_html': generated.get('body_html') or '',
                    'email_to': 'bran@sgctech.ai',
                    'attachment_ids': [(6, 0, attachment_ids)],
                    'auto_delete': False,
                }).send()
        return super().message_post(**kwargs)

    def action_store_pdf(self):
        self.ensure_one()
        # Get report reference safely

        report_xmlid = self._REPORT_XMLIDS.get(self.doc_type)

        if not report_xmlid:

            raise ValueError(_("No report configured for document type: %s") % self.doc_type)

        report = self.env.ref(report_xmlid)

        pdf, _ = report._render_qweb_pdf(report, self.ids)
        if self.pdf_attachment_id:
            self.pdf_attachment_id.unlink()
        attachment = self.env["ir.attachment"].create({
            "name": f"{self.name}.pdf",
            "type": "binary",
            "raw": pdf,
            "res_model": self._name,
            "res_id": self.id,
        })
        self.pdf_attachment_id = attachment
        return True
