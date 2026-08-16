# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sgc_ces_banner_enabled = fields.Boolean(
        string="Show the CES KPI banner",
        config_parameter="sgc_ces_kpi_banner.banner_enabled",
        default=True,
    )
    sgc_ces_job_id = fields.Many2one(
        "hr.job",
        string="CES job position",
        config_parameter="sgc_ces_kpi_banner.ces_job_id",
    )
    sgc_ces_job_name = fields.Char(
        string="CES job title (fallback lookup)",
        config_parameter="sgc_ces_kpi_banner.ces_job_name",
    )
    sgc_ces_proposal_stage_id = fields.Many2one(
        "crm.stage",
        string="Proposal stage",
        config_parameter="sgc_ces_kpi_banner.proposal_stage_id",
    )
    sgc_ces_won_stage_id = fields.Many2one(
        "crm.stage",
        string="Won stage",
        config_parameter="sgc_ces_kpi_banner.won_stage_id",
    )
    sgc_ces_excluded_stage_ids = fields.Char(
        string="Excluded stage ids (comma separated)",
        config_parameter="sgc_ces_kpi_banner.excluded_stage_ids",
    )
    sgc_ces_cache_seconds = fields.Integer(
        string="KPI cache (seconds)",
        config_parameter="sgc_ces_kpi_banner.cache_seconds",
        default=60,
    )
    sgc_ces_review_email_enabled = fields.Boolean(
        string="Send review alerts by email",
        config_parameter="sgc_ces_kpi_banner.review_email_enabled",
        default=False,
        help="Off by default: reviewers get an activity and an inbox notification only.",
    )
    sgc_ces_baseline_assessment_days = fields.Integer(
        string="Baseline assessment period (days)",
        config_parameter="sgc_ces_kpi_banner.baseline_assessment_days",
        default=7,
        help="Existing CES employees: how many days a manager has to complete the "
             "baseline assessment before it's due.",
    )
    sgc_ces_fallback_manager_uid = fields.Many2one(
        "res.users",
        string="Fallback reviewer",
        config_parameter="sgc_ces_kpi_banner.fallback_manager_uid",
    )

    @api.model
    def action_open_ces_health_check(self):
        wizard = self.env["sgc.ces.health.wizard"].create({})
        wizard.action_refresh()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sgc.ces.health.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
