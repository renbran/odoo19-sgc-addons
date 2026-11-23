# -*- coding: utf-8 -*-
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from markupsafe import Markup, escape

from odoo import models, fields, api, _

from . import lead_intelligence as li

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML rendering helpers for the read-only "intelligence tab" computed fields
# (Task 7). These are intentionally simple bullet-list renderers over the
# Universal JSON Contract's per-section shape — not a generic JSON->HTML
# framework. Every helper tolerates missing/malformed input by falling back
# to a plain "not applicable" / "no data" message (never raises).
# ---------------------------------------------------------------------------

_NOT_APPLICABLE_HTML = '<p><i>Not applicable for this lead.</i></p>'
_NO_DATA_HTML = '<p><i>No data available.</i></p>'


def _humanize_key(key):
    """``some_field_name`` -> ``Some Field Name``."""
    return ' '.join(word.capitalize() for word in str(key).split('_'))


def _format_contract_value(value):
    """Render one Universal Contract field value as an HTML-safe fragment.

    Handles the three shapes a field can take in the contract: a
    ``{value, confidence, reason}`` wrapper dict, a flat list of strings
    (post-parser flattening, Decision E), or a plain scalar. Returns ''
    when there is nothing worth displaying.
    """
    if isinstance(value, dict):
        if value.get('not_applicable'):
            return ''
        inner = _format_contract_value(value.get('value'))
        confidence = value.get('confidence')
        if inner and confidence:
            return '%s <i>(confidence: %s)</i>' % (inner, escape(str(confidence)))
        return inner
    if isinstance(value, list):
        items = [_format_contract_value(v) for v in value]
        items = [i for i in items if i]
        return ', '.join(items)
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if value in (None, ''):
        return ''
    return str(escape(str(value)))


def _render_contract_section(section, title=None):
    """Bullet-list HTML for one Universal Contract section dict.

    Renders '<p><i>Not applicable...</i></p>' when the section is absent,
    not a dict, empty, or explicitly marked ``not_applicable``.
    """
    if not isinstance(section, dict) or not section or section.get('not_applicable'):
        body = _NOT_APPLICABLE_HTML
    else:
        rows = []
        for key, value in section.items():
            if key == 'not_applicable':
                continue
            text = _format_contract_value(value)
            if text:
                rows.append('<li><b>%s</b>: %s</li>' % (escape(_humanize_key(key)), text))
        body = ('<ul>%s</ul>' % ''.join(rows)) if rows else _NO_DATA_HTML
    if title:
        return '<h6>%s</h6>%s' % (escape(title), body)
    return body


def _render_evidence_html(evidence_list):
    """Bullet-list HTML for the normalized evidence list (Evidence tab)."""
    if not isinstance(evidence_list, list) or not evidence_list:
        return '<p><i>No research evidence recorded for this lead.</i></p>'
    rows = []
    for item in evidence_list:
        if not isinstance(item, dict):
            continue
        title = item.get('title') or item.get('url') or 'Untitled source'
        url = item.get('url') or ''
        snippet = item.get('snippet') or ''
        provider = item.get('provider') or ''
        retrieved_at = item.get('retrieved_at') or ''
        if url:
            title_html = '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (
                escape(url), escape(title))
        else:
            title_html = escape(title)
        meta_bits = [b for b in (
            ('<i>%s</i>' % escape(provider)) if provider else '',
            escape(retrieved_at) if retrieved_at else '',
        ) if b]
        meta = ' &mdash; '.join(meta_bits)
        snippet_html = ('<br/>%s' % escape(snippet)) if snippet else ''
        rows.append('<li>%s%s%s</li>' % (
            title_html, snippet_html, ('<br/><small>%s</small>' % meta) if meta else ''))
    return ('<ul>%s</ul>' % ''.join(rows)) if rows else '<p><i>No research evidence recorded for this lead.</i></p>'


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    ai_probability_score = fields.Float(
        string='AI Probability Score',
        aggregator='avg',
        help='AI-calculated probability score based on lead quality analysis',
    )
    ai_enrichment_status = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('partial', 'Partial'),
        ('parse_failure', 'Parse Failure'),
        ('failed', 'Failed'),
    ], string='AI Enrichment Status', default='pending')
    ai_last_enrichment_date = fields.Datetime(
        string='Last AI Enrichment',
        readonly=True,
    )
    auto_enrich = fields.Boolean(
        string='Auto-Enrich',
        default=False,
        help='Pick up this lead in the (opt-in) auto-enrichment cron. Off by '
             'default: enrichment calls a paid LLM, so a lead only gets '
             'swept up automatically once someone opts it in -- otherwise '
             'use the "AI Enrich" button for an on-demand, explicitly '
             'triggered run.',
    )
    ai_completeness_score = fields.Float(
        string='Completeness Score',
        aggregator='avg',
        help='Score based on form completeness (0-100)',
    )
    ai_clarity_score = fields.Float(
        string='Clarity Score',
        aggregator='avg',
        help='Score based on requirement clarity (0-100)',
    )
    ai_engagement_score = fields.Float(
        string='Engagement Score',
        aggregator='avg',
        help='Score based on engagement level (0-100)',
    )
    ai_enrichment_report = fields.Text(
        string='AI Enrichment Report',
        readonly=True,
    )
    ai_analysis_summary = fields.Text(
        string='AI Analysis Summary',
        readonly=True,
    )
    ai_enrichment_data = fields.Text(
        string='AI Enrichment Data (JSON)',
        readonly=True,
    )
    ai_score_color = fields.Integer(
        string='AI Score Color Indicator',
        compute='_compute_ai_score_color',
        store=True,
    )

    # ------------------------------------------------------------------
    # Lead Intelligence Engine fields (Universal JSON Contract)
    # ------------------------------------------------------------------
    entity_hint = fields.Selection(
        li.ENTITY_HINT_SELECTION, string='Entity Hint (heuristic)', readonly=True)
    ai_entity_type = fields.Selection(
        li.ENTITY_TYPE_SELECTION, string='AI Entity Type', readonly=True)
    ai_entity_type_confidence = fields.Selection(
        li.CONFIDENCE_SELECTION, string='AI Entity Confidence', readonly=True)
    ai_need_score = fields.Float(string='Need Score', readonly=True, aggregator='avg')
    ai_budget_score = fields.Float(string='Budget Score', readonly=True, aggregator='avg')
    ai_authority_score = fields.Float(string='Authority Score', readonly=True, aggregator='avg')
    ai_timeline_score = fields.Float(string='Timeline Score', readonly=True, aggregator='avg')
    ai_urgency_score = fields.Float(string='Urgency Score', readonly=True, aggregator='avg')
    ai_relationship_score = fields.Float(string='Relationship Score', readonly=True, aggregator='avg')
    ai_digital_maturity_score = fields.Float(
        string='Digital Maturity Score', readonly=True, aggregator='avg')
    ai_implementation_complexity_score = fields.Float(
        string='Implementation Complexity Score', readonly=True, aggregator='avg')
    ai_proposal_confidence_score = fields.Float(
        string='Proposal Confidence Score', readonly=True, aggregator='avg')
    ai_win_probability_score = fields.Float(
        string='Win Probability Score', readonly=True, aggregator='avg')
    ai_opportunity_score = fields.Float(string='Opportunity Score', readonly=True, aggregator='avg')
    ai_scoring_rationale = fields.Text(string='Scoring Rationale (11 lines)', readonly=True)
    ai_budget_tier = fields.Char(string='Budget Tier', readonly=True)
    ai_industry = fields.Char(string='Industry', readonly=True)
    ai_readiness = fields.Selection([
        ('hot', 'Hot'), ('warm', 'Warm'), ('nurture', 'Nurture'), ('cold', 'Cold'),
    ], string='Readiness', compute='_compute_readiness', store=True, readonly=True)
    ai_enrichment_evidence = fields.Text(string='Normalized Evidence (JSON)', readonly=True)
    ai_classification_mismatch = fields.Boolean(
        string='Classification Mismatch', compute='_compute_mismatch', store=True, readonly=True,
    )

    # ------------------------------------------------------------------
    # Notebook-tab computed Html fields (Task 7). Non-stored, purely
    # derived display data parsed from ai_enrichment_data / _evidence —
    # never searched/filtered/aggregated on, so store=True is unneeded.
    # ------------------------------------------------------------------
    ai_company_intelligence_html = fields.Html(
        string='Company Intelligence', compute='_compute_ai_company_intelligence_html', readonly=True)
    ai_customer_intelligence_html = fields.Html(
        string='Customer Intelligence', compute='_compute_ai_customer_intelligence_html', readonly=True)
    ai_relationship_intelligence_html = fields.Html(
        string='Relationship Intelligence', compute='_compute_ai_relationship_intelligence_html', readonly=True)
    ai_buying_intelligence_html = fields.Html(
        string='Buying Intelligence', compute='_compute_ai_buying_intelligence_html', readonly=True)
    ai_opportunity_intelligence_html = fields.Html(
        string='Opportunity Intelligence', compute='_compute_ai_opportunity_intelligence_html', readonly=True)
    ai_proposal_intelligence_html = fields.Html(
        string='Proposal Intelligence', compute='_compute_ai_proposal_intelligence_html', readonly=True)
    ai_executive_summary_html = fields.Html(
        string='Executive Summary', compute='_compute_ai_executive_summary_html', readonly=True)
    ai_evidence_html = fields.Html(
        string='Evidence', compute='_compute_ai_evidence_html', readonly=True)

    @api.depends('ai_probability_score')
    def _compute_ai_score_color(self):
        for lead in self:
            if lead.ai_probability_score >= 70:
                lead.ai_score_color = 10  # green/success
            elif lead.ai_probability_score >= 40:
                lead.ai_score_color = 5   # orange/warning
            else:
                lead.ai_score_color = 1   # red/danger

    @api.depends('ai_win_probability_score', 'ai_need_score', 'ai_budget_score')
    def _compute_readiness(self):
        """Stored readiness label derived from the win/need/budget scores
        (Decision G.1). The pure logic lives in the helper module so it is
        unit-testable without an Odoo environment."""
        for lead in self:
            label = li.compute_readiness_label({
                'ai_win_probability_score': lead.ai_win_probability_score,
                'ai_need_score': lead.ai_need_score,
                'ai_budget_score': lead.ai_budget_score,
            })
            lead.ai_readiness = label.lower()

    @api.depends('entity_hint', 'ai_entity_type', 'ai_entity_type_confidence')
    def _compute_mismatch(self):
        """True iff the heuristic family disagrees with the LLM family AND the
        LLM classified with high confidence (Decision I). ``unknown`` has no
        family and therefore never produces a mismatch on its own."""
        for lead in self:
            hint_family = li.entity_family(lead.entity_hint)
            llm_family = li.entity_family(lead.ai_entity_type)
            lead.ai_classification_mismatch = bool(
                hint_family and llm_family
                and hint_family != llm_family
                and lead.ai_entity_type_confidence == 'high'
            )

    def _parsed_enrichment_data(self):
        """Best-effort ``json.loads(ai_enrichment_data)`` -> dict, or ``{}``
        on empty/malformed content. Never raises (parser tolerance is a core
        design principle of this feature — a bad/absent JSON blob must never
        break the form view)."""
        self.ensure_one()
        try:
            data = json.loads(self.ai_enrichment_data or '{}')
        except (ValueError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    @api.depends('ai_enrichment_data')
    def _compute_ai_company_intelligence_html(self):
        for lead in self:
            parsed = lead._parsed_enrichment_data()
            lead.ai_company_intelligence_html = Markup(
                _render_contract_section(parsed.get('company_intelligence')))

    @api.depends('ai_enrichment_data')
    def _compute_ai_customer_intelligence_html(self):
        for lead in self:
            parsed = lead._parsed_enrichment_data()
            lead.ai_customer_intelligence_html = Markup(
                _render_contract_section(parsed.get('customer_intelligence')))

    @api.depends('ai_enrichment_data')
    def _compute_ai_relationship_intelligence_html(self):
        for lead in self:
            parsed = lead._parsed_enrichment_data()
            html = (
                _render_contract_section(parsed.get('relationship_intelligence'), title=_('Relationship'))
                + _render_contract_section(parsed.get('conversation_intelligence'), title=_('Conversation'))
            )
            lead.ai_relationship_intelligence_html = Markup(html)

    @api.depends('ai_enrichment_data')
    def _compute_ai_buying_intelligence_html(self):
        for lead in self:
            parsed = lead._parsed_enrichment_data()
            html = (
                _render_contract_section(parsed.get('buying_intelligence'), title=_('Buying Signals'))
                + _render_contract_section(parsed.get('needs_assessment'), title=_('Needs Assessment'))
                + _render_contract_section(parsed.get('business_requirements'), title=_('Business Requirements'))
                + _render_contract_section(parsed.get('decision_makers'), title=_('Decision Makers'))
            )
            lead.ai_buying_intelligence_html = Markup(html)

    @api.depends('ai_enrichment_data')
    def _compute_ai_opportunity_intelligence_html(self):
        for lead in self:
            parsed = lead._parsed_enrichment_data()
            html = (
                _render_contract_section(parsed.get('opportunity_intelligence'), title=_('Opportunity'))
                + _render_contract_section(parsed.get('implementation_readiness'), title=_('Implementation Readiness'))
            )
            lead.ai_opportunity_intelligence_html = Markup(html)

    @api.depends('ai_enrichment_data')
    def _compute_ai_proposal_intelligence_html(self):
        for lead in self:
            parsed = lead._parsed_enrichment_data()
            html = (
                _render_contract_section(parsed.get('proposal_intelligence'), title=_('Proposal'))
                + _render_contract_section(parsed.get('recommended_solution'), title=_('Recommended Solution'))
            )
            lead.ai_proposal_intelligence_html = Markup(html)

    @api.depends('ai_enrichment_data')
    def _compute_ai_executive_summary_html(self):
        for lead in self:
            parsed = lead._parsed_enrichment_data()
            lead.ai_executive_summary_html = Markup(
                _render_contract_section(parsed.get('summary')))

    @api.depends('ai_enrichment_evidence')
    def _compute_ai_evidence_html(self):
        for lead in self:
            try:
                evidence = json.loads(lead.ai_enrichment_evidence or '[]')
            except (ValueError, TypeError):
                evidence = []
            lead.ai_evidence_html = Markup(_render_evidence_html(evidence))

    def action_enrich_with_ai(self):
        """Enrich this lead with AI-powered analysis."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enrich Lead with AI'),
            'res_model': 'lead.enrichment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_lead_ids': self.ids},
        }

    def action_regenerate_report(self):
        """Regenerate AI report from existing enrichment data (no API call)."""
        self.ensure_one()
        return True

    def _build_research_queries(self, company_name, display_name, lead_name=''):
        """Search queries for multi_search(). ``company_name``, ``display_name``
        and ``lead_name`` are all already anonymized upstream when the toggle
        is on (Decision F / F.2), so the fallback chain never leaks a real
        name into the query even when partner_name/contact_name are blank."""
        subject = company_name or display_name or lead_name or ''
        queries = []
        if subject:
            queries.append('%s profile about' % subject)
            queries.append('%s news %s' % (subject, date.today().year))
        if self.website:
            queries.append('site:%s products services' % self.website)
        return queries

    def _lead_intelligence_note(self, parsed, research, evidence):
        """Build the structured HTML chatter note from ``summary.*`` (step 17).

        ``summary.*`` is LLM-controlled content (itself influenced by
        scraped web-search results), so every interpolated value is passed
        through ``escape()`` before being placed inside an HTML tag -- the
        same pattern as ``_render_contract_section``/``_format_contract_value``
        above. Only the literal structural tags (``<b>``, ``<p>``, ``<ul>``,
        ``<li>``, ``<i>``) are trusted template text. The fully-assembled
        string is wrapped in ``Markup(...)`` right before it is returned, so
        ``message_post()`` renders it as real HTML instead of re-escaping the
        whole thing as untrusted plain text.

        Defensive note (Task 10.5, live-discovered crash): ``parsed`` is
        normally pre-normalized by ``lead_intelligence.parse_llm_response()``
        (every schema-``object`` section is coerced to a ``dict`` there), but
        this method still guards locally in case ``summary`` arrives as a
        non-dict anyway (e.g. a caller that bypasses the parser). A bare
        string/other-typed ``summary`` is treated as if it were
        ``{'executive_summary': str(summary)}`` -- the LLM's one-line summary
        still renders as a real chatter note instead of crashing with
        ``AttributeError: 'str' object has no attribute 'get'``.
        """
        summary = parsed.get('summary') or {}
        if not isinstance(summary, dict):
            summary = {'executive_summary': str(summary)}
        note = ['<b>%s</b>' % escape(_('AI Research Summary'))]
        # '.get(\'value\')' fallback covers the parser-level normalization
        # path above, which wraps a stray string section as {'value': ...}
        # rather than {'executive_summary': ...} (that key is specific to
        # this call site's own local guard, immediately above).
        exec_summary = summary.get('executive_summary') or summary.get('value')
        if exec_summary:
            note.append('<p>%s</p>' % escape(exec_summary))

        def _section(title, items):
            if not items:
                return
            if isinstance(items, str):
                items = [items]
            lis = ''.join('<li>%s</li>' % escape(item) for item in items if item)
            if lis:
                note.append('<p><b>%s</b></p><ul>%s</ul>' % (escape(title), lis))

        _section(_('Key Findings'), summary.get('key_findings'))
        conversation_strategy = summary.get('conversation_strategy')
        if conversation_strategy:
            note.append('<p><b>%s</b>: %s</p>' % (
                escape(_('Conversation Strategy')), escape(conversation_strategy)))
        _section(_('Risks'), summary.get('risks'))
        _section(_('Opportunities'), summary.get('opportunities'))
        _section(_('Recommended Next Actions'), summary.get('recommended_next_actions'))

        providers = research.get('providers_used') or [
            e['provider'] for e in evidence if e.get('provider')
        ]
        if providers:
            note.append('<p><i>%s: %s</i></p>' % (
                escape(_('Sources')), ', '.join(escape(p) for p in dict.fromkeys(providers))))
        return Markup(''.join(note))

    def _enrich_lead(self):
        """Universal Lead Intelligence enrichment: pre-classify, search,
        one (or at most two) LLM call(s), parse the Universal JSON Contract,
        promote to native fields, persist 3 artifacts and post a structured
        chatter note. See the design spec's Resolved Decisions A-I."""
        self.ensure_one()
        # 1 — do not double-run an in-flight enrichment.
        if self.ai_enrichment_status == 'processing':
            return
        # 2 — mark in-flight.
        self.ai_enrichment_status = 'processing'

        # 3 — deterministic pre-classifier hint.
        entity_hint = li.classify_entity_hint(self, self.env)
        self.entity_hint = entity_hint

        # 4 — anonymized (or plain) contact display name.
        display_name = li.anonymize_contact_name(self, self.env)

        # 5 + 6 — search (existing infrastructure, unchanged). Company name
        # (and the lead-name fallback subject) are anonymized the same way as
        # contact name (Decision F.2) so the hashed value reaches both the
        # search query and the LLM prompt, never the raw name.
        company_name = li.anonymize_company_name(self, self.env)
        lead_name = li.anonymize_lead_name(self, self.env)
        queries = self._build_research_queries(company_name, display_name, lead_name)
        research = self.env['web.research.service'].multi_search(queries, parallel=True)

        # 7 + 8 — normalize evidence and persist artifact 3 immediately.
        evidence = li.normalize_evidence(research)
        self.ai_enrichment_evidence = json.dumps(evidence)

        # 9 — build the prompt (injection-defended evidence block).
        messages = li.build_prompt(self, entity_hint, evidence, self.env)

        # 10 + 11 — at most two LLM calls: initial + one deterministic retry.
        parsed = None
        raw_content = ''
        parse_error = ''
        for _attempt in range(2):
            resp = self.env['llm.service'].call_llm(
                messages=messages, response_schema=li.LEAD_INTELLIGENCE_SCHEMA)
            raw_content = resp.get('content') or ''
            try:
                parsed = li.parse_llm_response(raw_content)
                break
            except li.ParseFailure as exc:
                parse_error = str(exc)
                continue

        if parsed is None:
            # Terminal parse failure: persist the raw content for diagnosis.
            self.ai_enrichment_data = raw_content
            self.ai_enrichment_status = 'parse_failure'
            self.ai_last_enrichment_date = fields.Datetime.now()
            self.message_post(
                body=Markup('<b>%s</b><p>%s</p>' % (
                    escape(_('AI Research Summary')),
                    escape(_('Enrichment could not parse the AI response after 2 attempts: %s') % parse_error),
                )),
                subtype_xmlid='mail.mt_note',
            )
            return

        # 11.5 — hallucination guardrail: confidence/citations can't exceed
        # what the evidence actually supports (see apply_evidence_guardrails).
        parsed = li.apply_evidence_guardrails(parsed, evidence)

        # 12 — persist artifact 2 (full validated JSON).
        self.ai_enrichment_data = json.dumps(parsed)

        # 13 + 14 — promote to native fields. The stored-compute fields
        # (ai_readiness, ai_classification_mismatch) are derived by their own
        # methods on write, so they are intentionally not written here.
        native = li.promote_to_native_fields(parsed)
        write_vals = {field: native[field] for _key, field in li.SCORE_KEYS}
        write_vals.update({
            'ai_entity_type': native['ai_entity_type'],
            'ai_entity_type_confidence': native['ai_entity_type_confidence'],
            'ai_scoring_rationale': native['ai_scoring_rationale'],
            'ai_budget_tier': native['ai_budget_tier'],
            'ai_industry': native['ai_industry'],
        })
        self.write(write_vals)

        # 15 + 16 — terminal status + timestamp.
        self.ai_enrichment_status = 'completed'
        self.ai_last_enrichment_date = fields.Datetime.now()

        # 17 + 18 — structured chatter note.
        note_body = self._lead_intelligence_note(parsed, research, evidence)
        self.message_post(body=note_body, subtype_xmlid='mail.mt_note')

    @api.model
    def _cron_enrich_leads(self):
        """Scheduled cron: auto-enrich up to 50 leads, 5 at a time, each
        worker on its own cursor so one lead's failure/rollback can't
        affect another's commit."""
        leads = self.search([
            ('auto_enrich', '=', True),
            ('ai_enrichment_status', '!=', 'processing'),
        ], limit=50)

        def _enrich_one(lead_id):
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, self.env.uid, self.env.context)
                lead = env['crm.lead'].browse(lead_id)
                try:
                    lead._enrich_lead()
                except Exception:
                    _logger.exception('crm.lead._cron_enrich_leads: lead %s failed', lead_id)
                    lead.ai_enrichment_status = 'failed'
                cr.commit()

        with ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(_enrich_one, leads.ids))
        return True
