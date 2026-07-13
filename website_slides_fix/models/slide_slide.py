from odoo import api, fields, models
from dateutil.relativedelta import relativedelta


class SlideSlide(models.Model):
    _inherit = 'slide.slide'

    @api.depends('date_published', 'is_published')
    def _compute_is_new_slide(self):
        for slide in self:
            slide.is_new_slide = (
                slide.date_published > fields.Datetime.now() - relativedelta(days=7)
            ) if (slide.is_published and slide.date_published) else False
