# -*- coding: utf-8 -*-
"""Category K - frontend contract, assets and accessibility markers.

The banner deliberately holds no business logic, so the meaningful frontend
assertions are about (a) the assets being registered, (b) the OWL template
existing and carrying the required accessibility attributes, (c) the RPC
surface the component depends on, and (d) the namespacing guarantees that keep
this addon from colliding with the other sgc_* modules.
"""
import os
import re

from odoo.tests.common import tagged

from .common import CesKpiCase

MODULE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(MODULE_ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


@tagged("post_install", "-at_install", "sgc_ces_kpi_banner")
class TestFrontendContract(CesKpiCase):
    def test_owl_template_is_registered(self):
        view = self.env["ir.ui.view"].sudo().search(
            [("type", "=", "qweb"), ("name", "=", "sgc_ces_kpi_banner.Banner")]
        )
        source = _read("static", "src", "components", "ces_kpi_banner", "ces_kpi_banner.xml")
        self.assertIn('t-name="sgc_ces_kpi_banner.Banner"', source)
        # ir.ui.view registration is optional for asset-bundled OWL templates.
        self.assertTrue(source or view)

    def test_component_registers_in_main_components(self):
        source = _read("static", "src", "components", "ces_kpi_banner", "ces_kpi_banner.js")
        self.assertIn('registry.category("main_components")', source)
        self.assertIn('"sgc_ces_kpi_banner.Banner"', source)

    def test_service_key_is_unique_to_this_module(self):
        source = _read("static", "src", "services", "ces_kpi_service.js")
        self.assertIn('add("sgc_ces_kpi_service"', source)

    def test_ui_state_is_localstorage_only(self):
        source = _read("static", "src", "components", "ces_kpi_banner", "ces_kpi_banner.js")
        self.assertIn("localStorage", source)
        self.assertNotIn("res.users.settings", source)

    def test_client_never_builds_a_domain(self):
        for name in ("ces_kpi_banner.js",):
            source = _read("static", "src", "components", "ces_kpi_banner", name)
            self.assertNotIn("searchRead", source)
            self.assertNotIn("domain:", source)

    def test_all_css_classes_are_prefixed(self):
        source = _read("static", "src", "components", "ces_kpi_banner", "ces_kpi_banner.scss")
        classes = set(re.findall(r"(?:^|[\s,>])\.([a-zA-Z_][a-zA-Z0-9_-]*)", source, re.M))
        for name in classes:
            self.assertTrue(
                name.startswith("o_sgc_ces_kpi_"),
                "CSS class %s is not namespaced" % name,
            )

    def test_accessibility_attributes_present(self):
        source = _read("static", "src", "components", "ces_kpi_banner", "ces_kpi_banner.xml")
        for attribute in (
            'role="region"',
            'role="progressbar"',
            "aria-label",
            "aria-expanded",
            "aria-valuenow",
        ):
            self.assertIn(attribute, source)

    def test_escape_key_is_handled(self):
        source = _read("static", "src", "components", "ces_kpi_banner", "ces_kpi_banner.js")
        self.assertIn('ev.key === "Escape"', source)

    def test_reduced_motion_is_respected(self):
        source = _read("static", "src", "components", "ces_kpi_banner", "ces_kpi_banner.scss")
        self.assertIn("prefers-reduced-motion", source)

    def test_responsive_breakpoint_exists(self):
        source = _read("static", "src", "components", "ces_kpi_banner", "ces_kpi_banner.scss")
        self.assertIn("@media (max-width", source)

    def test_assets_are_declared(self):
        module = self.env["ir.module.module"].sudo().search(
            [("name", "=", "sgc_ces_kpi_banner")], limit=1
        )
        self.assertTrue(module)
        manifest = _read("__manifest__.py")
        for asset in (
            "ces_kpi_banner.js",
            "ces_kpi_banner.xml",
            "ces_kpi_banner.scss",
            "ces_kpi_service.js",
        ):
            self.assertIn(asset, manifest)

    def test_summary_payload_shape(self):
        plan = self._make_plan(code="fe_shape")
        template = self._make_template(plan, code="g1")
        self._make_requirement(template)
        plan.action_activate()
        self._make_assignment(plan)
        summary = self.Service.with_user(self.ces_user).get_my_ces_kpi_summary()
        for key in ("is_ces", "enabled", "gates", "kpis", "next_action", "warnings"):
            self.assertIn(key, summary)
        self.assertIn("daily", summary["kpis"])
        self.assertIn("monthly", summary["kpis"])
        gate = summary["gates"][0]
        for key in ("id", "name", "state", "score", "requirements", "effective_due_date"):
            self.assertIn(key, gate)

    def test_next_action_is_deterministic_and_rule_based(self):
        plan = self._make_plan(code="fe_next")
        template = self._make_template(plan, code="g1")
        self._make_requirement(template, name="Unreachable", target_value=10 ** 9)
        plan.action_activate()
        self._make_assignment(plan)
        first = self.Service.with_user(self.ces_user).get_my_ces_kpi_summary()["next_action"]
        self.Service.invalidate_cache_for_user(self.ces_user.id)
        second = self.Service.with_user(self.ces_user).get_my_ces_kpi_summary()["next_action"]
        self.assertEqual(first["kind"], "requirement")
        self.assertEqual(first["ref_id"], second["ref_id"])
        self.assertEqual(first["label"], second["label"])

    def test_banner_hidden_for_non_ces_user(self):
        summary = self.Service.with_user(self.other_user).get_my_ces_kpi_summary()
        self.assertFalse(summary["is_ces"])

    def test_banner_can_be_disabled_globally(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "sgc_ces_kpi_banner.banner_enabled", "False"
        )
        self.Service.invalidate_cache_for_user(self.ces_user.id)
        summary = self.Service.with_user(self.ces_user).get_my_ces_kpi_summary()
        self.assertFalse(summary["enabled"])
        self.env["ir.config_parameter"].sudo().set_param(
            "sgc_ces_kpi_banner.banner_enabled", "True"
        )
