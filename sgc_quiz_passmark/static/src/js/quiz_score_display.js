/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { markup } from "@odoo/owl";
import { Quiz } from "@website_slides/js/slides_course_quiz";

/**
 * Expose the quiz passing score on the quiz object so the templates can
 * display it (before and after submission).
 *
 * The backend already returns `score`, `passing_score` and `passed` in the
 * `/slides/slide/quiz/submit` response; those keys are merged into
 * `widget.quiz` by the standard `_submitQuiz` handler (Object.assign) and are
 * therefore directly usable by the validation / finish dialog templates.
 */
Quiz.include({
    init: function (parent, slide_data, channel_data, quiz_data) {
        this._super.apply(this, arguments);
        if (this.quiz) {
            this.quiz.passingScore =
                (quiz_data && quiz_data.passingScore) ||
                slide_data.quizPassingScore ||
                80;
        }
    },

    _fetchQuiz: function () {
        const self = this;
        return rpc('/slides/slide/quiz/get', {
            'slide_id': self.slide.id,
        }).then(function (quiz_data) {
            self.slide.sessionAnswers = quiz_data.session_answers;
            self.quiz = {
                description_safe: quiz_data.slide_description ? markup(quiz_data.slide_description) : '',
                questions: quiz_data.slide_questions || [],
                questionsCount: quiz_data.slide_questions.length,
                quizAttemptsCount: quiz_data.quiz_attempts_count || 0,
                quizKarmaGain: quiz_data.quiz_karma_gain || 0,
                quizKarmaWon: quiz_data.quiz_karma_won || 0,
                slideResources: quiz_data.slide_resource_ids || [],
                passingScore: quiz_data.passing_score || 80,
            };
        });
    },
});