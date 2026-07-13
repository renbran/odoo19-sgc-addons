# -*- coding: utf-8 -*-
from odoo import models, fields

class SGCCopilotLog(models.Model):
    _name = 'sgc.copilot.log'
    _description = 'SGC Copilot Conversation Log'
    _order = 'create_date desc'
    _rec_name = 'session_id'

    session_id    = fields.Char('Session ID', index=True)
    user_message  = fields.Text('User Message')
    bot_reply     = fields.Text('Bot Reply')
    page_url      = fields.Char('Page URL')
    # NOTE: create_date is automatically provided by models.Model — no need to redeclare.
