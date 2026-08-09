from odoo import api, fields, models, _
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
import binascii
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
_ASSET_GROUPS = ("laptop", "mobile", "tablet", "access_card", "key", "monitor", "printer")
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
def _asset_fields():
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
    fields_list = []
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
    for group in _ASSET_GROUPS:
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
        fields_list.append(f"{group}_id")
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
        fields_list.append(f"{group}_condition")
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
            raise ValueError(_("No report configured for document type: %s") % self.doc_type)
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
        fields_list.append(f"{group}_returned_date")
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
        fields_list.append(f"{group}_remarks")
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
    return fields_list
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
SNAPSHOT_FIELDS = [
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
    "employee_name",
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
    "job_title",
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
    "department_id",
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
    "last_working_day",
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
    "nda_version",
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
    "nda_duration_years",
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
    "warning_letter_supervisor_id",
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
    "warning_letter_improvement_period",
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
] + _asset_fields()
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
_SNAPSHOT_SOURCES = {
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
    "employee_name": "name",
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
    "warning_letter_supervisor_id": "warning_letter_supervisor",
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
}
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
class SgcEmployeeDocument(models.Model):
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
    _name = "sgc.employee.document"
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
    _description = "Employee Document"
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
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
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
    _order = "create_date desc"
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
    _REPORT_XMLIDS = {
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
        "nda": "sgc_mailcow_connector.action_report_nda",
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
        "warning_letter": "sgc_mailcow_connector.action_report_warning_letter",
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
        "asset_handover": "sgc_mailcow_connector.action_report_company_asset_handover",
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
    }
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
    _EMAIL_TEMPLATE_XMLIDS = {
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
        "nda": "sgc_mailcow_connector.email_template_nda",
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
        "warning_letter": "sgc_mailcow_connector.email_template_warning_letter",
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
        "asset_handover": "sgc_mailcow_connector.email_template_company_asset_handover",
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
    }
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
    # New fields for signature
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
    signature = fields.Image(copy=False, attachment=True, max_width=1024, max_height=1024)
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
    signed_by = fields.Char(copy=False)
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
    signed_on = fields.Datetime(copy=False)
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
    # Existing fields...
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
    name = fields.Char("Document Number", readonly=True, copy=False)
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
    doc_type = fields.Selection([
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
        ("nda", "NDA"),
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
        ("warning_letter", "Warning Letter"),
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
        ("asset_handover", "Asset Handover"),
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
    ], string="Document Type", required=True)
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
    employee_id = fields.Many2one(
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
        "hr.employee", string="Employee", required=True, ondelete="cascade", index=True)
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
    state = fields.Selection([
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
        ("draft", "Draft"),
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
        ("sent", "Sent"),
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
        ("signed", "Signed"),
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
    ], string="Status", default="draft", tracking=True)
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
    date = fields.Date("Document Date", default=fields.Date.context_today, readonly=True)
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
    # Frozen snapshot of the report-relevant employee data, copied at creation.
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
    employee_name = fields.Char("Employee Name", readonly=True)
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
    job_title = fields.Char("Job Title", readonly=True)
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
    department_id = fields.Many2one("hr.department", string="Department", readonly=True)
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
    last_working_day = fields.Date("Last Working Day", readonly=True)
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
    nda_version = fields.Char("NDA Version", readonly=True)
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
    nda_duration_years = fields.Integer("NDA Duration (Years)", readonly=True)
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
    warning_letter_supervisor_id = fields.Many2one(
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
        "hr.employee", string="Supervisor", readonly=True)
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
    warning_letter_improvement_period = fields.Integer(
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
        "Improvement Period (Days)", readonly=True)
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
    laptop_id = fields.Char("Laptop ID/Serial", readonly=True)
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
    laptop_condition = fields.Selection([
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
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
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
        ("poor", "Poor"), ("damaged", "Damaged"),
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
    ], string="Laptop Condition", readonly=True)
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
    laptop_issued_date = fields.Date("Laptop Issued Date", readonly=True)
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
    laptop_returned_date = fields.Date("Laptop Returned Date", readonly=True)
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
    laptop_remarks = fields.Text("Laptop Remarks", readonly=True)
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
    mobile_id = fields.Char("Mobile ID/Serial", readonly=True)
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
    mobile_condition = fields.Selection([
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
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
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
        ("poor", "Poor"), ("damaged", "Damaged"),
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
    ], string="Mobile Condition", readonly=True)
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
    mobile_issued_date = fields.Date("Mobile Issued Date", readonly=True)
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
    mobile_returned_date = fields.Date("Mobile Returned Date", readonly=True)
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
    mobile_remarks = fields.Text("Mobile Remarks", readonly=True)
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
    tablet_id = fields.Char("Tablet/iPad ID/Serial", readonly=True)
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
    tablet_condition = fields.Selection([
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
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
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
        ("poor", "Poor"), ("damaged", "Damaged"),
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
    ], string="Tablet Condition", readonly=True)
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
    tablet_issued_date = fields.Date("Tablet Issued Date", readonly=True)
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
    tablet_returned_date = fields.Date("Tablet Returned Date", readonly=True)
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
    tablet_remarks = fields.Text("Tablet Remarks", readonly=True)
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
    access_card_id = fields.Char("Access Card ID", readonly=True)
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
    access_card_condition = fields.Selection([
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
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
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
        ("poor", "Poor"), ("damaged", "Damaged"),
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
    ], string="Access Card Condition", readonly=True)
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
    access_card_issued_date = fields.Date("Access Card Issued Date", readonly=True)
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
    access_card_returned_date = fields.Date("Access Card Returned Date", readonly=True)
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
    access_card_remarks = fields.Text("Access Card Remarks", readonly=True)
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
    key_id = fields.Char("Key ID", readonly=True)
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
    key_condition = fields.Selection([
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
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
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
        ("poor", "Poor"), ("damaged", "Damaged"),
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
    ], string="Key Condition", readonly=True)
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
    key_issued_date = fields.Date("Key Issued Date", readonly=True)
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
    key_returned_date = fields.Date("Key Returned Date", readonly=True)
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
    key_remarks = fields.Text("Key Remarks", readonly=True)
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
    monitor_id = fields.Char("Monitor ID/Serial", readonly=True)
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
    monitor_condition = fields.Selection([
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
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
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
        ("poor", "Poor"), ("damaged", "Damaged"),
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
    ], string="Monitor Condition", readonly=True)
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
    monitor_issued_date = fields.Date("Monitor Issued Date", readonly=True)
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
    monitor_returned_date = fields.Date("Monitor Returned Date", readonly=True)
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
    monitor_remarks = fields.Text("Monitor Remarks", readonly=True)
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
    printer_id = fields.Char("Printer/Scanner ID/Serial", readonly=True)
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
    printer_condition = fields.Selection([
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
        ("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"),
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
        ("poor", "Poor"), ("damaged", "Damaged"),
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
    ], string="Printer/Scanner Condition", readonly=True)
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
    printer_issued_date = fields.Date("Printer/Scanner Issued Date", readonly=True)
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
    printer_returned_date = fields.Date("Printer/Scanner Returned Date", readonly=True)
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
    printer_remarks = fields.Text("Printer/Scanner Remarks", readonly=True)
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
    pdf_attachment_id = fields.Many2one(
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
        "ir.attachment", string="PDF Document", readonly=True, copy=False,
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
        ondelete="set null")
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
    _name_uniq = models.Constraint(
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
        "unique(name)",
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
        "Document number must be unique",
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
    )
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
    @api.model_create_multi
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
    def create(self, vals_list):
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
        for vals in vals_list:
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
            if not vals.get("name") and vals.get("doc_type"):
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
                vals["name"] = self.env["ir.sequence"].next_by_code(
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
                    "sgc.employee.document." + vals["doc_type"])
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
            if vals.get("employee_id"):
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
                emp = self.env["hr.employee"].browse(vals["employee_id"])
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
                if emp:
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
                    for fname in SNAPSHOT_FIELDS:
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
                        if fname not in vals:
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
                            source = _SNAPSHOT_SOURCES.get(fname, fname)
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
                            value = emp[source]
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
                            if isinstance(emp._fields[source], fields.Many2one):
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
                                value = value.id
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
                            vals[fname] = value
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
        return super().create(vals_list)
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
    def _compute_access_url(self):
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
        for doc in self:
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
            doc.access_url = "/my/employee-documents/%s" % doc.id
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
    def _has_to_be_signed(self):
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
        return self.state == 'sent' and not self.signature
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
    def action_send(self):
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
        """ Opens a wizard to compose an email, with relevant mail template loaded by default """
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
        self.ensure_one()
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
        template_id = self.env.ref(self._EMAIL_TEMPLATE_XMLIDS[self.doc_type]).id
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
        ctx = {
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
            'default_model': 'sgc.employee.document',
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
            'default_res_ids': self.ids,
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
            'default_composition_mode': 'comment',
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
            'default_template_id': template_id,
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
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
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
            'force_email': True,
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
            'mark_doc_as_sent': True,
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
            'hide_mail_template_management_options': True,
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
        }
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
        return {
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
            'name': _('Send'),
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
            'type': 'ir.actions.act_window',
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
            'view_mode': 'form',
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
            'res_model': 'mail.compose.message',
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
            'views': [(False, 'form')],
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
            'target': 'new',
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
            'context': ctx,
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
        }
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
    def message_post(self, **kwargs):
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
        if self.env.context.get('mark_doc_as_sent'):
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
            self.filtered(lambda d: d.state == 'draft').with_context(tracking_disable=True).write({'state': 'sent'})
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
    def action_store_pdf(self):
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
        self.ensure_one()
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
        report = self.env.ref(self._REPORT_XMLIDS[self.doc_type])
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
        pdf, _ = report._render_qweb_pdf(report, self.ids)
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
        if self.pdf_attachment_id:
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
            self.pdf_attachment_id.unlink()
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
        attachment = self.env["ir.attachment"].create({
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
            "name": f"{self.name}.pdf",
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
            "type": "binary",
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
            "raw": pdf,
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
            "res_model": self._name,
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
            "res_id": self.id,
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
        })
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
        self.pdf_attachment_id = attachment
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
        return True
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
