from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    mailcow_mailbox_ids = fields.One2many(
        "mailcow.mailbox", "employee_id", string="Mailcow Mailboxes")
    mailcow_mailbox_count = fields.Integer(
        compute="_compute_mailcow_mailbox_count")

    laptop_id = fields.Char("Laptop ID/Serial", help="Laptop serial number or asset ID")
    laptop_model = fields.Char("Laptop Model")
    laptop_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ], string="Laptop Condition")
    laptop_issued_date = fields.Date("Laptop Issued Date")
    laptop_returned_date = fields.Date("Laptop Returned Date")
    laptop_estimated_value = fields.Monetary("Laptop Estimated Value", currency_field='company_currency_id')
    laptop_remarks = fields.Text("Laptop Remarks")

    mobile_id = fields.Char("Mobile ID/Serial", help="Mobile serial number or asset ID")
    mobile_model = fields.Char("Mobile Model")
    mobile_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ], string="Mobile Condition")
    mobile_issued_date = fields.Date("Mobile Issued Date")
    mobile_returned_date = fields.Date("Mobile Returned Date")
    mobile_estimated_value = fields.Monetary("Mobile Estimated Value", currency_field='company_currency_id')
    mobile_remarks = fields.Text("Mobile Remarks")

    tablet_id = fields.Char("Tablet/iPad ID/Serial", help="Tablet serial number or asset ID")
    tablet_model = fields.Char("Tablet/iPad Model")
    tablet_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ], string="Tablet Condition")
    tablet_issued_date = fields.Date("Tablet Issued Date")
    tablet_returned_date = fields.Date("Tablet Returned Date")
    tablet_estimated_value = fields.Monetary("Tablet/iPad Estimated Value", currency_field='company_currency_id')
    tablet_remarks = fields.Text("Tablet Remarks")

    access_card_id = fields.Char("Access Card ID", help="Access card ID or number")
    access_card_model = fields.Char("Access Card Type/Model")
    access_card_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ], string="Access Card Condition")
    access_card_issued_date = fields.Date("Access Card Issued Date")
    access_card_returned_date = fields.Date("Access Card Returned Date")
    access_card_estimated_value = fields.Monetary("Access Card Estimated Value", currency_field='company_currency_id')
    access_card_remarks = fields.Text("Access Card Remarks")

    key_id = fields.Char("Key ID", help="Key ID or number")
    key_model = fields.Char("Key Type/Label")
    key_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ], string="Key Condition")
    key_issued_date = fields.Date("Key Issued Date")
    key_returned_date = fields.Date("Key Returned Date")
    key_estimated_value = fields.Monetary("Key Estimated Value", currency_field='company_currency_id')
    key_remarks = fields.Text("Key Remarks")

    monitor_id = fields.Char("Monitor ID/Serial", help="Monitor serial number or asset ID")
    monitor_model = fields.Char("Monitor Model")
    monitor_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ], string="Monitor Condition")
    monitor_issued_date = fields.Date("Monitor Issued Date")
    monitor_returned_date = fields.Date("Monitor Returned Date")
    monitor_estimated_value = fields.Monetary("Monitor Estimated Value", currency_field='company_currency_id')
    monitor_remarks = fields.Text("Monitor Remarks")

    printer_id = fields.Char("Printer/Scanner ID/Serial", help="Printer serial number or asset ID")
    printer_model = fields.Char("Printer/Scanner Model")
    printer_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ], string="Printer/Scanner Condition")
    printer_issued_date = fields.Date("Printer/Scanner Issued Date")
    printer_returned_date = fields.Date("Printer/Scanner Returned Date")
    printer_estimated_value = fields.Monetary("Printer/Scanner Estimated Value", currency_field='company_currency_id')
    printer_remarks = fields.Text("Printer/Scanner Remarks")

    company_currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    warning_letter_date = fields.Date("Warning Letter Date")
    warning_letter_type = fields.Selection([
        ('verbal', 'Verbal Warning'),
        ('first_written', 'First Written Warning'),
        ('final_written', 'Final Written Warning'),
        ('dismissal', 'Notice of Dismissal'),
    ], string="Warning Type", default='first_written')
    warning_letter_reason = fields.Text("Warning Letter Reason", required=True)
    warning_letter_supervisor = fields.Many2one('hr.employee', string="Supervisor")
    warning_letter_improvement_period = fields.Integer("Improvement Period (Days)", default=30)
    warning_letter_acknowledged = fields.Boolean("Acknowledged by Employee")
    warning_letter_acknowledged_date = fields.Date("Acknowledged Date")

    nda_signed_date = fields.Date("NDA Signed Date")
    nda_version = fields.Char("NDA Version")
    nda_duration_years = fields.Integer("NDA Duration (Years)", default=2)
    nda_signed = fields.Boolean("NDA Signed")
    nda_signed_by_employee = fields.Boolean("Signed by Employee")
    nda_signed_by_company = fields.Boolean("Signed by Company")

    last_working_day = fields.Date("Last Working Day")

    def _compute_mailcow_mailbox_count(self):
        counts = dict(self.env["mailcow.mailbox"]._read_group(
            [("employee_id", "in", self.ids)],
            groupby=["employee_id"], aggregates=["__count"]))
        for rec in self:
            rec.mailcow_mailbox_count = counts.get(rec, 0)

    sgc_employee_document_ids = fields.One2many(
        "sgc.employee.document", "employee_id", string="Documents")
    sgc_employee_document_count = fields.Integer(
        compute="_compute_sgc_employee_document_count")

    def _compute_sgc_employee_document_count(self):
        counts = dict(self.env["sgc.employee.document"]._read_group(
            [("employee_id", "in", self.ids)],
            groupby=["employee_id"], aggregates=["__count"]))
        for rec in self:
            rec.sgc_employee_document_count = counts.get(rec, 0)

    def action_open_employee_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Documents",
            "res_model": "sgc.employee.document",
            "view_mode": "list,form",
            "domain": [("employee_id", "=", self.id)],
        }

    def action_new_document_nda(self):
        return self._new_employee_document("nda")

    def action_new_document_warning_letter(self):
        return self._new_employee_document("warning_letter")

    def action_new_document_asset_handover(self):
        return self._new_employee_document("asset_handover")

    def _new_employee_document(self, doc_type):
        self.ensure_one()
        document = self.env["sgc.employee.document"].create({
            "doc_type": doc_type,
            "employee_id": self.id,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "sgc.employee.document",
            "res_id": document.id,
            "view_mode": "form",
        }

    def action_open_mailcow_mailboxes(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": "Mailboxes",
            "res_model": "mailcow.mailbox",
            "context": {
                "default_employee_id": self.id,
                "default_name": self.name,
                "default_user_id": self.user_id.id,
                "default_local_part": (
                    self.work_email.split("@")[0].lower()
                    if self.work_email else False),
            },
        }
        if self.mailcow_mailbox_count == 1:
            action.update({
                "view_mode": "form",
                "res_id": self.mailcow_mailbox_ids[0].id,
            })
        elif self.mailcow_mailbox_count:
            action.update({
                "view_mode": "list,form",
                "domain": [("employee_id", "=", self.id)],
            })
        else:
            # No mailbox yet: open a prefilled creation form.
            action["view_mode"] = "form"
        return action
