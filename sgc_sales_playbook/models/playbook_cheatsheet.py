# -*- coding: utf-8 -*-
from odoo import models, fields

CHEAT_SHEET_HTML = """
<div class="o_sgc_playbook_cheatsheet">
<h2>SGC TECH AI — Sales Playbook Cheat Sheet</h2>

<h3>4 Value Statements</h3>
<ol>
<li><b>Commission tracking</b> — "Spreadsheets that break every month. We fix that."</li>
<li><b>FTA deadline</b> — "Your invoicing system may not be Phase 2 ready. Let's check."</li>
<li><b>Manual back-office</b> — "Cheque processing taking 3 weeks? We automate that."</li>
<li><b>Growth systems</b> — "Growing past 10 agents? Excel won't cut it anymore."</li>
</ol>

<h3>4 Objection Responses (Mr. Miyagi Method)</h3>
<ol>
<li><b>"Already have a system"</b> → "That's exactly why I'm calling. We work with [system] users every day."</li>
<li><b>"Not interested"</b> → "Quick question — are you already set up for this? If yes, I'll leave you alone."</li>
<li><b>"Send email"</b> → "I will — but a 3-minute call saves 30 minutes of email. Got 3 minutes?"</li>
<li><b>"No budget"</b> → "The diagnostic is free. If the gap is small, walk away. If it's big, plan for it."</li>
</ol>

<h3>4 Gate Questions (Verifiable Buyer Exit Criteria)</h3>
<ol>
<li>What is the specific problem we're solving?</li>
<li>What is the cost of doing nothing?</li>
<li>Who needs to approve this?</li>
<li>What is the timeline?</li>
</ol>
<p><i>If you can't answer all four, it's not a deal yet — it's a conversation. Keep it in
discovery.</i></p>

<h3>4 Mindset Shifts</h3>
<ol>
<li>"They rejected me" → "One step closer to yes."</li>
<li>"I'm tired" → "One more call."</li>
<li>"This isn't working" → "Volume cures everything."</li>
<li>"I'm not good at this" → "Every call makes me better."</li>
</ol>
</div>
"""


class SgcPlaybookCheatsheetWizard(models.TransientModel):
    _name = "sgc.playbook.cheatsheet.wizard"
    _description = "SGC Sales Playbook Cheat Sheet"

    content = fields.Html(default=CHEAT_SHEET_HTML, readonly=True, sanitize=False)
