# -*- coding: utf-8 -*-
"""Category J - access control, drill-down safety, non-blocking guarantees."""
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .common import CesKpiCase


@tagged("post_install", "-at_install", "sgc_ces_kpi_banner")
class TestSecurity(CesKpiCase):
    def _gate(self, code="sec"):
        plan = self._make_plan(code=code)
        template = self._make_template(plan, code="g1")
        self._make_requirement(template)
        plan.action_activate()
        return self._make_assignment(plan).instance_ids

    def test_groups_exist_and_imply_each_other(self):
        user = self.env.ref("sgc_ces_kpi_banner.group_ces_kpi_user")
        manager = self.env.ref("sgc_ces_kpi_banner.group_ces_kpi_manager")
        admin = self.env.ref("sgc_ces_kpi_banner.group_ces_kpi_admin")
        self.assertIn(user, manager.implied_ids)
        self.assertIn(manager, admin.implied_ids)

    def test_user_can_read_own_summary(self):
        self._gate("sec_own")
        summary = self.Service.with_user(self.ces_user).get_my_ces_kpi_summary()
        self.assertEqual(summary["user_id"], self.ces_user.id)
        self.assertTrue(summary["is_ces"])

    def test_user_cannot_read_another_users_summary(self):
        with self.assertRaises(AccessError):
            self.Service.with_user(self.ces_user).get_ces_kpi_summary(self.other_user.id)

    def test_manager_can_read_managed_user_summary(self):
        self._gate("sec_mgr")
        summary = self.Service.with_user(self.manager_user).get_ces_kpi_summary(
            self.ces_user.id
        )
        self.assertEqual(summary["user_id"], self.ces_user.id)

    def test_manager_cannot_read_unmanaged_user_summary(self):
        with self.assertRaises(AccessError):
            self.Service.with_user(self.manager_user).get_ces_kpi_summary(
                self.other_user.id
            )

    def test_admin_can_read_anyone(self):
        summary = self.Service.get_ces_kpi_summary(self.ces_user.id)
        self.assertEqual(summary["user_id"], self.ces_user.id)

    def test_user_cannot_see_another_users_gate_instance(self):
        instance = self._gate("sec_rule")
        visible = self.env["sgc.ces.gate.instance"].with_user(self.other_user).search(
            [("id", "=", instance.id)]
        )
        self.assertFalse(visible)

    def test_owner_and_manager_can_see_the_gate_instance(self):
        instance = self._gate("sec_rule2")
        for user in (self.ces_user, self.manager_user):
            visible = self.env["sgc.ces.gate.instance"].with_user(user).search(
                [("id", "=", instance.id)]
            )
            self.assertTrue(visible, user.name)

    def test_user_cannot_write_configuration(self):
        plan = self._make_plan(code="sec_conf")
        with self.assertRaises(AccessError):
            self.env["sgc.ces.gate.plan"].with_user(self.ces_user).create(
                {"name": "Rogue", "code": "rogue"}
            )
        with self.assertRaises(AccessError):
            plan.with_user(self.ces_user).write({"name": "Hacked"})

    def test_drilldown_rejects_unknown_kind(self):
        with self.assertRaises(AccessError):
            self.Service.with_user(self.ces_user).get_drilldown_action("arbitrary", 1)

    def test_drilldown_domain_is_server_generated(self):
        instance = self._gate("sec_drill")
        instance.evaluate()
        result = instance.result_ids
        action = self.Service.with_user(self.ces_user).get_drilldown_action(
            "requirement", result.id
        )
        if action.get("type") == "ir.actions.act_window":
            self.assertIn(action["res_model"], ("crm.lead", "sale.order"))
            self.assertIsInstance(action["domain"], list)

    def test_drilldown_respects_record_rules(self):
        """Opening someone else's requirement must be refused."""
        instance = self._gate("sec_drill2")
        instance.evaluate()
        with self.assertRaises(AccessError):
            self.Service.with_user(self.other_user).get_drilldown_action(
                "requirement", instance.result_ids.id
            )

    def test_installing_does_not_activate_any_assignment(self):
        shipped = self.env.ref("sgc_ces_kpi_banner.gate_plan_ces_ramp")
        self.assertEqual(shipped.state, "draft")
        self.assertFalse(shipped.assignment_ids)

    def test_shipped_plan_invents_no_targets(self):
        shipped = self.env.ref("sgc_ces_kpi_banner.gate_plan_ces_ramp")
        mandatory = shipped.template_ids.requirement_ids.filtered(
            lambda r: r.level == "mandatory"
        )
        self.assertTrue(mandatory)
        for requirement in mandatory:
            self.assertEqual(requirement.target_value, 0.0)

    def test_module_never_blocks_a_crm_write(self):
        stage_a = self.env["crm.stage"].create({"name": "Sec Stage A"})
        stage_b = self.env["crm.stage"].create({"name": "Sec Stage B"})
        lead = self._make_lead(self.ces_user, revenue=1.0, stage=stage_a)
        lead.with_user(self.ces_user).write({"stage_id": stage_b.id})
        self.assertEqual(lead.stage_id, stage_b)

    def test_service_never_returns_accounting_identifiers(self):
        self._gate("sec_acct")
        summary = self.Service.with_user(self.ces_user).get_my_ces_kpi_summary()
        blob = str(summary).lower()
        for forbidden in ("account.move", "invoice_id", "journal_id", "payment_id"):
            self.assertNotIn(forbidden, blob)
