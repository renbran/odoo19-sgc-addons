from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class LearningQuiz(models.Model):
    _name = 'learning.quiz'
    _description = 'Learning Quiz'
    _order = 'name'

    name = fields.Char(string='Quiz Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
    question_ids = fields.One2many('learning.quiz.question', 'quiz_id', string='Questions')
    question_count = fields.Integer(compute='_compute_question_count', string='Question Count')
    passing_score = fields.Integer(string='Passing Score (%)', default=70)
    time_limit = fields.Integer(string='Time Limit (minutes)', help='Time limit in minutes for the quiz')
    allow_retake = fields.Boolean(string='Allow Retake', default=True)
    show_result_immediately = fields.Boolean(string='Show Result Immediately', default=True)
    randomize_questions = fields.Boolean(string='Randomize Questions', default=False)
    randomize_options = fields.Boolean(string='Randomize Options', default=False)


class LearningQuizQuestion(models.Model):
    _name = 'learning.quiz.question'
    _description = 'Learning Quiz Question'
    _order = 'sequence'

    quiz_id = fields.Many2one('learning.quiz', string='Quiz', required=True, ondelete='cascade')
    sequence = fields.Integer(default=1)
    question_type = fields.Selection([
        ('multiple_choice', 'Multiple Choice'),
        ('fill_blank', 'Fill in the Blank'),
        ('true_false', 'True/False'),
    ], string='Question Type', required=True)
    question_text = fields.Html(string='Question Text', required=True)
    explanation = fields.Html(string='Explanation')
    points = fields.Integer(string='Points', default=1)
    position = fields.Integer(string='Position', default=1)
    option_ids = fields.One2many('learning.quiz.option', 'question_id', string='Options')
    correct_answer = fields.Char(string='Correct Answer')
    fill_blank_count = fields.Integer(string='Blank Count', default=1)
    is_required = fields.Boolean(string='Required', default=True)
    
    @api.depends('quiz_id')
    def _compute_question_count(self):
        for question in self:
            question.question_count = len(question.quiz_id.question_ids)


class LearningQuizOption(models.Model):
    _name = 'learning.quiz.option'
    _description = 'Learning Quiz Option'
    _order = 'sequence'

    question_id = fields.Many2one('learning.quiz.question', string='Question', required=True, ondelete='cascade')
    sequence = fields.Integer(default=1)
    text = fields.Char(string='Option Text', required=True)
    is_correct = fields.Boolean(string='Is Correct', default=False)
    explanation = fields.Text(string='Explanation')


class LearningQuizAttempt(models.Model):
    _name = 'learning.quiz.attempt'
    _description = 'Learning Quiz Attempt'
    _order = 'create_date desc'

    quiz_id = fields.Many2one('learning.quiz', string='Quiz', required=True)
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    state = fields.Selection([
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('passed', 'Passed'),
    ], string='State', default='in_progress')
    score = fields.Float(string='Score', compute='_compute_score', store=True)
    max_score = fields.Float(string='Maximum Score', compute='_compute_max_score', store=True)
    percentage = fields.Float(string='Percentage', compute='_compute_percentage', store=True)
    time_spent = fields.Integer(string='Time Spent (seconds)')
    start_time = fields.Datetime(string='Start Time')
    end_time = fields.Datetime(string='End Time')
    answer_ids = fields.One2many('learning.quiz.answer', 'attempt_id', string='Answers')
    feedback = fields.Text(string='Feedback')
    
    @api.depends('answer_ids.score')
    def _compute_score(self):
        for attempt in self:
            attempt.score = sum(answer.score for answer in attempt.answer_ids)
    
    @api.depends('quiz_id.question_ids.points')
    def _compute_max_score(self):
        for attempt in self:
            attempt.max_score = sum(question.points for question in attempt.quiz_id.question_ids)
    
    @api.depends('score', 'max_score')
    def _compute_percentage(self):
        for attempt in self:
            if attempt.max_score > 0:
                attempt.percentage = (attempt.score / attempt.max_score) * 100
            else:
                attempt.percentage = 0

    def action_complete(self):
        for attempt in self:
            attempt.end_time = fields.Datetime.now()
            passing = attempt.quiz_id.passing_score or 0
            attempt.state = 'passed' if attempt.percentage >= passing else 'failed'

    def action_reset(self):
        for attempt in self:
            attempt.write({'state': 'in_progress', 'end_time': False, 'feedback': False})
            attempt.answer_ids.unlink()


class LearningQuizAnswer(models.Model):
    _name = 'learning.quiz.answer'
    _description = 'Learning Quiz Answer'
    _order = 'sequence'

    attempt_id = fields.Many2one('learning.quiz.attempt', string='Attempt', required=True, ondelete='cascade')
    question_id = fields.Many2one('learning.quiz.question', string='Question', required=True)
    sequence = fields.Integer(related='question_id.sequence')
    answer_text = fields.Text(string='Answer')
    selected_options = fields.Many2many('learning.quiz.option', string='Selected Options')
    is_correct = fields.Boolean(string='Is Correct', compute='_compute_is_correct', store=True)
    score = fields.Float(string='Score', compute='_compute_score', store=True)
    points = fields.Integer(related='question_id.points')
    
    @api.depends('selected_options', 'question_id.correct_answer')
    def _compute_is_correct(self):
        for answer in self:
            if answer.question_id.question_type == 'multiple_choice':
                correct_options = answer.question_id.option_ids.filtered('is_correct')
                answer.is_correct = len(answer.selected_options) == len(correct_options) and \
                                  all(opt in answer.selected_options for opt in correct_options)
            elif answer.question_id.question_type == 'fill_blank':
                answer.is_correct = answer.answer_text.strip().lower() == answer.question_id.correct_answer.strip().lower()
            elif answer.question_id.question_type == 'true_false':
                answer.is_correct = answer.answer_text.strip().lower() == answer.question_id.correct_answer.strip().lower()
    
    @api.depends('is_correct', 'question_id.points')
    def _compute_score(self):
        for answer in self:
            if answer.is_correct:
                answer.score = answer.question_id.points
            else:
                answer.score = 0


class LearningQuizResult(models.Model):
    _name = 'learning.quiz.result'
    _description = 'Learning Quiz Result'
    
    attempt_id = fields.Many2one('learning.quiz.attempt', string='Attempt', required=True)
    user_id = fields.Many2one('res.users', string='User', related='attempt_id.user_id')
    quiz_id = fields.Many2one('learning.quiz', string='Quiz', related='attempt_id.quiz_id')
    score = fields.Float(related='attempt_id.score')
    percentage = fields.Float(related='attempt_id.percentage')
    state = fields.Selection(related='attempt_id.state')
    created_at = fields.Datetime(related='attempt_id.create_date')
    feedback = fields.Text(related='attempt_id.feedback')