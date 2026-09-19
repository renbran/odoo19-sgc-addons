from odoo import fields, models


class BaseDocumentLayout(models.TransientModel):
    """external_layout_sgc (views/report_layout_sgc.xml) reads all six of
    company.social_facebook / social_twitter / social_linkedin /
    social_instagram / social_youtube / social_github. When that template
    renders a real report, `company` is a genuine res.company record and
    those fields exist (from the `social_media` module). When the same
    template renders the "Configure Document Layout" live preview
    (base.document.layout._compute_preview), `company` is this transient
    wizard instead, which never related those fields onto itself the way
    Odoo core already does for logo/report_header/colors/etc. below -- so
    `company.social_linkedin` (and, separately, `social_instagram`) raised
    AttributeError instead of being falsy.

    2026-09-19: the first pass of this fix only added facebook/twitter/
    linkedin and missed instagram/youtube/github, which the same template
    also reads (confirmed by grepping every `company.social_*` reference in
    views/report_layout_sgc.xml) -- adding the remaining three now so this
    doesn't recur a third time.

    Fix is additive only, matching Odoo core's own pattern on this model:
    related fields, readonly, no new report/layout logic.
    """

    _inherit = "base.document.layout"

    social_facebook = fields.Char(related="company_id.social_facebook", readonly=True)
    social_twitter = fields.Char(related="company_id.social_twitter", readonly=True)
    social_linkedin = fields.Char(related="company_id.social_linkedin", readonly=True)
    social_instagram = fields.Char(related="company_id.social_instagram", readonly=True)
    social_youtube = fields.Char(related="company_id.social_youtube", readonly=True)
    social_github = fields.Char(related="company_id.social_github", readonly=True)
