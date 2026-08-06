# -*- coding: utf-8 -*-
from odoo import fields, models


class SlideSlide(models.Model):
    """Add a configurable passing score to quiz slides.

    A quiz is only considered completed when the user reaches this score.
    """

    _inherit = 'slide.slide'

    passing_score = fields.Float(
        string='Passing Score (%)',
        default=80.0,
        help='Minimum score (in %) that must be reached for the quiz to be '
             'marked as completed. The user is informed of his achieved score '
             'after every submission.',
    )