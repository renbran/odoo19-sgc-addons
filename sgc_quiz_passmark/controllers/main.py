# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

from odoo.addons.website_slides.controllers.main import WebsiteSlides


class WebsiteSlidesQuizPassmark(WebsiteSlides):
    """Quiz submission with a passing score.

    The quiz is marked as completed only when the achieved score is at least
    the slide's passing score (default 80%). The achieved score, the passing
    score and the pass/fail state are returned to the frontend so the user
    always sees how much he scored after checking and submitting the quiz.
    """

    def _get_slide_quiz_data(self, slide):
        values = super()._get_slide_quiz_data(slide)
        values['passing_score'] = slide.passing_score
        return values

    @http.route('/slides/slide/quiz/submit', type="jsonrpc", auth="public", website=True)
    def slide_quiz_submit(self, slide_id, answer_ids):
        if request.website.is_public_user():
            return {'error': 'public_user'}
        fetch_res = self._fetch_slide(slide_id)
        if fetch_res.get('error'):
            return fetch_res
        slide = fetch_res['slide']

        if slide.user_has_completed:
            self._channel_remove_session_answers(slide.channel_id, slide)
            return {'error': 'slide_quiz_done'}

        all_questions = request.env['slide.question'].sudo().search([('slide_id', '=', slide.id)])

        user_answers = request.env['slide.answer'].sudo().search([('id', 'in', answer_ids)])
        if user_answers.mapped('question_id') != all_questions:
            return {'error': 'slide_quiz_incomplete'}

        user_bad_answers = user_answers.filtered(lambda answer: not answer.is_correct)

        total = len(user_answers)
        correct = total - len(user_bad_answers)
        score = round(correct / total * 100, 2) if total else 0.0
        passed = score >= slide.passing_score

        self._set_viewed_slide(slide, quiz_attempts_inc=True)
        quiz_info = self._get_slide_quiz_partner_info(slide, quiz_done=passed)

        rank_progress = {}
        if passed:
            rank_progress['previous_rank'] = self._get_rank_values(request.env.user)
            slide._action_mark_completed()
            rank_progress['new_rank'] = self._get_rank_values(request.env.user)
            rank_progress.update({
                'description': request.env.user.rank_id.description,
                'last_rank': not request.env.user._get_next_rank(),
                'level_up': rank_progress['previous_rank']['lower_bound'] != rank_progress['new_rank']['lower_bound']
            })
        self._channel_remove_session_answers(slide.channel_id, slide)
        return {
            'answers': {
                answer.question_id.id: {
                    'is_correct': answer.is_correct,
                    'comment': answer.comment,
                } for answer in user_answers
            },
            'completed': slide.user_has_completed,
            'channel_completion': slide.channel_id.completion,
            'quizKarmaWon': quiz_info['quiz_karma_won'],
            'quizKarmaGain': quiz_info['quiz_karma_gain'],
            'quizAttemptsCount': quiz_info['quiz_attempts_count'],
            'rankProgress': rank_progress,
            'score': score,
            'passing_score': slide.passing_score,
            'passed': passed,
        }