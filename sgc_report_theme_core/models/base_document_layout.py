from odoo import fields, models


class BaseDocumentLayout(models.TransientModel):
    """external_layout_sgc (views/report_layout_sgc.xml) reads
    company.social_facebook / social_twitter / social_linkedin. When that
    template renders a real report, `company` is a genuine res.company
    record and those fields exist (from the `social_media` module). When
    the same template renders the "Configure Document Layout" live preview
    (base.document.layout._compute_preview), `company` is this transient
    wizard instead, which never related those fields onto itself the way
    Odoo core already does for logo/report_header/colors/etc. below -- so
    `company.social_linkedin` raised AttributeError instead of being falsy.

    Fix is additive only, matching Odoo core's own pattern on this model:
    related fields, readonly, no new report/layout logic.
    """

    _inherit = "base.document.layout"

    social_facebook = fields.Char(related="company_id.social_facebook", readonly=True)
    social_twitter = fields.Char(related="company_id.social_twitter", readonly=True)
    social_linkedin = fields.Char(related="company_id.social_linkedin", readonly=True)
