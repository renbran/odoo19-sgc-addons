from odoo import api, fields, models, _
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
    warning_letter_supervisor_id = fields.Many2one(
        "hr.employee", string="Supervisor", readonly=True)
    warning_letter_improvement_period = fields.Integer(
        "Improvement Period (Days)", readonly=True)

    laptop_id = fields.Char("Laptop ID/Serial", readonly=True)
    laptop_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Laptop Condition", readonly=True)
    laptop_issued_date = fields.Date("Laptop Issued Date", readonly=True)
    laptop_returned_date = fields.Date("Laptop Returned Date", readonly=True)
    laptop_remarks = fields.Text("Laptop Remarks", readonly=True)

    mobile_id = fields.Char("Mobile ID/Serial", readonly=True)
    mobile_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Mobile Condition", readonly=True)
    mobile_issued_date = fields.Date("Mobile Issued Date", readonly=True)
    mobile_returned_date = fields.Date("Mobile Returned Date", readonly=True)
    mobile_remarks = fields.Text("Mobile Remarks", readonly=True)

    tablet_id = fields.Char("Tablet/iPad ID/Serial", readonly=True)
    tablet_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Tablet Condition", readonly=True)
    tablet_issued_date = fields.Date("Tablet Issued Date", readonly=True)
    tablet_returned_date = fields.Date("Tablet Returned Date", readonly=True)
    tablet_remarks = fields.Text("Tablet Remarks", readonly=True)

    access_card_id = fields.Char("Access Card ID", readonly=True)
    access_card_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Access Card Condition", readonly=True)
    access_card_issued_date = fields.Date("Access Card Issued Date", readonly=True)
    access_card_returned_date = fields.Date("Access Card Returned Date", readonly=True)
    access_card_remarks = fields.Text("Access Card Remarks", readonly=True)

    key_id = fields.Char("Key ID", readonly=True)
    key_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Key Condition", readonly=True)
    key_issued_date = fields.Date("Key Issued Date", readonly=True)
    key_returned_date = fields.Date("Key Returned Date", readonly=True)
    key_remarks = fields.Text("Key Remarks", readonly=True)

    monitor_id = fields.Char("Monitor ID/Serial", readonly=True)
    monitor_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Monitor Condition", readonly=True)
    monitor_issued_date = fields.Date("Monitor Issued Date", readonly=True)
    monitor_returned_date = fields.Date("Monitor Returned Date", readonly=True)
    monitor_remarks = fields.Text("Monitor Remarks", readonly=True)

    printer_id = fields.Char("Printer/Scanner ID/Serial", readonly=True)
    printer_condition = fields.Selection([
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
        ("poor", "Poor"), ("damaged", "Damaged"),
    ], string="Printer/Scanner Condition", readonly=True)
    printer_issued_date = fields.Date("Printer/Scanner Issued Date", readonly=True)
    printer_returned_date = fields.Date("Printer/Scanner Returned Date", readonly=True)
    printer_remarks = fields.Text("Printer/Scanner Remarks", readonly=True)

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

    def action_store_pdf(self):
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
