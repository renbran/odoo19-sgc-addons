# Copyright 2026 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Fixture-based tests for the notes service's pure logic — prompt building,
response parsing, and gate-answers HTML rendering. No LLM/network call: the
D1 deploy risk isn't extraction quality (a product concern, and the
apply-wizard requires human confirmation anyway) — it's whether the
modified code throws, which these exercise directly."""

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_meeting_ai")
class TestNotesServicePromptAndParsing(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["sgc.meeting.notes.service"]
        cls.provider = cls.env.ref("sgc_meeting_ai.sgc_provider_in_person")
        cls.opportunity = cls.env["crm.lead"].create(
            {"name": "Test Opportunity for Gate Section", "type": "opportunity"}
        )

    def _make_session(self, opportunity=None):
        event_vals = {
            "name": "Test Meeting",
            "start": fields.Datetime.now(),
            "stop": fields.Datetime.now(),
        }
        if opportunity:
            event_vals["opportunity_id"] = opportunity.id
        event = self.env["calendar.event"].create(event_vals)
        return self.env["sgc.meeting.session"].create(
            {"meeting_id": event.id, "provider_id": self.provider.id}
        )

    def _make_transcript(self, session, text="Hello, this is the transcript."):
        return self.env["sgc.meeting.transcript"].create(
            {"session_id": session.id, "text": text}
        )

    # ── _build_prompt: with / without a linked opportunity ─────────────────

    def test_build_prompt_without_opportunity_omits_gate_section(self):
        session = self._make_session()
        transcript = self._make_transcript(session)
        prompt = self.service._build_prompt(transcript)
        self.assertIn("Hello, this is the transcript.", prompt)
        self.assertNotIn("gate_answers", prompt)
        self.assertNotIn("Verifiable Buyer Exit Criteria", prompt)

    def test_build_prompt_with_opportunity_includes_gate_section(self):
        session = self._make_session(opportunity=self.opportunity)
        transcript = self._make_transcript(session)
        prompt = self.service._build_prompt(transcript)
        self.assertIn("gate_answers", prompt)
        self.assertIn(self.opportunity.name, prompt)
        self.assertIn("Buyer Exit Criteria", prompt)

    def test_build_prompt_handles_no_attendees(self):
        # calendar.event.name is NOT NULL, so an actually-nameless meeting
        # can't be created via the ORM — the "(untitled meeting)" fallback
        # in _build_prompt only matters for that impossible case. What's
        # real and worth covering: a meeting with no attendees added yet.
        event = self.env["calendar.event"].create(
            {"name": "Untitled", "start": fields.Datetime.now(), "stop": fields.Datetime.now()}
        )
        session = self.env["sgc.meeting.session"].create(
            {"meeting_id": event.id, "provider_id": self.provider.id}
        )
        transcript = self._make_transcript(session)
        prompt = self.service._build_prompt(transcript)
        self.assertIn("(unknown)", prompt)

    # ── _parse_response: with gate_answers, without, and malformed ─────────

    def test_parse_response_with_gate_answers(self):
        raw = """{
            "summary": "Discussed pricing and timeline.",
            "key_points": "<ul><li>Pricing</li></ul>",
            "decisions": "<ul></ul>",
            "action_items": "<ul><li>Alice: send proposal</li></ul>",
            "risks": "<ul></ul>",
            "gate_answers": {
                "problem": "Manual reconciliation takes 3 days/month",
                "cost_of_inaction": "AED 40k/year in overtime",
                "approver": "CFO",
                "timeline": "Q1 2027"
            }
        }"""
        parsed = self.service._parse_response(raw)
        self.assertEqual(parsed["summary"], "Discussed pricing and timeline.")
        self.assertEqual(parsed["gate_answers"]["problem"], "Manual reconciliation takes 3 days/month")
        self.assertEqual(parsed["gate_answers"]["approver"], "CFO")

    def test_parse_response_without_gate_answers_defaults_to_empty_dict(self):
        raw = """{
            "summary": "Internal standup, no sales content.",
            "key_points": "<ul><li>Sprint status</li></ul>",
            "decisions": "<ul></ul>",
            "action_items": "<ul></ul>",
            "risks": "<ul></ul>"
        }"""
        parsed = self.service._parse_response(raw)
        self.assertEqual(parsed["gate_answers"], {})

    def test_parse_response_ignores_non_dict_gate_answers(self):
        # Defensive: if the LLM returns gate_answers as a string/list instead
        # of an object, don't propagate a non-dict into downstream code.
        raw = '{"summary": "x", "key_points": "", "decisions": "", "action_items": "", "risks": "", "gate_answers": "not an object"}'
        parsed = self.service._parse_response(raw)
        self.assertEqual(parsed["gate_answers"], {})

    def test_parse_response_strips_markdown_fences(self):
        raw = (
            '```json\n'
            '{"summary": "Fenced response.", "key_points": "", '
            '"decisions": "", "action_items": "", "risks": ""}\n'
            '```'
        )
        parsed = self.service._parse_response(raw)
        self.assertEqual(parsed["summary"], "Fenced response.")

    def test_parse_response_salvages_json_surrounded_by_prose(self):
        raw = (
            "Sure, here's the summary:\n"
            '{"summary": "Salvaged from prose.", "key_points": "", '
            '"decisions": "", "action_items": "", "risks": ""}\n'
            "Let me know if you need anything else!"
        )
        parsed = self.service._parse_response(raw)
        self.assertEqual(parsed["summary"], "Salvaged from prose.")

    def test_parse_response_truly_malformed_raises_usererror(self):
        raw = "Sorry, I can't process that transcript right now."
        with self.assertRaises(UserError):
            self.service._parse_response(raw)

    # ── _build_gate_answers_html ─────────────────────────────────────────

    def test_build_gate_answers_html_renders_populated_answers(self):
        gate_answers = {
            "problem": "Manual reconciliation takes 3 days/month",
            "cost_of_inaction": "",
            "approver": "CFO",
            "timeline": "",
        }
        html = self.service._build_gate_answers_html(gate_answers)
        self.assertTrue(html)
        self.assertIn("Manual reconciliation takes 3 days/month", html)
        self.assertIn("CFO", html)
        self.assertIn("(not discussed)", html)  # cost_of_inaction/timeline fallback

    def test_build_gate_answers_html_returns_false_when_all_empty(self):
        gate_answers = {"problem": "", "cost_of_inaction": "", "approver": "", "timeline": ""}
        self.assertFalse(self.service._build_gate_answers_html(gate_answers))

    def test_build_gate_answers_html_returns_false_for_empty_dict(self):
        self.assertFalse(self.service._build_gate_answers_html({}))

    def test_build_gate_answers_html_escapes_content(self):
        gate_answers = {
            "problem": '<script>alert(1)</script>',
            "cost_of_inaction": "",
            "approver": "",
            "timeline": "",
        }
        html = self.service._build_gate_answers_html(gate_answers)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    # ── End-to-end (still no network): build -> parse -> render ────────────

    def test_full_pipeline_with_opportunity_end_to_end_without_llm_call(self):
        """Exercises _build_prompt -> _parse_response -> _build_gate_answers_html
        back to back against a fixed fake LLM response, matching what
        summarize() itself does after the actual HTTP call — the exact
        code path a real transcript would hit once the LLM key is scoped."""
        session = self._make_session(opportunity=self.opportunity)
        transcript = self._make_transcript(
            session, text="Prospect said budget is tight but CFO must approve by March."
        )
        prompt = self.service._build_prompt(transcript)
        self.assertIn("gate_answers", prompt)

        fake_llm_response = """{
            "summary": "Budget-constrained prospect, CFO approval needed.",
            "key_points": "<ul><li>Tight budget</li></ul>",
            "decisions": "<ul></ul>",
            "action_items": "<ul></ul>",
            "risks": "<ul><li>Budget constraints</li></ul>",
            "gate_answers": {
                "problem": "",
                "cost_of_inaction": "",
                "approver": "CFO",
                "timeline": "March"
            }
        }"""
        parsed = self.service._parse_response(fake_llm_response)
        html = self.service._build_gate_answers_html(parsed["gate_answers"])
        self.assertTrue(html)
        self.assertIn("CFO", html)
        self.assertIn("March", html)
        self.assertIn("(not discussed)", html)
