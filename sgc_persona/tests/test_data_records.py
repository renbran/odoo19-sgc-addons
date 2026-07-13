from odoo.tests import common


class TestPersonaDataRecords(common.TransactionCase):
    """Verify all 14 llm.assistant records load with valid prompt links and tool assignments."""

    def setUp(self):
        super().setUp()
        self.Assistant = self.env["llm.assistant"]

    def test_14_personas_exist(self):
        assistants = self.Assistant.search([("code", "!=", False)])
        self.assertGreaterEqual(
            len(assistants), 14,
            f"Expected at least 14 personas, found {len(assistants)}",
        )

    def test_every_persona_has_code(self):
        assistants = self.Assistant.search([("code", "!=", False)])
        for a in assistants:
            self.assertTrue(a.code, f"Persona {a.name} has no code")

    def test_every_persona_has_prompt(self):
        assistants = self.Assistant.search([("code", "!=", False)])
        for a in assistants:
            self.assertTrue(
                a.prompt_id,
                f"Persona {a.name} ({a.code}) has no prompt_id",
            )

    def test_every_persona_has_tools(self):
        assistants = self.Assistant.search([("code", "!=", False)])
        for a in assistants:
            self.assertTrue(
                a.tool_ids,
                f"Persona {a.name} ({a.code}) has no tool_ids assigned",
            )

    def test_prompts_have_templates(self):
        assistants = self.Assistant.search([("code", "!=", False)])
        for a in assistants:
            self.assertTrue(
                a.prompt_id.template,
                f"Prompt for {a.name} ({a.code}) has no template content",
            )

    def test_persona_codes_are_unique(self):
        assistants = self.Assistant.search([("code", "!=", False)])
        codes = [a.code for a in assistants]
        self.assertEqual(
            len(codes), len(set(codes)),
            f"Duplicate persona codes found: {codes}",
        )

    def test_xml_ids_are_stable(self):
        """Verify namespaced XML IDs exist for all persona records."""
        expected_xml_ids = [
            "sgc_persona.assistant_finance_analyst",
            "sgc_persona.assistant_aml_officer",
            "sgc_persona.assistant_hr_assistant",
            "sgc_persona.assistant_sales_analyst",
            "sgc_persona.assistant_operations_manager",
            "sgc_persona.assistant_inventory_specialist",
            "sgc_persona.assistant_customer_support",
            "sgc_persona.assistant_marketing_analyst",
            "sgc_persona.assistant_project_manager",
            "sgc_persona.assistant_procurement_officer",
            "sgc_persona.assistant_compliance_auditor",
            "sgc_persona.assistant_executive_assistant",
            "sgc_persona.assistant_it_support",
            "sgc_persona.assistant_data_analyst",
        ]
        for xml_id in expected_xml_ids:
            record = self.env.ref(xml_id, raise_if_not_found=False)
            self.assertIsNotNone(
                record,
                f"XML ID {xml_id} not found — data record may be missing",
            )
