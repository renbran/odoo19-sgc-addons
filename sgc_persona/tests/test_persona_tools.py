from odoo.tests import common


class TestPersonaTools(common.TransactionCase):
    """Verify persona tool behavior — authorization, graceful degradation, data shape."""

    def setUp(self):
        super().setUp()
        self.PersonaTool = self.env["sgc.persona.tool"]

    def test_finance_tool_returns_dict(self):
        result = self.PersonaTool.sgc_fetch_finance_data(
            sections=["cash"],
            _persona_code="finance_analyst",
        )
        self.assertIn("finance", result)
        self.assertIsInstance(result["finance"], dict)

    def test_finance_tool_rejects_wrong_persona(self):
        result = self.PersonaTool.sgc_fetch_finance_data(
            sections=["cash"],
            _persona_code="hr_assistant",
        )
        self.assertTrue(result.get("error"), "Wrong persona should be rejected")

    def test_hr_tool_graceful_on_missing_model(self):
        """hr.payslip may not exist — tool should degrade gracefully, not crash."""
        result = self.PersonaTool.sgc_fetch_hr_data(
            _persona_code="hr_assistant",
        )
        self.assertIn("hr", result)
        hr_data = result["hr"]
        self.assertIn("payroll", hr_data)

    def test_aml_tool_graceful_on_missing_kyc(self):
        result = self.PersonaTool.sgc_fetch_aml_data(
            _persona_code="aml_officer",
        )
        self.assertIn("aml", result)
        aml_data = result["aml"]
        self.assertIn("high_risk_assessments", aml_data)
        self.assertIn("pending_kyc", aml_data)
        self.assertIn("monitoring_alerts", aml_data)

    def test_sales_tool_returns_dict(self):
        result = self.PersonaTool.sgc_fetch_sales_data(
            _persona_code="sales_analyst",
        )
        self.assertIn("sales", result)
        sales = result["sales"]
        self.assertIn("pipeline", sales)
        self.assertIn("sales_performance", sales)

    def test_operations_tool_returns_dict(self):
        result = self.PersonaTool.sgc_fetch_operations_data(
            _persona_code="operations_manager",
        )
        self.assertIn("operations", result)
        ops = result["operations"]
        self.assertIn("stock_moves", ops)
        self.assertIn("inventory", ops)
        self.assertIn("manufacturing", ops)

    def test_executive_summary_returns_dict(self):
        result = self.PersonaTool.sgc_fetch_executive_summary(
            _persona_code="executive_assistant",
        )
        self.assertIn("executive_summary", result)

    def test_all_tools_authorize_by_persona_code(self):
        """Every tool should reject a non-matching persona code."""
        tools = [
            (self.PersonaTool.sgc_fetch_finance_data, "hr_assistant"),
            (self.PersonaTool.sgc_fetch_hr_data, "finance_analyst"),
            (self.PersonaTool.sgc_fetch_sales_data, "operations_manager"),
            (self.PersonaTool.sgc_fetch_aml_data, "sales_analyst"),
            (self.PersonaTool.sgc_fetch_operations_data, "aml_officer"),
            (self.PersonaTool.sgc_fetch_inventory_data, "finance_analyst"),
            (self.PersonaTool.sgc_fetch_customer_data, "finance_analyst"),
            (self.PersonaTool.sgc_fetch_marketing_data, "finance_analyst"),
            (self.PersonaTool.sgc_fetch_project_data, "finance_analyst"),
            (self.PersonaTool.sgc_fetch_procurement_data, "finance_analyst"),
            (self.PersonaTool.sgc_fetch_compliance_data, "finance_analyst"),
            (self.PersonaTool.sgc_fetch_executive_summary, "finance_analyst"),
            (self.PersonaTool.sgc_fetch_it_data, "finance_analyst"),
        ]
        for tool_method, wrong_code in tools:
            result = tool_method(_persona_code=wrong_code)
            self.assertTrue(
                result.get("error"),
                f"{tool_method.__name__} should reject persona '{wrong_code}'",
            )
